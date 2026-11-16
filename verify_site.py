"""Check the public manifest and every catalog route without API credentials."""
import json
import sys
import argparse
from urllib.parse import quote
from urllib.request import urlopen
from browse_catalogs import BROWSE_GROUPS, BROWSE_PAGE_SIZE


def read_json(url):
    with urlopen(url, timeout=30) as response:
        if response.status != 200:
            raise ValueError('Expected HTTP 200')
        return json.load(response)


def read_metas(url, kind):
    metas = read_json(url).get('metas')
    if not isinstance(metas, list) or any(
        not m.get('id', '').startswith('tt') or m.get('type') != kind or not m.get('name')
        for m in metas
    ):
        raise ValueError('Invalid catalog metadata')
    return metas


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
    paginated = {
        (catalog['type'], catalog['id']) for catalog in catalogs
        if {'name': 'skip', 'isRequired': False} in catalog.get('extra', [])
    }
    browse_totals = {}
    if paginated:
        browse_totals = {
            (catalog['type'], catalog['id']): catalog['entries']
            for catalog in read_json(base + '/status.json')['catalogs']
            if catalog['section'] in BROWSE_GROUPS and catalog['status'] == 'active'
        }
        if paginated != browse_totals.keys():
            raise ValueError('Unexpected pagination scope')
    seen = set()
    for catalog in catalogs:
        key = (catalog['type'], catalog['id'])
        if key in seen or key[0] not in ('movie', 'series'):
            raise ValueError('Invalid or duplicate catalog')
        seen.add(key)
        url = base + '/catalog/' + '/'.join(quote(part, safe='') for part in key)
        metas = read_metas(url + '.json', key[0])
        if not metas:
            raise ValueError('Catalog has no entries')
        if key in browse_totals:
            total = browse_totals[key]
            if len(metas) != min(total, BROWSE_PAGE_SIZE):
                raise ValueError('Unexpected first page size')
            if total > len(metas):
                second = read_metas(f'{url}/skip={len(metas)}.json', key[0])
                seen_ids = {m['id'] for m in metas}
                if len(second) != min(total - len(metas), BROWSE_PAGE_SIZE) or any(
                    m['id'] in seen_ids for m in second
                ):
                    raise ValueError('Unexpected second page')
            if read_metas(f'{url}/skip={total}.json', key[0]):
                raise ValueError('Expected empty page at catalog end')
    print(f'Verified {len(catalogs)} catalogs and pagination for {len(paginated)}: {base}/manifest.json')


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
