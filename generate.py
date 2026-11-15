#!/usr/bin/env python3
"""Generate a static catalog-only Nuvio/Stremio addon for GitHub Pages.

Only publishes catalogs with data from a stated source. BetterPosters and
personalized Trakt rows stay in their respective existing addons. Exclusive,
subtitle and awards claims require a human-verifiable allowlist.
"""
from __future__ import annotations
import csv
import io
import json
import os
import re
import shutil
import tempfile
import sys
import time
import unicodedata
from collections import defaultdict
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.client import IncompleteRead
from browse_catalogs import build_browse_catalogs
from shahid_home_rows import build_shahid_home_rows
from netflix_home_rows import build_netflix_home_rows

ROOT = Path(__file__).parent
OUT = ROOT / 'site'
TODAY = datetime.now(timezone.utc).date()
API_KEY = os.getenv('TMDB_API_KEY', '').strip()
TOKEN = os.getenv('TMDB_BEARER_TOKEN', '').strip()
BASE = os.getenv('PAGE_URL', '').strip().rstrip('/')
LIMIT = max(5, min(30, int(os.getenv('ITEMS_PER_ROW', '15'))))
ALL = json.loads((ROOT / 'catalogs.json').read_text())
VERIFIED = json.loads((ROOT / 'data' / 'verified.json').read_text())
BETTERPOSTERS_PATTERN = os.getenv('BETTERPOSTERS_POSTER_PATTERN','').strip()
CACHE = {}
ADDON_VERSION = '1.5.0'


def catalog_plan():
    labels = json.loads((ROOT / 'browsing-folders.json').read_text())
    original = sorted(ALL, key=lambda row: row['group'] != 'BetterPosters Discovery')
    # Add homepage-inspired Shahid rows near the existing Shahid catalogs.
    # Preserve all original 58 definitions and their relative order.
    additions = build_shahid_home_rows()
    netflix_additions = build_netflix_home_rows()
    after = {
        'shahid_top_arabic_series': additions[:2],
        'shahid_top_arabic_movies': additions[2:4],
        'shahid_trending_arabic': additions[4:],
        'netflix_sa_popular_movies': netflix_additions[:3],
        'netflix_sa_new': netflix_additions[3:],
    }
    plan = []
    for row in original:
        plan.append(row)
        plan.extend(after.get(row['id'], []))
    return plan + build_browse_catalogs(labels, TODAY)


def fetch(url, *, headers=None, retries=3, timeout=40):
    for attempt in range(retries):
        try:
            with urlopen(Request(url, headers={**{'User-Agent':'MyNuvioN1/1.0 (+personal catalog)'}, **(headers or {})}), timeout=timeout) as r:
                return r.read()
        except (OSError, HTTPError, IncompleteRead):
            # An interrupted HTTP body is not an OSError. Discard its partial
            # bytes and restart the entire request; a truncated chart can
            # silently omit countries or weeks if parsed as valid TSV.
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def tmdb(path, params=None):
    if not (API_KEY or TOKEN):
        raise RuntimeError('TMDB_API_KEY or TMDB_BEARER_TOKEN is required')
    query = {'language':'en-US', **(params or {})}
    if API_KEY:
        query['api_key'] = API_KEY
    url = 'https://api.themoviedb.org/3' + path + '?' + urlencode(query)
    if url in CACHE:
        return CACHE[url]
    headers = {'Authorization':'Bearer ' + TOKEN} if TOKEN else {}
    value = json.loads(fetch(url, headers=headers))
    CACHE[url] = value
    return value


def media_type(spec):
    return 'movie' if spec['type'] == 'movie' else 'tv'


def norm(s):
    t = unicodedata.normalize('NFKD', str(s)).casefold()
    return re.sub(r'[^a-z0-9]+', '', t)


def external_id(kind, tmdb_id):
    # TMDB occasionally includes an indexed discover result whose separate
    # /external_ids detail record is not available (HTTP 404). Skip that item,
    # but still stop the build on authentication/rate-limit/server failures.
    try:
        e = tmdb(f'/{kind}/{tmdb_id}/external_ids')
    except HTTPError as err:
        if err.code == 404:
            return None
        raise
    v = e.get('imdb_id')
    return v if isinstance(v, str) and re.fullmatch(r'tt\d+', v) else None


def details(kind, tmdb_id):
    return tmdb(f'/{kind}/{tmdb_id}')


def preview(kind, item, *, verified_note=None, source_rank=None, source_week=None):
    imdb = external_id(kind, item['id'])
    if not imdb:
        return None
    title = item.get('title' if kind == 'movie' else 'name')
    if not title:
        return None
    p = {'id':imdb, 'type':'movie' if kind == 'movie' else 'series', 'name':title}
    if item.get('poster_path'):
        p['poster'] = 'https://image.tmdb.org/t/p/w500' + item['poster_path']
    # Only use a URL pattern actually copied from the user's own BetterPosters
    # configurator. We never invent a BetterPosters API path.
    if BETTERPOSTERS_PATTERN and any(x in BETTERPOSTERS_PATTERN for x in ('{imdb_id}','{id}')):
        p['poster'] = BETTERPOSTERS_PATTERN.replace('{imdb_id}',imdb).replace('{id}',imdb)
    if item.get('backdrop_path'):
        p['background'] = 'https://image.tmdb.org/t/p/w1280' + item['backdrop_path']
    released = item.get('release_date' if kind == 'movie' else 'first_air_date','')
    if released:
        p['releaseInfo'] = str(released)[:4]
    d = item.get('overview', '') or ''
    prefixes = []
    if source_rank is not None:
        prefixes.append('Original chart position #' + str(source_rank))
    if source_week:
        prefixes.append('Chart week ending ' + str(source_week))
    if verified_note:
        prefixes.append(verified_note)
    p['description'] = ' · '.join(prefixes) + ('. ' if prefixes else '') + d
    return p


def enrich_from_imdb(imdb, expected_type):
    results = tmdb('/find/'+quote(imdb), {'external_source':'imdb_id'})
    k = 'movie_results' if expected_type == 'movie' else 'tv_results'
    choices = results.get(k, [])
    if not choices:
        return None
    kind = 'movie' if expected_type == 'movie' else 'tv'
    return preview(kind, choices[0])


def fetch_discover(spec, *, max_pages=3, pool_size=None):
    kind = media_type(spec)
    path = '/discover/' + kind
    params = dict(spec.get('params', {}))
    items = []
    # Pool multiple pages to compensate for titles without IMDb IDs.
    for page in range(1, max_pages + 1):
        rows = tmdb(path, {**params, 'page':page}).get('results', [])
        if not rows:
            break
        items.extend(x for x in rows if x.get('poster_path') and x.get('id'))
        if len(items) >= (pool_size if pool_size is not None else LIMIT + 20):
            break
    return kind, items



def shahid_provider_id(kind):
    """Resolve Shahid VIP in the TMDB watch-provider registry, not by guessing an ID.

    The provider's JustWatch coverage reflects regional catalog availability,
    not Shahid's own ranking or exact subscription entitlement.
    """
    providers = tmdb('/watch/providers/' + kind).get('results', [])
    for provider in providers:
        if str(provider.get('provider_name', '')).strip().casefold() in ('shahid vip', 'shahid'):
            provider_id = provider.get('provider_id')
            if isinstance(provider_id, int) and provider_id > 0:
                return provider_id
    return None


def shahid_arabic_poster(kind, item):
    """Prefer Arabic TMDB artwork for Shahid discovery, never scrape Shahid.

    TMDB may not have an Arabic poster. Any optional artwork lookup failure
    leaves the ordinary poster in place so the catalog can still publish.
    """
    media_id = item.get('id')
    if not media_id:
        return None
    try:
        images = tmdb('/' + kind + '/' + str(media_id) + '/images',
                      {'language': 'ar', 'include_image_language': 'en,null'})
        posters = images.get('posters', [])
        arabic = [p for p in posters
                  if isinstance(p, dict) and p.get('iso_639_1') == 'ar'
                  and isinstance(p.get('file_path'), str)
                  and re.fullmatch(r'/[A-Za-z0-9_.-]+\.(?:jpg|png|webp)',
                                   p['file_path'])]
        if arabic:
            best = max(arabic, key=lambda p: (p.get('vote_average') or 0,
                                             p.get('vote_count') or 0,
                                             p.get('width') or 0))
            return 'https://image.tmdb.org/t/p/w500' + best['file_path']
    except Exception:
        # This is optional artwork: never let an image-lookup fault suppress
        # Shahid titles or fail a scheduled catalog rebuild.
        return None
    return None


def discover_shahid(spec):
    kind = media_type(spec)
    provider_id = shahid_provider_id(kind)
    if provider_id is None:
        return [], 'Shahid VIP is not listed as a TMDB provider for this media type'
    params = dict(spec.get('params', {}))
    # Never freeze the publication cutoff at the day the code was written.
    date_field = 'primary_release_date.lte' if kind == 'movie' else 'first_air_date.lte'
    # Respect stricter catalog-specific cutoff dates (e.g., Syrian classics).
    params[date_field] = min(params.get(date_field, str(TODAY)), str(TODAY))
    params.update({
        'watch_region': 'SA',
        'with_watch_providers': str(provider_id),
        # TMDB supports OR-separated monetization types; keep VIP alongside
        # separately indexed free/ad-supported offers, not just subscriptions.
        'with_watch_monetization_types': 'flatrate|free|ads',
    })
    _, items = fetch_discover({**spec, 'params': params}, max_pages=6, pool_size=180)
    results = []
    used = set()
    for item in items:
        poster = preview(kind, item, verified_note=spec.get('note'))
        if not poster or poster['id'] in used:
            continue
        arabic_poster = shahid_arabic_poster(kind, item)
        if arabic_poster:
            poster['poster'] = arabic_poster
        used.add(poster['id'])
        results.append(poster)
        if len(results) >= LIMIT:
            break
    if len(results) < 5:
        return [], 'Fewer than five Shahid Saudi titles with reliable IMDb poster metadata'
    return results, ''


def discover_turkish(spec):
    """Create non-sparse Turkish discovery rows from TMDB, not subtitle claims.

    Stream availability is only asserted for the separate Netflix Saudi rows,
    which apply an explicit regional watch-provider filter.
    """
    params = dict(spec.get('params', {}))
    kind = media_type(spec)
    date_field = 'primary_release_date' if kind == 'movie' else 'first_air_date'
    params[date_field + '.lte'] = str(TODAY)
    if spec.get('release_window_days'):
        params[date_field + '.gte'] = str(
            TODAY - timedelta(days=spec['release_window_days']))
    if spec.get('episode_window_days'):
        if kind != 'tv':
            return [], 'Episode date filters require series'
        params['air_date.gte'] = str(
            TODAY - timedelta(days=spec['episode_window_days']))
        params['air_date.lte'] = str(TODAY)
    kind, items = fetch_discover(
        {**spec, 'params': params}, max_pages=6, pool_size=max(100, LIMIT * 6))
    results = []
    seen = set()
    for item in items:
        # Only Turkish-original-language works belong here, even if the
        # upstream discover service returns an unexpected mixed-language row.
        if item.get('original_language') != 'tr':
            continue
        poster = preview(kind, item, verified_note=spec.get('note'))
        if poster and poster['id'] not in seen:
            seen.add(poster['id'])
            results.append(poster)
        if len(results) >= LIMIT:
            break
    if len(results) < 5:
        return [], 'Fewer than five Turkish-language titles with reliable IMDb poster metadata'
    return results, ''


def discover_netflix(spec):
    """TMDB-discovery rows for titles listed on Netflix Saudi Arabia.

    Netflix official weekly chart rankings come from get_netflix_rows(), not
    this provider catalog. Its 'new' filter means original premiere only.
    """
    kind = media_type(spec)
    params = dict(spec['params'])
    date_field = 'primary_release_date' if kind == 'movie' else 'first_air_date'
    params[date_field + '.lte'] = str(TODAY)
    if spec.get('release_window_days'):
        params[date_field + '.gte'] = str(
            TODAY - timedelta(days=spec['release_window_days']))
    _, candidates = fetch_discover({**spec, 'params': params},
                                   max_pages=5, pool_size=max(100, LIMIT * 5))
    found = []
    seen = set()
    for item in candidates:
        poster = preview(kind, item, verified_note=spec.get('note'))
        if poster and poster['id'] not in seen:
            seen.add(poster['id'])
            found.append(poster)
        if len(found) >= LIMIT:
            break
    if len(found) < 5:
        return [], 'Fewer than five Netflix Saudi titles with reliable IMDb poster metadata'
    return found, ''


def fetch_keyword(spec, **discovery_options):
    params = dict(spec.get('params', {}))
    keywords=[]
    for phrase in spec['keyword'].split('|'):
        phrase=phrase.strip()
        matches=tmdb('/search/keyword',{'query':phrase.strip()}).get('results',[])
        exact=next((x for x in matches if x.get('name','').casefold()==phrase.casefold()), None)
        if exact:
            keywords.append(str(exact['id']))
    if not keywords:
        return media_type(spec), []
    params['with_keywords'] = '|'.join(keywords)
    return fetch_discover({**spec,'params':params}, **discovery_options)


def fetch_verified(spec):
    rows=[]
    for entry in VERIFIED:
        if spec.get('tag') not in entry.get('tags',[]):
            continue
        if entry.get('type')!=spec['type'] or not entry.get('source_url'):
            continue
        # The operator must explicitly record verification: blank examples do not qualify.
        if entry.get('verified') is not True:
            continue
        if spec['group']=='Turkish Content':
            if entry.get('origin_country')!='TR' or entry.get('original_language')!='tr':
                continue
            if entry.get('arabic_subtitles_verified') is not True or not entry.get('subtitle_source_url'):
                continue
            if spec['id']=='turkish_streaming_originals' and not entry.get('original_source_url'):
                continue
            if spec['id'].startswith('netflix_') and (
                    entry.get('provider') != 'netflix' or entry.get('region') != 'SA'):
                continue
        if spec['group'] in ('Turkish Content', 'Shahid Arabic Exclusives'):
            # Availability and subtitle evidence can expire; never keep these
            # claims indefinitely based on a historical announcement.
            try:
                checked = date.fromisoformat(entry.get('verified_on', ''))
            except ValueError:
                continue
            if not 0 <= (TODAY - checked).days <= 90:
                continue
        if spec['group']=='Shahid Arabic Exclusives':
            if entry.get('original_language')!='ar' or entry.get('shahid_exclusive_verified') is not True:
                continue
            if spec['id']=='shahid_saudi_originals' and entry.get('origin_country')!='SA':
                continue
            if spec['id']=='shahid_gulf' and entry.get('origin_country') not in ('SA','AE','KW','BH','QA','OM'):
                continue
        try:
            p = enrich_from_imdb(entry['imdb_id'],spec['type'])
            if p:
                p['description'] = (entry.get('label','Verified curated entry') + ' · Source: ' + entry['source_url'] + '. ') + p.get('description','')
                rows.append(p)
        except (KeyError, ValueError):
            continue
    return rows[:LIMIT]


def netflix_chart_search_queries(kind, title):
    """Allow conservative season/collection suffix removal for TV chart items.

    Netflix uses 'Show: Season 2' in its weekly chart, whereas TMDB usually
    indexes the parent series as 'Show'. Never strip movie sequel names.
    """
    queries = [title]
    if kind == 'series':
        base = re.sub(
            r'\s*[:\-–]\s*(?:season\s+\d+|limited\s+series|collection\s+\d+)\s*$',
            '', title, flags=re.IGNORECASE).strip()
        if base and base != title:
            queries.append(base)
    return queries


def match_netflix_chart_title(kind, title):
    """Match by an exact display/original title; never guess a Netflix rank."""
    target = 'movie' if kind == 'movie' else 'tv'
    title_keys = ('title', 'original_title') if kind == 'movie' else ('name', 'original_name')
    for query in netflix_chart_search_queries(kind, title):
        matches = tmdb('/search/' + target, {'query': query}).get('results', [])
        expected = norm(query)
        strong = {
            candidate['id']: candidate
            for candidate in matches[:20]
            if candidate.get('id') and any(
                expected == norm(candidate.get(field, ''))
                for field in title_keys)
        }
        if len(strong) > 1:
            # Different productions share this exact name; do not guess.
            return None
        if len(strong) == 1:
            return next(iter(strong.values()))
    return None


def get_netflix_rows():
    """Get latest SA country movie and TV chart rows from official TSV file.

    Do not use TMDB popularity as a substitute for official rank. Rankings
    preserve Netflix's original rank; failed title matches are simply omitted.
    """
    url='https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv'
    b=fetch(url, retries=5, timeout=120)
    reader=csv.DictReader(io.StringIO(b.decode('utf-8-sig')),delimiter='\t')
    required={'country_iso2','category','week','weekly_rank','show_title'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('Netflix chart is missing required columns')
    by = defaultdict(list)
    for r in reader:
        if r.get('country_iso2')!='SA':
            continue
        cat = r.get('category','').casefold()
        if 'films' in cat:
            kind='movie'
        elif 'tv' in cat:
            kind='series'
        else:
            continue
        date.fromisoformat(r.get('week',''))
        by[(r.get('week'),kind)].append(r)
    output={}
    for kind in ('movie','series'):
        weeks = [week for week,k in by if k==kind]
        if not weeks:
            raise ValueError('Netflix chart has no Saudi rows for ' + kind)
        last=max(weeks)
        recent=sorted(by[(last,kind)],key=lambda r:int(r['weekly_rank']))
        if (len(recent)!=10 or {int(r['weekly_rank']) for r in recent}!=set(range(1,11))
                or any(not r.get('show_title','').strip() for r in recent)):
            raise ValueError('Netflix Saudi weekly chart is incomplete')
        collected=[]
        for r in recent:
            title=r['show_title'].strip()
            target='movie' if kind=='movie' else 'tv'
            best=match_netflix_chart_title(kind, title)
            if best is None:
                continue
            p=preview(target,best,source_rank=r['weekly_rank'],
                      source_week=last, verified_note='Netflix chart: '+title)
            if p:
                collected.append(p)
        if not collected:
            raise ValueError('Netflix chart has no reliable IMDb matches for ' + kind)
        output[kind]=collected
    return output


def rating_eligible(kind, item, allowed):
    media_id=item['id']
    if kind=='movie':
        data=tmdb(f'/movie/{media_id}/release_dates')
        results=data.get('results',[])
        # Prefer national guidance when a Saudi certification is present.
        for country in ('SA','US'):
            vals=[]
            for r in results:
                if r.get('iso_3166_1')!=country:
                    continue
                vals += [v for x in r.get('release_dates',[])
                         if (v := x.get('certification','').strip().upper())]
            if vals:
                return any(v in allowed for v in vals)
        return False
    data=tmdb(f'/tv/{media_id}/content_ratings')
    results=data.get('results',[])
    for country in ('SA','US'):
        vals=[v for x in results if x.get('iso_3166_1')==country
              and (v := x.get('rating','').strip().upper())]
        if vals:
            return any(v in allowed for v in vals)
    return False


def fetch_kids(spec):
    params=dict(spec['params'])
    if spec['id']=='new_for_kids':
        params['primary_release_date.gte']=str(TODAY-timedelta(days=365))
        params['primary_release_date.lte']=str(TODAY)
    row={**spec,'params':params}
    # Strict certification checks discard many candidates. A small popularity
    # pool previously left New for Kids empty before eligible films were seen.
    options={'max_pages':8, 'pool_size':max(100, LIMIT * 5)}
    kind,items=fetch_keyword(row, **options) if spec.get('keyword') else fetch_discover(row, **options)
    result=[]
    for item in items:
        if len(result)>=LIMIT:
            break
        if rating_eligible(kind,item,spec['ratings']):
            p=preview(kind,item,verified_note='Rating filter matched (not a parental-control guarantee)')
            if p:
                result.append(p)
    return result


def fetch_collection(spec):
    out=[]
    seen=set()
    for colid in spec['collection_ids']:
        info=tmdb(f'/collection/{colid}')
        for x in sorted(info.get('parts',[]), key=lambda p:p.get('release_date') or '9999'):
            if x['id'] not in seen and x.get('media_type','movie')=='movie':
                seen.add(x['id'])
                if x.get('poster_path'):
                    out.append(x)
            if len(out)>=LIMIT:
                break
        if len(out)>=LIMIT:
            break
    return [p for x in out if (p:=preview('movie',x))]


def fetch_airing(spec):
    rows=tmdb(spec['path']).get('results',[])
    return [p for x in rows if (p:=preview('tv',x))][:LIMIT]


def fetch_episodes(spec, mode):
    out=[]
    start=TODAY
    end=TODAY+timedelta(days=60 if mode=='returning' else 7)
    if mode=='returning':
        # A returning season announced several weeks ahead is usually absent
        # from the two-page "on the air" sample used for weekly episodes.
        _,rows=fetch_discover({'type':'series','params':{
            'air_date.gte':str(start), 'air_date.lte':str(end),
            'first_air_date.lte':str(start), 'sort_by':'popularity.desc'
        }}, max_pages=5, pool_size=100)
    else:
        rows=tmdb('/tv/on_the_air').get('results',[])
        rows+=tmdb('/tv/on_the_air',{'page':2}).get('results',[])
    for x in rows:
        dt=details('tv',x['id'])
        ep=dt.get('next_episode_to_air') or {}
        ep_date=ep.get('air_date')
        if not ep_date or not (str(start)<=ep_date<=str(end)):
            continue
        if mode=='returning' and not (ep.get('episode_number')==1 and ep.get('season_number',0)>1):
            continue
        p=preview('tv',x, verified_note=('Scheduled for '+ep_date+'; availability may lag'))
        if p:
            out.append(p)
        if len(out)>=LIMIT:
            break
    return out


def fetch_premieres(spec):
    kind,items=fetch_discover({'type':'series','params':{
        'first_air_date.gte':str(TODAY),
        'first_air_date.lte':str(TODAY+timedelta(days=60)),
        'sort_by':'first_air_date.asc'
    }})
    return [p for x in items if (p:=preview(kind,x,verified_note='Scheduled premiere; not confirmed streaming availability'))][:LIMIT]


def catalog(spec, netflix=None):
    mode=spec['mode']
    if mode=='external':
        return None,'Handled by independently installed BetterPosters / personalized addon'
    if mode=='verified':
        rows=fetch_verified(spec)
        if spec['group']=='Shahid Arabic Exclusives' and len(rows) < 5:
            return [], 'Curated Shahid row withheld until five verified titles are available'
        return rows,('Awaiting verified entries and source evidence' if not rows else '')
    if mode=='discover_provider' and spec.get('provider')=='shahid':
        return discover_shahid(spec)
    if mode=='discover' and spec.get('group')=='Turkish Content':
        return discover_turkish(spec)
    if mode=='netflix_discover' and spec.get('group')=='Netflix Saudi':
        return discover_netflix(spec)
    if mode=='netflix_official':
        rows=(netflix or {}).get(spec['kind'],[])
        return rows,('Official Netflix data unavailable or unmatched' if not rows else '')
    if mode in ('discover','discover_keyword'):
        if spec['id']=='netflix_sa_new':
            spec={**spec,'params':{**spec['params'],
                'primary_release_date.gte':str(TODAY-timedelta(days=120)),
                'primary_release_date.lte':str(TODAY)}}
        kind,items=(fetch_discover(spec) if mode=='discover' else fetch_keyword(spec))
        rows=[]
        for item in items:
            p=preview(kind,item,verified_note=spec.get('note'))
            if p:
                rows.append(p)
            if len(rows)>=LIMIT:
                break
        return rows,'' if rows else 'No reliable IMDb-mapped titles returned'
    if mode=='kids':
        rows=fetch_kids(spec)
        return rows,'' if rows else 'No titles passed strict age-rating filter'
    if mode=='collections':
        rows=fetch_collection(spec)
        return rows,'' if rows else 'No franchise entries could be mapped'
    if mode=='airing':
        rows=fetch_airing(spec)
        return rows,'' if rows else 'No currently airing shows available'
    if mode in ('episodes','returning'):
        rows=fetch_episodes(spec,mode)
        return rows,'' if rows else 'No confirmed upcoming episode matched this period'
    if mode=='premieres':
        rows=fetch_premieres(spec)
        return rows,'' if rows else 'No upcoming series matched this period'
    return None,'Not implemented'


def write_json(filename,data):
    filename.parent.mkdir(parents=True,exist_ok=True)
    filename.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def safe_error(err):
    # Exception messages can contain request URLs with TMDB API keys.
    # Publish only the exception class and, for HTTP failures, the status code.
    if isinstance(err, HTTPError):
        return f'HTTPError (HTTP {err.code})'
    return type(err).__name__


def main():
    if not BASE.startswith('https://'):
        raise SystemExit('PAGE_URL must be your real public HTTPS website URL')
    if not (API_KEY or TOKEN):
        raise SystemExit('Configure TMDB_API_KEY or TMDB_BEARER_TOKEN as a private GitHub Actions secret')
    # Netflix top ranks: if the upstream TSV fails, do NOT relabel TMDB as the Netflix Top 10.
    try:
        netflix=get_netflix_rows()
    except Exception as err:
        raise SystemExit('Netflix official source unavailable: ' + safe_error(err) +
                         '; build stopped to preserve the previous website') from None
    # Generate in a temporary directory; do not touch the existing site on failure.
    with tempfile.TemporaryDirectory(prefix='nuvio-build-', dir=OUT.parent) as staging_dir:
        stage = Path(staging_dir)
        active=[]
        status=[]
        planned=catalog_plan()
        for spec in planned:
            try:
                rows,reason=catalog(spec,netflix)
                if rows:
                    path=stage/'catalog'/spec['type']/(spec['id']+'.json')
                    write_json(path,{'metas':rows})
                    active.append({'type':spec['type'],'id':spec['id'],'name':spec['name']})
                    state='active'
                else:
                    state='external' if spec['mode']=='external' else 'held'
                status.append({'id':spec['id'],'type':spec['type'],'section':spec['group'],'catalog':spec['name'],'status':state,
                               'entries':len(rows or []),'reason':reason})
                print(f"{state:8} {spec['name']}: {len(rows or [])}",flush=True)
            except Exception as err:
                # A transient TMDB/network error is not an empty catalog.
                # Fail the whole build so GitHub Pages keeps the last verified site.
                raise SystemExit(
                    'Catalog update failed (' + spec['id'] + '): ' + safe_error(err) +
                    '; build stopped to preserve the previously published site'
                ) from None
        if not active:
            raise SystemExit('No catalogs could be populated; keeping previous website untouched')
        manifest={'id':'com.mynuvio.buildn1','version':ADDON_VERSION,'name':'My Nuvio · Build N1',
          'description':'Personal discovery catalogs. Genuine Netflix weekly positions, TMDB classifications, verified-only exclusives. No playback or subtitle streams. BetterPosters remains separate.',
          'types':['movie','series'],'resources':['catalog'],
          'catalogs':active,'behaviorHints':{'configurable':False}}
        write_json(stage/'manifest.json',manifest)
        write_json(stage/'status.json',{'built_utc':datetime.now(timezone.utc).isoformat(),
            'planned':len(planned),'original_planned':len(ALL),
            'browse_planned':40,'shahid_home_planned':len(build_shahid_home_rows()),
            'netflix_home_planned':len(build_netflix_home_rows()),'active':len(active),'catalogs':status})
        # Apps that support collections can use this as a planning guide; Stremio
        # protocol itself does not define nested catalog folders.
        folders={}
        for x in planned:
            folders.setdefault(x['group'],[]).append(x['id'])
        write_json(stage/'grouping-plan.json',folders)
        html='''<!DOCTYPE html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>My Nuvio Build N1</title><style>body{font:16px system-ui;background:#10131a;color:#f6f6f9;max-width:800px;margin:auto;padding:24px}a{color:#9bd1ff}code{background:#262d39;padding:8px;border-radius:6px;display:block;overflow-wrap:anywhere}</style><h1>My Nuvio · Build N1</h1><p>Catalog-only addon. Stream and subtitle addons remain separate.</p><h2>Install URL</h2><code>'''+BASE+'''/manifest.json</code><p><a href="manifest.json">Open manifest</a> · <a href="status.json">See feed status and skipped catalogs</a> · <a href="grouping-plan.json">Grouping plan</a></p><p>Official Netflix weekly country charts where mapped; other feeds are labeled by source. Exclusive claims need verified evidence. Turkish discovery rows do not confirm Arabic subtitles or playback availability. TMDB attribution: This product uses the TMDB API but is not endorsed or certified by TMDB.</p></html>'''
        (stage/'index.html').write_text(html,encoding='utf-8')
        previous = OUT.with_name(OUT.name + '.previous')
        if previous.exists():
            shutil.rmtree(previous)
        if OUT.exists():
            OUT.rename(previous)
        try:
            stage.rename(OUT)
        except Exception:
            if previous.exists():
                previous.rename(OUT)
            raise
        if previous.exists():
            shutil.rmtree(previous)
        print('BUILT',len(active),'active of',len(planned),'planned; manifest',BASE+'/manifest.json')

if __name__=='__main__':
    main()
