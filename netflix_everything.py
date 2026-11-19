"""Netflix-only poster artwork inspired by the TopToday *layout* reference.

Matches the user-supplied reference's placement of a large translucent number
at the upper left, a small black Netflix-service icon at the upper right, and
a full-width editorial ribbon at the bottom. The visuals are original artwork,
not fetched from or represented as TopToday's API. Labels are evidence-based:
no invented season status, streaming premiere, or Netflix Originals claims.
Artwork falls back to its original URL if image generation fails.
"""
from __future__ import annotations

import io
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from netflix_sources import netflix_image_url

POSTER_SIZE = (500, 750)
IMAGE_BASE = "https://image.tmdb.org"
IMDB_ID = re.compile(r"tt[0-9]{5,12}\Z")
MOVIE_IMAGE = re.compile(r"/t/p/w[0-9]+/[a-zA-Z0-9_./-]+[.](?:jpg|jpeg|png|webp)\Z")


def safe_tmdb_image_url(url):
    """Only request public TMDB image CDN posters (no private/addon URLs)."""
    parsed = urlsplit(url or "")
    if parsed.scheme != "https" or parsed.netloc != "image.tmdb.org":
        return False
    return bool(MOVIE_IMAGE.fullmatch(parsed.path)) and not parsed.query


def score_label(meta):
    value = meta.get("_tmdb_score")
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None
    if not 0.0 < rating <= 10:
        return None
    return f"TMDB {rating:.1f}"


def rank_label(meta, spec):
    if spec.get("mode") != "netflix_official":
        return None
    found = re.search(r"Original chart position #([0-9]{1,2})", meta.get("description", ""))
    if not found:
        return None
    number = int(found.group(1))
    return number if 1 <= number <= 10 else None


def _font(size, bold=True):
    from PIL import ImageFont
    names = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _pill(draw, xy, label, fill, font, text_fill="white", border=None):
    x, y = xy
    left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
    w, h = right - left + 24, bottom - top + 17
    draw.rounded_rectangle((x, y, x + w, y + h), radius=13,
                           fill=fill, outline=border, width=2 if border else 1)
    draw.text((x + 12, y + 7 - top), label, font=font, fill=text_fill)
    return w, h


def status_label(meta, spec, rank):
    """Prefer only editorial labels demonstrably supported by the source."""
    if rank is not None:
        return "Top 10 in Saudi Arabia"
    desc = str(meta.get("description") or "")
    season = re.search(r"Season ([2-9][0-9]*) premiere ([0-9]{4}-[0-9]{2}-[0-9]{2})", desc)
    if season:
        try:
            age = (date.today() - date.fromisoformat(season.group(2))).days
            if 0 <= age <= 45:
                return "New Season"
        except ValueError:
            pass
    series = re.search(r"Series premiere ([0-9]{4}-[0-9]{2}-[0-9]{2})", desc)
    if series:
        try:
            age = (date.today() - date.fromisoformat(series.group(1))).days
            if 0 <= age <= 45:
                return "New Series"
        except ValueError:
            pass
    if spec.get("source_row") == "New on Netflix" or (
        "Netflix Saudi public category: New on Netflix" in desc
    ):
        return "New on Netflix"
    # Do not imply a fresh premiere or a season renewal without evidence.
    return "Netflix Saudi"


def _draw_netflix_icon(draw):
    """Compact black rounded service-logo badge, like the supplied reference."""
    x, y, side = 417, 17, 65
    draw.rounded_rectangle((x, y, x + side, y + side),
                           radius=12, fill=(15, 15, 18, 246))
    red = (229, 9, 20, 255)
    # Stylized N composed of three strokes, not an 'Original' attribution.
    draw.polygon(((x + 14, y + 11), (x + 25, y + 11),
                  (x + 25, y + 53), (x + 14, y + 53)), fill=red)
    draw.polygon(((x + 39, y + 11), (x + 50, y + 11),
                  (x + 50, y + 53), (x + 39, y + 53)), fill=red)
    draw.polygon(((x + 22, y + 11), (x + 32, y + 11),
                  (x + 43, y + 53), (x + 33, y + 53)), fill=(249, 34, 44, 255))


def _render(raw, meta, kind, rank, ribbon):
    """Create a 500x750 poster styled after the user's TopToday screenshot."""
    from PIL import Image, ImageDraw, ImageOps, ImageStat
    with Image.open(io.BytesIO(raw)) as opened:
        poster = ImageOps.fit(opened.convert("RGB"), POSTER_SIZE,
                              method=Image.Resampling.LANCZOS)
    image = poster.convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")

    # The reference uses a large unprefixed translucent number high in the
    # poster, unlike N1's former "#1" at the bottom.
    if rank is not None:
        large = _font(139)
        value = str(rank)
        # A subdued shadow is visible on both dark and light cover art.
        draw.text((19, 1), value, font=large, fill=(0, 0, 0, 135),
                  stroke_width=2, stroke_fill=(0, 0, 0, 105))
        draw.text((14, -4), value, font=large, fill=(245, 245, 242, 224))

    _draw_netflix_icon(draw)

    # The reference has a full-width title/status ribbon at the bottom, not
    # separate rating and movie/year pills. Choose a light or dark ribbon
    # based on the source's actual luminance.
    brightness = ImageStat.Stat(poster.crop((80, 150, 420, 500)).convert("L")).mean[0]
    light = brightness >= 166
    if light:
        fill, foreground = (240, 235, 225, 248), (31, 32, 36, 255)
    else:
        fill, foreground = (24, 26, 31, 239), (245, 245, 245, 255)
    top = 674
    draw.rounded_rectangle((0, top, 500, 762), radius=20, fill=fill)
    f = _font(27, bold=True)
    bbox = draw.textbbox((0, 0), ribbon, font=f)
    width = bbox[2] - bbox[0]
    if width > 466:
        f = _font(23, bold=True)
        bbox = draw.textbbox((0, 0), ribbon, font=f)
        width = bbox[2] - bbox[0]
    draw.text(((500 - width) / 2, 705 - bbox[1]), ribbon,
              font=f, fill=foreground)

    out = io.BytesIO()
    image.convert("RGB").save(out, "JPEG", quality=87, optimize=True)
    return out.getvalue()


def style_netflix_catalog(stage: Path, spec: dict, rows: list, base: str,
                          cache: dict | None = None):
    """Style only Netflix Saudi rows; keep every non-Netflix catalog unchanged.

    Poster errors never drop catalog entries or invalidate a working deployment.
    Cache artwork across rows, preserving source fallbacks for unavailable art.
    """
    if spec.get("group") != "Netflix Saudi":
        return rows
    if cache is None:
        cache = {}
    for meta in rows:
        original = meta.get("poster")
        imdb = meta.get("id", "")
        rank = rank_label(meta, spec)
        label = status_label(meta, spec, rank)
        if not IMDB_ID.fullmatch(imdb) or not (safe_tmdb_image_url(original) or netflix_image_url(original)):
            meta.pop("_tmdb_score", None)
            continue
        # The changed image filename busts old artwork caches on Sony TV.
        # Include label in the cache key so different catalog labels cannot
        # overwrite each other's image.
        key = (imdb, rank, label, original, meta.get("type"))
        if key not in cache:
            try:
                req = Request(original, headers={"User-Agent": "MyNuvioN1/1.0"})
                with urlopen(req, timeout=12) as response:
                    raw = response.read(3 * 1024 * 1024 + 1)
                if len(raw) > 3 * 1024 * 1024:
                    raise ValueError("Poster image exceeds size limit")
                image_bytes = _render(raw, meta, spec["type"], rank, label)
                suffix = ("-rank" + str(rank)) if rank else ""
                label_slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
                destination = stage / "posters" / "netflix" / (
                    imdb + suffix + "-ttv2-" + label_slug + ".jpg")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(image_bytes)
                cache[key] = base + "/posters/netflix/" + destination.name
            except (OSError, ValueError, TypeError, ImportError) as err:
                # Do not store URLs or image bytes in public logs on failure.
                print("Netflix poster fallback:", type(err).__name__, flush=True)
                cache[key] = None
        if cache[key]:
            meta["poster"] = cache[key]
        meta.pop("_tmdb_score", None)
    return rows
