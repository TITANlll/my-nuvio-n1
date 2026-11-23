"""Check the public manifest and every catalog route without API credentials."""
import json
import sys
import argparse
from urllib.parse import quote
from urllib.request import urlopen
from browse_catalogs import BROWSE_GROUPS, BROWSE_PAGE_SIZE
from generate import COLLECTION_NETWORKS, COLLECTION_PRESETS, collection_network


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


def verify_collection_presets(base, addon_id, expected):
    for filename in COLLECTION_PRESETS:
        folders = {
            folder['title'].split(maxsplit=1)[0].lower(): folder
            for collection in read_json(f'{base}/{filename}')
            for folder in collection['folders']
        }
        for network, routes in expected.items():
            folder = folders[network]
            for field in ('catalogSources', 'sources'):
                if field == 'sources' and field not in folder:
                    continue
                actual = [
                    (source['type'], source['catalogId']) for source in folder[field]
                    if source.get('addonId') == addon_id
                    and collection_network(source['catalogId']) in COLLECTION_NETWORKS
                ]
                if len(actual) != len(routes) or set(actual) != routes:
                    raise ValueError(f'Incomplete {network} folder in {filename}')


def verify(base, expected_version=None):
    base = base.rstrip('/')
    if not base.startswith('https://'):
        raise ValueError('Expected a public HTTPS base URL')
    manifest = read_json(base + '/manifest.json')
    if expected_version and manifest.get('version') != expected_version:
        raise ValueError('Expected updated addon version')
    if manifest.get('id') != 'com.mynuvio.buildn1' or 'catalog' not in manifest.get('resources', []):
        raise ValueError('Unexpected addon manifest')
    for resource in manifest['resources']:
        if resource == 'catalog':
            continue
        if resource.get('name') != 'meta' or not resource.get('idPrefixes'):
            raise ValueError('Unexpected addon resource')
        for imdb in resource['idPrefixes']:
            if imdb == 'tt36838527':
                detail = read_json(base + '/meta/series/' + imdb + '.json')['meta']
                if (detail['id'] != imdb or not any(t['source'] == 'xo0g9Y5syCE' for t in detail['trailers'])
                        or not {f'{imdb}:1:{n}' for n in range(1, 5)} <= {v['id'] for v in detail['videos']}):
                    raise ValueError('Obsess trailer or episodes missing')
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
    collection_routes = {}
    for catalog in catalogs:
        key = (catalog['type'], catalog['id'])
        network = collection_network(catalog['id'])
        collection_only = network in COLLECTION_NETWORKS
        if collection_only and catalog.get('showInHome') is not False:
            raise ValueError('Network catalog still appears on Home')
        if not collection_only and catalog.get('showInHome') is False:
            raise ValueError('Unexpected change to Home catalog visibility')
        if collection_only:
            collection_routes.setdefault(network, set()).add(key)
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
    if collection_routes:
        verify_collection_presets(base, manifest['id'], collection_routes)
        counts = ', '.join(f'{network}={len(routes)}' for network, routes in sorted(collection_routes.items()))
        print(f'Verified collection-only catalogs and both presets ({counts})')
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
