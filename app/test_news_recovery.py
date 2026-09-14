import jinx_test_support
import unittest
from unittest.mock import Mock,patch
import news_briefing as n
import jinx as j


def prepared():
 return {'observations':[{'region':region,'search':{'provider':'Newsroom','feed_url':'https://example.org/feed',
   'results':[{'url':f'https://example.org/{region}/{i}','title':f'{region} headline {i}',
               'published':'2026-09-14T12:00:00+00:00','snippet':'Publisher summary of a current reported event.'} for i in range(3)]}}
   for region in ('Germany','World')], 'news_briefing':True,'_tools':['jinx_news_feed']}

def compose(rows,cancelled):
 return {r['id']:{'headline':r['title'],'summary':'The publisher reported this event.'} for r in rows}

class Recovery(unittest.TestCase):
 def test_actual_utterances_and_politeness(self):
  for text in ("Thanks, what's new?", "Yeah, let's dive into today's news.", "Jinx, tell me in the news.",
               'Thank you Jinx, can you give me the news?', 'Sure, let us hear the latest news.',
               'News, please'):
   self.assertTrue(n.requested(text),text)
  for text in ("Thanks, what's new in Blender?", "Write an email saying thanks what's new", "Thanks, don't give me the news",'I saw the news yesterday'):
   self.assertFalse(n.requested(text),text)
 def test_all_article_failures_keep_real_publisher_summaries(self):
  reader=Mock(side_effect=ValueError('HTTP403'))
  result=n.complete(prepared(),reader,compose=compose)
  self.assertEqual(reader.call_count,6)
  self.assertEqual(len(result['news_sources']),6)
  self.assertEqual(result['reply'].count('[Publisher summary]'),6)
  self.assertFalse(result.get('news_summary_failed'))
 def test_search_snippets_without_article_are_not_presented_as_verified(self):
  data=prepared()
  for group in data['observations']:group['search'].pop('feed_url')
  result=n.complete(data,Mock(side_effect=ValueError()),compose=Mock(side_effect=AssertionError('no verified sources')))
  self.assertIn('could not read reliable',result['reply'])
 def test_fixed_six_sources_and_links_come_from_application(self):
  reader=Mock(return_value={'text':'A current article excerpt of more than thirty characters.'})
  result=n.complete(prepared(),reader,compose=compose)
  self.assertEqual(len(result['news_sources']),6)
  self.assertEqual(result['reply'].count('[Source]'),6)
  self.assertIn('https://example.org/Germany/0',result['reply'])
 def test_cancellation_never_generates_reply(self):
  writer=Mock();reader=Mock()
  self.assertEqual(n.complete(prepared(),reader,cancelled=lambda:True,compose=writer)['reply'],'Stopped.')
  writer.assert_not_called();reader.assert_not_called()
 def test_writer_failure_does_not_escalate_or_retry(self):
  writer=Mock(side_effect=ValueError())
  result=n.complete(prepared(),Mock(return_value={'text':'A current article excerpt of more than thirty characters.'}),compose=writer)
  writer.assert_called_once();self.assertTrue(result['news_summary_failed'])
  self.assertIn('original publisher headlines',result['reply'])
 def test_actual_chat_avoids_agent_and_old_conversation(self):
  with patch.object(n,'prepare',return_value=prepared()), \
       patch.object(n,'complete',side_effect=lambda *args,**kwargs:n_result()), \
       patch.object(j,'run_tiered_turn',side_effect=AssertionError('27B agent must not run')), \
       patch.object(j,'say'),patch.object(j.voice.breeze,'release'),patch.object(j,'task_router',None), \
       patch.dict(j.data,speak=False,episodic_memory=False):
   for request in ("Thanks, what's new?","Yeah, let's dive into today's news."):
    j.chat(request,False)
    self.assertEqual(j.status['error'],'');self.assertEqual(j.status['active_model'],'qwen3.5:4b')
    self.assertEqual(j.status['last_draft'],'Germany\nThree stories\nWorld\nThree stories')

def n_result():return {'reply':'Germany\nThree stories\nWorld\nThree stories','news_summary_model':'qwen3.5:4b','news_sources':[]}

if __name__=='__main__':unittest.main()
