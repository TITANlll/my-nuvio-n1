"""Read the title identifiers and rows published on Netflix Saudi's public pages."""

import ast
import json
import re
from dataclasses import dataclass, replace
from html.parser import HTMLParser
from urllib.parse import urlsplit


@dataclass(frozen=True)
class NetflixTitle:
    name: str
    netflix_id: int | None = None
    year: int | None = None
    poster: str | None = None
    kind: str | None = None


# Netflix titles were matched to IMDb by year, credits and title on the two
# services. A known ID also resolves localized titles and releases with aliases.
VERIFIED_IMDB = {
    82078375: ('movie', 'tt38793125'),  # Collision Course (2026)
    60020557: ('movie', 'tt0252503'),   # Heist (2001)
    81952372: ('movie', 'tt43738050'),  # Crazy Rich, Incredibly Broke
    70226288: ('movie', 'tt0903624'),   # The Hobbit: An Unexpected Journey
    83042404: ('movie', 'tt41082370'),  # Shabab El Bomb 3
    82046358: ('movie', 'tt37458193'),  # My Best Friend (2026)
    81913551: ('movie', 'tt37961714'),  # Surviving Hurricane Otis
    81757047: ('movie', 'tt31049299'),  # Animals (2026)
    814862: ('movie', 'tt0107711'),     # Nowhere to Run (1993)
    70305930: ('movie', 'tt2310332'),   # The Hobbit: The Battle of the Five Armies
    80994082: ('series', 'tt2531336'),  # Lupin (2021)
    81772075: ('series', 'tt29625288'), # Akka: The Protectors
    81925711: ('series', 'tt36838527'), # Obsess
    82915757: ('series', 'tt40238655'), # Jinn Wedding
    81997887: ('series', 'tt36458668'), # Dead-End Job
    82682379: ('series', 'tt39328047'), # Doctor X: Mafia in White
    81944880: ('series', 'tt42767924'), # A Couple of Lies
    82682433: ('series', 'tt39201866'), # 100 Days of Deception
    82135610: ('movie', 'tt20877986'),  # Sons of Rizk 3
    81767085: ('movie', 'tt32893080'),  # Esabet El Maahx
    81041495: ('movie', 'tt9252468'),   # Mosul (2019)
    82065716: ('movie', 'tt34446945'),  # Esaaf
    81908699: ('movie', 'tt31048146'),  # The Alexandrian
    81716255: ('movie', 'tt27881699'),  # Bogeyman (2023)
    81908693: ('movie', 'tt10935956'),  # Kira & El Gin
}

CHART_DATA = re.compile(
    r"netflix\.reactContext\.models\.graphql\s*=\s*JSON\.parse\(('(?:\\.|[^'\\])*')\)",
    re.DOTALL,
)
TITLE_LINK = re.compile(r'(?:https://www\.netflix\.com)?/sa-en/title/([0-9]+)\Z')
NETFLIX_IMAGE_HOST = re.compile(r'(?:dnm\.nflximg\.net|occ-[0-9-]+\.\d+\.nflxso\.net)\Z')
CARD_IMAGE = re.compile(r'\bbackground-image\s*:\s*url\(([^)]+)\)')


def netflix_image_url(value):
    if not isinstance(value, str):
        return None
    url = urlsplit(value)
    if (url.scheme == 'https' and NETFLIX_IMAGE_HOST.fullmatch(url.netloc)
            and url.path.startswith(('/api/v6/', '/dnm/api/v6/', '/dna/')) and not url.fragment):
        return value
    return None


def _chart_image(artwork):
    for version in ('storyArt', 'sdpArt'):
        art = artwork.get(version) or {}
        for key, images in art.items():
            if key.startswith('urlsSized(') and isinstance(images, list) and images:
                if poster := netflix_image_url(images[0].get('url')):
                    return poster
    return None


def _page_data(html):
    match = CHART_DATA.search(html)
    if not match:
        return {}
    return json.loads(ast.literal_eval(match[1]))['data']


def parse_saudi_chart(html, kind, week):
    """Read identities for the same country, week and ranks as the official TSV."""
    body = _page_data(html)
    category = 'MOVIES' if kind == 'movie' else 'SERIES'
    chart = {}
    conflicting_ranks = set()
    for item in body.values():
        if not isinstance(item, dict) or item.get('__typename') != 'PulseTop10ItemEntity':
            continue
        top = item.get('top10') or {}
        rank = top.get('weeklyRank')
        if (top.get('weekEndDate') != week or top.get('category') != category
                or rank not in range(1, 11)):
            continue
        if not any(c.get('countryId') == 'SA' and c.get('rank') == rank
                   for c in (item.get('countryRanks') or [])):
            continue
        video = item.get('top10Video') or {}
        ranked_name = video.get('title')
        if not ranked_name:
            continue
        parent = video.get('parentShow') or {}
        displayed = (item.get('displayVideo') or {}).get('video') or {}
        parent_id = (displayed.get('parentShow') or {}).get('videoId')
        netflix_id = parent_id if parent else video.get('videoId')
        year = video.get('releaseYear') if kind == 'movie' or video.get('number') == 1 else None
        title = NetflixTitle(parent.get('title') or ranked_name, netflix_id, year,
                             _chart_image(item.get('artwork') or {}))
        if rank in chart and chart[rank][1].netflix_id != title.netflix_id:
            conflicting_ranks.add(rank)
        chart[rank] = (ranked_name, title)
    return {rank: value for rank, value in chart.items() if rank not in conflicting_ranks}


class _GenreRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = {}
        self.depth = 0
        self.heading = ''
        self.in_heading = False
        self.card = None
        self.card_poster = None
        self.titles = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'div' and (self.depth or attrs.get('data-uia') == 'locp-collections-title-row'):
            self.depth += 1
        if not self.depth:
            return
        if tag == 'h2':
            self.in_heading = True
        if tag == 'a':
            match = TITLE_LINK.fullmatch(attrs.get('href') or '')
            label = attrs.get('aria-label') or ''
            if match and label.startswith('Go to '):
                self.card = (label.removeprefix('Go to ').strip(), int(match[1]))
        if self.card and not self.card_poster:
            image = CARD_IMAGE.search(attrs.get('style') or '')
            if image:
                self.card_poster = netflix_image_url(image[1].strip(' \"\''))
            elif tag == 'img':
                self.card_poster = netflix_image_url(attrs.get('src'))

    def handle_data(self, data):
        if self.in_heading:
            self.heading += data

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag == 'h2':
            self.in_heading = False
        if tag == 'a' and self.card:
            name, netflix_id = self.card
            if name:
                self.titles.setdefault(netflix_id, NetflixTitle(name, netflix_id, poster=self.card_poster))
            self.card = self.card_poster = None
        if tag == 'div':
            self.depth -= 1
            if not self.depth:
                heading = ' '.join(self.heading.split())
                if heading and self.titles:
                    self.rows.setdefault(heading, list(self.titles.values()))
                self.heading = ''
                self.titles = {}


def parse_saudi_genre_rows(html):
    parser = _GenreRows()
    parser.feed(html)
    parser.close()
    kinds = {'Movie': 'movie', 'Show': 'series'}
    by_id = {
        item.get('videoId'): kinds[item['__typename']]
        for item in _page_data(html).values()
        if isinstance(item, dict) and item.get('__typename') in kinds
    }
    return {
        heading: [replace(title, kind=by_id.get(title.netflix_id)) for title in titles]
        for heading, titles in parser.rows.items()
    }
