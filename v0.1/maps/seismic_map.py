from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

import folium
import pandas as pd


def seismic_points(earthquakes: pd.DataFrame, minerals: pd.DataFrame | None = None) -> pd.DataFrame:
    data = earthquakes.copy()
    if data.empty:
        return data.assign(color=pd.Series(dtype=str), size=pd.Series(dtype=float))
    if minerals is not None and not minerals.empty:
        data = _attach_nearest_mineral(data, minerals)
    data["color"] = data["magnitude"].apply(_magnitude_color)
    data["size"] = data["magnitude"].fillna(2.5).clip(lower=2.5) ** 3 * 2
    return data


def _attach_nearest_mineral(earthquakes: pd.DataFrame, minerals: pd.DataFrame) -> pd.DataFrame:
    result = earthquakes.copy()

    def ranked_candidates(row: pd.Series) -> pd.DataFrame:
        candidates = minerals.copy()
        candidates["mineral_distance_km"] = candidates.apply(
            lambda mineral: _haversine_km(row["lat"], row["lon"], mineral["lat"], mineral["lon"]), axis=1
        )
        magnitude = float(row.get("magnitude") or 0)
        depth = float(row.get("depth_km") or 0)
        candidates["mineral_score"] = 100 / (1 + candidates["mineral_distance_km"] / 100) \
            + min(magnitude, 7) * 1.5 \
            + (2 if 2 <= depth <= 35 else 0)
        return candidates.sort_values(["mineral_score", "mineral_distance_km"], ascending=[False, True]).head(3)

    enriched = []
    for _, row in result.iterrows():
        candidates = ranked_candidates(row)
        best = candidates.iloc[0]
        candidate_names = ", ".join(candidates["mineral"].tolist())
        enriched.append({
            "mineral": best["mineral"],
            "mineral_country": best["country"],
            "mineral_note": best["note"],
            "mineral_image_url": best["image_url"],
            "mineral_distance_km": round(float(best["mineral_distance_km"]), 1),
            "mineral_score": round(float(best["mineral_score"]), 2),
            "mineral_candidates": candidate_names,
            "mineral_reason": f"Closest documented occurrence among the dataset; distance {best['mineral_distance_km']:.0f} km, adjusted for event magnitude and depth.",
        })
    matches = pd.DataFrame(enriched, index=result.index)
    for column in matches.columns:
        result[column] = matches[column]
    return result


def _haversine_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    radius_km = 6371.0
    lat_delta = radians(lat_b - lat_a)
    lon_delta = radians(lon_b - lon_a)
    value = sin(lat_delta / 2) ** 2 + cos(radians(lat_a)) * cos(radians(lat_b)) * sin(lon_delta / 2) ** 2
    return 2 * radius_km * asin(sqrt(value))


def seismic_hover_map(events: pd.DataFrame, language: str = "Italiano", text: dict[str, str] | None = None) -> folium.Map:
    """Build a lightweight Folium view with damage and mineral hover details."""
    text = text or {}
    center = [float(events["lat"].mean()), float(events["lon"].mean())] if not events.empty else [20.0, 0.0]
    seismic_map = folium.Map(location=center, zoom_start=2, tiles="OpenStreetMap")
    for _, event in events.iterrows():
        damage = event.get("damage_status", "unavailable")
        damage_labels = {
            "Italiano": {"reported_or_probable_damage": "Danni segnalati o probabili", "no_damage_signal": "Nessun segnale di danni", "unavailable": "Dati non disponibili"},
            "English": {"reported_or_probable_damage": "Reported or probable damage", "no_damage_signal": "No damage signal", "unavailable": "Data unavailable"},
            "Español": {"reported_or_probable_damage": "Daños notificados o probables", "no_damage_signal": "Sin indicios de daños", "unavailable": "Datos no disponibles"},
            "Polski": {"reported_or_probable_damage": "Zgłoszone lub prawdopodobne szkody", "no_damage_signal": "Brak sygnałów o szkodach", "unavailable": "Brak dostępnych danych"},
            "中文": {"reported_or_probable_damage": "已报告或可能存在损害", "no_damage_signal": "没有损害迹象", "unavailable": "暂无数据"},
        }
        damage_reason = text.get(f"damage_reason_{damage}", event.get("damage_reason", ""))
        damage_label = damage_labels.get(language, damage_labels["Italiano"]).get(damage, damage)
        candidates = event.get("mineral_candidates", event.get("mineral", "Unavailable"))
        tooltip = (
            f"{text.get('magnitude', 'Magnitudo')} M{float(event['magnitude']):.1f} · {event.get('place', '')} · "
            f"{text.get('damage', 'Danni')}: {damage_label} · {text.get('mineral_candidates', 'Minerali candidati')}: {candidates}"
        )
        popup = (
            f"<b>{text.get('magnitude', 'Magnitudo')}:</b> {event.get('magnitude')}<br>"
            f"<b>{text.get('depth_label', 'Profondità')}:</b> {event.get('depth_km')} km<br>"
            f"<b>{text.get('damage', 'Danni')}:</b> {damage_label}<br>"
            f"<b>{text.get('damage_reason', 'Motivazione danni')}:</b> {damage_reason}<br>"
            f"<b>{text.get('mineral_candidates', 'Minerali candidati')}:</b> {candidates}<br>"
            f"<b>{text.get('mineral_score_label', 'Punteggio minerale')}:</b> {event.get('mineral_score', 'n/d')}<br>"
            f"<b>{text.get('mineral_distance', 'Distanza minerale (km)')}:</b> {event.get('mineral_distance_km', 'n/d')} km"
        )
        folium.CircleMarker(
            location=[event["lat"], event["lon"]],
            radius=max(4, min(14, float(event.get("magnitude", 2.5)) * 2)),
            color=event.get("color", "#d74331"),
            fill=True,
            fill_color=event.get("color", "#d74331"),
            fill_opacity=0.75,
            tooltip=tooltip,
            popup=folium.Popup(popup, max_width=360),
        ).add_to(seismic_map)
    return seismic_map


def _magnitude_color(magnitude: float) -> str:
    if magnitude < 3:
        return "#2ca05b"
    if magnitude < 4:
        return "#f2cd39"
    if magnitude < 5:
        return "#ef8b2d"
    if magnitude < 6:
        return "#d74331"
    return "#682c84"
