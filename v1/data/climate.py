"""Texture del globo e correnti oceaniche da NASA GIBS (WMS + colormap XML)."""
from __future__ import annotations

import io
import re
import time as _time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import streamlit as st
from PIL import Image

GIBS_WMS_URL = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
COLORMAP_URL = "https://gibs.earthdata.nasa.gov/colormaps/v1.0/{}.xml"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "globe_component" / "frontend" / "assets"

LAYER_BASE = "BlueMarble_ShadedRelief"
LAYER_CLIMATE_SST = "GHRSST_L4_MUR_Sea_Surface_Temperature"
LAYER_REFS = "Reference_Features"
LAYER_CURRENTS_ZONAL = "OSCAR_Sea_Surface_Currents_Zonal"
LAYER_CURRENTS_MERIDIONAL = "OSCAR_Sea_Surface_Currents_Meridional"
LAYERS_BASE = f"{LAYER_BASE},{LAYER_REFS}"
LAYERS_CLIMATE = f"{LAYER_BASE},{LAYER_CLIMATE_SST},{LAYER_REFS}"
# Temperatura dell'aria a 2 m, mensile, copertura globale (terra+oceano):
# la mappa «zone di calore» della sezione Clima.
LAYER_HEAT = "MERRA2_2m_Air_Temperature_Monthly"
LAYERS_HEAT = f"{LAYER_HEAT},{LAYER_REFS}"

_TIMEOUT = 60
_MAX_ATTEMPTS = 2
_MAX_VECTORS = 12000
_MAX_SPEED_MS = 2.5  # filtro fisico: OSCAR non supera ~1.5 m/s


def _wms_params(layers: str, time_str: str | None, width: int, height: int) -> dict:
    params: dict = {
        "SERVICE": "WMS",
        "REQUEST": "GetMap",
        "VERSION": "1.3.0",
        "CRS": "EPSG:4326",
        "BBOX": "-90,-180,90,180",
        "FORMAT": "image/png",
        "WIDTH": width,
        "HEIGHT": height,
        "LAYERS": layers,
    }
    if time_str:
        params["TIME"] = time_str
    return params


def _download_png(url: str, params: dict) -> bytes | None:
    """GET di un'immagine WMS con un retry; None in caso di errore."""
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = requests.get(url, params=params, timeout=_TIMEOUT)
            response.raise_for_status()
            if response.content:
                return response.content
        except requests.RequestException:
            if attempt < _MAX_ATTEMPTS - 1:
                _time.sleep(1.0)
    return None


def _download_text(url: str) -> str | None:
    """GET di testo (colormap XML) con un retry; None in caso di errore."""
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = requests.get(url, timeout=_TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException:
            if attempt < _MAX_ATTEMPTS - 1:
                _time.sleep(1.0)
    return None


def _wms_time_default(layer: str) -> str | None:
    """Estrae la data di default (più recente disponibile) di un layer WMS.

    Serve per OSCAR: il prodotto è fermo a ~lug 2024 e GIBS non approssima
    TIME (nearestValue=0), quindi senza TIME il server serve la data default.
    """
    xml_text = _download_text(f"{GIBS_WMS_URL}?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0")
    if not xml_text:
        return None
    marker = f"<Name>{layer}</Name>"
    idx = xml_text.find(marker)
    if idx == -1:
        return None
    block = xml_text[idx:idx + 20000]
    match = re.search(r'<Dimension name="time"[^>]*default="(\d{4}-\d{2}-\d{2})"', block)
    return match.group(1) if match else None


def _utc_today(lag_days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=lag_days)).strftime("%Y-%m-%d")


def _valid_png(data: bytes | None) -> bool:
    """True se i bytes sono un PNG decodificabile (GIBS ritorna XML di errore)."""
    if not data:
        return False
    try:
        Image.open(io.BytesIO(data)).verify()
        return True
    except (OSError, ValueError):
        return False


def _assets_dir() -> Path:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    return ASSETS_DIR


def _parse_range(value: str) -> tuple[float, float] | None:
    """Converte un attributo value "[lo,hi)" in un intervallo numerico."""
    cleaned = value.strip().strip("[]()")
    if "," in cleaned:
        lo_raw, _, hi_raw = cleaned.partition(",")
    elif ";" in cleaned:
        lo_raw, _, hi_raw = cleaned.partition(";")
    else:
        return None
    try:
        lo = float(lo_raw)
        hi = float(hi_raw)
    except ValueError:
        return None
    if lo == float("-inf"):
        lo = -_MAX_SPEED_MS
    if hi == float("inf"):
        hi = _MAX_SPEED_MS
    return lo, hi


def _parse_colormap(xml_text: str) -> dict[tuple[int, int, int], float]:
    """Parsa un colormap GIBS in {(r,g,b): midpoint}; salta la voce No Data.

    La prima entry con transparent="true" è "No Data" e viene ignorata.
    """
    mapping: dict[tuple[int, int, int], float] = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return mapping
    first_entry = True
    for entry in root.iter("ColorMapEntry"):
        rgb_raw = entry.get("rgb")
        if not rgb_raw:
            continue
        try:
            r, g, b = (int(c) for c in rgb_raw.split(","))
        except ValueError:
            continue
        transparent = entry.get("transparent", "false").lower() == "true"
        if first_entry:
            first_entry = False
            if transparent:
                continue
        span = _parse_range(entry.get("value", ""))
        midpoint = (span[0] + span[1]) / 2 if span else 0.0
        mapping[(r, g, b)] = midpoint
    return mapping


def _decode_current_grid(
    zonal_png: bytes,
    meridional_png: bytes,
    zonal_map: dict[tuple[int, int, int], float],
    meridional_map: dict[tuple[int, int, int], float],
    step: int,
) -> list[list[float]]:
    """Decodifica i due PNG pixel-aligned in una griglia [lat, lon, u, v]."""
    zonal = Image.open(io.BytesIO(zonal_png)).convert("RGBA")
    meridional = Image.open(io.BytesIO(meridional_png)).convert("RGBA")
    width, height = zonal.size
    if meridional.size != (width, height):
        raise ValueError("PNG correnti non allineati")
    zonal = zonal.load()
    meridional = meridional.load()

    grid: list[list[float]] = []
    for y in range(0, height, step):
        lat = 90.0 - (y + 0.5) * 180.0 / height
        for x in range(0, width, step):
            ru, gu, bu, au = zonal[x, y]
            rv, gv, bv, av = meridional[x, y]
            if au <= 0 or av <= 0:
                continue
            u = zonal_map.get((ru, gu, bu))
            v = meridional_map.get((rv, gv, bv))
            if u is None or v is None:
                continue
            if abs(u) > _MAX_SPEED_MS or abs(v) > _MAX_SPEED_MS:
                continue
            lon = (x + 0.5) * 360.0 / width - 180.0
            grid.append([round(lat, 2), round(lon, 2), round(u, 3), round(v, 3)])
    return grid


@st.cache_data(ttl=604800, show_spinner=False)
def base_texture_url(width: int = 2048) -> str | None:
    """Scarica la texture di base Blue Marble + Reference Features.

    Salva il PNG in ``globe_component/frontend/assets/base_<width>.png`` e
    ritorna l'URL relativo "assets/base_<width>.png", oppure None in errore.
    """
    height = width // 2
    path = _assets_dir() / f"base_{width}.png"
    relative = f"assets/base_{width}.png"
    if path.exists() and path.stat().st_mtime > _time.time() - 7 * 86400:
        return relative
    params = _wms_params(LAYERS_BASE, None, width, height)
    png = _download_png(GIBS_WMS_URL, params)
    if not _valid_png(png):
        return None
    try:
        path.write_bytes(png)  # type: ignore[arg-type]
    except OSError:
        return None
    return relative


@st.cache_data(ttl=172800, show_spinner=False)
def climate_texture_url(width: int = 2048, lag_days: int = 2) -> str | None:
    """Texture clima: Blue Marble + SST termica MUR + Reference Features.

    Il parametro TIME è (oggi UTC - lag_days); GIBS lo approssima alla data
    disponibile più vicina. Ritorna "assets/climate_<TIME>_<width>.png" o None.
    """
    height = width // 2
    time_str = _utc_today(lag_days)
    path = _assets_dir() / f"climate_{time_str}_{width}.png"
    relative = f"assets/climate_{time_str}_{width}.png"
    if path.exists():
        return relative
    params = _wms_params(LAYERS_CLIMATE, time_str, width, height)
    png = _download_png(GIBS_WMS_URL, params)
    if not _valid_png(png):
        return None
    try:
        path.write_bytes(png)  # type: ignore[arg-type]
    except OSError:
        return None
    return relative


def _png_has_data(png: bytes) -> bool:
    """True se il PNG ha pixel opachi: GIBS serve un'immagine vuota (tutta
    trasparente ma decodificabile) quando TIME cade in un buco dell'extent."""
    try:
        img = Image.open(io.BytesIO(png)).convert("RGBA")
    except (OSError, ValueError):
        return False
    width, height = img.size
    step = max(1, min(width, height) // 64)
    pixels = img.load()
    for y in range(0, height, step):
        for x in range(0, width, step):
            if pixels[x, y][3] > 200:
                return True
    return False


def _first_of_month(lag_months: int) -> str:
    """Primo giorno del mese di (oggi UTC - lag_months), formato YYYY-MM-01."""
    now = datetime.now(timezone.utc)
    month = now.month - lag_months
    year = now.year
    while month <= 0:
        month += 12
        year -= 1
    return f"{year:04d}-{month:02d}-01"


@st.cache_data(ttl=43200, show_spinner=False)
def heat_texture_url(width: int = 2048, lag_months: int = 3) -> dict:
    """Texture «zone di calore»: temperatura dell'aria a 2 m (MERRA-2, mensile).

    Il layer ha un extent con buchi e nearestValue=0: se TIME non è un mese
    disponibile GIBS restituisce un'immagine vuota. Si prova quindi
    (oggi - lag_months), poi un mese indietro, poi senza TIME (data di
    default del layer = ultimo mese disponibile, ~2-3 mesi indietro).
    Ritorna {"url": "assets/heat_<...>.png" | None, "date": "YYYY-MM" | None}.
    """
    height = width // 2
    attempts = [_first_of_month(m) for m in (lag_months, lag_months + 1)]
    attempts.append(None)
    for when in attempts:
        stamp = when or "default"
        path = _assets_dir() / f"heat_{stamp}_{width}.png"
        relative = f"assets/heat_{stamp}_{width}.png"
        if path.exists():
            date = when or _wms_time_default(LAYER_HEAT)
            return {"url": relative, "date": (date or "latest")[:7]}
        png = _download_png(GIBS_WMS_URL, _wms_params(LAYERS_HEAT, when, width, height))
        if png and _valid_png(png) and _png_has_data(png):
            try:
                path.write_bytes(png)  # type: ignore[arg-type]
            except OSError:
                return {"url": None, "date": None}
            date = when or _wms_time_default(LAYER_HEAT)
            return {"url": relative, "date": (date or "latest")[:7]}
    return {"url": None, "date": None}


@st.cache_data(ttl=86400, show_spinner=False)
def heat_colormap_bar() -> dict | None:
    """Leggenda della mappa termica: gradiente CSS + estremi in °C.

    Ritorna {"gradient": <css>, "min_c": int, "max_c": int} o None se il
    colormap non è disponibile.
    """
    xml_text = _download_text(COLORMAP_URL.format(LAYER_HEAT))
    if not xml_text:
        return None
    return _parse_colormap_legend(xml_text)


def _parse_colormap_legend(xml_text: str) -> dict | None:
    """Parsa il colormap GIBS in una legenda: colori campionati in ordine
    (gradiente CSS) ed estremi numerici in Kelvin convertiti in °C."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    rows: list[tuple[float | None, tuple[int, int, int]]] = []
    for entry in root.iter("ColorMapEntry"):
        rgb_raw = entry.get("rgb")
        if not rgb_raw:
            continue
        try:
            r, g, b = (int(c) for c in rgb_raw.split(","))
        except ValueError:
            continue
        match = re.match(r"\[(-?inf|-?\d+(?:\.\d+)?)[,;]", entry.get("value", "").strip(), re.I)
        if not match:
            continue
        lo_raw = match.group(1).lower()
        kelvin = None if lo_raw in ("-inf", "+inf", "inf") else float(lo_raw)
        rows.append((kelvin, (r, g, b)))
    numeric = [k for k, _ in rows if k is not None]
    if len(numeric) < 2:
        return None
    colored = [rgb for _, rgb in rows]
    sample = colored[:: max(1, len(colored) // 24)]
    stops = ", ".join(f"#{r:02x}{g:02x}{b:02x}" for r, g, b in sample)
    return {
        "gradient": f"linear-gradient(to right, {stops})",
        "min_c": round(min(numeric) - 273.15),
        "max_c": round(max(numeric) - 273.15),
    }


@st.cache_data(ttl=43200, show_spinner=False)
def ocean_currents() -> dict:
    """Griglia di correnti oceaniche OSCAR (componenti zonal u e meridionale v).

    Ritorna {"date": <data effettiva>, "grid": [[lat, lon, u, v], ...],
    "error": None}; in caso di errore {"date": None, "grid": [], "error": msg}.

    Nota: il prodotto OSCAR su GIBS è fermo a ~luglio 2024 e, a differenza di
    SST e BlueMarble, non approssima TIME alla data più vicina
    (nearestValue=0): una data non disponibile restituisce un'immagine vuota.
    Viene quindi provata la data richiesta e, se la griglia è vuota, la data
    di default del layer (l'ultima disponibile). Il campo "date" riflette
    sempre lo snapshot effettivo, non una previsione.
    """
    time_str = _utc_today(5)
    width, height = 2048, 1024
    layers = {
        "zonal": LAYER_CURRENTS_ZONAL,
        "meridional": LAYER_CURRENTS_MERIDIONAL,
    }

    colormaps: dict[str, dict[tuple[int, int, int], float]] = {}
    for key, layer in layers.items():
        xml_text = _download_text(COLORMAP_URL.format(layer))
        if xml_text is None:
            return {"date": None, "grid": [], "error": f"download colormap fallito ({key})"}
        mapping = _parse_colormap(xml_text)
        if not mapping:
            return {"date": None, "grid": [], "error": f"colormap vuoto o non valido ({key})"}
        colormaps[key] = mapping

    def fetch_pngs(when: str | None) -> dict[str, bytes] | None:
        pngs: dict[str, bytes] = {}
        for key, layer in layers.items():
            png = _download_png(GIBS_WMS_URL, _wms_params(layer, when, width, height))
            if png is None:
                return None
            pngs[key] = png
        return pngs

    def build_grid(pngs: dict[str, bytes]) -> list[list[float]]:
        step = 11
        grid = _decode_current_grid(
            pngs["zonal"], pngs["meridional"],
            colormaps["zonal"], colormaps["meridional"], step,
        )
        while len(grid) > _MAX_VECTORS:
            step += 4
            grid = _decode_current_grid(
                pngs["zonal"], pngs["meridional"],
                colormaps["zonal"], colormaps["meridional"], step,
            )
        return grid

    try:
        pngs = fetch_pngs(time_str)
        if pngs is None:
            return {"date": None, "grid": [], "error": "download WMS correnti fallito"}
        grid = build_grid(pngs)
        if grid:
            return {"date": time_str, "grid": grid, "error": None}
        # La data richiesta non ha dati (prodotto fermo): riprova con la
        # data di default del layer (ultimo istante disponibile, senza TIME).
        pngs = fetch_pngs(None)
        if pngs is None:
            return {"date": None, "grid": [], "error": "download WMS correnti (default) fallito"}
        grid = build_grid(pngs)
        if not grid:
            return {"date": None, "grid": [], "error": "nessun dato correnti disponibile"}
        return {"date": _wms_time_default(LAYER_CURRENTS_ZONAL) or "latest", "grid": grid, "error": None}
    except (ValueError, OSError) as exc:
        return {"date": None, "grid": [], "error": f"decode PNG fallito: {exc}"}
