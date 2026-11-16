import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import generate as g
from netflix_everything import (rank_label, safe_tmdb_image_url,
                                score_label, style_netflix_catalog)
from netflix_home_rows import build_netflix_release_rows
from netflix_public_rows import build_public_netflix_rows
from netflix_sources import NetflixTitle, parse_saudi_genre_rows


class NetflixEverythingTests(unittest.TestCase):
    def test_real_public_page_rows_have_documented_sources_and_distinct_ids(self):
        rows = build_public_netflix_rows()
        self.assertEqual(len(rows), 13)
        self.assertEqual(len({r["id"] for r in rows}), 13)
        self.assertTrue(all(r["mode"] == "netflix_public" for r in rows))
        self.assertTrue(all(r["group"] == "Netflix Saudi" for r in rows))
        self.assertTrue(all(r["snapshot_date"] == "2026-11-16" for r in rows))
        self.assertTrue(all(r["source_url"].startswith("https://www.netflix.com/sa-en/")
                            for r in rows))
        self.assertTrue(all(len(r["titles"]) >= 10 for r in rows if r['minimum_items'] == 5))
        self.assertTrue(all(not r['titles'] for r in rows if r['source_row'] == 'New on Netflix'))

    def test_public_page_resolution_keeps_source_order_and_skips_ambiguity(self):
        spec = build_public_netflix_rows()[0]
        ids = {title: number for number, title in enumerate(spec["titles"], start=1)}
        def find(kind, title, **kw):
            if title == spec["titles"][2]:
                return None
            return {"id": ids[title], "name": title, "vote_average": 7.1}
        def preview(kind, item, **kw):
            return {"id": "tt" + str(item["id"]).zfill(7), "type": "series",
                    "name": item["name"], "description": kw["verified_note"]}
        with patch.object(g, "netflix_genre_rows", return_value={}), \
                patch.object(g, "match_netflix_chart_title", side_effect=find), \
                patch.object(g, "preview", side_effect=preview):
            items, note = g.fetch_public_netflix(spec)
        self.assertEqual(note, "")
        self.assertEqual(items[0]["name"], spec["titles"][0])
        self.assertNotIn(spec["titles"][2], [p["name"] for p in items])
        self.assertIn(spec["source_url"], items[0]["description"])
        self.assertNotIn("Original chart position #", items[0]["description"])
        self.assertLessEqual(len(items), g.NETFLIX_LIMIT)

    def test_no_fabricated_public_titles_when_tmdb_cannot_match(self):
        spec = build_public_netflix_rows()[1]
        with patch.object(g, "netflix_genre_rows", return_value={}), \
                patch.object(g, "match_netflix_chart_title", return_value=None):
            items, reason = g.fetch_public_netflix(spec)
        self.assertEqual(items, [])
        self.assertIn("Fewer than 5", reason)

    def test_public_page_extracts_only_saudi_titles_in_page_order(self):
        title = 'https://occ-0-4249-2164.1.nflxso.net/dnm/api/v6/example.jpg?r=079'
        page = f'''<div data-uia="locp-collections-title-row"><h2>Kids &amp; Family</h2>
          <li><a href="https://www.netflix.com/sa-en/title/123" aria-label="Go to First">
              <span style="background-image:url({title})"></span></a></li>
          <li><a href="/us-en/title/456" aria-label="Go to Other country">Other country</a></li>
          <li><a href="/sa-en/title/789" aria-label="Go to Second">Second</a></li></div>'''
        rows = parse_saudi_genre_rows(page)
        self.assertEqual(rows['Kids & Family'], [NetflixTitle('First', 123, poster=title),
                                                 NetflixTitle('Second', 789)])

    def test_new_on_netflix_only_uses_first_party_matching_media_types(self):
        spec = next(row for row in build_public_netflix_rows()
                    if row['id'] == 'netflix_sa_public_arab_new_movies')
        rows = [NetflixTitle('Newest TV', 10, kind='series'),
                NetflixTitle('Unknown media type', 11),
                NetflixTitle('Newest Movie', 12, kind='movie')]
        with patch.object(g, 'netflix_genre_rows', return_value={'New on Netflix': rows}), \
                patch.object(g, 'resolve_netflix_title', return_value={'id': 'tt1234567'}) as resolve:
            self.assertEqual(g.fetch_public_netflix(spec), ([{'id': 'tt1234567'}], ''))
        self.assertEqual(resolve.call_args.args, ('movie', rows[2]))

    def test_release_rows_use_saudi_availability_and_real_season_start(self):
        _, series = build_netflix_release_rows()
        found = [{'id': n, 'original_language': language} for n, language in
                 [(1, 'ar'), (2, 'ar'), (3, 'en'), (4, 'ar')]]
        records = {
            1: {'first_air_date': '2021-03-01', 'seasons': [{'season_number': 2, 'air_date': '2026-11-12'}],
                'networks': [{'name': 'Shasha'}], 'production_companies': [{'name': 'Shasha Studios'}]},
            2: {'first_air_date': '2024-07-02', 'seasons': [{'season_number': 1, 'air_date': '2024-07-02'}],
                'last_episode_to_air': {'air_date': '2026-11-14'}},
            4: {'first_air_date': '2026-11-15', 'seasons': [{'season_number': 1, 'air_date': '2026-11-15'}]},
        }
        with patch.object(g, 'TODAY', date(2026, 11, 16)), \
                patch.object(g, 'fetch_discover', return_value=('tv', found)) as discover, \
                patch.object(g, 'details', side_effect=lambda kind, id: records[id]), \
                patch.object(g, 'preview', side_effect=lambda kind, item, **kw: {
                    'id': f'tt{item["id"]:07}', 'description': kw['verified_note']}):
            rows, reason = g.catalog(series)
        self.assertEqual(reason, '')
        self.assertEqual([row['id'] for row in rows], ['tt0000004', 'tt0000001'])
        self.assertIn('Season 2 premiere 2026-11-12', rows[1]['description'])
        self.assertIn('Networks: Shasha', rows[1]['description'])
        self.assertIn('Production: Shasha Studios', rows[1]['description'])
        for call, field in zip(discover.call_args_list, ('first_air_date', 'air_date')):
            params = call.args[0]['params']
            self.assertEqual((params['watch_region'], params['with_watch_providers']), ('SA', '8'))
            self.assertEqual(params[field + '.gte'], '2026-10-18')
            self.assertEqual(params[field + '.lte'], '2026-11-16')

    def test_digital_release_must_be_in_saudi_arabia_and_have_the_digital_type(self):
        with patch.object(g, 'tmdb', return_value={'results': [
                {'iso_3166_1': 'SA', 'release_dates': [
                    {'type': 3, 'release_date': '2026-11-16T00:00:00Z'},
                    {'type': 4, 'release_date': '2026-11-09T00:00:00Z'}]},
                {'iso_3166_1': 'AE', 'release_dates': [
                    {'type': 4, 'release_date': '2026-11-12T00:00:00Z'}]},
        ]}):
            self.assertEqual(g.netflix_release_dates('movie', {'id': 75, 'release_date': '2015-01-01'}, True),
                             [('2015-01-01', 'Film release'), ('2026-11-09', 'Saudi digital release')])

    def test_style_restricted_to_netflix_and_valid_image_sources(self):
        valid = "https://image.tmdb.org/t/p/w500/example.jpg"
        invalid = "https://wrong.org/a.jpg"
        self.assertTrue(safe_tmdb_image_url(valid))
        self.assertFalse(safe_tmdb_image_url(invalid))
        self.assertFalse(safe_tmdb_image_url("file:///etc/passwd"))
        self.assertFalse(safe_tmdb_image_url("https://image.tmdb.org.evil.org/t/p/w500/a.jpg"))
        self.assertFalse(safe_tmdb_image_url(valid + "?token=secret"))
        self.assertEqual(score_label({"_tmdb_score": 8.53}), "TMDB 8.5")
        self.assertIsNone(score_label({"_tmdb_score": 55}))
        self.assertEqual(rank_label({"description": "Original chart position #6"},
                                    {"mode": "netflix_official"}), 6)
        self.assertIsNone(rank_label({"description": "Original chart position #6"},
                                     {"mode": "netflix_public"}))
        untouched = [{"id": "tt1234567", "poster": valid, "_tmdb_score": 8.0}]
        with tempfile.TemporaryDirectory() as temp:
            result = style_netflix_catalog(Path(temp),
                {"type": "movie", "group": "Shahid Arabic Exclusives"}, untouched,
                "https://example.org", {})
        self.assertIs(result, untouched)
        self.assertEqual(untouched[0]["poster"], valid)

    def test_rendered_netflix_image_with_rank_and_score(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow installed in GitHub Actions")
        image = Image.new("RGB", (500, 750), "#51718a")
        buf = io.BytesIO()
        image.save(buf, "JPEG")
        data = buf.getvalue()

        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self, size): return data

        rows = [{"id": "tt1234567", "type": "movie", "releaseInfo": "2026",
                 "poster": "https://image.tmdb.org/t/p/w500/x.jpg",
                 "_tmdb_score": 7.85,
                 "description": "Original chart position #2"}]
        with tempfile.TemporaryDirectory() as temp:
            with patch("netflix_everything.urlopen", return_value=Reply()):
                style_netflix_catalog(Path(temp),
                    {"type": "movie", "group": "Netflix Saudi",
                     "mode": "netflix_official"}, rows,
                    "https://example.org/my-nuvio-n1", {})
            output = Path(temp, "posters", "netflix", "tt1234567-rank2.jpg")
            self.assertTrue(output.is_file())
            with Image.open(output) as poster:
                self.assertEqual(poster.size, (500, 750))
            self.assertTrue(rows[0]["poster"].endswith("/tt1234567-rank2.jpg"))
            self.assertNotIn("_tmdb_score", rows[0])

    def test_failure_preserves_original_image_and_movie(self):
        rows = [{"id": "tt1234567", "type": "movie",
                 "poster": "https://image.tmdb.org/t/p/w500/x.jpg"}]
        with tempfile.TemporaryDirectory() as temp:
            with patch("netflix_everything.urlopen", side_effect=OSError("network down")), \
                    contextlib.redirect_stdout(io.StringIO()):
                style_netflix_catalog(Path(temp),
                    {"group": "Netflix Saudi", "type": "movie",
                     "mode": "netflix_public"}, rows, "https://example.org")
            self.assertEqual(rows[0]["poster"],
                             "https://image.tmdb.org/t/p/w500/x.jpg")

    def test_saved_collections_change_only_netflix_folder(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("nuvio-collections.json", "nuvio-collections-streaming.json"):
            data = json.loads((root / name).read_text())
            folders = data[0]["folders"]
            netflix = folders[0]
            ids = {row["catalogId"] for row in netflix["catalogSources"]}
            public = {row["id"] for row in build_public_netflix_rows() + build_netflix_release_rows()}
            self.assertTrue(public <= ids)
            self.assertTrue({"netflix_sa_top_movies", "netflix_sa_top_series"} <= ids)
            self.assertEqual(netflix['catalogSources'][0]['catalogId'], 'netflix_sa_top_movies')
            for other in folders[1:]:
                self.assertFalse(any(src["catalogId"] in public
                                     for src in other.get("catalogSources", [])))


if __name__ == "__main__":
    unittest.main()
