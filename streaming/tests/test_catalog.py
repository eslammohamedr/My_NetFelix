from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import catalog

HASH = 'a' * 40
OTHER = 'b' * 40


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.detail = {'title': 'Film', 'mediaInfo': {'status': 3, 'requests': [{'status': 2}]}}
        self.queue = []
        self.history = [{'movieId': 7, 'downloadId': HASH.upper()}]
        self.calls = []
        self.qbt = Mock()
        self.qbt.call.side_effect = lambda route, **kw: ([
            {'hash': HASH, 'name': 'Film release', 'progress': .1, 'state': 'downloading', 'dlspeed': 1000},
            {'hash': OTHER, 'name': 'Film same title but unrelated', 'progress': 1, 'state': 'stalledUP', 'dlspeed': 0}
        ] if route == 'torrents/info' else [
            {'index': 0, 'name': 'sample.mp4', 'size': 100, 'progress': 1},
            {'index': 1, 'name': 'feature.mkv', 'size': 1000000, 'progress': .1}])
        self.patcher = patch.object(catalog, 'api', self.api)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def api(self, service, route, **params):
        self.calls.append((service, route, params))
        if service == 'JELLYSEERR':
            return self.detail
        if route == 'movie':
            return [{'id': 7, 'tmdbId': 42}, {'id': 8, 'tmdbId': 99}]
        if route == 'series':
            return [{'id': 7, 'tvdbId': 1234}, {'id': 8, 'tvdbId': 9876}]
        if route == 'queue':
            return {'records': self.queue, 'totalRecords': len(self.queue)}
        if route.startswith('history/'):
            return self.history
        raise AssertionError(route)

    def test_completed_queue_uses_history_and_ignores_same_title(self):
        result = catalog.resolve('movie', 42, self.qbt)
        self.assertEqual(result['state'], 'download')
        self.assertEqual([t['hash'] for t in result['downloads']], [HASH])
        self.assertEqual(result['downloads'][0]['files'][0]['name'], 'feature.mkv')

    def test_active_queue_matches_media_id(self):
        self.history = []
        self.queue = [{'movieId': 7, 'downloadId': HASH}, {'movieId': 8, 'downloadId': OTHER}]
        result = catalog.resolve('movie', 42, self.qbt)
        self.assertEqual([t['hash'] for t in result['downloads']], [HASH])

    def test_queue_pagination(self):
        original = self.api
        def paginated(service, route, **params):
            if route == 'queue':
                records = [{'movieId': 7, 'downloadId': HASH}] if params['page'] == 2 else []
                return {'records': records, 'totalRecords': 101}
            return original(service, route, **params)
        self.history = []
        with patch.object(catalog, 'api', paginated):
            self.assertEqual(catalog.resolve('movie', 42, self.qbt)['state'], 'download')

    def test_pending_approval_does_not_start_or_lookup_downloads(self):
        self.detail['mediaInfo']['status'] = 2
        result = catalog.resolve('movie', 42, self.qbt)
        self.assertEqual(result['state'], 'approval')
        self.qbt.call.assert_not_called()
        self.assertEqual(len(self.calls), 1)

    def test_blocked_or_unrequested_titles(self):
        for media, state in [({'status': 6}, 'blocked'), ({}, 'request')]:
            self.detail['mediaInfo'] = media
            self.assertEqual(catalog.resolve('movie', 42, self.qbt)['state'], state)
        self.qbt.call.assert_not_called()

    def test_tv_uses_tvdb_id_and_preserves_episode_choices(self):
        self.detail = {'name': 'Show', 'externalIds': {'tvdbId': 1234}, 'mediaInfo': {'status': 3}}
        self.history = [{'seriesId': 7, 'downloadId': HASH}]
        result = catalog.resolve('tv', 42, self.qbt)
        self.assertEqual(len(result['downloads'][0]['files']), 2)
        self.assertIn(('SONARR', 'series', {'tvdbId': 1234}), self.calls)
        self.assertIn(('SONARR', 'history/series', {'seriesId': 7}), self.calls)

    def test_missing_tvdb_id_does_not_guess(self):
        self.assertEqual(catalog.resolve('tv', 42, self.qbt)['state'], 'waiting')
        self.qbt.call.assert_not_called()

    def test_library_fallback_when_torrent_removed(self):
        self.detail['mediaInfo'].update(status=5, jellyfinMediaId='a123')
        self.qbt.call.side_effect = lambda *a, **k: []
        result = catalog.resolve('movie', 42, self.qbt)
        self.assertEqual(result['state'], 'library')
        self.assertEqual(result['library_path'], '/web/index.html#!/details?id=a123')

    def test_library_title_without_arr_record(self):
        self.detail['mediaInfo'].update(status=5, jellyfinMediaId='a123')
        original = self.api
        with patch.object(catalog, 'api', lambda service, route, **params:
                          [] if route == 'movie' else original(service, route, **params)):
            self.assertEqual(catalog.resolve('movie', 42, self.qbt)['state'], 'library')

    def test_invalid_download_ids_not_accepted(self):
        self.history = [{'movieId': 7, 'downloadId': '../bad'}]
        self.assertEqual(catalog.resolve('movie', 42, self.qbt)['downloads'], [])

    def test_theatrical_release_state(self):
        self.history = []
        self.queue = []
        self.qbt.call.side_effect = lambda *a, **k: []
        original = self.api
        def movie_in_cinemas(service, route, **params):
            if route == 'movie':
                return [{'id': 7, 'tmdbId': 42, 'status': 'inCinemas', 'inCinemas': '2026-07-29', 'digitalRelease': '2026-09-29'}]
            return original(service, route, **params)
        with patch.object(catalog, 'api', movie_in_cinemas):
            result = catalog.resolve('movie', 42, self.qbt)
            self.assertEqual(result['state'], 'in_cinemas')
            self.assertIn('in theaters', result['message'])
            self.assertEqual(result['dates']['digitalRelease'], '2026-09-29')

    def test_announced_release_state(self):
        self.history = []
        self.queue = []
        self.qbt.call.side_effect = lambda *a, **k: []
        original = self.api
        def movie_announced(service, route, **params):
            if route == 'movie':
                return [{'id': 7, 'tmdbId': 42, 'status': 'announced'}]
            return original(service, route, **params)
        with patch.object(catalog, 'api', movie_announced):
            result = catalog.resolve('movie', 42, self.qbt)
            self.assertEqual(result['state'], 'announced')
            self.assertIn('not been released yet', result['message'])

    def test_not_found_release_state(self):
        self.history = []
        self.queue = []
        self.qbt.call.side_effect = lambda *a, **k: []
        original = self.api
        def movie_released(service, route, **params):
            if route == 'movie':
                return [{'id': 7, 'tmdbId': 42, 'status': 'released'}]
            return original(service, route, **params)
        with patch.object(catalog, 'api', movie_released):
            result = catalog.resolve('movie', 42, self.qbt)
            self.assertEqual(result['state'], 'not_found')
            self.assertIn('No active download found', result['message'])

    def test_arabic_dub_missing_warning_with_downloads(self):
        self.detail['mediaInfo']['requests'] = [{'profileId': 7}]
        result = catalog.resolve('movie', 42, self.qbt)
        self.assertTrue(result['is_arabic_dub'])
        self.assertFalse(result['has_arabic_dub'])
        self.assertTrue(result['arabic_dub_missing'])

    def test_arabic_dub_matched_when_name_contains_arabic(self):
        self.detail['mediaInfo']['requests'] = [{'profileId': 7}]
        self.qbt.call.side_effect = lambda route, **kw: ([
            {'hash': HASH, 'name': 'Film Arabic Dubbed 1080p', 'progress': .1, 'state': 'downloading', 'dlspeed': 1000}
        ] if route == 'torrents/info' else [
            {'index': 1, 'name': 'feature.mkv', 'size': 1000000, 'progress': .1}])
        result = catalog.resolve('movie', 42, self.qbt)
        self.assertTrue(result['is_arabic_dub'])
        self.assertTrue(result['has_arabic_dub'])
        self.assertFalse(result['arabic_dub_missing'])


if __name__ == '__main__':
    unittest.main()


