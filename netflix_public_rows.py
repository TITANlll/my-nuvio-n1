"""Snapshot of rows and titles published on Netflix Saudi's public pages.

Netflix does not publish a supported live API for these editorial rows. These
lists were transcribed from public sa-en genre pages on 2026-11-16. They are
source-labeled snapshots, NOT personalized Netflix home recommendations and
NOT daily Netflix rankings. TMDB is used strictly to resolve title IDs/art.
"""

SNAPSHOT_DATE = "2026-11-16"
ARAB_STORIES_URL = "https://www.netflix.com/sa-en/browse/genre/81727603"
ARABIC_URL = "https://www.netflix.com/sa-en/browse/genre/107456"
ONLY_URL = "https://www.netflix.com/sa-en/browse/genre/839338"

# Keep each movie/series row independent. The source's mixed-type rows are
# split by type to avoid producing Stremio entries with the wrong media type.
PUBLIC_ROWS = [
    ("netflix_sa_public_arab_series", "Arab Stories · International TV Shows",
     "series", ARAB_STORIES_URL, "International TV Shows", [
        "Roses & Chocolates", "Amr Ekhlaa", "AlRawabi School for Girls",
        "Catalog", "Alkhallat+: The Series", "Echoes of the Past",
        "In Blood", "Finding Ola", "Devil's Advocate",
        "Love Is Blind, Habibi", "Al Kabeer", "Franklin", "Whispers",
        "Masameer County", "Love Beyond The Name", "The Exchange",
        "Takki", "Till Death", "Dubai Bling", "Hard Broken",
        "Without Warning", "The Deep State", "Tahir's House",
        "Crashing Eid", "Dollar", "The Cage", "Jinn",
        "Abla Fahita: Drama Queen", "It's OK", "Saudi Pro League: Kickoff",
        "Khawatir", "Paranormal", "The Fastest", "Camel Quest",
    ]),
    ("netflix_sa_public_arab_movies", "Arab Stories · Arabic-Language Movies",
     "movie", ARAB_STORIES_URL, "Arabic-Language Movies", [
        "El Dashash", "Groom & Two Brides", "A Toxic Marriage", "Bahebak",
        "Sugar Daddy", "On the Go", "Esabet El Maahx", "Esaaf",
        "From the Ashes", "Shabab Albomb", "Maksoum", "Honeymoonish",
        "Sattar - The Return of the Legendary Slap", "Head to Head",
        "Bogeyman", "Siko Siko", "Marei the Primo", "Abu Nassab",
        "The Only Witness", "Hobal", "NAGA", "The Alexandrian",
        "Mosul", "Alkhallat+", "My Cousin and I", "Night Courier",
        "My Wife's Ex", "Tag", "Aamil Sefer",
        "The Humans and the Mongoose", "Alhamour H.A.",
        "Masameer Junior", "Flight 404", "Slave", "El Hareefa",
        "Charging Card", "El Ruby House",
    ]),
    ("netflix_sa_public_arab_tv_comedies", "Arabic · TV Comedies",
     "series", ARABIC_URL, "TV Comedies", [
        "Alkhallat+: The Series", "Amr Ekhlaa", "Love Beyond The Name",
        "Al Kabeer", "Catalog", "Masameer County", "The Cage",
        "Crashing Eid", "Tahir's House", "Abla Fahita: Drama Queen",
        "Love, Life & Everything in Between",
    ]),
    ("netflix_sa_public_arab_comedy_movies", "Arabic · Comedy Movies",
     "movie", ARABIC_URL, "Comedy Movies", [
        "Alzarfah: Escape from Hanhounia Hell", "Family Business",
        "Playing with children", "Love in Slow Motion", "Bahebak",
        "Groom & Two Brides", "The Fakenapping", "Esabet El Maahx",
        "Abu Nassab", "My Cousin and I", "On the Go",
        "Nabil El Gamil Plastic Surgeon", "Honeymoonish", "Sugar Daddy",
        "My Wife's Ex", "The Humans and the Mongoose",
        "Sattar - The Return of the Legendary Slap", "Taslim Ahali",
        "A Toxic Marriage", "Head to Head", "Marei the Primo",
        "Siko Siko", "Bogeyman", "Tag", "Esaaf",
        "Alhamour H.A.", "Shabab Albomb", "Alkhallat+",
    ]),
    ("netflix_sa_public_arab_action_movies", "Arabic · Action & Adventure Movies",
     "movie", ARAB_STORIES_URL, "Action & Adventure Movies", [
        "Sons of Rizk 3", "Shabab Albomb", "Esaaf", "Esabet El Maahx",
        "Bogeyman", "Mosul", "The Alexandrian", "Tag",
        "In Broad Daylight", "Hassan El Masry", "Africano",
        "Kira & El Gin", "No Turning Back, No Surrendering!", "Fireworks",
    ]),
    ("netflix_sa_public_arab_drama_movies", "Arabic · Drama Movies",
     "movie", ARABIC_URL, "Drama Movies", [
        "Bahebak", "Alhamour H.A.", "The Queen", "A Nose and Three Eyes",
        "The Matchmaker", "Tek Tek Boom", "Alzheimer's", "Hobal",
        "El Hareefa", "The Back Row", "El Ruby House", "Fever Dream",
        "Goodbye Julia", "Kira & El Gin", "Kamla", "Two Girls From Egypt",
        "Why Live It Solo?!", "People of the Cave", "19B",
        "Birds of the Nile", "Voy! Voy! Voy!", "Saify", "Hajjan",
        "Mikano", "Nezouh", "Inshallah a Boy", "The Sand Castle",
        "Within Sand", "C-Section", "Last Party in R Desert",
        "The Great Muse", "Basma", "Beirut Holdem",
        "The Snake and the Ladder", "Aziz's Dream",
        "Palestine 36", "Friends or Business",
    ]),
    ("netflix_sa_public_arab_weekend_series", "Arabic · Watch in One Weekend",
     "series", ARABIC_URL, "Watch in One Weekend", [
        "Roses & Chocolates", "Devil's Advocate", "The Exchange",
        "Echoes of the Past", "Whispers", "Masameer County",
        "The Deep State", "Hard Broken", "The Cage",
        "Without Warning", "Franklin", "Paranormal",
        "Saudi Pro League: Kickoff", "Dark Minds", "Khawatir",
    ]),
    ("netflix_sa_public_arab_emotional_movies", "Arabic · Emotional Movies",
     "movie", ARAB_STORIES_URL, "Emotional Movies", [
        "Hobal", "Flight 404", "Face to Face", "Hajjan",
        "Aziz's Dream", "Why Live It Solo?!", "Two Girls From Egypt",
        "Palestine 36", "Within Sand", "Mikano", "Birds of the Nile",
        "Basma", "The Magician", "Girls' Secrets", "All Roads Lead To Rome",
        "Captains of Za'atari", "Ghodwa", "Four Daughters",
        "The White Helmets",
    ]),
    ("netflix_sa_public_only_on_netflix", "Only on Netflix · Series",
     "series", ONLY_URL, "Your Next Watch", [
        "Squid Game", "AlRawabi School for Girls", "Manifest",
        "Bon Appétit, Your Majesty", "Peaky Blinders", "The Witcher",
        "The Gentlemen", "Anne with an E", "Elite", "Lucifer",
        "El Chapo", "Alkhallat+: The Series", "Emily in Paris",
        "Ozark", "Outer Banks", "Weak Hero", "Alice in Borderland",
        "All of Us Are Dead", "Orange Is the New Black",
        "Another Self", "The Diplomat", "Love Next Door",
        "When Life Gives You Tangerines", "Alchemy of Souls", "Dark",
        "Money Trap", "Crash Landing on You",
    ]),
]


def build_public_netflix_rows():
    output = []
    for identifier, name, kind, url, source_row, titles in PUBLIC_ROWS:
        output.append({
            "id": identifier,
            "name": name + " (Netflix public page)",
            "type": kind,
            "group": "Netflix Saudi",
            "mode": "netflix_public",
            "titles": list(titles),
            "source_url": url,
            "source_row": source_row,
            "snapshot_date": SNAPSHOT_DATE,
        })
    return output
