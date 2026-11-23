import contextlib
import copy
import gzip
import io
import json
import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path
from unittest.mock import patch

import generate as g
from browse_catalogs import BROWSE_PAGE_SIZE, build_browse_catalogs


class BrowseCatalogTests(unittest.TestCase):
    def setUp(self):
        self.labels = json.loads((g.ROOT / 'browsing-folders.json').read_text())
        self.today = date(2026, 11, 15)
        self.rows = build_browse_catalogs(self.labels, self.today)

    def test_each_saved_label_has_unique_movie_and_series_routes(self):
        self.assertEqual(len(self.labels['Genres']), 12)
        self.assertEqual(len(self.labels['Moods']), 8)
        self.assertEqual(len(self.rows), 40)
        self.assertEqual(len({(row['type'], row['id']) for row in self.rows}), 40)
        self.assertEqual(len({row['id'] for row in self.rows}), 40)
        actual = Counter((row['group'], row['browse_label'], row['type']) for row in self.rows)
        expected = Counter((group, label, kind)
                           for group in ('Genres', 'Moods')
                           for label in self.labels[group]
                           for kind in ('movie', 'series'))
        self.assertEqual(actual, expected)

    def test_plan_adds_browsing_without_altering_the_58_original_definitions(self):
        frozen = copy.deepcopy(g.ALL)
        saved = json.loads((g.ROOT / 'catalogs.json').read_text())
        self.assertEqual(len(frozen), 58)
        self.assertEqual(frozen, saved)
        planned = g.catalog_plan()
        original_by_route = {(row['type'], row['id']): row for row in frozen}
        retained = [row for row in planned if (row['type'], row['id']) in original_by_route]
        self.assertEqual(len(retained), 58)
        self.assertEqual({(row['type'], row['id']): row for row in retained}, original_by_route)
        self.assertEqual(g.ALL, frozen)
        self.assertEqual(len(planned), 135)
        self.assertEqual(len({(row['type'], row['id']) for row in planned}), 135)
        self.assertEqual([row['group'] for row in planned[:10]], ['BetterPosters Discovery'] * 10)
        # The saved N1 order is retained after moving only BetterPosters first.
        self.assertEqual([row for row in retained if row['group'] != 'BetterPosters Discovery'],
                         [row for row in frozen if row['group'] != 'BetterPosters Discovery'])

    def test_tv_filters_do_not_reuse_movie_only_genre_ids(self):
        official_tv_genres = {'10759', '16', '35', '80', '99', '18', '10751',
                              '10762', '9648', '10763', '10764', '10765', '10766',
                              '10767', '10768', '37'}
        for row in self.rows:
            if row['type'] != 'series':
                continue
            for key in ('with_genres', 'without_genres'):
                values = row['params'].get(key, '').replace('|', ',').split(',')
                self.assertTrue(set(filter(None, values)) <= official_tv_genres, row['id'])
        genre_rows = {(row['browse_label'], row['type']): row
                      for row in self.rows if row['group'] == 'Genres'}
        for label, movie_id, tv_id in [('Action', '28', '10759'),
                                       ('Adventure', '12', '10759'),
                                       ('Sci-Fi', '878', '10765'),
                                       ('Fantasy', '14', '10765')]:
            self.assertEqual(genre_rows[label, 'movie']['params']['with_genres'], movie_id)
            self.assertEqual(genre_rows[label, 'series']['params']['with_genres'], tv_id)

    def test_missing_and_combined_tv_genres_are_narrowed_by_keywords(self):
        tv = {row['browse_label']: row for row in self.rows
              if row['group'] == 'Genres' and row['type'] == 'series'}
        missing = {'Romance', 'Horror', 'Thriller', 'Music'}
        combined = {'Action', 'Adventure', 'Sci-Fi', 'Fantasy'}
        for label in missing | combined:
            self.assertEqual(tv[label]['mode'], 'discover_keyword', label)
            self.assertTrue(tv[label]['keyword'].strip(), label)
        for label in missing:
            self.assertNotIn('with_genres', tv[label]['params'], label)

    def test_browse_filters_exclude_future_titles_and_label_editorial_moods(self):
        for row in self.rows:
            params = row['params']
            self.assertEqual(params['include_adult'], 'false')
            key = 'primary_release_date.lte' if row['type'] == 'movie' else 'first_air_date.lte'
            self.assertEqual(params[key], str(self.today))
            if row['group'] == 'Moods':
                self.assertIn('Editorial', row['note'])
                self.assertIn('TMDB', row['note'])
                self.assertIn('subjective', row['note'])
                self.assertIn('not age ratings', row['note'])

    def test_generated_grouping_puts_betterposters_first_and_includes_browse_routes(self):
        def fake_catalog(spec, netflix):
            if spec['mode'] == 'external':
                return None, 'Separate addon'
            return [{'id': 'tt1234567', 'type': spec['type'], 'name': 'Test title'}], ''

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'site'
            with patch.object(g, 'OUT', output), patch.object(g, 'BASE', 'https://example.org/n1'), \
                    patch.object(g, 'API_KEY', 'offline-test-key'), patch.object(g, 'TOKEN', ''), \
                    patch.object(g, 'get_netflix_rows', return_value={}), \
                    patch.object(g, 'catalog', side_effect=fake_catalog), \
                    contextlib.redirect_stdout(io.StringIO()):
                g.main()
            grouping = json.loads((output / 'grouping-plan.json').read_text())
            self.assertEqual(next(iter(grouping)), 'BetterPosters Discovery')
            self.assertEqual(len(grouping['BetterPosters Discovery']), 10)
            self.assertEqual(len(grouping['Genres']), 24)
            self.assertEqual(len(grouping['Moods']), 16)
            status = json.loads((output / 'status.json').read_text())
            self.assertEqual(status['original_planned'], 58)
            self.assertEqual(status['browse_planned'], 40)
            self.assertEqual(status['shahid_home_planned'], 7)
            self.assertEqual(status['netflix_home_planned'], 6)
            self.assertEqual(status['netflix_release_planned'], 2)
            self.assertEqual(status['netflix_public_planned'], 13)
            self.assertEqual(status['planned'], 135)
            manifest = json.loads((output / 'manifest.json').read_text())
            published = {(row['type'], row['id']) for row in manifest['catalogs']}
            for row in self.rows:
                self.assertIn((row['type'], row['id']), published)
                endpoint = output / 'catalog' / row['type'] / (row['id'] + '.json')
                self.assertEqual(json.loads(endpoint.read_text())['metas'][0]['type'], row['type'])

    def test_discovery_stops_at_15_valid_imdb_mappings_after_skipping_unmapped(self):
        candidates = [{'id': number} for number in range(1, 41)]

        def fake_preview(kind, item, **kwargs):
            if item['id'] <= 3:
                return None
            return {'id': 'tt' + str(item['id']).zfill(7), 'type': 'movie'}

        for mode, source in [('discover', 'fetch_discover'),
                             ('discover_keyword', 'fetch_keyword')]:
            spec = {'id': 'browse_test', 'type': 'movie', 'mode': mode,
                    'note': 'Editorial source note'}
            with self.subTest(mode=mode), patch.object(g, 'LIMIT', 15), \
                    patch.object(g, source, return_value=('movie', candidates)), \
                    patch.object(g, 'preview', side_effect=fake_preview) as preview:
                rows, reason = g.catalog(spec)
            self.assertEqual(len(rows), 15)
            self.assertEqual(preview.call_count, 18)
            self.assertEqual(rows[0]['id'], 'tt0000004')
            self.assertEqual(rows[-1]['id'], 'tt0000018')
            self.assertEqual(preview.call_args.kwargs['verified_note'], spec['note'])
            self.assertEqual(reason, '')

    def test_discovery_with_no_imdb_mappings_remains_held(self):
        spec = {'id': 'browse_test', 'type': 'series', 'mode': 'discover'}
        with patch.object(g, 'fetch_discover', return_value=('tv', [{'id': 1}, {'id': 2}])), \
                patch.object(g, 'preview', return_value=None):
            rows, reason = g.catalog(spec)
        self.assertEqual(rows, [])
        self.assertIn('No reliable IMDb', reason)

    def test_paginated_mood_keeps_source_order_and_resolves_missing_ids(self):
        spec = next(row for row in self.rows if row['id'] == 'browse_mood_mind_bending_series')
        source = [
            {'id': i, 'name': f'Title {i}', 'poster_path': f'/{i}.jpg'}
            for i in range(1, 249)
        ]
        source.insert(22, source[0])
        source[23].pop('poster_path')
        ids = {('tv', i): f'tt{i:07d}' for i in range(1, 249)}
        ids['tv', 24] = ids['tv', 1]
        del ids['tv', 248]

        def tmdb(path, params, *, cache=True):
            if path == '/search/keyword':
                return {'results': [{'id': 99, 'name': 'time travel'}]}
            self.assertEqual(path, '/discover/tv')
            self.assertFalse(cache)
            self.assertEqual(params['with_keywords'], '99')
            self.assertEqual({k: params[k] for k in spec['params']}, spec['params'])
            start = (params['page'] - 1) * 20
            return {'results': source[start:start + 20], 'total_pages': 13}

        with patch.object(g, 'tmdb', side_effect=tmdb), \
                patch.object(g, 'browse_imdb_ids', return_value=ids), \
                patch.object(g, 'external_id', return_value='tt0000248') as external:
            rows, reason = g.catalog(spec)
        external.assert_called_once_with('tv', 248)
        self.assertEqual(reason, '')
        self.assertEqual([row['id'] for row in rows],
                         [f'tt{i:07d}' for i in range(1, 249) if i not in {23, 24}])

    def test_action_trailers_match_the_movie_on_catalog_and_detail_pages(self):
        key = 'abcdefghij1'
        item = {'type': 'movie', 'id': 'tt1234567', 'name': 'Movie', '_tmdb_id': 45}
        record = {'external_ids': {'imdb_id': item['id']}, 'videos': {'results': [
            {'site': 'YouTube', 'type': 'Trailer', 'official': False, 'key': '0123456789A'},
            {'site': 'YouTube', 'type': 'Trailer', 'official': True, 'key': key}]}}
        with patch.object(g, 'tmdb', return_value=record) as tmdb:
            detail = g.action_movie_details(item)
            tmdb.assert_called_once()
            self.assertEqual(item['trailers'], [{'type': 'Trailer', 'source': key}])
            self.assertEqual(item['trailerStreams'], detail['trailerStreams'])
            self.assertEqual(detail['trailerStreams'][0]['ytId'], key)
            other = dict(type='movie', id='tt0000001', _tmdb_id=45)
            self.assertIsNone(g.action_movie_details(other))
            self.assertNotIn('trailers', other)

    def test_browse_publisher_matches_clients_actual_skip_offsets(self):
        spec = self.rows[0]
        rows = [{'id': f'tt{i:07d}', 'type': spec['type'], 'name': f'Title {i}'}
                for i in range(247)]
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            entry = g.publish_catalog(stage, spec, rows)
            self.assertIn({'name': 'skip', 'isRequired': False}, entry['extra'])
            route = stage / 'catalog' / spec['type'] / spec['id']
            first = json.loads(route.with_suffix('.json').read_text())['metas']
            self.assertEqual(len(first), BROWSE_PAGE_SIZE)
            loaded = first.copy()
            while len(loaded) < len(rows):
                current = json.loads((route / f'skip={len(loaded)}.json').read_text())['metas']
                self.assertTrue(current)
                loaded.extend(current)
            self.assertEqual(loaded, rows)
            for end in (247, 300):
                self.assertEqual(json.loads((route / f'skip={end}.json').read_text()), {'metas': []})

    def test_browse_imdb_map_uses_media_type_and_ignores_conflicts(self):
        data = gzip.compress(b'TMDB ID,TMDB Type,IMDB ID\n'
                             b'99,tv,tt1234567\n99,movie,tt7654321\n'
                             b'92,tv,tt3131313\n92,tv,tt5555555\n10,tv,\n')
        load_map = g.browse_imdb_ids.__wrapped__
        with patch.object(g, 'fetch', return_value=data):
            self.assertEqual(load_map(), {('tv', 99): 'tt1234567', ('movie', 99): 'tt7654321',
                                          ('tv', 92): None})


if __name__ == '__main__':
    unittest.main()
