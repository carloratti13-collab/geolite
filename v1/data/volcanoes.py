"""Eventi vulcanici aperti dal catalogo NASA EONET (v3)."""
from __future__ import annotations

import time as _time

import requests
import streamlit as st

EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
_TIMEOUT = 30
_MAX_ATTEMPTS = 2


@st.cache_data(ttl=3600, show_spinner=False)
def volcano_events() -> list[dict]:
    """Vulcani con evento aperto: posizione, data e fonti di monitoraggio.

    In caso di errore di rete o di parsing ritorna una lista vuota.
    """
    params = {"category": "volcanoes", "status": "open", "limit": 50}
    payload: dict | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = requests.get(EONET_URL, params=params, timeout=_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            break
        except (requests.RequestException, ValueError, TypeError):
            if attempt < _MAX_ATTEMPTS - 1:
                _time.sleep(1.0)
    if payload is None:
        return []

    events: list[dict] = []
    for event in payload.get("events", []):
        geometries = event.get("geometry") or []
        if not geometries:
            continue
        geometry = geometries[-1]  # posizione più recente
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2 or geometry.get("date") is None:
            continue
        try:
            lon, lat = float(coordinates[0]), float(coordinates[1])
        except (TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        categories = [c.get("title", "") for c in event.get("categories") or [] if c.get("title")]
        sources = [s.get("title", "") for s in event.get("sources") or [] if s.get("title")]
        events.append({
            "id": event.get("id") or "unknown",
            "title": event.get("title") or "Volcano event",
            "lat": lat,
            "lon": lon,
            "date": geometry["date"],
            "link": event.get("link") or EONET_URL,
            "categories": categories,
            "sources": sources,
        })
    return events
