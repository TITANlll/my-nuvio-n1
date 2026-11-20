import unittest
from unittest.mock import Mock
from arabic_details import title_details


class ArabicDetailsTests(unittest.TestCase):
    item = {'id': 'tt36838527', 'name': 'Obsess', 'type': 'series',
            'trailers': [{'source': 'xo0g9Y5syCE', 'type': 'Trailer'}]}
    record = {'external_ids': {'imdb_id': 'tt36838527'},
              'seasons': [{'season_number': 1, 'episode_count': 4}]}

    def test_details_include_trailer_and_playable_episode_ids(self):
        season = {'episodes': [{'episode_number': n} for n in range(1, 5)]}
        meta = title_details(self.item, 311853, Mock(side_effect=[self.record, season]))
        self.assertEqual(meta['trailers'], self.item['trailers'])
        self.assertEqual(meta['trailerStreams'][0]['ytId'], 'xo0g9Y5syCE')
        self.assertEqual([v['id'] for v in meta['videos']], [f'tt36838527:1:{n}' for n in range(1, 5)])

    def test_incomplete_season_and_mismatched_identity_use_existing_provider(self):
        self.assertIsNone(title_details(self.item, 311853, Mock(side_effect=[self.record, {'episodes': []}])))
        self.assertIsNone(title_details(self.item, 311853, Mock(return_value={'external_ids': {}})))
