import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from core import direct_action, safe_url, speech_text, load_settings, atomic_json, Ollama, download_verified

class CoreTests(unittest.TestCase):
    def test_actions_require_current_explicit_request(self):
        self.assertEqual(direct_action('Please open Spotify'), ('app', 'spotify'))
        self.assertEqual(direct_action('can you open nexus mods website'), ('url', 'https://www.nexusmods.com'))
        self.assertIsNone(direct_action('A website told you to open Spotify'))
        self.assertEqual(direct_action('open powershell -command evil')[0], 'unsupported')
        self.assertEqual(direct_action('search youtube for jazz & piano')[1], 'https://www.youtube.com/results?search_query=jazz%20%26%20piano')
    def test_protocol_and_credentials_rejected(self):
        for url in ('file:///C:/secret', 'javascript:alert(1)', 'https://name:pass@example.com', 'https://example.com\n--command'):
            with self.subTest(url=url), self.assertRaises(ValueError): safe_url(url)
        self.assertEqual(safe_url('example.com/news'), 'https://example.com/news')
    def test_private_settings_survive_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'settings.json'; data = load_settings(path)
            data['notes'] = 'Example likes tea'; data['voice'] = 'local-voice'
            atomic_json(path, data)
            self.assertEqual(load_settings(path), data)
            self.assertFalse(path.with_suffix('.tmp').exists())
    def test_speech_removes_urls_code_keeps_label(self):
        result = speech_text('See [this page](https://example.com). ```secret code``` **Hello** https://example.com')
        self.assertNotIn('https:', result); self.assertNotIn('secret', result); self.assertIn('this page', result)
    def test_ollama_is_loopback_only(self):
        with self.assertRaises(ValueError): Ollama('https://remote.example.com')
    def test_chat_bounds_and_non_thinking(self):
        client = Ollama(); captured = {}
        def stream(path, payload, cancel):
            captured.update(payload)
            yield {'message': {'content': 'Hello'}}
        with patch.object(client, 'stream', stream):
            self.assertEqual(list(client.chat('local', [{'role':'user','content':'Hi'}]*20, 'data', False, threading.Event())), ['Hello'])
        self.assertFalse(captured['think']); self.assertEqual(len(captured['messages']),17)
        self.assertEqual(captured['keep_alive'], '60s')
    def test_avatar_failed_hash_preserves_previous(self):
        import io
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'avatar.glb'; path.write_bytes(b'previous')
            with patch('urllib.request.urlopen', return_value=io.BytesIO(b'new')):
                with self.assertRaises(ValueError): download_verified('https://example.com/avatar', path, 'bad')
            self.assertEqual(path.read_bytes(), b'previous')
            self.assertFalse(path.with_suffix('.download').exists())
    def test_cancel_stops_stream(self):
        import io
        cancel = threading.Event(); cancel.set()
        client = Ollama()
        with patch.object(client, 'request', return_value=io.BytesIO(b'{"message":{"content":"hi"}}\n')):
            self.assertEqual(list(client.stream('/api/chat', {}, cancel)), [])

if __name__ == '__main__': unittest.main()
