"""Interactive map for NASA EONET volcano events."""
from __future__ import annotations

from html import escape

import folium
import pandas as pd


def volcano_event_map(events: pd.DataFrame, labels: dict[str, str]) -> folium.Map:
    center = [float(events["lat"].mean()), float(events["lon"].mean())] if not events.empty else [0.0, 0.0]
    event_map = folium.Map(location=center, zoom_start=2, tiles="OpenStreetMap", prefer_canvas=True)
    for _, event in events.iterrows():
        title = escape(str(event["title"]))
        source_url = escape(str(event["source_url"]), quote=True)
        popup = (
            f"<b>{escape(labels['volcano_name'])}:</b> {title}<br>"
            f"<b>{escape(labels['eruption_date'])}:</b> {escape(str(event['date']))}<br>"
            f"<a href=\"{source_url}\" target=\"_blank\" rel=\"noopener\">{escape(labels['source'])}</a>"
        )
        folium.CircleMarker(
            location=[event["lat"], event["lon"]],
            radius=7,
            color="#c83b2c",
            weight=2,
            fill=True,
            fill_color="#ff8069",
            fill_opacity=0.9,
            tooltip=f"{title} · {event['date']}",
            popup=folium.Popup(popup, max_width=320),
        ).add_to(event_map)
    return event_map
