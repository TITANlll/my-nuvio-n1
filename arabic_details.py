"""Detail pages for Arabic catalog titles with a known trailer."""
from datetime import date


def title_details(item, tmdb_id, tmdb):
    kind = 'movie' if item['type'] == 'movie' else 'tv'
    path = f'/{kind}/{tmdb_id}'
    record = tmdb(path, {'append_to_response': 'external_ids,credits,images',
                         'include_image_language': 'en,ar,null'})
    if record.get('external_ids', {}).get('imdb_id') != item['id']:
        return None
    meta = {k: item[k] for k in ('id', 'name', 'type', 'poster', 'background',
                                  'releaseInfo', 'trailers') if k in item}
    meta['trailerStreams'] = [{'ytId': t['source'], 'title': 'Official Trailer'}
                              for t in item['trailers']]
    meta['description'] = record.get('overview') or item.get('description', '')
    meta['genres'] = [g['name'] for g in record.get('genres', [])]
    credits = record.get('credits', {})
    meta['cast'] = [c['name'] for c in credits.get('cast', [])[:20]]
    meta['director'] = [c['name'] for c in credits.get('crew', []) if c.get('job') == 'Director']
    if record.get('status'):
        meta['status'] = record['status']
    logos = record.get('images', {}).get('logos', [])
    if logos:
        meta['logo'] = 'https://image.tmdb.org/t/p/w500' + logos[0]['file_path']
    if kind == 'tv':
        meta['videos'] = []
        for season in record.get('seasons', []):
            number = season['season_number']
            episodes = tmdb(f'{path}/season/{number}').get('episodes', [])
            if len(episodes) < season['episode_count']:
                return None
            for ep in episodes:
                episode = ep['episode_number']
                video = {'id': f"{item['id']}:{number}:{episode}", 'season': number,
                         'episode': episode, 'title': ep.get('name') or f'Episode {episode}',
                         'overview': ep.get('overview', '')}
                if ep.get('air_date'):
                    video['released'] = date.fromisoformat(ep['air_date']).isoformat() + 'T00:00:00Z'
                if ep.get('still_path'):
                    video['thumbnail'] = 'https://image.tmdb.org/t/p/w780' + ep['still_path']
                meta['videos'].append(video)
        if not meta['videos']:
            return None
    return meta
