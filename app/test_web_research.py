import jinx_test_support  # Isolate state and memory before importing jinx.
import json,socket,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import web_research as w
import jinx as a

class WebSafety(unittest.TestCase):
 def test_local_credentials_and_nonweb_urls_blocked(self):
  for url in ['file:///etc/passwd','http://127.0.0.1:17341/status','http://192.0.2.1/','http://169.254.169.254/','http://[::1]/','http://[::ffff:127.0.0.1]/','http://localhost/','http://box.local/','https://u:p@example.org/','https://example.org:22/','https://example.org/\nHost:x','http://example.org\\@127.0.0.1/']:
   with self.subTest(url=url),self.assertRaises(ValueError):w.normal_url(url)
 def test_public_urls_keep_queries_and_drop_fragments(self):
  self.assertEqual(w.normal_url('https://example.org/article?q=one#part'),'https://example.org/article?q=one')
 def test_mixed_public_private_dns_is_blocked(self):
  records=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443)),(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]
  with patch.object(w.socket,'getaddrinfo',return_value=records),self.assertRaises(ValueError):w.public_addresses('example.org',443)
 def test_redirect_to_private_blocked_before_second_connection(self):
  class Response:
   status=302
   def getheader(self,k):return 'http://127.0.0.1/secret'
  class Connection:
   def request(self,*args,**kw):pass
   def getresponse(self):return Response()
   def close(self):pass
  with patch.object(w,'public_addresses',return_value=[]),patch.object(w.http.client,'HTTPSConnection',return_value=Connection()) as connect,self.assertRaises(ValueError):w.fetch('https://example.org/')
  self.assertEqual(connect.call_count,1)
 def test_extraction_removes_script_and_keeps_article(self):
  raw=('<html><head><title>Decimal arithmetic</title><script>window.steal_secret()</script></head><body><article><h1>Decimal arithmetic</h1>'+('<p>Decimal represents decimal numbers exactly and can be useful for accounting calculations.</p>'*6)+'</article></body></html>').encode()
  page=w.extract('https://example.org/',raw,'text/html')
  self.assertNotIn('steal_secret',page['text']);self.assertIn('accounting',page['text'])
 def test_pagination_reuses_download(self):
  page={'url':'https://example.org/','title':'Example','text':'abc '*7000,'fetched_at':w.now(),'truncated':False}
  client=w.Web()
  with patch.object(w,'fetch',return_value=('https://example.org/',b'body','text/html')) as fetch,patch.object(w,'extract',return_value=page):
   first=client.read({'url':'https://example.org/','length':100});second=client.read({'url':'https://example.org/','offset':100,'length':100})
   self.assertEqual(first['text']+second['text'],page['text'][:200]);self.assertTrue(first['more']);self.assertEqual(fetch.call_count,1)
 def test_assistant_excerpts_are_small_and_followup_offsets_preserve_text(self):
  page={'url':'https://example.org/','title':'Example','text':'section '*5000,'fetched_at':w.now(),'truncated':False}
  client=w.Web()
  with patch.object(a,'web',client),patch.object(a.attention,'begin'),patch.dict(a.data,{'web_enabled':True}),patch.dict(a.status,{'web_sources':{}}),patch.object(w,'fetch',return_value=(page['url'],b'body','text/html')),patch.object(w,'extract',return_value=page):
   args={'url':page['url']};first=a.read_web(args)
   self.assertEqual(len(first['text']),2400);self.assertTrue(first['more']);self.assertEqual(first['coverage'],'partial excerpt')
   self.assertEqual(args,{'url':page['url']})
   second=a.read_web({'url':page['url'],'offset':len(first['text']),'length':12000})
   self.assertEqual(len(second['text']),4000)
   self.assertEqual(first['text']+second['text'],page['text'][:6400])
 def test_disabled_web_stops_before_network(self):
  with patch.dict(a.data,{'web_enabled':False}),patch.object(a.web,'read') as read,self.assertRaises(ValueError):a.read_web({'url':'https://example.org/'})
  read.assert_not_called()
 def test_learning_requires_request_and_read_source(self):
  original=a.current_request
  try:
   with patch.object(a.notebook,'save') as save:
    a.current_request='Summarise this article'
    with self.assertRaises(ValueError):a.learn_web({'title':'Claim','note':'Fact','urls':['https://example.org/']})
    a.current_request='Learn about decimal numbers'
    with patch.dict(a.status,{'web_sources':{'https://example.org/':{'kind':'search result'}}}):
     with self.assertRaises(ValueError):a.learn_web({'title':'Claim','note':'Fact','urls':['https://example.org/']})
    save.assert_not_called()
  finally:a.current_request=original

 def test_negative_learning_request_is_not_authority(self):
  for text in ["I don't want you to save this research",'Research it without saving, and do not learn it','What does learn mean on this website?']:
   self.assertFalse(a.wants_learning(text))
  self.assertTrue(a.wants_learning('Please learn from this website'))
 def test_invalid_generated_note_never_saved(self):
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def __iter__(self):return iter([json.dumps({'message':{'content':'invalid JSON'}}).encode()])
  source={'url':'https://example.org/','title':'Example','kind':'read','text':'Some original source facts.'}
  with patch.dict(a.status,{'web_sources':{source['url']:source}}),patch.object(a,'read_web',return_value=source),patch.object(a.urllib.request,'urlopen',return_value=Response()),patch.object(a,'learn_web') as learn:
   with self.assertRaises(json.JSONDecodeError):a.complete_learning('Learn from this source',a.status['voice_epoch'])
   learn.assert_not_called()

class Notebook(unittest.TestCase):
 def test_persist_recall_deduplicate_and_delete(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'notes.sqlite3';book=w.Notebook(path)
   source={'url':'https://docs.python.org/3/library/decimal.html','fetched_at':'2026-09-09'}
   saved=book.save('Decimal arithmetic','Decimal avoids binary representation error for base-ten fractions.',[source])
   book=w.Notebook(path)
   self.assertEqual(book.search('What did we learn about decimal?')[0]['id'],saved['id'])
   self.assertEqual(book.save(saved['title'],saved['note'],[{**source,'fetched_at':'2026-09-10'}])['status'],'already_saved')
   self.assertEqual(book.listing()['count'],1);self.assertEqual(path.stat().st_mode & 0o777,0o600)
   self.assertEqual(book.search('unrelated elephant'),[])
   book.edit(saved['id'],'Corrected: default precision is 28 significant digits and can be increased.')
   self.assertIn('increased',book.search('precision')[0]['note'])
   self.assertEqual(book.search('precision')[0]['sources'][0]['url'],source['url'])
   book.delete(saved['id']);self.assertEqual(book.listing()['count'],0)
 def test_search_input_is_not_sql_or_fts_syntax(self):
  with tempfile.TemporaryDirectory() as folder:
   book=w.Notebook(Path(folder)/'notes.sqlite3')
   book.save('Battery',"Battery draw is measured in watts.",[{'url':'https://example.org/'}])
   self.assertEqual(len(book.search('battery " OR * ; DROP TABLE notes;')),1)
   self.assertEqual(book.listing()['count'],1)
if __name__=='__main__':unittest.main()
