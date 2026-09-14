import json
import queue
import unittest
from unittest.mock import Mock, patch
import subscription_model as s


def done(text='Hello David.'):
    return [ {'method':'item/agentMessage/delta','params':{'delta':text}},
             {'method':'item/completed','params':{'item':{'type':'agentMessage','text':text}}},
             {'method':'turn/completed','params':{'turn':{'status':'completed'}}} ]


def tool(name='jinx_calculate', identity='call1'):
    return {'id':99,'method':'item/tool/call','params':{'tool':name,'arguments':{'expression':'2+2'},'callId':identity}}


class Pipe:
    def __init__(self, owner): self.owner=owner
    def write(self, value): self.owner.send(json.loads(value))
    def flush(self): pass
    def close(self): pass
    def __iter__(self):
        while True:
            event=self.owner.events.get()
            if event is None:return
            yield json.dumps(event)+'\n'


class Process:
    def __init__(self, events, account='chatgpt'):
        self.events=queue.Queue();self.future=events;self.sent=[];self.account=account
        self.stdin=Pipe(self);self.stdout=Pipe(self)
    def send(self, request):
        self.sent.append(request)
        if 'method' not in request or 'id' not in request:return
        method=request['method'];result={}
        if method=='account/read':result={'account':{'type':self.account}}
        if method=='thread/start':result={'thread':{'id':'thread1'}}
        self.events.put({'id':request['id'],'result':result})
        if method=='turn/start':
            for e in self.future:self.events.put(e)
    def terminate(self):self.events.put(None)
    def wait(self, timeout=None):return 0
    def kill(self):self.terminate()


class SubscriptionTests(unittest.TestCase):
    def test_builtin_access_disabled_but_dynamic_dispatch_host_enabled(self):
        args=s.server_command()
        self.assertIn('forced_login_method="chatgpt"',args)
        for name in ['shell_tool','apps','plugins','browser_use','multi_agent','computer_use']:
            self.assertIn('features.'+name+'=false',args)
        self.assertIn('features.code_mode_host=true',args)

    def run_client(self, events, account='chatgpt', cancelled=lambda:False):
        self.process=Process(events,account);self.dispatch=Mock(return_value='4');self.seen=[]
        self.client=s.Subscription()
        definitions=[{'function':{'name':'jinx_calculate','description':'Calculate','parameters':{'type':'object'}}}]
        with patch.object(s.subprocess,'Popen',return_value=self.process) as launch, \
             patch.object(s,'server_command',return_value=['codex','app-server']), \
             patch.object(s.shutil,'which',return_value='/usr/bin/codex'):
            result=self.client.run('hello','Jinx',[],definitions,self.dispatch,cancelled,self.seen.append)
            self.launch=launch
        return result

    def test_subscription_success_and_no_machine_environment(self):
        result=self.run_client(done())
        self.assertTrue(result['completed'])
        start=next(x['params'] for x in self.process.sent if x.get('method')=='thread/start')
        self.assertEqual(start['environments'],[])
        self.assertEqual(start['sandbox'],'read-only')
        self.assertTrue(start['ephemeral'])
        self.assertNotIn('OPENAI_API_KEY',self.launch.call_args.kwargs['env'])

    def test_api_login_rejected_before_model_call(self):
        self.assertIsNone(self.run_client([],account='apiKey'))
        self.assertFalse(any(x.get('method')=='turn/start' for x in self.process.sent))
        self.assertFalse(self.client.info()['api_billing'])

    def test_tool_roundtrip(self):
        self.assertTrue(self.run_client([tool()]+done('Four.'))['completed'])
        self.dispatch.assert_called_once_with('jinx_calculate',{'expression':'2+2'})

    def test_unknown_tool_never_executes(self):
        self.run_client([tool('terminal')]+done())
        self.dispatch.assert_not_called()

    def test_duplicate_tool_call_not_repeated(self):
        self.run_client([tool(),tool()]+done())
        self.dispatch.assert_called_once()

    def test_error_before_output_allows_fallback(self):
        self.assertIsNone(self.run_client([{'method':'error','params':{}}]))
        self.assertGreater(self.client.info()['retry_seconds'],20)

    def test_error_after_action_does_not_fallback(self):
        r=self.run_client([tool(),{'method':'error','params':{}}])
        self.assertIsNotNone(r);self.assertFalse(r['completed'])
        self.dispatch.assert_called_once()

    def test_cancel_does_not_fallback(self):
        r=self.run_client([],cancelled=lambda:True)
        self.assertTrue(r['interrupted']);self.launch.assert_not_called()

    def test_subscription_mode_cannot_fall_through_to_paid_api(self):
        import cloud_model
        with patch.dict('os.environ',{'JINX_ONLINE_PROVIDER':'subscription'}):
            cloud=cloud_model.Cloud()
        with patch.object(cloud.subscription,'available',return_value=True), \
             patch.object(cloud.subscription,'run',return_value=None) as run, \
             patch('openai.OpenAI') as api:
            self.assertIsNone(cloud.run('hello','Jinx',[],[],Mock(),lambda:False,Mock()))
            run.assert_called_once();api.assert_not_called()


if __name__=='__main__':unittest.main()
