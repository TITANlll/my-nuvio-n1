"""Add free Netflix Saudi discovery rows without implying official daily ranks.

All rows use TMDB/JustWatch's Netflix subscription availability filter in
Saudi Arabia. Popularity, ratings and original premiere dates are TMDB data.
"""


def build_netflix_home_rows():
    common = {
        'with_watch_providers': '8',
        'watch_region': 'SA',
        'with_watch_monetization_types': 'flatrate',
        'include_adult': 'false',
    }
    definitions = [
        (
            'netflix_sa_popular_series', 'Netflix Saudi · Popular Series (TMDB)',
            'series', {'sort_by': 'popularity.desc'},
            'Netflix Saudi availability based on TMDB/JustWatch; sorted by TMDB popularity, not Netflix viewing numbers',
            None,
        ),
        (
            'netflix_sa_highly_rated_movies', 'Netflix Saudi · Highly Rated Movies (TMDB)',
            'movie', {'sort_by': 'vote_average.desc', 'vote_count.gte': '100'},
            'Top rated using TMDB votes (at least 100); not a Netflix Top 10 or audience chart',
            None,
        ),
        (
            'netflix_sa_highly_rated_series', 'Netflix Saudi · Highly Rated Series (TMDB)',
            'series', {'sort_by': 'vote_average.desc', 'vote_count.gte': '100'},
            'Top rated using TMDB votes (at least 100); not a Netflix Top 10 or audience chart',
            None,
        ),
        (
            'netflix_sa_recent_series', 'Netflix Saudi · Recently Premiered Series (TMDB)',
            'series', {'sort_by': 'first_air_date.desc'},
            'Shows first premiered during the last 2 years and listed on Netflix Saudi; NOT newly added to Netflix',
            730,
        ),
        (
            'netflix_sa_arabic_series', 'Netflix Saudi · Arabic Series (TMDB)',
            'series', {'sort_by': 'popularity.desc', 'with_original_language': 'ar'},
            'Originally Arabic-language series listed on Netflix Saudi; ordered by TMDB popularity',
            None,
        ),
        (
            'netflix_sa_crime_series', 'Netflix Saudi · Crime Series (TMDB)',
            'series', {'sort_by': 'popularity.desc', 'with_genres': '80'},
            'Crime series listed on Netflix Saudi; ordered by TMDB popularity, not Netflix viewing rank',
            None,
        ),
    ]
    rows = []
    for identifier, title, kind, filters, note, days in definitions:
        row = {'id': identifier, 'name': title, 'type': kind,
               'group': 'Netflix Saudi', 'mode': 'netflix_discover',
               'params': {**common, **filters}, 'note': note}
        if days:
            row['release_window_days'] = days
        rows.append(row)
    return rows
