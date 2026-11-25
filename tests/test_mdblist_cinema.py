import json
import unittest
from unittest.mock import patch
import generate

class MDBListCinemaTests(unittest.TestCase):
    def setUp(self):
        self.spec = {'id': 'oscar_winners', 'type': 'movie',
                     'group': 'Awards & Collections', 'mode': 'verified'}

    def test_missing_key_uses_existing_source(self):
        with patch.object(generate, 'MDBLIST_API_KEY', ''), \
             patch.object(generate, 'fetch_verified', return_value=[{'id':'tt123'}]):
            self.assertEqual(generate.catalog(self.spec)[0], [{'id':'tt123'}])

    def test_type_and_duplicate_filter(self):
        data = {'movies': [
            {'imdb_id':'tt123', 'mediatype':'movie'},
            {'imdb_id':'tt123', 'mediatype':'movie'},
            {'imdb_id':'tt456', 'mediatype':'show'},
            {'imdb_id':'bad', 'mediatype':'movie'},
            {'imdb_id':'tt789', 'mediatype':'movie'},
        ]}
        def metadata(imdb, kind):
            return {'id':imdb, 'poster':'https://example.com/poster.jpg', 'description':''}
        with patch.object(generate, 'MDBLIST_API_KEY', 'test'), \
             patch.object(generate, 'fetch', return_value=json.dumps(data).encode()), \
             patch.object(generate, 'enrich_from_imdb', side_effect=metadata):
            rows = generate.fetch_mdblist_cinema(self.spec)
        self.assertEqual([x['id'] for x in rows], ['tt123', 'tt789'])

    def test_sparse_source_keeps_existing_row(self):
        with patch.object(generate, 'fetch_mdblist_cinema', return_value=[{'id':'tt123'}]), \
             patch.object(generate, 'fetch_verified', return_value=[{'id':'tt456'}]):
            self.assertEqual(generate.catalog(self.spec)[0], [{'id':'tt456'}])

if __name__ == '__main__':
    unittest.main()
