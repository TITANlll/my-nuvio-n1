import unittest
from unittest.mock import patch

import generate as g


class NetflixTrailerTests(unittest.TestCase):
    def setUp(self):
        g.netflix_trailer.cache_clear()
        self.addCleanup(g.netflix_trailer.cache_clear)

    def test_obsess_uses_verified_series_identity_without_tmdb(self):
        item = {'id': 'tt36838527', 'type': 'series', 'name': 'Obsess'}
        g.attach_netflix_trailer(item)
        self.assertEqual(item['trailers'], [{'source': 'xo0g9Y5syCE', 'type': 'Trailer'}])
        movie = {'id': 'tt36838527', 'type': 'movie', 'name': 'Obsess'}
        g.attach_netflix_trailer(movie)
        self.assertNotIn('trailers', movie)

    def test_localized_official_trailer_fallback_and_cache(self):
        clip = {'key': 'abcdefghijk', 'site': 'YouTube', 'official': True, 'type': 'Clip'}
        with patch.object(g, 'tmdb', side_effect=[
            {'results': [clip]}, {'results': [{**clip, 'type': 'Trailer'}]}
        ]) as lookup:
            for _ in range(2):
                item = {'type': 'series', 'id': 'tt1234567', '_tmdb_id': 42}
                g.attach_netflix_trailer(item)
                self.assertEqual(item['trailers'][0]['source'], 'abcdefghijk')
        self.assertEqual([call.args for call in lookup.call_args_list], [
            ('/tv/42/videos', {'language': 'en-US'}),
            ('/tv/42/videos', {'language': 'ar-SA'})
        ])
