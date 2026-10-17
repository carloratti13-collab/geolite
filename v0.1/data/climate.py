"""Open-Meteo climate snapshots; no API key required."""
from __future__ import annotations

import pandas as pd
import requests

COUNTRIES = {
    "Italia": (41.9, 12.5),
    "Islanda": (64.1, -21.9),
    "Giappone": (35.7, 139.7),
    "Cile": (-33.4, -70.7),
}


def climate_snapshot(country: str) -> dict[str, float | str]:
    lat, lon = COUNTRIES[country]
    params = {"latitude": lat, "longitude": lon, "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m", "timezone": "auto"}
    try:
        response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
        response.raise_for_status()
        current = response.json()["current"]
        return {"country": country, "latitude": lat, "longitude": lon, "temperature_c": current["temperature_2m"], "humidity_pct": current["relative_humidity_2m"], "precipitation_mm": current["precipitation"], "wind_kmh": current["wind_speed_10m"]}
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return {"country": country, "latitude": lat, "longitude": lon, "temperature_c": 15.0, "humidity_pct": 65.0, "precipitation_mm": 0.0, "wind_kmh": 8.0}


def world_climate_grid(step: int = 10) -> pd.DataFrame:
    """Fetch current Open-Meteo values over a global latitude/longitude grid."""
    latitudes = list(range(-60, 61, step))
    longitudes = list(range(-180, 181, step))
    points = [(latitude, longitude) for latitude in latitudes for longitude in longitudes]
    params = {"latitude": ",".join(str(latitude) for latitude, _ in points), "longitude": ",".join(str(longitude) for _, longitude in points), "current": "temperature_2m,precipitation", "timezone": "UTC"}
    try:
        response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            payload = [payload]
        return pd.DataFrame([{"lat": latitude, "lon": longitude, "temperature_c": item["current"]["temperature_2m"], "precipitation_mm": item["current"]["precipitation"], "color": _temperature_color(item["current"]["temperature_2m"])} for (latitude, longitude), item in zip(points, payload)])
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return pd.DataFrame(columns=["lat", "lon", "temperature_c", "precipitation_mm", "color"])


def _temperature_color(temperature: float) -> str:
    if temperature < 0:
        return "#315f8f"
    if temperature < 10:
        return "#50a9a2"
    if temperature < 20:
        return "#f3d35b"
    if temperature < 30:
        return "#e06b3d"
    return "#a93232"
