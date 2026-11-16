"""Netflix Saudi public row definitions and dated fallback selections."""

SNAPSHOT_DATE = "2026-11-16"
ARAB_STORIES_URL = "https://www.netflix.com/sa-en/browse/genre/81727603"
ARABIC_URL = "https://www.netflix.com/sa-en/browse/genre/107456"
ONLY_URL = "https://www.netflix.com/sa-en/browse/genre/839338"
FAMILY_URL = "https://www.netflix.com/sa-en/browse/genre/783"
KIDS_TV_URL = "https://www.netflix.com/sa-en/browse/genre/27346"

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
    ("netflix_sa_public_arab_action_movies", "Arabic · Action Movies",
     "movie", ARABIC_URL, "Action Movies", [
        ("Sons of Rizk 3", 82135610), ("Esabet El Maahx", 81767085),
        ("Mosul", 81041495), ("Esaaf", 82065716),
        ("The Alexandrian", 81908699), "Tag", ("Bogeyman", 81716255),
        "العنكبوت", "Fireworks", "In Broad Daylight", "Hassan El Masry",
        ("Kira & El Gin", 81908693), "No Turning Back, No Surrendering!",
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
    ("netflix_sa_public_family_movies", "Children & Family Movies",
     "movie", FAMILY_URL, "Your Next Watch", [
        "Swapped", "Sing 2", "Sing", "Sonic the Hedgehog 3", "The Witches",
        "How to Train Your Dragon: The Hidden World", "We Can Be Heroes",
        "Ice Age 4: Continental Drift", "KPop Demon Hunters", "The Wild Robot",
        "Shrek", "The Addams Family", "That Christmas", "How to Train Your Dragon",
        "Roald Dahl's Matilda The Musical", "How the Grinch Stole Christmas",
        "The Sea Beast", "Bee Movie", "The Angry Birds Movie",
        "How to Train Your Dragon 2", "Howl’s Moving Castle", "Shrek 2",
        "A Boy Called Christmas", "Wish Dragon", "Dr. Seuss' The Grinch",
        "Ponyo", "Rango", "Back to the Outback", "The Princess Switch",
    ]),
    ("netflix_sa_public_kids_series", "Kids TV Shows",
     "series", KIDS_TV_URL, "Your Next Watch", [
        "The Amazing World of Gumball", "SpongeBob SquarePants",
        "Avatar: The Last Airbender", "Miraculous: Tales of Ladybug & Cat Noir",
        "The Smurfs", "Teen Titans Go!", "Masha and the Bear", "Victorious",
        "Henry Danger", "Ms. Rachel", "Grizzy and the Lemmings",
        "ALVINNN!!! And the Chipmunks", "LEGO Ninjago: Masters of Spinjitzu",
        "The Worst Witch", "The Thundermans", "Sam & Cat", "PAW Patrol",
        "Dragons: Race to the Edge", "Shaun the Sheep: Adventures from Mossy Bottom",
        "Power Rangers Ninja Steel", "Barbie Life in the Dreamhouse",
        "Trollhunters: Tales of Arcadia", "Free Rein",
        "Kung Fu Panda: The Dragon Knight", "Peppa Pig", "The InBESTigators",
        "Sonic Prime", "The Boss Baby: Back in Business", "The Cuphead Show!",
        "Shaun the Sheep", "Carmen Sandiego", "Hilda",
    ]),
    ("netflix_sa_public_arab_new_movies", "Arabic · New on Netflix Movies",
     "movie", ARABIC_URL, "New on Netflix", []),
    ("netflix_sa_public_arab_new_series", "Arabic · New on Netflix Series",
     "series", ARABIC_URL, "New on Netflix", []),
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
            "minimum_items": 1 if source_row == "New on Netflix" else 5,
        })
    return output
