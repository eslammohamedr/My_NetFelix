import http.client
import importlib.util
from pathlib import Path
import tempfile
import threading
import time
import unittest
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
spec = importlib.util.spec_from_file_location('streaming_server', Path(__file__).parents[1] / 'server.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
HASH = 'a' * 40


class Helpers(unittest.TestCase):
    def test_ranges(self):
        for value, expected in [(None, (0, 99, False)), ('bytes=10-19', (10, 19, True)),
                                ('bytes=90-', (90, 99, True)), ('bytes=-5', (95, 99, True)),
                                ('bytes=80-999', (80, 99, True))]:
            self.assertEqual(s.parse_range(value, 100), expected)
        for value in ['bytes=-0', 'bytes=100-', 'bytes=20-10', 'bytes=0-1,3-4', 'bytes=-', 'garbage']:
            with self.assertRaises(s.Problem):
                s.parse_range(value, 100)

    def test_unaligned_file_offset(self):
        files = [{'index': 0, 'size': 3}, {'index': 1, 'size': 12}]
        info = {b'info': {b'files': [{b'length': 3}, {b'length': 12}]}}
        self.assertEqual(s.file_offset(info, files, files[1]), 3)
        self.assertEqual(s.available_bytes([2, 0, 2, 2], 3, 12, 4), 1)
        self.assertEqual(s.available_bytes([2, 2, 2, 2], 3, 12, 4), 12)
        info[b'info'][b'meta version'] = 2
        with self.assertRaises(s.Problem):
            s.file_offset(info, files, files[1])

    def test_metadata(self):
        self.assertEqual(s.bdecode(b'd4:infod6:lengthi12e12:piece lengthi4eee'),
                         {b'info': {b'length': 12, b'piece length': 4}})
        for raw in [b'3:a', b'lejunk', b'd']:
            with self.assertRaises((ValueError, IndexError)):
                s.bdecode(raw)

    def test_path_confinement_and_incomplete_suffix(self):
        with tempfile.TemporaryDirectory() as d, patch.object(s, 'ROOT', Path(d)):
            Path(d, 'movie.mp4.!qB').write_bytes(b'data')
            t = {'save_path': '/data/torrents'}
            self.assertEqual(s.local_path(t, {'name': 'movie.mp4'}, {}).name, 'movie.mp4.!qB')
            with self.assertRaises(s.Problem):
                s.local_path(t, {'name': '../../etc/passwd'}, {})
            Path(d, 'link.mp4').symlink_to('/etc/passwd')
            with self.assertRaises(s.Problem):
                s.local_path(t, {'name': 'link.mp4'}, {})

    def test_srt_to_vtt(self):
        srt = b"1\n00:01:20,000 --> 00:01:23,500\nHello\n"
        vtt = s.srt_to_vtt(srt)
        self.assertTrue(vtt.startswith('WEBVTT\n'))
        self.assertIn('00:01:20.000 --> 00:01:23.500', vtt)

    def test_detect_language(self):
        self.assertEqual(s.detect_language('Subs/Arabic.srt'), ('Arabic', 'ar'))
        self.assertEqual(s.detect_language('Subs/SDH.eng.HI.srt'), ('English [SDH]', 'en'))
        self.assertEqual(s.detect_language('Movie.2024.1080p.srt'), ('English', 'en'))


class FakeQbit:
    def __init__(self):
        self.states = [2, 0, 0, 0]
        self.actions = []
        self.torrent = {'state': 'downloading', 'save_path': '/data/torrents', 'seq_dl': False, 'f_l_piece_prio': False}
        self.files = [{'index': 0, 'size': 3, 'name': 'note.txt', 'progress': 1},
                      {'index': 1, 'size': 12, 'name': 'movie.mp4', 'progress': .1},
                      {'index': 2, 'size': 50, 'name': 'subs/english.srt', 'progress': 1}]

    def call(self, endpoint, data=None, raw=False, **kwargs):
        if data is not None:
            self.actions.append((endpoint, data))
            if endpoint.endswith('toggleSequentialDownload'):
                self.torrent['seq_dl'] = not self.torrent['seq_dl']
            if endpoint.endswith('toggleFirstLastPiecePrio'):
                self.torrent['f_l_piece_prio'] = not self.torrent['f_l_piece_prio']
            return b''
        return {'torrents/info': [self.torrent], 'torrents/files': self.files,
                'torrents/properties': {'piece_size': 4},
                'torrents/pieceStates': self.states,
                'torrents/export': b'd4:infod5:filesld6:lengthi3eed6:lengthi12eed6:lengthi50eee12:piece lengthi4eee'}[endpoint]


class HTTPIntegration(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        Path(self.directory.name, 'movie.mp4').write_bytes(b'abcdefghijkl')
        sub_dir = Path(self.directory.name, 'subs')
        sub_dir.mkdir(exist_ok=True)
        (sub_dir / 'english.srt').write_bytes(b"1\n00:00:01,000 --> 00:00:03,000\nHello world\n")
        self.fake = FakeQbit()
        self.patches = [patch.object(s, 'ROOT', Path(self.directory.name)), patch.object(s, 'qbt', self.fake),
                        patch.object(s, 'WAIT_SECONDS', 1), patch.object(s, 'BUFFER', 4)]
        for p in self.patches:
            p.start()
        self.httpd = s.ThreadingHTTPServer(('127.0.0.1', 0), s.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()
        for p in reversed(self.patches):
            p.stop()
        self.directory.cleanup()

    def request(self, path, headers=None, method='GET'):
        conn = http.client.HTTPConnection(*self.httpd.server_address, timeout=5)
        conn.request(method, path, headers=headers or {})
        response = conn.getresponse()
        status, headers, body = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return status, headers, body

    def test_verified_range_and_suffix(self):
        self.fake.states = [2, 2, 2, 2]
        status, headers, body = self.request(f'/stream/{HASH}/1', {'Range': 'bytes=1-5'})
        self.assertEqual((status, body), (206, b'bcdef'))
        self.assertEqual(headers['Content-Range'], 'bytes 1-5/12')
        self.assertEqual(self.request(f'/stream/{HASH}/1', {'Range': 'bytes=-2'})[2], b'kl')
        status, headers, _ = self.request(f'/stream/{HASH}/1', {'Range': 'bytes=99-'})
        self.assertEqual((status, headers['Content-Range']), (416, 'bytes */12'))

    def test_missing_piece_waits_instead_of_reading_existing_bytes(self):
        result = []
        worker = threading.Thread(target=lambda: result.append(self.request(f'/stream/{HASH}/1', {'Range': 'bytes=1-4'})))
        worker.start()
        time.sleep(.3)
        self.assertTrue(worker.is_alive(), 'Must not serve bytes whose torrent piece is incomplete')
        self.fake.states = [2, 2, 2, 2]
        worker.join(4)
        self.assertEqual(result[0][2], b'bcde')

    def test_missing_piece_timeout(self):
        status, _, body = self.request(f'/stream/{HASH}/1', {'Range': 'bytes=1-4'})
        self.assertEqual(status, 503)
        self.assertNotEqual(body, b'bcde')

    def test_buffer_requires_tail_and_disk(self):
        self.fake.states = [2, 2, 0, 0]
        self.assertFalse(s.readiness(HASH, 1)['ready'])
        self.fake.states = [2, 2, 0, 2]
        self.assertTrue(s.readiness(HASH, 1)['ready'])
        Path(self.directory.name, 'movie.mp4').unlink()
        self.assertFalse(s.readiness(HASH, 1)['ready'])

    def test_prepare_is_idempotent_and_requires_header(self):
        path = f'/api/prepare/{HASH}/1'
        self.assertEqual(self.request(path, method='POST')[0], 403)
        self.assertEqual(self.fake.actions, [])
        for _ in range(2):
            self.assertEqual(self.request(path, {'X-NetFelix': '1'}, 'POST')[0], 200)
        toggles = [e for e, _ in self.fake.actions if 'toggle' in e]
        self.assertEqual(len(toggles), 2)
        self.assertTrue(self.fake.torrent['seq_dl'])
        self.assertEqual(self.request(path, {'X-NetFelix': '1', 'Origin': 'http://untrusted.invalid'}, 'POST')[0], 403)

    def test_missing_files_rejected(self):
        self.fake.torrent['state'] = 'missingFiles'
        self.assertEqual(self.request(f'/stream/{HASH}/1')[0], 409)

    def test_subtitles_endpoint_and_vtt(self):
        status, headers, body = self.request(f'/subtitles/torrent/{HASH}/2.vtt')
        self.assertEqual(status, 200)
        self.assertIn('text/vtt', headers['Content-Type'])
        self.assertTrue(body.startswith(b'WEBVTT'))
        self.assertIn(b'00:00:01.000 --> 00:00:03.000', body)
        self.assertIn(b'Hello world', body)

    def test_subtitles_in_readiness(self):
        ready = s.readiness(HASH, 1)
        self.assertIn('subtitles', ready)
        self.assertEqual(len(ready['subtitles']), 1)
        self.assertEqual(ready['subtitles'][0]['lang'], 'en')
        self.assertEqual(ready['subtitles'][0]['label'], 'English')
        self.assertTrue(ready['subtitles'][0]['ready'])

    def test_playlist_includes_subtitle_option(self):
        status, _, body = self.request(f'/playlist/{HASH}/1')
        self.assertEqual(status, 200)
        self.assertIn(b'#EXTVLCOPT:sub-file=', body)
        self.assertIn(b'/subtitles/torrent/', body)

    def test_prepare_prioritizes_subtitles(self):
        self.request(f'/api/prepare/{HASH}/1', {'X-NetFelix': '1'}, 'POST')
        prios = [args for ep, args in self.fake.actions if ep.endswith('filePrio')]
        self.assertTrue(any(p.get('id') == 2 and p.get('priority') == 7 for p in prios))

    def test_prepare_multi_video_focuses_bandwidth_on_selected_file(self):
        self.fake.files.append({'index': 3, 'size': 120, 'name': 'episode2.mp4', 'progress': 0})
        orig_call = self.fake.call
        def mock_call(endpoint, data=None, raw=False, **kwargs):
            if endpoint == 'torrents/export':
                return b'd4:infod5:filesld6:lengthi3eed6:lengthi12eed6:lengthi50eed6:lengthi120eee12:piece lengthi4eee'
            return orig_call(endpoint, data=data, raw=raw, **kwargs)
        self.fake.call = mock_call
        status, _, _ = self.request(f'/api/prepare/{HASH}/1', {'X-NetFelix': '1'}, 'POST')
        self.assertEqual(status, 200)
        prios = [args for ep, args in self.fake.actions if ep.endswith('filePrio')]
        self.assertTrue(any(p.get('id') == '3' and p.get('priority') == 1 for p in prios))
        self.assertTrue(any(p.get('id') == 1 and p.get('priority') == 7 for p in prios))


if __name__ == '__main__':
    unittest.main()
