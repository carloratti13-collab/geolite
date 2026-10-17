"""Country polygon climate map for Streamlit."""
from __future__ import annotations

from functools import lru_cache

import folium
import pandas as pd
import requests

WORLD_GEOJSON = "https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson"


@lru_cache(maxsize=1)
def _world_geojson() -> dict:
    response = requests.get(WORLD_GEOJSON, timeout=20)
    response.raise_for_status()
    return response.json()


def _coordinates(geometry: dict) -> list[tuple[float, float]]:
    values: list[tuple[float, float]] = []

    def walk(value: object) -> None:
        if isinstance(value, list) and len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
            values.append((float(value[1]), float(value[0])))
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(geometry.get("coordinates", []))
    return values


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


def climate_choropleth(grid: pd.DataFrame) -> folium.Map:
    geojson = _world_geojson()
    enriched = []
    for feature in geojson.get("features", []):
        points = _coordinates(feature.get("geometry", {}))
        if not points:
            continue
        latitude = sum(point[0] for point in points) / len(points)
        longitude = sum(point[1] for point in points) / len(points)
        distance = (grid["lat"] - latitude) ** 2 + (grid["lon"] - longitude) ** 2
        temperature = float(grid.loc[distance.idxmin(), "temperature_c"])
        feature["properties"]["geobrain_temperature"] = temperature
        feature["properties"]["geobrain_color"] = _temperature_color(temperature)
        enriched.append(feature)
    geojson["features"] = enriched
    climate_map = folium.Map(location=[20, 10], zoom_start=2, tiles="OpenStreetMap", control_scale=True)
    folium.GeoJson(geojson, name="Temperatura corrente", style_function=lambda feature: {"fillColor": feature["properties"].get("geobrain_color", "#b7c2c8"), "color": "#ffffff", "weight": 0.4, "fillOpacity": 0.78}, tooltip=folium.GeoJsonTooltip(fields=["name", "geobrain_temperature"], aliases=["Paese", "Temperatura °C"], localize=True)).add_to(climate_map)
    return climate_map
