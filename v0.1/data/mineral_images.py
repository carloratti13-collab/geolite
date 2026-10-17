"""Cached Wikimedia Commons image search for minerals."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import requests

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"


@lru_cache(maxsize=32)
def search_mineral_images(mineral: str, limit: int = 4) -> tuple[dict[str, str], ...]:
    """Return a small cached set of Commons images for one mineral."""
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"{mineral} mineral",
        "gsrnamespace": 6,
        "gsrlimit": min(max(limit, 1), 16),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 700,
    }
    try:
        response = requests.get(
            WIKIMEDIA_API,
            params=params,
            headers={"User-Agent": "GeoLite/1.0 educational dashboard"},
            timeout=10,
        )
        response.raise_for_status()
        pages: dict[str, Any] = response.json().get("query", {}).get("pages", {})
    except (requests.RequestException, ValueError, TypeError):
        return ()

    images: list[dict[str, str]] = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        image_url = info.get("thumburl") or info.get("url")
        page_url = f"https://commons.wikimedia.org/?curid={page.get('pageid')}"
        if not image_url or not page.get("pageid"):
            continue
        metadata = info.get("extmetadata") or {}
        artist = metadata.get("Artist", {}).get("value", "Unknown author")
        license_name = metadata.get("LicenseShortName", {}).get("value", "License information unavailable")
        images.append({
            "title": page.get("title", "Wikimedia Commons image").removeprefix("File:"),
            "image_url": image_url,
            "page_url": page_url,
            "artist": artist,
            "license": license_name,
        })
    return tuple(images[:16])


def search_candidate_mineral_images(minerals: list[str], limit: int = 16) -> list[dict[str, str]]:
    """Search candidates in order and return at most ``limit`` unique images."""
    images: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    per_mineral = max(1, min(4, limit // max(len(minerals), 1)))
    for mineral in minerals:
        for image in search_mineral_images(mineral.strip(), per_mineral):
            if image["image_url"] in seen_urls:
                continue
            seen_urls.add(image["image_url"])
            image = dict(image)
            image["mineral"] = mineral.strip()
            images.append(image)
            if len(images) >= limit:
                return images
    return images
