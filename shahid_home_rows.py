"""Shahid-homepage-inspired, region-filtered discovery rows.

These are NOT Shahid's proprietary rankings or editorial recommendations.
The public Shahid homepage changes by region, account and campaign.
Use separately sourced, attributable TMDB/JustWatch discovery instead.
"""


def build_shahid_home_rows():
    """Return additive rows that can be rebuilt from public provider metadata."""
    common = {'include_adult': 'false'}
    definitions = [
        (
            'shahid_home_arabic_drama', 'شاهد · دراما عربية (حسب TMDB)', 'series',
            {'sort_by': 'popularity.desc', 'with_original_language': 'ar',
             'with_genres': '18'},
            'Arabic-language drama listed for Shahid Saudi by TMDB/JustWatch; '
            'TMDB popularity, not Shahid editorial or audience ranking',
        ),
        (
            'shahid_home_egyptian_series', 'شاهد · مسلسلات مصرية (حسب TMDB)', 'series',
            {'sort_by': 'popularity.desc', 'with_origin_country': 'EG'},
            'Egyptian-produced series listed for Shahid Saudi by TMDB/JustWatch; '
            'TMDB popularity, not an official Shahid chart',
        ),
        (
            'shahid_home_turkish_movies', 'شاهد · أفلام تركية (حسب TMDB)', 'movie',
            {'sort_by': 'popularity.desc', 'with_original_language': 'tr'},
            'Turkish-language films listed for Shahid Saudi by TMDB/JustWatch; '
            'Arabic subtitle availability is not guaranteed',
        ),
        (
            'shahid_home_syrian_classics', 'شاهد · كلاسيكيات سورية (حسب TMDB)', 'series',
            {'sort_by': 'popularity.desc', 'with_origin_country': 'SY',
             'first_air_date.lte': '2016-12-31'},
            'Syrian series first aired by the end of 2016 and listed for Shahid '
            'Saudi; editorial classics approximation, not Shahid curation',
        ),
        (
            'shahid_home_saudi_series', 'شاهد · مسلسلات سعودية (حسب TMDB)', 'series',
            {'sort_by': 'popularity.desc', 'with_origin_country': 'SA'},
            'Saudi-produced series listed for Shahid Saudi by TMDB/JustWatch; '
            'not a claim of exclusive rights or official ranking',
        ),
        (
            'shahid_home_arabic_comedy', 'شاهد · كوميديا عربية (حسب TMDB)', 'series',
            {'sort_by': 'popularity.desc', 'with_original_language': 'ar',
             'with_genres': '35'},
            'Arabic-language comedy listed for Shahid Saudi by TMDB/JustWatch; '
            'TMDB popularity, not Shahid viewing statistics',
        ),
    ]
    return [
        {'id': identifier, 'name': name, 'type': kind,
         'group': 'Shahid Arabic Exclusives', 'mode': 'discover_provider',
         'provider': 'shahid', 'params': {**common, **filters},
         'note': note}
        for identifier, name, kind, filters, note in definitions
    ]
