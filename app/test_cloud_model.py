import jinx_test_support  # Isolate state and memory before importing jinx.
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import cloud_model as c


def event(text=None, call=None, finish=None):
    return NS(choices=[NS(finish_reason=finish, delta=NS(content=text, tool_calls=[call] if call else []))])


def tool(name='jinx_calculate', args='{"expression":"2+2"}'):
    return NS(index=0, id='call1', function=NS(name=name, arguments=args))


class Stream:
    def __init__(self, events): self.events=events
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def __iter__(self):
        for e in self.events:
            if isinstance(e, Exception): raise e
            yield e


class CloudTests(unittest.TestCase):
    def setUp(self):
        self.key=patch.object(c, 'api_key', return_value='test-key');self.key.start()
        self.addCleanup(self.key.stop)
        self.cloud=c.Cloud();self.client=Mock();self.dispatch=Mock(return_value='{"result":4}')
        self.seen=[]
        self.defs=[{'type':'function','function':{'name':'jinx_calculate','parameters':{'type':'object'}}}]

    def run_cloud(self, streams, cancelled=lambda:False):
        self.client.chat.completions.create.side_effect=streams
        return self.cloud.run('calculate', 'Jinx', [], self.defs, self.dispatch,
                              cancelled, self.seen.append, client=self.client)

    def test_streaming_and_tool_roundtrip(self):
        r=self.run_cloud([Stream([event(call=tool(),finish='tool_calls')]),Stream([event('Four.',finish='stop')])])
        self.assertEqual(r['final_response'],'Four.')
        self.dispatch.assert_called_once_with('jinx_calculate', {'expression':'2+2'})
        self.assertEqual(self.seen,['Four.'])
        payload=self.client.chat.completions.create.call_args.kwargs
        self.assertEqual(payload['messages'][-1]['role'],'tool')
        self.assertFalse(payload['store']);self.assertEqual(payload['reasoning_effort'],'none')

    def test_no_key_never_connects(self):
        self.key.stop()
        with patch.object(c,'api_key',return_value=''):
            self.assertIsNone(self.run_cloud([]))
        self.client.chat.completions.create.assert_not_called()

    def test_disconnect_before_output_allows_local_fallback_and_cooldown(self):
        self.assertIsNone(self.run_cloud([OSError('private-request-must-not-leak')]))
        self.assertFalse(self.cloud.available())
        self.assertNotIn('private',json.dumps(self.cloud.info()))
        with patch.object(c.time,'monotonic',return_value=self.cloud.retry_at+1):
            self.assertTrue(self.cloud.available())

    def test_disconnect_after_tool_never_replays(self):
        r=self.run_cloud([Stream([event(call=tool(),finish='tool_calls')]),OSError()])
        self.assertIsNotNone(r);self.assertFalse(r['completed'])
        self.dispatch.assert_called_once()

    def test_disconnect_after_text_never_restarts_answer(self):
        r=self.run_cloud([Stream([event('Hello'),OSError()])])
        self.assertIsNotNone(r);self.assertFalse(r['completed'])

    def test_cancel_before_tool_does_not_execute_or_fallback(self):
        cancelled=Mock(side_effect=[False,False,False,True])
        r=self.run_cloud([Stream([event(call=tool(),finish='tool_calls')])],cancelled)
        self.assertTrue(r['interrupted']);self.dispatch.assert_not_called()

    def test_unknown_tool_cannot_escape_allowlist(self):
        r=self.run_cloud([Stream([event(call=tool('terminal'),finish='tool_calls')]),
                          Stream([event('Unavailable.',finish='stop')])])
        self.dispatch.assert_not_called();self.assertTrue(r['completed'])

    def test_malformed_arguments_do_not_execute(self):
        self.run_cloud([Stream([event(call=tool(args='[]'),finish='tool_calls')]),
                        Stream([event('Unable.',finish='stop')])])
        self.dispatch.assert_not_called()

    def test_incomplete_tool_stream_does_not_execute(self):
        self.assertIsNone(self.run_cloud([Stream([event(call=tool(),finish='length')])]))
        self.dispatch.assert_not_called()

    def test_auth_failure_has_longer_cooldown(self):
        error=RuntimeError('secret');error.status_code=401
        self.assertIsNone(self.run_cloud([error]))
        self.assertGreater(self.cloud.info()['retry_seconds'],290)

    def test_real_sdk_parses_stream_and_sends_expected_contract(self):
        import httpx
        from openai import OpenAI
        requests=[]
        def handle(request):
            requests.append(json.loads(request.content))
            row={'id':'chatcmpl-test','object':'chat.completion.chunk','created':1,
                 'model':c.MODEL,'choices':[{'index':0,'delta':{'content':'Hello David.'},'finish_reason':'stop'}]}
            return httpx.Response(200,headers={'content-type':'text/event-stream'},
                                  text='data: '+json.dumps(row)+'\n\ndata: [DONE]\n\n')
        with OpenAI(api_key='test-key',http_client=httpx.Client(transport=httpx.MockTransport(handle))) as client:
            result=self.cloud.run('hello','Jinx',[],self.defs,self.dispatch,lambda:False,self.seen.append,client=client)
        self.assertEqual(result['final_response'],'Hello David.')
        self.assertEqual(requests[0]['model'],c.MODEL)
        self.assertFalse(requests[0]['parallel_tool_calls'])


class WiringTests(unittest.TestCase):
    def test_online_is_preferred_without_local_inference(self):
        import jinx as j
        with patch.object(j.cloud,'available',return_value=True), patch.object(j,'get_agent') as agent, \
             patch.object(j.cloud,'run',return_value={'final_response':'online'}), \
             patch.object(j,'fast_turn') as fast, patch.object(j,'run_agent_turn') as deep:
            agent.return_value.valid_tool_names=set()
            r=j.run_tiered_turn('hello','hello','Jinx',j.status['voice_epoch'],lambda x:None,{})
            self.assertEqual(r['final_response'],'online')
            fast.assert_not_called();deep.assert_not_called()

    def test_failed_online_returns_to_existing_local_route(self):
        import jinx as j
        with patch.object(j.cloud,'available',return_value=True), patch.object(j,'get_agent') as agent, \
             patch.object(j.cloud,'run',return_value=None), \
             patch.object(j.routing,'model_for',return_value=(j.routing.FAST,'everyday')), \
             patch.object(j,'fast_turn',return_value=('local','')) as fast:
            agent.return_value.valid_tool_names=set()
            r=j.run_tiered_turn('hello','hello','Jinx',j.status['voice_epoch'],lambda x:None,{})
            self.assertEqual(r['final_response'],'local');fast.assert_called_once()


if __name__=='__main__': unittest.main()
