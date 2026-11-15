import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import generate as g
import verify_site


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / 'site'
        for name, value in {'OUT': self.out, 'BASE': 'https://example.org/my-nuvio-n1',
                            'API_KEY': 'test-secret', 'TOKEN': ''}.items():
            p = patch.object(g, name, value)
            p.start()
            self.addCleanup(p.stop)

    def build(self, handler):
        log = io.StringIO()
        with patch.object(g, 'get_netflix_rows', return_value={}), \
                patch.object(g, 'catalog', side_effect=handler), contextlib.redirect_stdout(log):
            g.main()
        return log.getvalue()

    def test_all_catalog_definitions_preserved_and_unique(self):
        self.assertEqual(len(g.ALL), 58)
        keys = [(s['type'], s['id']) for s in g.ALL]
        self.assertEqual(len(set(keys)), 58)

    def test_manifest_routes_status_and_grouping(self):
        def handler(spec, netflix):
            if spec['mode'] == 'external':
                return None, 'Separate addon'
            return [{'id': 'tt1234567', 'type': spec['type'], 'name': 'Test title'}], ''
        self.build(handler)
        manifest = json.loads((self.out / 'manifest.json').read_text())
        self.assertEqual(manifest['resources'], ['catalog'])
        self.assertEqual(manifest['types'], ['movie', 'series'])
        expected = [s for s in g.ALL if s['mode'] != 'external']
        self.assertEqual(len(manifest['catalogs']), len(expected))
        for spec, entry in zip(expected, manifest['catalogs']):
            self.assertEqual(entry, {k: spec[k] for k in ('type', 'id', 'name')})
            route = self.out / 'catalog' / entry['type'] / (entry['id'] + '.json')
            self.assertEqual(json.loads(route.read_text())['metas'][0]['id'], 'tt1234567')
        status = json.loads((self.out / 'status.json').read_text())
        self.assertEqual(status['planned'], 58)
        self.assertEqual(len(status['catalogs']), 58)
        groups = json.loads((self.out / 'grouping-plan.json').read_text())
        self.assertEqual(sum(map(len, groups.values())), 58)
        self.assertIn(g.BASE + '/manifest.json', (self.out / 'index.html').read_text())

    def test_no_active_catalogs_fails_build(self):
        with self.assertRaisesRegex(SystemExit, 'No catalogs'):
            self.build(lambda *args: ([], 'Unavailable'))
        self.assertFalse((self.out / 'manifest.json').exists())

    def test_missing_credentials_fail_before_removing_output(self):
        self.out.mkdir()
        marker = self.out / 'manifest.json'
        marker.write_text('previous')
        with patch.object(g, 'API_KEY', ''), patch.object(g, 'TOKEN', ''):
            with self.assertRaisesRegex(SystemExit, 'private GitHub Actions secret'):
                g.main()
        self.assertEqual(marker.read_text(), 'previous')

    def test_exception_secrets_never_reach_status_or_logs(self):
        def handler(spec, netflix):
            if spec == g.ALL[0]:
                return [{'id': 'tt1234567', 'type': 'movie', 'name': 'Test'}], ''
            raise HTTPError('https://api.example/?api_key=test-secret', 401,
                            'test-secret', {}, None)
        log = self.build(handler)
        public = ''.join(p.read_text() for p in self.out.rglob('*') if p.is_file())
        self.assertNotIn('test-secret', log + public)
        self.assertIn('HTTPError (HTTP 401)', log)
        self.assertEqual(g.safe_error(RuntimeError('test-secret')), 'RuntimeError')

    def test_netflix_exception_is_safe(self):
        log = io.StringIO()
        with patch.object(g, 'get_netflix_rows', side_effect=RuntimeError('test-secret')), \
                patch.object(g, 'catalog', return_value=([], 'Unavailable')), \
                contextlib.redirect_stdout(log), self.assertRaises(SystemExit):
            g.main()
        self.assertNotIn('test-secret', log.getvalue())

    def test_unverified_entries_are_withheld(self):
        spec = next(s for s in g.ALL if s['mode'] == 'verified')
        entry = {'type': spec['type'], 'tags': [spec['tag']],
                 'imdb_id': 'tt1234567', 'source_url': 'https://example.org'}
        with patch.object(g, 'VERIFIED', [entry]), patch.object(g, 'enrich_from_imdb') as enrich:
            self.assertEqual(g.fetch_verified(spec), [])
            enrich.assert_not_called()

    def test_external_addons_stay_separate(self):
        for spec in g.ALL:
            if spec['mode'] == 'external':
                rows, reason = g.catalog(spec)
                self.assertIsNone(rows)
                self.assertTrue(reason)

    def test_turkish_subtitles_and_shahid_require_specific_evidence(self):
        for group in ('Turkish Content', 'Shahid Arabic Exclusives'):
            spec = next(s for s in g.ALL if s['group'] == group and s['mode'] == 'verified')
            entry = {'type': spec['type'], 'tags': [spec['tag']], 'verified': True,
                     'imdb_id': 'tt1234567', 'source_url': 'https://example.org',
                     'origin_country': 'TR', 'original_language': 'tr'}
            with patch.object(g, 'VERIFIED', [entry]), patch.object(g, 'enrich_from_imdb') as enrich:
                self.assertEqual(g.fetch_verified(spec), [])
                enrich.assert_not_called()

    def test_live_verifier_checks_catalog_routes(self):
        manifest = {'id': 'com.mynuvio.buildn1', 'resources': ['catalog'],
                    'catalogs': [{'type': 'movie', 'id': 'example'}]}
        with patch.object(verify_site, 'read_json', side_effect=[
                manifest, {'metas': [{'id': 'tt1234567', 'type': 'movie', 'name': 'Test'}]}
        ]) as read, contextlib.redirect_stdout(io.StringIO()):
            verify_site.verify('https://example.org/addon/')
        self.assertEqual(read.call_args_list[-1].args[0],
                         'https://example.org/addon/catalog/movie/example.json')
        with patch.object(verify_site, 'read_json', side_effect=[manifest, {'metas': []}]):
            with self.assertRaisesRegex(ValueError, 'no entries'):
                verify_site.verify('https://example.org/addon')


if __name__ == '__main__':
    unittest.main()
