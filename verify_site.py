"""Check the public manifest and every catalog route without API credentials."""
import json
import sys
import argparse
from urllib.parse import quote
from urllib.request import urlopen


def read_json(url):
    with urlopen(url, timeout=30) as response:
        if response.status != 200:
            raise ValueError('Expected HTTP 200')
        return json.load(response)


def verify(base, expected_version=None):
    base = base.rstrip('/')
    if not base.startswith('https://'):
        raise ValueError('Expected a public HTTPS base URL')
    manifest = read_json(base + '/manifest.json')
    if expected_version and manifest.get('version') != expected_version:
        raise ValueError('Expected updated addon version')
    if manifest.get('id') != 'com.mynuvio.buildn1' or manifest.get('resources') != ['catalog']:
        raise ValueError('Unexpected addon manifest')
    catalogs = manifest.get('catalogs', [])
    if not catalogs:
        raise ValueError('Manifest contains no catalogs')
    seen = set()
    for catalog in catalogs:
        key = (catalog['type'], catalog['id'])
        if key in seen or key[0] not in ('movie', 'series'):
            raise ValueError('Invalid or duplicate catalog')
        seen.add(key)
        path = '/catalog/' + '/'.join(quote(part, safe='') for part in key) + '.json'
        metas = read_json(base + path).get('metas')
        if not isinstance(metas, list) or not metas:
            raise ValueError('Catalog has no entries')
        if any(not m.get('id', '').startswith('tt') or m.get('type') != key[0]
               or not m.get('name') for m in metas):
            raise ValueError('Invalid catalog metadata')
    print(f'Verified manifest and {len(catalogs)} catalog routes: {base}/manifest.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base')
    parser.add_argument('--expected-version')
    args = parser.parse_args()
    try:
        verify(args.base, args.expected_version)
    except Exception as err:
        # Avoid printing arbitrary response bodies or request details.
        raise SystemExit('Live verification failed: ' + type(err).__name__)
