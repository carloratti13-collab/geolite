"""Live USGS earthquake feed."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
EARTHQUAKE_COLUMNS = [
    "event_id", "time", "magnitude", "place", "depth_km", "lat", "lon",
    "url", "updated", "alert", "felt", "mmi", "sig", "status", "mag_type",
    "damage_status", "damage_reason",
]


def damage_status(event: dict | pd.Series) -> tuple[str, str]:
    """Classify only the damage signals explicitly present in USGS data."""
    felt = event.get("felt")
    alert = event.get("alert")
    mmi = event.get("mmi")
    significance = event.get("sig")

    if (felt is not None and felt > 0) or (mmi is not None and mmi >= 6) or (alert in {"orange", "red"}):
        return "reported_or_probable_damage", "USGS reports felt reports, strong shaking, or an elevated alert level."
    if (felt == 0) or (alert == "green") or (mmi is not None and mmi < 4) or (significance is not None and significance < 300):
        return "no_damage_signal", "USGS contains no signal suggesting damaging effects for this event."
    return "unavailable", "USGS does not provide enough information to determine damage."


def earthquake_feed(days: int = 7, min_magnitude: float = 2.5) -> pd.DataFrame:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    params = {"format": "geojson", "starttime": start.isoformat(), "endtime": end.isoformat(), "minmagnitude": min_magnitude, "orderby": "time"}
    try:
        response = requests.get(USGS_URL, params=params, timeout=12)
        response.raise_for_status()
        rows = []
        for feature in response.json().get("features", []):
            properties = feature.get("properties", {})
            coordinates = feature.get("geometry", {}).get("coordinates", [None, None, None])
            if len(coordinates) < 3 or coordinates[0] is None or coordinates[1] is None or properties.get("time") is None:
                continue
            status, reason = damage_status(properties)
            rows.append({
                "event_id": feature.get("id"),
                "time": datetime.fromtimestamp(properties["time"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                "magnitude": properties.get("mag"),
                "place": properties.get("place", "Unknown"),
                "depth_km": coordinates[2],
                "lat": coordinates[1],
                "lon": coordinates[0],
                "url": properties.get("url"),
                "updated": properties.get("updated"),
                "alert": properties.get("alert"),
                "felt": properties.get("felt"),
                "mmi": properties.get("mmi"),
                "sig": properties.get("sig"),
                "status": properties.get("status"),
                "mag_type": properties.get("magType"),
                "damage_status": status,
                "damage_reason": reason,
            })
        return pd.DataFrame(rows, columns=EARTHQUAKE_COLUMNS)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return pd.DataFrame(columns=EARTHQUAKE_COLUMNS)
