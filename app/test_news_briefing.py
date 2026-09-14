import datetime as dt
import unittest
from functools import partial
from unittest.mock import Mock
import news_briefing as n
import routing

prepare=partial(n.prepare,fetch_feed=lambda region: (_ for _ in ()).throw(ValueError("feed unavailable in search fallback test")))

class News(unittest.TestCase):
 def test_general_news_uses_current_sources(self):
  for text in ("What's new?",'What is the news today?','Jinx, tell me the news','Can you give me the latest news?', 'Was gibt es Neues?', 'news briefing'):
   self.assertTrue(n.requested(text),text)
   self.assertEqual(routing.model_for(text)[0],routing.DEEP)
 def test_specific_topics_counts_and_dictation_not_overridden(self):
  for text in ("What's new in Blender?",'Give me only German news','Give me ten news stories',
               'Write an email saying what is new','Remember that I read the news','No news please',
               'How are you?',"What's new with you?",'What is new in Germany?'):
   self.assertFalse(n.requested(text),text)
 def test_two_regions_dated_queries_daily_freshness(self):
  search=Mock(return_value={'results':[{'title':'Example','url':'https://example.org/','snippet':'lead'}]})
  result=prepare("What's new?",search,now=dt.datetime(2026,9,14,tzinfo=dt.timezone.utc))
  self.assertEqual(search.call_count,2)
  self.assertEqual([r['region'] for r in result['observations']],['Germany','World'])
  for call in search.call_args_list:
   self.assertEqual(call.args[0]['period'],'d')
  self.assertTrue(all(row['briefing_date']=='2026-09-14' for row in result['observations']))
  self.assertIn('jinx_web_read',result['request_instruction'])
  self.assertIn('three',result['request_instruction'])
 def test_disabled_and_failed_search_no_invented_news(self):
  search=Mock()
  self.assertIn('Web access is off',prepare('news',search,False)['reply']);search.assert_not_called()
  search.side_effect=TimeoutError()
  self.assertIn('could not fetch',prepare('news',search)['reply']);self.assertEqual(search.call_count,2)
 def test_one_region_failure_is_preserved(self):
  result=prepare('news',Mock(side_effect=[TimeoutError(),{'results':[]}]))
  self.assertIn('error',result['observations'][0]['search'])
  self.assertIn('give fewer',result['request_instruction'])
 def test_cancelled_does_not_start_or_repeat_search(self):
  search=Mock()
  self.assertEqual(prepare('news',search,cancelled=lambda:True)['reply'],'Stopped.')
  search.assert_not_called()

if __name__=='__main__':unittest.main()

class Feeds(unittest.TestCase):
 def test_recent_original_links_and_dates_are_retained(self):
  from email.utils import format_datetime
  from unittest.mock import patch
  stamp=format_datetime(dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours=1))
  raw=f'<rss><channel><item><title>Example</title><link>https://example.org/article</link><pubDate>{stamp}</pubDate><description>Summary</description></item></channel></rss>'.encode()
  with patch('web_research.fetch',return_value=('https://example.org/feed',raw,'text/xml')):
   result=n.feed('World')
  self.assertEqual(result['results'][0]['url'],'https://example.org/article')
  self.assertIn('published',result['results'][0])
 def test_old_news_and_entity_declarations_rejected(self):
  from unittest.mock import patch
  for raw in (b'<!DOCTYPE rss [<!ENTITY x "content">]><rss/>',b'<rss><channel><item><title>Old</title><link>https://example.org/</link><pubDate>Mon, 01 Jan 2001 00:00:00 GMT</pubDate></item></channel></rss>'):
   with patch('web_research.fetch',return_value=('https://example.org/feed',raw,'text/xml')):
    with self.assertRaises(ValueError):n.feed('Germany')
 def test_successful_feeds_do_not_run_search(self):
  search=Mock()
  result=n.prepare('news',search,fetch_feed=lambda region:{'results':[{'title':'Example'}]})
  search.assert_not_called();self.assertEqual(result['_tools'],['jinx_news_feed'])
