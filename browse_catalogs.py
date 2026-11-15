"""Turn the saved browsing labels into source-filtered static catalogs."""
import re


MOVIE_GENRES = {
    'Action': '28', 'Comedy': '35', 'Romance': '10749', 'Horror': '27',
    'Mystery': '9648', 'Thriller': '53', 'Sci-Fi': '878', 'Fantasy': '14',
    'Adventure': '12', 'Drama': '18', 'Crime': '80', 'Music': '10402',
}
TV_GENRES = {
    'Action': '10759', 'Comedy': '35', 'Mystery': '9648',
    'Sci-Fi': '10765', 'Fantasy': '10765', 'Adventure': '10759',
    'Drama': '18', 'Crime': '80',
}
# TMDB combines some TV genres and has no TV genre for several movie labels.
# Keywords narrow combined genres or supply the missing classification.
TV_KEYWORDS = {
    'Action': 'action|martial arts|superhero',
    'Adventure': 'adventure|expedition|treasure hunt',
    'Sci-Fi': 'science fiction|space travel|time travel',
    'Fantasy': 'fantasy|magic|supernatural',
    'Romance': 'romance|romantic comedy', 'Horror': 'horror|supernatural horror',
    'Thriller': 'thriller|psychological thriller', 'Music': 'music|musician|musical',
}


def mood_filters(label, kind):
    movie = kind == 'movie'
    filters = {
        'Feel-Good': ({'with_genres': '35|10751', 'vote_average.gte': '6.5'}, None),
        'Mind-Bending': ({'with_genres': '878|9648' if movie else '10765|9648'},
                         'time travel|alternate reality|psychological thriller'),
        'Dark & Suspenseful': ({'with_genres': '53|80|9648' if movie else '80|9648',
                               'without_genres': '35,10751'}, None),
        'Light & Funny': ({'with_genres': '35', 'with_runtime.lte': '120' if movie else '45',
                          'without_genres': '27,53' if movie else '80,9648'}, None),
        'Emotional Stories': ({'with_genres': '18|10749' if movie else '18',
                              'vote_average.gte': '7'}, None),
        'High-Adrenaline': ({'with_genres': '28|12' if movie else '10759'}, None),
        'Easy Watching': ({'with_genres': '35|10751',
                           'with_runtime.lte': '110' if movie else '35',
                           'without_genres': '27,53' if movie else '80,9648'}, None),
        'Twists & Mysteries': ({'with_genres': '9648|53' if movie else '9648'},
                              'plot twist|murder mystery|mystery'),
    }
    return filters[label]


def build_browse_catalogs(labels, today):
    """One movie and one series row per saved label; never modify the N1 plan."""
    rows = []
    for group in ('Genres', 'Moods'):
        for label in labels[group]:
            for kind in ('movie', 'series'):
                params = {'sort_by': 'popularity.desc', 'include_adult': 'false',
                          'vote_count.gte': '20',
                          'primary_release_date.lte' if kind == 'movie' else 'first_air_date.lte': str(today)}
                keyword = None
                if group == 'Genres':
                    genre = (MOVIE_GENRES if kind == 'movie' else TV_GENRES).get(label)
                    if genre:
                        params['with_genres'] = genre
                    if kind == 'series':
                        keyword = TV_KEYWORDS.get(label)
                    note = 'TMDB genre/keyword selection; not streaming-service availability'
                else:
                    filters, keyword = mood_filters(label, kind)
                    params.update(filters)
                    note = 'Editorial mood selection using TMDB genres/keywords; moods are subjective, not age ratings'
                slug = re.sub(r'[^a-z0-9]+', '_', label.lower()).strip('_')
                section = 'Genre' if group == 'Genres' else 'Mood'
                row = {'id': f'browse_{section.lower()}_{slug}_{kind}',
                       'name': f'{section} · {label} · {"Movies" if kind == "movie" else "Series"}',
                       'type': kind, 'group': group,
                       'mode': 'discover_keyword' if keyword else 'discover',
                       'params': params, 'note': note, 'browse_label': label}
                if keyword:
                    row['keyword'] = keyword
                rows.append(row)
    return rows
