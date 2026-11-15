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
        expected = [s for s in g.catalog_plan() if s['mode'] != 'external']
        self.assertEqual(len(manifest['catalogs']), len(expected))
        for spec, entry in zip(expected, manifest['catalogs']):
            self.assertEqual(entry, {k: spec[k] for k in ('type', 'id', 'name')})
            route = self.out / 'catalog' / entry['type'] / (entry['id'] + '.json')
            self.assertEqual(json.loads(route.read_text())['metas'][0]['id'], 'tt1234567')
        status = json.loads((self.out / 'status.json').read_text())
        self.assertEqual(status['original_planned'], 58)
        self.assertEqual(status['browse_planned'], 40)
        self.assertEqual(status['shahid_home_planned'], 6)
        self.assertEqual(status['planned'], 104)
        self.assertEqual(len(status['catalogs']), 104)
        groups = json.loads((self.out / 'grouping-plan.json').read_text())
        self.assertEqual(sum(map(len, groups.values())), 104)
        self.assertEqual(next(iter(groups)), 'BetterPosters Discovery')
        self.assertIn(g.BASE + '/manifest.json', (self.out / 'index.html').read_text())

    def test_shahid_home_rows_are_saudi_filtered_and_clearly_labeled(self):
        from shahid_home_rows import build_shahid_home_rows
        rows = build_shahid_home_rows()
        self.assertEqual(len(rows), 6)
        self.assertEqual(len({r['id'] for r in rows}), 6)
        self.assertTrue(all(r['provider'] == 'shahid' and
                            r['mode'] == 'discover_provider' for r in rows))
        self.assertTrue(all('Shahid' in r['note'] and 'TMDB' in r['note']
                            for r in rows))
        self.assertFalse(any('official Shahid Top 10' in r['name'] for r in rows))
        ids = {r['id'] for r in rows}
        self.assertIn('shahid_home_egyptian_series', ids)
        self.assertIn('shahid_home_turkish_movies', ids)
        self.assertIn('shahid_home_syrian_classics', ids)
        originals = {(r['type'], r['id']) for r in g.ALL}
        self.assertFalse(originals & {(r['type'], r['id']) for r in rows})
        planned = g.catalog_plan()
        self.assertEqual(len(planned), 104)
        self.assertEqual(len({(r['type'], r['id']) for r in planned}), 104)
        for r in rows:
            self.assertEqual(sum(p['id'] == r['id'] for p in planned), 1)

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
        # A failed refresh must not replace the last published site with
        # a partial set of catalogs or leak credentials into logs.
        self.out.mkdir()
        marker = self.out / 'manifest.json'
        marker.write_text('last verified publication')

        def handler(spec, netflix):
            if spec == g.ALL[0]:
                return [{'id': 'tt1234567', 'type': 'movie', 'name': 'Test'}], ''
            raise HTTPError('https://api.example/?api_key=test-secret', 401,
                            'test-secret', {}, None)

        log = io.StringIO()
        with patch.object(g, 'get_netflix_rows', return_value={}), \
                patch.object(g, 'catalog', side_effect=handler), \
                contextlib.redirect_stdout(log), self.assertRaises(SystemExit) as failed:
            g.main()
        public = ''.join(p.read_text() for p in self.out.rglob('*') if p.is_file())
        self.assertNotIn('test-secret', log.getvalue() + str(failed.exception) + public)
        self.assertIn('HTTPError (HTTP 401)', str(failed.exception))
        self.assertEqual(marker.read_text(), 'last verified publication')
        self.assertEqual(g.safe_error(RuntimeError('test-secret')), 'RuntimeError')

    def test_successful_refresh_replaces_previous_site_atomically(self):
        self.out.mkdir()
        marker = self.out / 'obsolete.json'
        marker.write_text('old publication')

        def handler(spec, netflix):
            if spec['mode'] == 'external':
                return None, 'Separate addon'
            return [{'id': 'tt1234567', 'type': spec['type'], 'name': 'Test title'}], ''

        self.build(handler)
        self.assertFalse(marker.exists())
        manifest = json.loads((self.out / 'manifest.json').read_text())
        self.assertEqual(manifest['version'], g.ADDON_VERSION)
        self.assertEqual(len(manifest['catalogs']), len(g.catalog_plan()) -
                         sum(s['mode'] == 'external' for s in g.catalog_plan()))
        self.assertFalse(self.out.with_name(self.out.name + '.previous').exists())

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

    def test_shahid_uses_arabic_poster_when_tmdb_has_one(self):
        images = {'posters': [
            {'iso_639_1': 'en', 'file_path': '/english.jpg', 'vote_average': 10},
            {'iso_639_1': 'ar', 'file_path': '/arabic-low.jpg', 'vote_average': 4, 'vote_count': 1},
            {'iso_639_1': 'ar', 'file_path': '/arabic-best.jpg', 'vote_average': 8, 'vote_count': 5},
            {'iso_639_1': 'ar', 'file_path': 'https://unsafe.example/image.jpg', 'vote_average': 10},
        ]}
        with patch.object(g, 'tmdb', return_value=images) as tmdb:
            poster = g.shahid_arabic_poster('tv', {'id': 42})
        self.assertEqual(poster, 'https://image.tmdb.org/t/p/w500/arabic-best.jpg')
        tmdb.assert_called_once_with('/tv/42/images',
                                     {'language': 'ar', 'include_image_language': 'en,null'})

    def test_shahid_arabic_poster_missing_or_error_keeps_existing_poster(self):
        with patch.object(g, 'tmdb', return_value={'posters': [
                {'iso_639_1': 'en', 'file_path': '/english.jpg'}]}):
            self.assertIsNone(g.shahid_arabic_poster('movie', {'id': 55}))
        with patch.object(g, 'tmdb', side_effect=HTTPError('https://example.org', 429, 'limit', {}, None)):
            self.assertIsNone(g.shahid_arabic_poster('tv', {'id': 55}))

    def test_shahid_catalog_prefers_arabic_poster_without_changing_count(self):
        spec = next(x for x in g.ALL if x['id'] == 'shahid_top_arabic_series')
        items = [{'id': n} for n in range(1, 21)]
        def preview(kind, item, **kwargs):
            return {'id': 'tt' + str(item['id']).zfill(7), 'type': 'series',
                    'name': 'Show', 'poster': 'https://image.tmdb.org/t/p/w500/default.jpg'}
        with patch.object(g, 'shahid_provider_id', return_value=777), \
                patch.object(g, 'fetch_discover', return_value=('tv', items)), \
                patch.object(g, 'preview', side_effect=preview), \
                patch.object(g, 'shahid_arabic_poster',
                             side_effect=lambda kind, item:
                             'https://image.tmdb.org/t/p/w500/ar.jpg' if item['id'] == 1 else None):
            posters, reason = g.catalog(spec)
        self.assertEqual(len(posters), g.LIMIT)
        self.assertEqual(reason, '')
        self.assertEqual(posters[0]['poster'], 'https://image.tmdb.org/t/p/w500/ar.jpg')
        self.assertEqual(posters[1]['poster'], 'https://image.tmdb.org/t/p/w500/default.jpg')

    def test_shahid_classics_keep_historical_cutoff(self):
        from shahid_home_rows import build_shahid_home_rows
        spec = next(r for r in build_shahid_home_rows()
                    if r['id'] == 'shahid_home_syrian_classics')
        candidates = [{'id': n} for n in range(1, 7)]
        with patch.object(g, 'shahid_provider_id', return_value=777), \
                patch.object(g, 'fetch_discover', return_value=('tv', candidates)) as fetch, \
                patch.object(g, 'preview', side_effect=lambda kind, item, **kwargs:
                             {'id': 'tt' + str(item['id']).zfill(7), 'name': 'Show',
                              'type': 'series', 'poster': '/img.jpg'}), \
                patch.object(g, 'shahid_arabic_poster', return_value=None):
            rows, reason = g.catalog(spec)
        self.assertEqual(len(rows), 6)
        self.assertEqual(reason, '')
        params = fetch.call_args.args[0]['params']
        self.assertEqual(params['first_air_date.lte'], '2016-12-31')
        self.assertEqual(params['watch_region'], 'SA')

    def test_missing_title_external_ids_are_skipped_but_api_failures_propagate(self):
        with patch.object(g, 'tmdb', side_effect=HTTPError(
                'https://api.themoviedb.org/3/tv/123/external_ids', 404,
                'not found', {}, None)):
            self.assertIsNone(g.external_id('tv', 123))
            self.assertIsNone(g.preview('tv', {'id': 123, 'name': 'Orphaned item'}))
        with patch.object(g, 'tmdb', side_effect=HTTPError(
                'https://api.themoviedb.org/3/tv/123/external_ids', 401,
                'unauthorized', {}, None)):
            with self.assertRaises(HTTPError):
                g.external_id('tv', 123)

    def test_shahid_provider_is_discovered_not_guessed(self):
        with patch.object(g, 'tmdb', return_value={'results': [
                {'provider_name': 'Other', 'provider_id': 123},
                {'provider_name': 'Shahid VIP', 'provider_id': 777}
        ]}) as tmdb:
            self.assertEqual(g.shahid_provider_id('movie'), 777)
            tmdb.assert_called_once_with('/watch/providers/movie')

        with patch.object(g, 'tmdb', return_value={'results': [
                {'provider_name': 'Different Service', 'provider_id': 7}
        ]}):
            self.assertIsNone(g.shahid_provider_id('tv'))

    def test_shahid_discovery_returns_multiple_posters_from_saudi_provider(self):
        spec = next(x for x in g.ALL if x['id'] == 'shahid_top_arabic_series')
        self.assertEqual(spec['mode'], 'discover_provider')
        items = [{'id': x, 'poster_path': '/poster.jpg'} for x in range(1, 21)]

        def poster(kind, item, **kwargs):
            return {'id': 'tt' + str(item['id']).zfill(7), 'type': 'series',
                    'name': f"Series {item['id']}", 'poster': 'https://image.tmdb.org/poster.jpg'}

        with patch.object(g, 'shahid_provider_id', return_value=777), \
                patch.object(g, 'fetch_discover', return_value=('tv', items)) as discover, \
                patch.object(g, 'preview', side_effect=poster), \
                patch.object(g, 'shahid_arabic_poster', return_value=None):
            rows, reason = g.catalog(spec)
        self.assertEqual(len(rows), min(g.LIMIT, 20))
        self.assertEqual(reason, '')
        request = discover.call_args.args[0]
        self.assertEqual(request['params']['watch_region'], 'SA')
        self.assertEqual(request['params']['with_watch_providers'], '777')
        self.assertEqual(request['params']['with_watch_monetization_types'],
                         'flatrate|free|ads')
        self.assertEqual(request['params']['first_air_date.lte'], str(g.TODAY))
        self.assertEqual(request['params']['sort_by'], 'popularity.desc')
        self.assertFalse(any('subtitle' in key for key in request['params']))

    def test_shahid_unavailable_or_sparse_catalog_is_held(self):
        spec = next(x for x in g.ALL if x['id'] == 'shahid_top_arabic_movies')
        with patch.object(g, 'shahid_provider_id', return_value=None):
            rows, reason = g.catalog(spec)
        self.assertEqual(rows, [])
        self.assertIn('not listed', reason)

        with patch.object(g, 'shahid_provider_id', return_value=777), \
                patch.object(g, 'fetch_discover', return_value=('movie', [{'id': 1}])), \
                patch.object(g, 'preview', return_value={
                    'id': 'tt1234567', 'type': 'movie', 'name': 'Test'}), \
                patch.object(g, 'shahid_arabic_poster', return_value=None):
            rows, reason = g.catalog(spec)
        self.assertEqual(rows, [])
        self.assertIn('Fewer than five', reason)

    def test_single_poster_curated_shahid_row_is_not_published(self):
        spec = next(x for x in g.ALL if x['id'] == 'shahid_saudi_originals')
        with patch.object(g, 'fetch_verified', return_value=[
                {'id': 'tt1234567', 'type': 'series', 'name': 'One title'}]):
            rows, reason = g.catalog(spec)
        self.assertEqual(rows, [])
        self.assertIn('five verified titles', reason)

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

    def test_live_verifier_rejects_previous_deployment_version(self):
        with patch.object(verify_site, 'read_json', return_value={
                'id': 'com.mynuvio.buildn1', 'version': '1.1.0', 'resources': ['catalog']}):
            with self.assertRaisesRegex(ValueError, 'updated addon version'):
                verify_site.verify('https://example.org/addon', g.ADDON_VERSION)

    def test_blank_saudi_certification_falls_back_to_us(self):
        movie = {'results': [
            {'iso_3166_1': 'SA', 'release_dates': [{'certification': ' '}]},
            {'iso_3166_1': 'US', 'release_dates': [{'certification': 'G'}]}
        ]}
        with patch.object(g, 'tmdb', return_value=movie):
            self.assertTrue(g.rating_eligible('movie', {'id': 1}, ['G']))
        movie['results'][0]['release_dates'][0]['certification'] = 'R'
        with patch.object(g, 'tmdb', return_value=movie):
            self.assertFalse(g.rating_eligible('movie', {'id': 1}, ['G']))
        tv = {'results': [{'iso_3166_1': 'SA', 'rating': ''},
                          {'iso_3166_1': 'US', 'rating': 'TV-Y'}]}
        with patch.object(g, 'tmdb', return_value=tv):
            self.assertTrue(g.rating_eligible('tv', {'id': 1}, ['TV-Y']))

    def test_discover_can_search_past_small_candidate_pool(self):
        def source(path, params):
            return {'results': [{'id': params['page'] * 100 + i, 'poster_path': '/p.jpg'}
                                for i in range(20)]}
        with patch.object(g, 'tmdb', side_effect=source) as tmdb:
            _, rows = g.fetch_discover({'type': 'movie'}, max_pages=8, pool_size=100)
            self.assertEqual(len(rows), 100)
            self.assertEqual(tmdb.call_count, 5)

    def test_returning_season_searches_announcements_beyond_this_week(self):
        spec = next(s for s in g.ALL if s['id'] == 'returning_seasons')
        episode = {'air_date': str(g.TODAY + g.timedelta(days=30)),
                   'episode_number': 1, 'season_number': 2}
        with patch.object(g, 'fetch_discover', return_value=('tv', [{'id': 1}])) as discover, \
                patch.object(g, 'details', return_value={'next_episode_to_air': episode}), \
                patch.object(g, 'preview', return_value={'id': 'tt1234567'}):
            self.assertEqual(len(g.fetch_episodes(spec, 'returning')), 1)
            self.assertEqual(discover.call_args.args[0]['params']['air_date.lte'],
                             str(g.TODAY + g.timedelta(days=60)))
            episode['episode_number'] = 2
            self.assertEqual(g.fetch_episodes(spec, 'returning'), [])

    def test_seeded_sources_unlock_remaining_curated_rows(self):
        ids = ['golden_bafta', 'shahid_saudi_originals',
               'shahid_gulf', 'netflix_turkish_movies', 'netflix_turkish_series',
               'turkish_streaming_originals']
        with patch.object(g, 'TODAY', g.date(2026, 11, 15)), \
                patch.object(g, 'enrich_from_imdb', side_effect=lambda imdb, kind: {
                    'id': imdb, 'type': kind, 'name': 'Source-mapped title'}):
            for catalog_id in ids:
                spec = next(s for s in g.ALL if s['id'] == catalog_id)
                self.assertTrue(g.fetch_verified(spec), catalog_id)

    def test_subtitle_evidence_expires_and_requires_saudi_provider(self):
        spec = next(s for s in g.ALL if s['id'] == 'netflix_turkish_movies')
        entry = dict(next(e for e in g.VERIFIED if spec['tag'] in e['tags']))
        with patch.object(g, 'VERIFIED', [entry]), \
                patch.object(g, 'enrich_from_imdb', return_value={'id': entry['imdb_id']}):
            for age in (-1, 91):
                with patch.object(g, 'TODAY', g.date.fromisoformat(entry['verified_on']) + g.timedelta(days=age)):
                    self.assertEqual(g.fetch_verified(spec), [])
            with patch.object(g, 'TODAY', g.date.fromisoformat(entry['verified_on'])):
                self.assertTrue(g.fetch_verified(spec))
                entry['region'] = 'US'
                self.assertEqual(g.fetch_verified(spec), [])


if __name__ == '__main__':
    unittest.main()
