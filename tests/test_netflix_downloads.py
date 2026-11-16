import contextlib
import csv
import io
import json
import tempfile
import unittest
from http.client import IncompleteRead
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import generate as g
from netflix_sources import NetflixTitle, parse_saudi_chart


FIELDS = ['country_iso2', 'week', 'category', 'weekly_rank', 'show_title']
WEEK = '2026-11-08'


def chart_rows(week=WEEK, country='SA'):
    return [dict(zip(FIELDS, [country, week, category, str(rank), f'{prefix} {rank}']))
            for category, prefix in [('Films', 'Movie'), ('TV', 'Show')]
            for rank in range(1, 11)]


def chart_bytes(rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, FIELDS, delimiter='\t')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8-sig')


def search_result(path, params):
    title = params['query']
    rank = int(title.split()[-1])
    movie = path == '/search/movie'
    return {'results': [{'id': rank if movie else rank + 100,
                         'title' if movie else 'name': title}]}


class DownloadTests(unittest.TestCase):
    def test_incomplete_body_restarts_request_and_discards_partial_bytes(self):
        broken = SimpleNamespace(read=Mock(side_effect=IncompleteRead(b'partial-body', 9)))
        complete = SimpleNamespace(read=Mock(return_value=b'complete-response'))
        with patch.object(g, 'urlopen', side_effect=[contextlib.nullcontext(broken),
                                                    contextlib.nullcontext(complete)]) as opened, \
                patch.object(g.time, 'sleep') as sleep:
            result = g.fetch('https://example.test/chart.tsv', retries=3, timeout=120)
        self.assertEqual(result, b'complete-response')
        self.assertEqual(opened.call_count, 2)
        self.assertEqual([c.kwargs['timeout'] for c in opened.call_args_list], [120, 120])
        broken.read.assert_called_once_with()
        complete.read.assert_called_once_with()
        sleep.assert_called_once_with(1)

    def test_incomplete_body_raises_after_retry_limit_without_returning_partial_data(self):
        def open_broken(*args, **kwargs):
            return contextlib.nullcontext(SimpleNamespace(
                read=Mock(side_effect=IncompleteRead(b'truncated', 100))))
        with patch.object(g, 'urlopen', side_effect=open_broken) as opened, \
                patch.object(g.time, 'sleep') as sleep:
            with self.assertRaises(IncompleteRead):
                g.fetch('https://example.test/chart.tsv', retries=3)
        self.assertEqual(opened.call_count, 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2])


class NetflixChartTests(unittest.TestCase):
    def mapped_chart(self, rows, search=search_result):
        with patch.object(g, 'fetch', return_value=chart_bytes(rows)) as fetch, \
                patch.object(g, 'netflix_chart_identities', return_value={}), \
                patch.object(g, 'tmdb', side_effect=search), \
                patch.object(g, 'external_id', side_effect=lambda kind, mid: f'tt{mid:07d}'):
            result = g.get_netflix_rows()
        return result, fetch

    def test_complete_latest_country_charts_preserve_source_rank_and_week(self):
        rows = chart_rows('2026-11-01') + chart_rows() + chart_rows(country='US')
        charts, fetch = self.mapped_chart(rows)
        self.assertEqual(set(charts), {'movie', 'series'})
        for kind, prefix in [('movie', 'Movie'), ('series', 'Show')]:
            self.assertEqual(len(charts[kind]), 10)
            for rank, item in enumerate(charts[kind], 1):
                self.assertEqual(item['name'], f'{prefix} {rank}')
                self.assertEqual(item['type'], kind)
                self.assertIn(f'Original chart position #{rank}', item['description'])
                self.assertIn(f'Chart week ending {WEEK}', item['description'])
        self.assertEqual(fetch.call_args.kwargs, {'retries': 5, 'timeout': 120})

    def test_season_suffix_is_matched_to_parent_series_without_renumbering(self):
        rows = chart_rows()
        for row in rows:
            if row['category'] == 'TV' and row['weekly_rank'] == '3':
                row['show_title'] = 'Show 3: Season 2'
        def search(path, params):
            if params['query'] == 'Show 3: Season 2':
                return {'results': []}
            return search_result(path, params)
        charts, _ = self.mapped_chart(rows, search)
        self.assertEqual(len(charts['series']), 10)
        self.assertEqual(charts['series'][2]['name'], 'Show 3')
        self.assertIn('Original chart position #3', charts['series'][2]['description'])
        self.assertIn('Netflix chart: Show 3: Season 2',
                      charts['series'][2]['description'])

    def test_sequel_movie_names_are_not_stripped(self):
        self.assertEqual(g.netflix_chart_search_queries('movie', 'Film: Part 2'),
                         ['Film: Part 2'])
        self.assertEqual(g.netflix_chart_search_queries('series',
                                                       'Mystery Show: Limited Series'),
                         ['Mystery Show: Limited Series', 'Mystery Show'])
        self.assertEqual(g.netflix_chart_search_queries('series', 'Show: Season 5'),
                         ['Show: Season 5', 'Show'])

    def test_original_title_fallback_and_ambiguous_match_rejection(self):
        candidate = {'id': 777, 'name': 'Localized Name', 'original_name': 'Drama'}
        with patch.object(g, 'tmdb', return_value={'results': [candidate]}):
            match = g.match_netflix_chart_title('series', 'Drama')
            self.assertEqual(match['id'], 777)
        with patch.object(g, 'tmdb', return_value={'results': [
                {'id': 1, 'name': 'Drama'}, {'id': 2, 'name': 'Drama'}]}):
            self.assertIsNone(g.match_netflix_chart_title('series', 'Drama'))

    def test_missing_schema_is_rejected(self):
        with patch.object(g, 'fetch', return_value=b'week\tshow_title\n2026-11-08\tMovie\n'), \
                patch.object(g, 'tmdb') as tmdb:
            with self.assertRaisesRegex(ValueError, 'required columns'):
                g.get_netflix_rows()
        tmdb.assert_not_called()

    def test_truncated_duplicate_or_blank_country_chart_is_rejected(self):
        valid = chart_rows()
        variants = {
            'missing rank': [r for r in valid if not (r['category'] == 'Films' and r['weekly_rank'] == '5')],
            'duplicate rank': [{**r, 'weekly_rank': '9'} if r['weekly_rank'] == '10' else r for r in valid],
            'blank title': [{**r, 'show_title': ' '} if r['weekly_rank'] == '1' else r for r in valid],
        }
        for label, rows in variants.items():
            with self.subTest(label=label), patch.object(g, 'fetch', return_value=chart_bytes(rows)), \
                    patch.object(g, 'tmdb') as tmdb:
                with self.assertRaisesRegex(ValueError, 'incomplete'):
                    g.get_netflix_rows()
                tmdb.assert_not_called()

    def test_missing_saudi_country_is_rejected(self):
        with patch.object(g, 'fetch', return_value=chart_bytes(chart_rows(country='US'))), \
                patch.object(g, 'tmdb') as tmdb:
            with self.assertRaisesRegex(ValueError, 'no Saudi rows'):
                g.get_netflix_rows()
        tmdb.assert_not_called()

    def test_ambiguous_title_is_skipped_without_renumbering_other_source_positions(self):
        def search(path, params):
            data = search_result(path, params)
            if path == '/search/movie' and params['query'] == 'Movie 1':
                data['results'].append({**data['results'][0], 'id': 999})
            return data
        charts, _ = self.mapped_chart(chart_rows(), search)
        self.assertEqual(len(charts['movie']), 9)
        self.assertEqual(charts['movie'][0]['name'], 'Movie 2')
        self.assertIn('Original chart position #2', charts['movie'][0]['description'])
        self.assertIn('Original chart position #10', charts['movie'][-1]['description'])
        self.assertEqual(len(charts['series']), 10)

    def test_tudum_identities_are_bound_to_the_saudi_week_and_rank(self):
        data = {
            '__typename': 'PulseTop10ItemEntity',
            'top10': {'category': 'MOVIES', 'weekEndDate': WEEK, 'weeklyRank': 2},
            'countryRanks': [{'countryId': 'SA', 'rank': 2}],
            'top10Video': {'title': 'Heist', 'releaseYear': 2001, 'videoId': 60020557},
        }
        html = 'netflix.reactContext.models.graphql = JSON.parse(' + repr(json.dumps({
            'data': {
                'sa': data,
                'us': {**data, 'top10': {**data['top10'], 'weeklyRank': 4}},
            },
        })) + ')'
        self.assertEqual(parse_saudi_chart(html, 'movie', WEEK), {
            2: ('Heist', NetflixTitle('Heist', 60020557, 2001)),
        })
        self.assertEqual(parse_saudi_chart(html, 'movie', '2026-11-01'), {})

    def test_verified_netflix_id_supplies_imdb_even_when_tmdb_has_no_record(self):
        title = NetflixTitle('Heist', 60020557, 2001, 'https://dnm.nflximg.net/api/v6/art.jpg')
        with patch.object(g, 'enrich_from_imdb', return_value=None):
            result = g.resolve_netflix_title('movie', title, source_rank=2, source_week=WEEK)
            self.assertEqual(g.resolve_netflix_title('series', title), None)
        self.assertEqual(result['id'], 'tt0252503')
        self.assertEqual(result['releaseInfo'], '2001')
        self.assertEqual(result['poster'], title.poster)
        self.assertIn('Original chart position #2', result['description'])

    def test_disambiguation_uses_release_year_and_preserves_arabic_characters(self):
        data = {'results': [{'id': 1, 'title': 'Heist', 'release_date': '2001-11-09'},
                            {'id': 2, 'title': 'Heist', 'release_date': '2015-11-13'}]}
        with patch.object(g, 'tmdb', return_value=data) as tmdb:
            self.assertEqual(g.match_netflix_chart_title('movie', 'Heist', year=2001)['id'], 1)
            tmdb.assert_called_once_with('/search/movie', {'query': 'Heist', 'primary_release_year': '2001'})
        with patch.object(g, 'tmdb', return_value={'results': [
                {'id': 3, 'title': 'العنكبوت'}, {'id': 4, 'title': 'الرهينة'}]}):
            self.assertEqual(g.match_netflix_chart_title('movie', 'العنكبوت')['id'], 3)

    def test_season_duplicates_use_the_highest_rank_and_include_the_other_position(self):
        rows = chart_rows()
        for row in rows:
            if row['category'] == 'TV' and row['weekly_rank'] == '8':
                row['show_title'] = 'Show 3'
        charts, _ = self.mapped_chart(rows)
        self.assertEqual(len(charts['series']), 9)
        third = charts['series'][2]
        self.assertIn('Original chart position #3', third['description'])
        self.assertIn('Also ranked #8', third['description'])

    def test_all_unmapped_titles_prevent_publication_instead_of_silently_dropping_chart(self):
        with patch.object(g, 'fetch', return_value=chart_bytes(chart_rows())), \
                patch.object(g, 'netflix_chart_identities', return_value={}), \
                patch.object(g, 'tmdb', return_value={'results': []}):
            with self.assertRaisesRegex(ValueError, 'no reliable IMDb matches'):
                g.get_netflix_rows()

    def test_netflix_failure_preserves_previous_manifest_and_never_leaks_exception_details(self):
        secret = 'example-private-key'
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'site'
            out.mkdir()
            manifest = out / 'manifest.json'
            manifest.write_text('previous manifest')
            log = io.StringIO()
            error = IncompleteRead(secret.encode(), 10)
            with patch.object(g, 'OUT', out), patch.object(g, 'BASE', 'https://example.test/addon'), \
                    patch.object(g, 'API_KEY', secret), patch.object(g, 'TOKEN', ''), \
                    patch.object(g, 'get_netflix_rows', side_effect=error), \
                    patch.object(g, 'catalog') as catalog, contextlib.redirect_stdout(log), \
                    contextlib.redirect_stderr(log):
                with self.assertRaises(SystemExit) as raised:
                    g.main()
            self.assertEqual(manifest.read_text(), 'previous manifest')
            catalog.assert_not_called()
            self.assertIn('IncompleteRead', str(raised.exception))
            self.assertIn('preserve the previous website', str(raised.exception))
            self.assertNotIn(secret, log.getvalue() + str(raised.exception))


if __name__ == '__main__':
    unittest.main()
