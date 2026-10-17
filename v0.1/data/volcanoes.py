"""Current volcano events from NASA's Earth Observatory Natural Event Tracker."""
from __future__ import annotations

import pandas as pd
import requests

EONET_VOLCANO_EVENTS_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
VOLCANO_EVENT_COLUMNS = ["event_id", "title", "date", "lat", "lon", "source_url"]


def recent_volcano_events() -> pd.DataFrame:
    """Return open, geolocated volcano events catalogued by NASA EONET."""
    params = {"category": "volcanoes", "status": "open", "limit": 100}
    try:
        response = requests.get(EONET_VOLCANO_EVENTS_URL, params=params, timeout=12)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError, TypeError):
        return pd.DataFrame(columns=VOLCANO_EVENT_COLUMNS)

    events: list[dict[str, object]] = []
    for event in payload.get("events", []):
        geometries = event.get("geometry") or []
        if not geometries:
            continue
        geometry = geometries[-1]
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2 or geometry.get("date") is None:
            continue
        try:
            longitude, latitude = float(coordinates[0]), float(coordinates[1])
        except (TypeError, ValueError):
            continue
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue
        events.append({
            "event_id": event.get("id"),
            "title": event.get("title") or "Volcano event",
            "date": geometry["date"],
            "lat": latitude,
            "lon": longitude,
            "source_url": event.get("link") or EONET_VOLCANO_EVENTS_URL,
        })

    return pd.DataFrame(events, columns=VOLCANO_EVENT_COLUMNS)
