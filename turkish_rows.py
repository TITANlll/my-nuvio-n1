"""Turkish network rows and the weekly broadcast chart."""
from datetime import date, datetime, timedelta
from pathlib import Path
import json
from html import unescape
import re
import unicodedata

WEEKLY_URL = 'https://turkish.vartolo.net/weekly-recap/'
# Resolve the network from a known production, checking its name and country.
NETWORKS = {'atv': ('ATV', 'Kuruluş Osman'), 'kanal_d': ('Kanal D', 'Yargı'),
            'show_tv': ('Show TV', 'Kızılcık Şerbeti'), 'star_tv': ('Star TV', 'Yalı Çapkını'),
            'trt_1': ('TRT 1', 'Gönül Dağı')}
ADDITIONS = {'weekly_top10': 'Top 10 This Week', 'coming_soon': 'Coming Soon',
             'on_tv': 'On TV This Week', **{k: v[0] for k, v in NETWORKS.items()},
             'originals': 'Streaming Originals'}
ORDER = ['weekly_top10', 'new_episodes', 'new_series', 'coming_soon', 'on_tv',
         *NETWORKS, 'originals', 'top_movies', 'new_movies']


def definitions():
    return [dict(id='turkish_' + key, name=name, group='Turkish Content',
                 type='series', mode='turkish_networks', section=key)
            for key, name in ADDITIONS.items()]


def folded(text):
    text = unicodedata.normalize('NFKD', text.casefold().replace('ı', 'i'))
    return ''.join(c for c in text if c.isalnum())


def weekly_chart(page, today):
    date_match = re.search(r'\b(?:\d{1,2}(?: [A-Za-z]+)?\s*[-–]\s*)(\d{1,2} [A-Za-z]+ \d{4})\b', page)
    if not date_match:
        return []
    week = datetime.strptime(date_match[1], '%d %B %Y').date()
    if not 0 <= (today - week).days <= 14:
        return []
    rows = []
    for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>', page, re.S | re.I):
        cells = [unescape(re.sub('<[^>]*>', '', c)).strip()
                 for c in re.findall(r'<td\b[^>]*>(.*?)</td>', tr, re.S | re.I)]
        if len(cells) == 6 and cells[0].isdigit() and 1 <= int(cells[0]) <= 10:
            rows.append((int(cells[0]), cells[1], cells[2], week.isoformat()))
    return rows if [r[0] for r in rows] == list(range(1, len(rows) + 1)) else []


def exact_show(title, tmdb):
    matches = [x for x in tmdb('/search/tv', {'query': title, 'language': 'tr-TR'}).get('results', [])
               if x.get('original_language') == 'tr' and folded(x.get('original_name', '')) == folded(title)]
    return matches[0] if len(matches) == 1 else None


def row(spec, today, fetch, tmdb, discover, preview, limit, numbered_poster):
    section = spec['section']
    if section == 'weekly_top10':
        saved = json.loads((Path(__file__).parent / 'data/turkish_weekly_ratings.json').read_text())
        saved_week = date.fromisoformat(saved['week_ending'])
        identities = {folded(r['series']): r for r in saved['entries']}
        try:
            chart = weekly_chart(fetch(WEEKLY_URL, timeout=10, retries=2).decode(), today)
        except OSError:
            chart = []
        if 0 <= (today - saved_week).days <= 14 and (not chart or chart[0][3] < saved_week.isoformat()):
            chart = [(r['rank'], r['series'], r['network'], saved_week.isoformat())
                     for r in saved['entries'] if 1 <= r['rank'] <= 10]
        result = []
        for rank, title, channel, week in chart:
            identity = identities.get(folded(title), {})
            imdb = identity.get('imdb_id')
            show = None
            if imdb:
                matches = tmdb('/find/' + imdb, {'external_source': 'imdb_id'}).get('tv_results', [])
                if len(matches) == 1 and matches[0].get('original_language') == 'tr':
                    show = matches[0]
            if not show and identity.get('tmdb_id'):
                candidate = tmdb('/tv/' + str(identity['tmdb_id']))
                if (candidate.get('original_language') == 'tr'
                        and folded(candidate.get('original_name', '')) == folded(title)):
                    show = candidate
            if not show:
                show = exact_show(title, tmdb)
            if show and (show.get('poster_path') or show['id'] == identity.get('tmdb_id')):
                verified_imdb = imdb if show['id'] == identity.get('tmdb_id') else None
                item = preview('tv', show, imdb_id=verified_imdb, source_rank=rank, source_week=week,
                               verified_note='Turkish weekly TOTAL ratings · ' + channel)
                if item:
                    item['poster'] = numbered_poster(show['id'], 'series', rank=rank)
                    result.append(item)
        return result, '' if result else 'Awaiting a dated chart with matched series'

    params = {'with_original_language': 'tr', 'with_origin_country': 'TR', 'sort_by': 'popularity.desc'}
    if section in NETWORKS:
        name, seed = NETWORKS[section]
        show = exact_show(seed, tmdb)
        networks = tmdb('/tv/' + str(show['id'])).get('networks', []) if show else []
        ids = [str(n['id']) for n in networks if folded(n['name']) == folded(name) and n.get('origin_country') == 'TR']
        if not ids:
            return [], 'Awaiting confirmed broadcaster identity'
        params['with_networks'] = '|'.join(ids)
    elif section == 'originals':
        # Originating networks in TV metadata, distinct from regional watch providers.
        params['with_networks'] = '213|1024'
    elif section == 'coming_soon':
        params.update({'first_air_date.gte': str(today + timedelta(days=1)),
                       'first_air_date.lte': str(today + timedelta(days=180)), 'sort_by': 'first_air_date.asc'})
    elif section == 'on_tv':
        params.update({'air_date.gte': str(today), 'air_date.lte': str(today + timedelta(days=6)),
                       'first_air_date.lte': str(today)})
    _, shows = discover({'type': 'series', 'params': params})
    items = []
    for show in shows:
        if show.get('original_language') != 'tr':
            continue
        note = spec['name']
        if section == 'on_tv':
            episode = tmdb('/tv/' + str(show['id'])).get('next_episode_to_air') or {}
            when = episode.get('air_date', '')
            if not str(today) <= when <= params['air_date.lte']:
                continue
            note = 'Next episode · ' + when
        if section == 'coming_soon':
            note = 'Scheduled premiere · ' + show['first_air_date']
        item = preview('tv', show, verified_note=note)
        if item and all(i['id'] != item['id'] for i in items):
            items.append(item)
        if len(items) >= limit:
            break
    if section == 'on_tv':
        items.sort(key=lambda x: x['description'])
    return items, '' if items else 'No matched titles in the current window'
