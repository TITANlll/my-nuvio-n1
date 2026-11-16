import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import generate as g
from netflix_everything import (rank_label, safe_tmdb_image_url,
                                score_label, style_netflix_catalog)
from netflix_public_rows import build_public_netflix_rows


class NetflixEverythingTests(unittest.TestCase):
    def test_real_public_page_rows_have_documented_sources_and_distinct_ids(self):
        rows = build_public_netflix_rows()
        self.assertEqual(len(rows), 9)
        self.assertEqual(len({r["id"] for r in rows}), 9)
        self.assertTrue(all(r["mode"] == "netflix_public" for r in rows))
        self.assertTrue(all(r["group"] == "Netflix Saudi" for r in rows))
        self.assertTrue(all(r["snapshot_date"] == "2026-11-16" for r in rows))
        self.assertTrue(all(r["source_url"].startswith("https://www.netflix.com/sa-en/")
                            for r in rows))
        self.assertTrue(all(len(r["titles"]) >= 10 for r in rows))

    def test_public_page_resolution_keeps_source_order_and_skips_ambiguity(self):
        spec = build_public_netflix_rows()[0]
        ids = {title: number for number, title in enumerate(spec["titles"], start=1)}
        def find(kind, title):
            if title == spec["titles"][2]:
                return None
            return {"id": ids[title], "name": title, "vote_average": 7.1}
        def preview(kind, item, **kw):
            return {"id": "tt" + str(item["id"]).zfill(7), "type": "series",
                    "name": item["name"], "description": kw["verified_note"]}
        with patch.object(g, "match_netflix_chart_title", side_effect=find), \
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
        with patch.object(g, "match_netflix_chart_title", return_value=None):
            items, reason = g.fetch_public_netflix(spec)
        self.assertEqual(items, [])
        self.assertIn("Fewer than five", reason)

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
            self.assertEqual(Image.open(output).size, (500, 750))
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
            public = {row["id"] for row in build_public_netflix_rows()}
            self.assertTrue(public <= ids)
            self.assertTrue({"netflix_sa_top_movies", "netflix_sa_top_series"} <= ids)
            for other in folders[1:]:
                self.assertFalse(any(src["catalogId"] in public
                                     for src in other.get("catalogSources", [])))


if __name__ == "__main__":
    unittest.main()
