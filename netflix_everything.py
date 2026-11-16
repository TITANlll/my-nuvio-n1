"""Netflix-only 'Everything'-inspired poster artwork for Nuvio catalog rows.

This is an original design, NOT the TopToday poster API or an official Netflix
artwork feed. Never paint a Netflix original claim onto licensed content.
Artwork falls back to the existing poster if Pillow or the source image fails.
"""
from __future__ import annotations

import io
import re
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


def _render(raw, meta, kind, rank):
    """Create one 500x750 JPEG with legible restrained OTT badges."""
    from PIL import Image, ImageDraw, ImageOps
    source = Image.open(io.BytesIO(raw))
    source = ImageOps.fit(source.convert("RGB"), POSTER_SIZE, method=Image.Resampling.LANCZOS)
    image = source.convert("RGBA")
    shade = Image.new("RGBA", POSTER_SIZE, (0, 0, 0, 0))
    shades = ImageDraw.Draw(shade, "RGBA")
    for y in range(0, 150, 2):
        a = max(0, 182 - int(y * 1.15))
        shades.rectangle((0, y, 500, y + 1), fill=(0, 0, 0, a))
    for y in range(565, 750, 2):
        a = min(211, int((y - 565) * 1.4))
        shades.rectangle((0, y, 500, y + 1), fill=(0, 0, 0, a))
    image = Image.alpha_composite(image, shade)
    draw = ImageDraw.Draw(image)
    badge_font = _font(20)
    micro_font = _font(18)
    score = score_label(meta)
    if score:
        _pill(draw, (18, 19), score, (17, 20, 26, 239), badge_font,
              border=(234, 234, 234, 160))
    # A Netflix Saudi *availability* or catalog badge, not an Originals badge.
    label = "NETFLIX SA"
    w = draw.textbbox((0, 0), label, font=badge_font)[2] + 24
    _pill(draw, (500 - w - 18, 19), label, (183, 18, 32, 245), badge_font)
    media_type = "MOVIE" if kind == "movie" else "SERIES"
    year = str(meta.get("releaseInfo") or "").strip()
    subtitle = media_type + (("  /  " + year) if re.fullmatch(r"[0-9]{4}", year) else "")
    _pill(draw, (18, 697), subtitle, (20, 24, 30, 216), micro_font)
    if rank is not None:
        draw.text((12, 561), "#" + str(rank), fill=(255, 255, 255, 249),
                  font=_font(97), stroke_width=4, stroke_fill=(4, 5, 10, 240))
        draw.rectangle((21, 667, 132, 676), fill=(232, 25, 45, 255))
    out = io.BytesIO()
    image.convert("RGB").save(out, "JPEG", quality=85, optimize=True)
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
        score = score_label(meta)
        if not IMDB_ID.fullmatch(imdb) or not (safe_tmdb_image_url(original) or netflix_image_url(original)):
            meta.pop("_tmdb_score", None)
            continue
        # A ranked image differs from an unranked image. Ratings are factual
        # TMDB data, never labeled as IMDb scores.
        key = (imdb, rank, score, original, meta.get("releaseInfo"), meta.get("type"))
        if key not in cache:
            try:
                req = Request(original, headers={"User-Agent": "MyNuvioN1/1.0"})
                with urlopen(req, timeout=12) as response:
                    raw = response.read(3 * 1024 * 1024 + 1)
                if len(raw) > 3 * 1024 * 1024:
                    raise ValueError("Poster image exceeds size limit")
                image_bytes = _render(raw, meta, spec["type"], rank)
                suffix = ("-rank" + str(rank)) if rank else ""
                destination = stage / "posters" / "netflix" / (imdb + suffix + ".jpg")
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
