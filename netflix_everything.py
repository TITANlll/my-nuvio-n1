"""Netflix-only integration with genuine TopToday artwork URLs.

The user-provided TMDB Top Today addon manifest includes poster URLs such as
https://toptoday.llamayu.com/poster/84773.jpg?type=series&tag=new_season&rank=1&lang=en&logos=1
N1 uses that real poster service, not an imitation or local renderer.
Netflix Saudi content selection and all other collections remain untouched.
"""
from __future__ import annotations
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlencode, urlsplit

TOPTODAY_BASE = "https://toptoday.llamayu.com"
IMDB_ID = re.compile(r"tt[0-9]{5,12}\Z")
MOVIE_IMAGE = re.compile(r"/t/p/w[0-9]+/[a-zA-Z0-9_./-]+[.](?:jpg|jpeg|png|webp)\Z")


def safe_tmdb_image_url(url):
    parsed = urlsplit(url or "")
    return (parsed.scheme == "https" and parsed.netloc == "image.tmdb.org"
            and bool(MOVIE_IMAGE.fullmatch(parsed.path)) and not parsed.query)


def score_label(meta):
    """Retained as a utility only. TopToday controls poster metadata."""
    try:
        value = float(meta.get("_tmdb_score"))
    except (ValueError, TypeError):
        return None
    return f"TMDB {value:.1f}" if 0 < value <= 10 else None


def rank_label(meta, spec):
    """Only the official Netflix Saudi weekly country chart has real ranks."""
    if spec.get("mode") != "netflix_official":
        return None
    match = re.search(
        r"Original chart position #([0-9]{1,2})",
        str(meta.get("description", "")))
    if not match:
        return None
    rank = int(match.group(1))
    return rank if 1 <= rank <= 10 else None


def status_label(meta, spec, rank):
    """Label only actual source-backed premieres; no guesses."""
    if rank is not None:
        return "Top 10 in Saudi Arabia"
    desc = str(meta.get("description") or "")
    for pattern, label in (
        (r"Season [2-9][0-9]* premiere ([0-9]{4}-[0-9]{2}-[0-9]{2})", "New Season"),
        (r"Series premiere ([0-9]{4}-[0-9]{2}-[0-9]{2})", "New Series"),
    ):
        match = re.search(pattern, desc)
        if match:
            try:
                days = (date.today() - date.fromisoformat(match.group(1))).days
                if 0 <= days <= 45:
                    return label
            except ValueError:
                pass
    if spec.get("source_row") == "New on Netflix" or (
        "Netflix Saudi public category: New on Netflix" in desc
    ):
        return "New on Netflix"
    return "Netflix Saudi"


def top_today_tag(meta, spec, rank):
    """Only observed TopToday native tag codes are used."""
    return {
        "New Season": "new_season",
        "New Series": "premiere",
        "New on Netflix": "now_streaming",
    }.get(status_label(meta, spec, rank), "none")


def top_today_poster_url(tmdb_id, kind, *, rank=None, tag="none"):
    """Use the real poster URL schema returned by TopToday, not generated art."""
    if not isinstance(tmdb_id, int) or isinstance(tmdb_id, bool):
        return None
    if not 1 <= tmdb_id <= 999999999:
        return None
    if kind not in ("movie", "series"):
        return None
    if rank is not None and (not isinstance(rank, int) or rank not in range(1, 11)):
        return None
    if tag not in ("none", "new_season", "premiere", "now_streaming"):
        return None
    qs = urlencode((
        ("type", kind),
        ("tag", tag),
        ("rank", rank if rank is not None else "none"),
        ("lang", "en"),
        ("logos", 1),
    ))
    return f"{TOPTODAY_BASE}/poster/{tmdb_id}.jpg?{qs}"


def style_netflix_catalog(stage: Path, spec: dict, rows: list, base: str,
                          cache: dict | None = None):
    """Switch only the Netflix Saudi catalogs to native TopToday poster URLs.

    The per-title TMDB id comes from N1's already verified TMDB mapping.
    Preserve the current poster when no reliable TMDB id is available.
    The signature stays compatible with the existing generator.
    """
    if spec.get("group") != "Netflix Saudi":
        return rows
    for meta in rows:
        tmdb_id = meta.pop("_tmdb_id", None)
        meta.pop("_tmdb_score", None)
        if not IMDB_ID.fullmatch(str(meta.get("id", ""))):
            continue
        rank = rank_label(meta, spec)
        tag = top_today_tag(meta, spec, rank)
        url = top_today_poster_url(tmdb_id, spec.get("type"), rank=rank, tag=tag)
        if url:
            meta["poster"] = url
    return rows
