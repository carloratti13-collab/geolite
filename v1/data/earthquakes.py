"""Feed USGS di eventi sismici (GeoJSON FDSN) per il globo 3D."""
from __future__ import annotations

import time as _time
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
_TIMEOUT = 30
_MAX_ATTEMPTS = 2


def _parse_feature(feature: dict) -> dict | None:
    """Converte una Feature GeoJSON USGS in un dizionario normalizzato.

    Ritorna None se la feature manca di dati essenziali (coordinate, tempo, magnitudo).
    """
    properties = feature.get("properties") or {}
    coordinates = (feature.get("geometry") or {}).get("coordinates") or []
    if len(coordinates) < 3:
        return None
    lon, lat, depth = coordinates[0], coordinates[1], coordinates[2]
    if lon is None or lat is None or properties.get("time") is None:
        return None
    magnitude = properties.get("mag")
    try:
        magnitude = float(magnitude) if magnitude is not None else None
        depth = float(depth) if depth is not None else 0.0
    except (TypeError, ValueError):
        return None
    if magnitude is None:
        return None
    when = datetime.fromtimestamp(properties["time"] / 1000, tz=timezone.utc)
    return {
        "id": feature.get("id") or "unknown",
        "lat": float(lat),
        "lon": float(lon),
        "depth_km": round(depth, 2),
        "magnitude": round(magnitude, 2),
        "place": properties.get("place") or "Unknown",
        "time": when.isoformat(),
        "url": properties.get("url") or "",
        "tsunami": bool(properties.get("tsunami")),
        "alert": properties.get("alert"),
        "felt": properties.get("felt"),
        "mag_type": properties.get("magType"),
    }


def _fetch(params: dict) -> list[dict]:
    """Esegue la richiesta con un retry e restituisce i dict normalizzati."""
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = requests.get(USGS_URL, params=params, timeout=_TIMEOUT)
            response.raise_for_status()
            features = response.json().get("features", [])
            events = [e for e in (_parse_feature(f) for f in features) if e is not None]
            events.sort(key=lambda e: e["magnitude"], reverse=True)
            return events
        except (requests.RequestException, ValueError, AttributeError, TypeError):
            if attempt < _MAX_ATTEMPTS - 1:
                _time.sleep(1.0)
    return []


@st.cache_data(ttl=600, show_spinner=False)
def earthquake_events(days: int = 7, min_magnitude: float = 2.5) -> list[dict]:
    """Terremoti degli ultimi ``days`` giorni, ordinati per magnitudo decrescente."""
    days = max(1, int(days))
    min_magnitude = max(0.0, float(min_magnitude))
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    params = {
        "format": "geojson",
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": end.strftime("%Y-%m-%dT%H:%M:%S"),
        "minmagnitude": min_magnitude,
        "orderby": "magnitude",
    }
    return _fetch(params)
