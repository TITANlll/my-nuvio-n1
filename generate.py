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
import sys
import time
import unicodedata
from collections import defaultdict
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError

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


def fetch(url, *, headers=None, retries=3):
    for attempt in range(retries):
        try:
            with urlopen(Request(url, headers={**{'User-Agent':'MyNuvioN1/1.0 (+personal catalog)'}, **(headers or {})}), timeout=40) as r:
                return r.read()
        except (OSError, HTTPError) as e:
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
    e = tmdb(f'/{kind}/{tmdb_id}/external_ids')
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


def fetch_keyword(spec, **discovery_options):
    params = dict(spec.get('params', {}))
    keywords=[]
    for phrase in spec['keyword'].split('|'):
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


def get_netflix_rows():
    """Get latest SA country movie and TV chart rows from official TSV file.

    Do not use TMDB popularity as a substitute for official rank. Rankings
    preserve Netflix's original rank; failed title matches are simply omitted.
    """
    url='https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv'
    b=fetch(url)
    reader=csv.DictReader(io.StringIO(b.decode('utf-8-sig')),delimiter='\t')
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
        by[(r.get('week'),kind)].append(r)
    output={}
    for kind in ('movie','series'):
        weeks = [week for week,k in by if k==kind]
        if not weeks:
            output[kind]=[]
            continue
        last=max(weeks)
        recent=sorted(by[(last,kind)],key=lambda r:int(r['weekly_rank']))
        collected=[]
        for r in recent:
            title=r['show_title'].strip()
            target='movie' if kind=='movie' else 'tv'
            matches=tmdb('/search/'+target,{'query':title}).get('results',[])
            # Only accept reliable name matches; do not invent a match.
            expected=norm(title)
            strong=[]
            for cand in matches[:10]:
                actual=norm(cand.get('title' if target=='movie' else 'name',''))
                if expected and actual==expected:
                    strong.append(cand)
            # A title shared by multiple productions is ambiguous without
            # a year in Netflix's TSV. Skip rather than misidentify it.
            if len(strong)!=1:
                continue
            best=strong[0]
            p=preview(target,best,source_rank=r['weekly_rank'],source_week=last)
            if p:
                collected.append(p)
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
        return rows,('Awaiting verified entries and source evidence' if not rows else '')
    if mode=='netflix_official':
        rows=(netflix or {}).get(spec['kind'],[])
        return rows,('Official Netflix data unavailable or unmatched' if not rows else '')
    if mode in ('discover','discover_keyword'):
        if spec['id']=='netflix_sa_new':
            spec={**spec,'params':{**spec['params'],
                'primary_release_date.gte':str(TODAY-timedelta(days=120)),
                'primary_release_date.lte':str(TODAY)}}
        kind,items=(fetch_discover(spec) if mode=='discover' else fetch_keyword(spec))
        rows=[p for x in items if (p:=preview(kind,x,verified_note=spec.get('note')))][:LIMIT]
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
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    # Netflix top ranks: if the upstream TSV fails, do NOT relabel TMDB as the Netflix Top 10.
    try:
        netflix=get_netflix_rows()
    except Exception as err:
        print('Netflix official source unavailable:',safe_error(err),flush=True)
        netflix={}
    active=[]
    status=[]
    for spec in ALL:
        try:
            rows,reason=catalog(spec,netflix)
            if rows:
                path=OUT/'catalog'/spec['type']/(spec['id']+'.json')
                write_json(path,{'metas':rows})
                active.append({'type':spec['type'],'id':spec['id'],'name':spec['name']})
                state='active'
            else:
                state='external' if spec['mode']=='external' else 'held'
            status.append({'id':spec['id'],'type':spec['type'],'section':spec['group'],'catalog':spec['name'],'status':state,
                           'entries':len(rows or []),'reason':reason})
            print(f"{state:8} {spec['name']}: {len(rows or [])}",flush=True)
        except Exception as err:
            status.append({'id':spec['id'],'type':spec['type'],'section':spec['group'],'catalog':spec['name'],
                           'status':'held','entries':0,'reason':safe_error(err)})
            print('HELD',spec['name'],safe_error(err),flush=True)
    if not active:
        raise SystemExit('No catalogs could be populated; keeping previous website untouched')
    manifest={'id':'com.mynuvio.buildn1','version':'1.1.0','name':'My Nuvio · Build N1',
      'description':'Personal discovery catalogs. Genuine Netflix weekly positions, TMDB classifications, verified-only exclusives. No playback or subtitle streams. BetterPosters remains separate.',
      'types':['movie','series'],'resources':['catalog'],
      'catalogs':active,'behaviorHints':{'configurable':False}}
    write_json(OUT/'manifest.json',manifest)
    write_json(OUT/'status.json',{'built_utc':datetime.now(timezone.utc).isoformat(),
        'planned':len(ALL),'active':len(active),'catalogs':status})
    # Apps that support collections can use this as a planning guide; Stremio
    # protocol itself does not define nested catalog folders.
    folders={}
    for x in ALL:
        folders.setdefault(x['group'],[]).append(x['id'])
    write_json(OUT/'grouping-plan.json',folders)
    html='''<!DOCTYPE html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>My Nuvio Build N1</title><style>body{font:16px system-ui;background:#10131a;color:#f6f6f9;max-width:800px;margin:auto;padding:24px}a{color:#9bd1ff}code{background:#262d39;padding:8px;border-radius:6px;display:block;overflow-wrap:anywhere}</style><h1>My Nuvio · Build N1</h1><p>Catalog-only addon. Stream and subtitle addons remain separate.</p><h2>Install URL</h2><code>'''+BASE+'''/manifest.json</code><p><a href="manifest.json">Open manifest</a> · <a href="status.json">See feed status and skipped catalogs</a> · <a href="grouping-plan.json">Grouping plan</a></p><p>Official Netflix weekly country charts where mapped; other feeds are labeled by source. Exclusive and Arabic-subtitle-only catalogs are held until verified. TMDB attribution: This product uses the TMDB API but is not endorsed or certified by TMDB.</p></html>'''
    (OUT/'index.html').write_text(html,encoding='utf-8')
    print('BUILT',len(active),'active of',len(ALL),'planned; manifest',BASE+'/manifest.json')

if __name__=='__main__':
    main()
