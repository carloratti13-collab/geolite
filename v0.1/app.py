"""GeoLite interactive geology dashboard."""
from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from ai.qwen_local import QwenLocal
from auth.auth import RegistrationError, authenticate, delete_account, logout, register_user
from data.climate import world_climate_grid
from data.earthquakes import earthquake_feed
from data.mineral_images import search_candidate_mineral_images
from data.minerals import mineral_occurrences
from data.volcanoes import recent_volcano_events
from maps.climate_map import climate_choropleth
from maps.seismic_map import seismic_hover_map, seismic_points
from maps.volcano_3d import volcano_scene_html
from maps.volcano_map import volcano_event_map

st.set_page_config(page_title="GeoLite", page_icon="🌋", layout="wide", initial_sidebar_state="expanded")


def apply_cartoon_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap');

        :root {
            --gb-ink: #202a2a;
            --gb-paper: #f5faf4;
            --gb-lime: #c5f36a;
            --gb-coral: #ff8069;
            --gb-sky: #87d8ef;
            --gb-yellow: #ffdc68;
            --gb-mint: #d8f2df;
            --gb-line: #25302d;
        }

        .stApp {
            color: var(--gb-ink);
            background-color: var(--gb-paper);
            background-image: radial-gradient(#d7e8d7 1px, transparent 1px);
            background-size: 22px 22px;
            font-family: 'Nunito', 'Avenir Next', ui-rounded, sans-serif;
        }
        [data-testid="stHeader"] { background: rgba(245, 250, 244, .88); }
        [data-testid="stAppViewContainer"] { background: transparent; }
        .block-container { position: relative; z-index: 1; padding-top: 2.2rem; }
        [data-testid="stSidebar"] {
            background: var(--gb-mint);
            border-right: 2px solid var(--gb-line);
        }
        [data-testid="stSidebar"] > div:first-child { background: transparent; }

        h1, h2, h3, [data-testid="stMetricValue"] {
            color: var(--gb-ink);
            font-family: 'Nunito', 'Avenir Next', ui-rounded, sans-serif;
            font-weight: 900;
        }
        h1 { width: fit-content; padding: .12em .38em; border: 2px solid var(--gb-line); border-radius: 8px; background: var(--gb-lime); box-shadow: 4px 4px 0 var(--gb-line); }
        h2 { display: flex; align-items: center; gap: .45rem; }
        h2::before { content: '✳'; color: #ef765e; font-size: .76em; }
        [data-testid="stCaptionContainer"] { color: #485654; }

        [data-testid="stMetric"] {
            min-height: 112px;
            padding: 14px 16px;
            border: 2px solid var(--gb-line);
            border-radius: 8px;
            background: var(--gb-lime);
            box-shadow: 4px 4px 0 var(--gb-line);
        }
        [data-testid="stHorizontalBlock"] [data-testid="stMetric"]:nth-child(2) { background: var(--gb-sky); }
        [data-testid="stHorizontalBlock"] [data-testid="stMetric"]:nth-child(3) { background: var(--gb-yellow); }

        .stButton > button, [data-testid="stFormSubmitButton"] > button {
            min-height: 42px;
            border: 2px solid var(--gb-line);
            border-radius: 8px;
            background: var(--gb-lime);
            color: var(--gb-ink);
            font-weight: 900;
            box-shadow: 3px 3px 0 var(--gb-line);
            transition: transform .15s ease, box-shadow .15s ease, background .15s ease;
        }
        .stButton > button::after, [data-testid="stFormSubmitButton"] > button::after { content: ' ↗'; }
        .stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
            transform: translate(2px, 2px);
            box-shadow: 1px 1px 0 var(--gb-line);
            background: var(--gb-yellow);
            color: var(--gb-ink);
        }
        [data-baseweb="select"] > div, [data-testid="stTextInput"] input, [data-testid="stChatInput"] textarea {
            border: 2px solid var(--gb-line);
            border-radius: 8px;
            background: #fff;
        }
        [data-testid="stDataFrame"], [data-testid="stTable"] {
            border: 2px solid var(--gb-line);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 3px 3px 0 rgba(37, 48, 45, .22);
        }
        [data-testid="stAlert"] { border: 2px solid var(--gb-line); border-radius: 8px; }
        [data-testid="stChatMessage"] { border: 1.5px solid #a8bbb0; border-radius: 8px; background: rgba(255,255,255,.78); }
        hr { border-color: #afc8b8; }

        .gb-sticker-layer {
            position: fixed;
            z-index: 0;
            inset: 0;
            overflow: hidden;
            pointer-events: none;
        }
        .gb-sticker {
            position: absolute;
            display: grid;
            width: 54px;
            height: 54px;
            place-items: center;
            border: 2px solid var(--gb-line);
            border-radius: 16px;
            background: white;
            box-shadow: 3px 3px 0 var(--gb-line);
            font-size: 27px;
            line-height: 1;
            opacity: .84;
            transform: rotate(-9deg);
        }
        .gb-sticker:nth-child(1) { top: 17%; left: 1.2%; background: var(--gb-sky); }
        .gb-sticker:nth-child(2) { top: 38%; left: 1.5%; transform: rotate(8deg); background: var(--gb-yellow); }
        .gb-sticker:nth-child(3) { top: 64%; left: .8%; background: var(--gb-coral); }
        .gb-sticker:nth-child(4) { top: 23%; right: 1.4%; transform: rotate(9deg); background: var(--gb-lime); }
        .gb-sticker:nth-child(5) { top: 49%; right: 1%; background: var(--gb-sky); }
        .gb-sticker:nth-child(6) { top: 73%; right: 1.6%; transform: rotate(-8deg); background: var(--gb-yellow); }
        .gb-sticker:nth-child(7) { top: 88%; left: 4%; width: 40px; height: 40px; background: var(--gb-lime); }
        .gb-sticker:nth-child(8) { top: 88%; right: 5%; width: 40px; height: 40px; transform: rotate(10deg); background: var(--gb-coral); }
        @media (max-width: 1250px) {
            .gb-sticker { display: none; }
        }
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after { transition-duration: .01ms !important; animation-duration: .01ms !important; }
        }
        </style>
        <div class="gb-sticker-layer" aria-hidden="true">
            <span class="gb-sticker">🌍</span><span class="gb-sticker">↗</span>
            <span class="gb-sticker">🌋</span><span class="gb-sticker">💎</span>
            <span class="gb-sticker">☄️</span><span class="gb-sticker">🪨</span>
            <span class="gb-sticker">✦</span><span class="gb-sticker">☁️</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


LANGUAGE_OPTIONS = ["Italiano", "English", "Español", "Polski", "中文"]
LANGUAGE_CODES = {"Italiano": "it", "English": "en", "Español": "es", "Polski": "pl", "中文": "zh"}
VOLCANO_TEXT = {
    "Italiano": {
        "navigation": "Sezione",
        "dashboard_view": "Atlante",
        "volcanology_view": "Vulcanologia",
        "simulation_controls": "Controlli della simulazione",
        "volcano_type": "Forma del vulcano",
        "stratovolcano": "Stratovulcano",
        "shield_volcano": "Vulcano a scudo",
        "caldera": "Caldera",
        "pressure": "Pressione magmatica",
        "gas_content": "Contenuto di gas",
        "viscosity": "Viscosità del magma",
        "didactic_notice": "Modello didattico: illustra strutture e comportamenti qualitativi; non è una previsione né una valutazione di pericolo.",
        "model_name": "Modello vulcanico 3D",
        "controls": "Trascina per ruotare · rotella per zoomare",
        "load_error": "La scena 3D non è disponibile: controlla la connessione al servizio Three.js.",
        "crater": "Cratere",
        "layers": "Strati vulcanici",
        "conduit": "Condotto",
        "chamber": "Camera magmatica",
        "flank": "Versante e colata",
        "eruption_events": "Eruzioni recenti e attività in corso",
        "eruption_caption": "Eventi vulcanici aperti e geolocalizzati nel catalogo NASA EONET. La data indica l’ultima osservazione riportata.",
        "volcano_name": "Vulcano",
        "eruption_date": "Data osservazione",
        "source": "Apri fonte NASA EONET",
        "feed_empty": "Il feed NASA EONET non è disponibile o non contiene eventi geolocalizzati.",
        "event_count": "Eventi vulcanici monitorati",
        "table_title": "Vulcano / evento",
        "table_date": "Data osservazione",
    },
    "English": {
        "navigation": "Section",
        "dashboard_view": "Atlas",
        "volcanology_view": "Volcanology",
        "simulation_controls": "Simulation controls",
        "volcano_type": "Volcano shape",
        "stratovolcano": "Stratovolcano",
        "shield_volcano": "Shield volcano",
        "caldera": "Caldera",
        "pressure": "Magma pressure",
        "gas_content": "Gas content",
        "viscosity": "Magma viscosity",
        "didactic_notice": "Educational model: illustrates structures and qualitative behavior; it is not a forecast or hazard assessment.",
        "model_name": "3D volcano model",
        "controls": "Drag to rotate · wheel to zoom",
        "load_error": "The 3D scene is unavailable. Check the connection to the Three.js service.",
        "crater": "Crater",
        "layers": "Volcanic layers",
        "conduit": "Conduit",
        "chamber": "Magma chamber",
        "flank": "Flank and lava flow",
        "eruption_events": "Recent eruptions and ongoing activity",
        "eruption_caption": "Open, geolocated volcanic events in NASA EONET. The date is the latest reported observation.",
        "volcano_name": "Volcano",
        "eruption_date": "Observation date",
        "source": "Open NASA EONET source",
        "feed_empty": "The NASA EONET feed is unavailable or contains no geolocated events.",
        "event_count": "Monitored volcanic events",
        "table_title": "Volcano / event",
        "table_date": "Observation date",
    },
    "Español": {
        "navigation": "Sección",
        "dashboard_view": "Atlas",
        "volcanology_view": "Vulcanología",
        "simulation_controls": "Controles de simulación",
        "volcano_type": "Forma del volcán",
        "stratovolcano": "Estratovolcán",
        "shield_volcano": "Volcán en escudo",
        "caldera": "Caldera",
        "pressure": "Presión magmática",
        "gas_content": "Contenido de gas",
        "viscosity": "Viscosidad del magma",
        "didactic_notice": "Modelo educativo: ilustra estructuras y comportamientos cualitativos; no es una predicción ni una evaluación de peligro.",
        "model_name": "Modelo volcánico 3D",
        "controls": "Arrastra para girar · rueda para ampliar",
        "load_error": "La escena 3D no está disponible. Comprueba la conexión al servicio Three.js.",
        "crater": "Cráter",
        "layers": "Capas volcánicas",
        "conduit": "Conducto",
        "chamber": "Cámara magmática",
        "flank": "Ladera y colada",
        "eruption_events": "Erupciones recientes y actividad en curso",
        "eruption_caption": "Eventos volcánicos abiertos y geolocalizados en el catálogo NASA EONET. La fecha indica la última observación registrada.",
        "volcano_name": "Volcán",
        "eruption_date": "Fecha de observación",
        "source": "Abrir fuente NASA EONET",
        "feed_empty": "El feed NASA EONET no está disponible o no contiene eventos geolocalizados.",
        "event_count": "Eventos volcánicos monitorizados",
        "table_title": "Volcán / evento",
        "table_date": "Fecha de observación",
    },
    "Polski": {
        "navigation": "Sekcja",
        "dashboard_view": "Atlas",
        "volcanology_view": "Wulkanologia",
        "simulation_controls": "Sterowanie symulacją",
        "volcano_type": "Kształt wulkanu",
        "stratovolcano": "Stratowulkan",
        "shield_volcano": "Wulkan tarczowy",
        "caldera": "Kaldera",
        "pressure": "Ciśnienie magmy",
        "gas_content": "Zawartość gazu",
        "viscosity": "Lepkość magmy",
        "didactic_notice": "Model edukacyjny: pokazuje struktury i jakościowe zachowanie; nie jest prognozą ani oceną zagrożenia.",
        "model_name": "Model wulkanu 3D",
        "controls": "Przeciągnij, aby obrócić · kółko, aby powiększyć",
        "load_error": "Scena 3D jest niedostępna. Sprawdź połączenie z usługą Three.js.",
        "crater": "Krater",
        "layers": "Warstwy wulkaniczne",
        "conduit": "Kanał wulkaniczny",
        "chamber": "Komora magmowa",
        "flank": "Zbocze i potok lawy",
        "eruption_events": "Niedawne erupcje i trwająca aktywność",
        "eruption_caption": "Otwarte, zlokalizowane zdarzenia wulkaniczne w katalogu NASA EONET. Data oznacza ostatnią zgłoszoną obserwację.",
        "volcano_name": "Wulkan",
        "eruption_date": "Data obserwacji",
        "source": "Otwórz źródło NASA EONET",
        "feed_empty": "Kanał NASA EONET jest niedostępny lub nie zawiera zlokalizowanych zdarzeń.",
        "event_count": "Monitorowane zdarzenia wulkaniczne",
        "table_title": "Wulkan / zdarzenie",
        "table_date": "Data obserwacji",
    },
    "中文": {
        "navigation": "页面",
        "dashboard_view": "地球图集",
        "volcanology_view": "火山学",
        "simulation_controls": "模拟控制",
        "volcano_type": "火山形态",
        "stratovolcano": "层状火山",
        "shield_volcano": "盾状火山",
        "caldera": "破火山口",
        "pressure": "岩浆压力",
        "gas_content": "气体含量",
        "viscosity": "岩浆黏度",
        "didactic_notice": "教学模型：展示结构和定性行为，不用于预测或危险评估。",
        "model_name": "3D 火山模型",
        "controls": "拖动旋转 · 滚轮缩放",
        "load_error": "3D 场景不可用，请检查 Three.js 服务连接。",
        "crater": "火山口",
        "layers": "火山地层",
        "conduit": "火山通道",
        "chamber": "岩浆房",
        "flank": "火山坡与熔岩流",
        "eruption_events": "近期喷发与持续活动",
        "eruption_caption": "NASA EONET 目录中开放且带地理位置的火山事件。日期表示最近一次报告的观测时间。",
        "volcano_name": "火山",
        "eruption_date": "观测日期",
        "source": "打开 NASA EONET 来源",
        "feed_empty": "NASA EONET 数据源不可用或没有带地理位置的事件。",
        "event_count": "监测中的火山事件",
        "table_title": "火山 / 事件",
        "table_date": "观测日期",
    },
}
MINERAL_NAMES = {
    "Zolfo nativo": {"English": "Native sulfur", "Español": "Azufre nativo", "Polski": "Siarka rodzima", "中文": "自然硫"},
    "Olivina": {"English": "Olivine", "Español": "Olivino", "Polski": "Oliwin", "中文": "橄榄石"},
    "Rame": {"English": "Copper", "Español": "Cobre", "Polski": "Miedź", "中文": "铜"},
    "Quarzo": {"English": "Quartz", "Español": "Cuarzo", "Polski": "Kwarc", "中文": "石英"},
    "Pirite": {"English": "Pyrite", "Español": "Pirita", "Polski": "Piryt", "中文": "黄铁矿"},
    "Ematite": {"English": "Hematite", "Español": "Hematita", "Polski": "Hematyt", "中文": "赤铁矿"},
    "Malachite": {"English": "Malachite", "Español": "Malaquita", "Polski": "Malachit", "中文": "孔雀石"},
    "Galena": {"English": "Galena", "Español": "Galena", "Polski": "Galena", "中文": "方铅矿"},
}
MINERAL_NOTES = {
    "Zolfo nativo": {"Italiano": "Area vulcanica e fumarolica", "English": "Volcanic and fumarolic area", "Español": "Zona volcánica y fumarólica", "Polski": "Obszar wulkaniczny i fumarolowy", "中文": "火山与 fumarole 活动区"},
    "Olivina": {"Italiano": "Rocce basaltiche", "English": "Basaltic rocks", "Español": "Rocas basálticas", "Polski": "Skały bazaltowe", "中文": "玄武岩"},
    "Rame": {"Italiano": "Cintura metallogenica andina", "English": "Andean metallogenic belt", "Español": "Franja metalogénica andina", "Polski": "Andyjski pas metalogeniczny", "中文": "安第斯成矿带"},
    "Quarzo": {"Italiano": "Zone metamorfiche", "English": "Metamorphic zones", "Español": "Zonas metamórficas", "Polski": "Strefy metamorficzne", "中文": "变质带"},
    "Pirite": {"Italiano": "Distretto minerario toscano", "English": "Tuscan mining district", "Español": "Distrito minero de Toscana", "Polski": "Toskański okręg górniczy", "中文": "托斯卡纳矿区"},
    "Ematite": {"Italiano": "Formazioni ferrifere del Minas Gerais", "English": "Iron formations of Minas Gerais", "Español": "Formaciones ferríferas de Minas Gerais", "Polski": "Formacje żelaziste Minas Gerais", "中文": "米纳斯吉拉斯铁矿地层"},
    "Malachite": {"Italiano": "Mineralizzazione di rame", "English": "Copper mineralization", "Español": "Mineralización de cobre", "Polski": "Mineralizacja miedzi", "中文": "铜矿化"},
    "Galena": {"Italiano": "Filoni idrotermali andini", "English": "Andean hydrothermal veins", "Español": "Filones hidrotermales andinos", "Polski": "Andyjskie żyły hydrotermalne", "中文": "安第斯热液脉"},
}
COUNTRY_NAMES = {
    "Italia": {"English": "Italy", "Español": "Italia", "Polski": "Włochy", "中文": "意大利"},
    "Islanda": {"English": "Iceland", "Español": "Islandia", "Polski": "Islandia", "中文": "冰岛"},
    "Giappone": {"English": "Japan", "Español": "Japón", "Polski": "Japonia", "中文": "日本"},
    "Cile": {"English": "Chile", "Español": "Chile", "Polski": "Chile", "中文": "智利"},
    "Brasile": {"English": "Brazil", "Español": "Brasil", "Polski": "Brazylia", "中文": "巴西"},
    "Peru": {"English": "Peru", "Español": "Perú", "Polski": "Peru", "中文": "秘鲁"},
    "Australia": {"English": "Australia", "Español": "Australia", "Polski": "Australia", "中文": "澳大利亚"},
}


def localize_mineral(value: str, language: str) -> str:
    return MINERAL_NAMES.get(value, {}).get(language, value)


def localize_country(value: str, language: str) -> str:
    return COUNTRY_NAMES.get(value, {}).get(language, value)


def localize_seismic_display(events: pd.DataFrame, language: str, text: dict[str, str]) -> pd.DataFrame:
    localized = events.copy()
    original = events
    damage_labels = {
        "reported_or_probable_damage": text["damage_reported"],
        "no_damage_signal": text["damage_none"],
        "unavailable": text["damage_unknown"],
    }
    if "damage_status" in localized:
        if "damage_reason" in localized:
            localized["damage_reason"] = original["damage_status"].map(
                lambda status: text.get(f"damage_reason_{status}", text["damage_reason_unavailable"])
            )
        localized["damage_status"] = localized["damage_status"].map(damage_labels).fillna(text["damage_unknown"])
    for column in ("mineral", "mineral_candidates"):
        if column in localized:
            localized[column] = localized[column].map(
                lambda value: ", ".join(localize_mineral(name.strip(), language) for name in str(value).split(","))
            )
    if "mineral_country" in localized:
        localized["mineral_country"] = localized["mineral_country"].map(lambda value: localize_country(value, language))
    if "mineral_note" in localized:
        localized["mineral_note"] = original["mineral"].map(
            lambda mineral: MINERAL_NOTES.get(mineral, {}).get(language, "")
        )
    if "mineral_reason" in localized:
        localized["mineral_reason"] = localized["mineral_distance_km"].map(
            lambda distance: text["mineral_reason_template"].format(distance=distance)
        )
    return localized


@st.cache_data(ttl=60)
def load_earthquakes(days: int, min_magnitude: float) -> pd.DataFrame:
    return earthquake_feed(days=days, min_magnitude=min_magnitude)


@st.cache_data(ttl=3600)
def load_minerals() -> pd.DataFrame:
    return mineral_occurrences()


@st.cache_data(ttl=900)
def load_world_climate() -> pd.DataFrame:
    return world_climate_grid()


@st.cache_data(ttl=900)
def load_volcano_events() -> pd.DataFrame:
    return recent_volcano_events()


@st.cache_resource
def load_qwen() -> QwenLocal:
    return QwenLocal()


def get_text(language: str) -> dict[str, str]:
    translations = {
        "Italiano": {
            "caption": "Un atlante live per leggere sismicità, rocce e clima.",
            "seismic": "Sismicità recente",
            "climate": "Atlante climatico mondiale",
            "chat": "Chiedi a Qwen",
            "events": "Eventi",
            "depth": "Profondità media",
            "temperature": "Temperatura",
            "gallery": "Immagini autentiche dei minerali",
            "source_usgs": "Fonte live: USGS. Colori: verde, giallo, arancione, rosso e viola in base alla magnitudo.",
            "no_events": "Nessun evento corrisponde ai filtri selezionati.",
            "event_detail": "Dettaglio evento sismico",
            "location": "Luogo",
            "magnitude": "Magnitudo",
            "depth_label": "Profondità",
            "coordinates": "Coordinate",
            "nearest_mineral": "Minerale più vicino",
            "source_climate": "Fonte live: Open-Meteo. La mappa mostra la temperatura attuale globale.",
            "climate_unavailable": "La griglia climatica non è disponibile in questo momento.",
            "question_placeholder": "Scrivi una domanda...",
            "assistant_waiting": "Qwen sta elaborando la risposta...",
            "login_intro": "Un atlante interattivo del pianeta con dati live e tutor AI locale.",
            "login_button": "Accedi",
            "invalid_credentials": "Credenziali non valide",
            "logout": "Esci",
            "language": "Lingua",
            "time_window": "Arco temporale (giorni)",
            "minimum_magnitude": "Magnitudo minima",
            "ask_limit": "Domande illimitate. Scrivi domande su sismologia, geografia fisica o geologia del pianeta.",
            "username": "Username",
            "password": "Password",
            "dashboard_title": "GeoLite",
            "table_time": "Tempo",
            "table_magnitude": "Magnitudo",
            "table_place": "Località",
            "table_depth": "Profondità (km)",
            "table_mineral": "Minerale",
            "table_country": "Paese del minerale",
            "damage": "Danni",
            "damage_reason": "Motivazione danni",
            "mineral_candidates": "Minerali candidati",
            "mineral_distance": "Distanza minerale (km)",
            "mineral_reason": "Motivazione minerale",
            "map_hint": "Passa il cursore sui punti per vedere danni e minerali candidati.",
            "damage_reason_reported_or_probable_damage": "USGS segnala persone che hanno avvertito l’evento, forti scuotimenti o un livello di allerta elevato.",
            "damage_reason_no_damage_signal": "Nei dati USGS non risultano segnali di effetti dannosi per questo evento.",
            "damage_reason_unavailable": "USGS non fornisce informazioni sufficienti per valutare i danni.",
            "mineral_score_label": "Punteggio minerale",
            "live_images": "Immagini dei minerali da Wikimedia Commons",
            "ai_insights": "Analisi AI",
            "ai_caption": "Analisi, grafici e avvisi basati sui dati sismici e climatici disponibili.",
            "analysis_mode": "Tipo di analisi",
            "mode_overview": "Panoramica",
            "mode_risk": "Rischio sismico",
            "mode_climate": "Clima",
            "generate_insight": "Genera analisi AI",
            "empty_analysis": "Non ci sono dati sismici recenti da analizzare.",
            "alert_seismic": "Allerta sismica elevata: M{magnitude:.1f} vicino a {place}.",
            "alert_activity": "L’attività sismica è elevata rispetto ai dati recenti.",
            "alert_climate": "Avviso climatico: la temperatura media della griglia è {temperature:.1f} °C.",
            "damage_reported": "Danni segnalati o probabili",
            "damage_none": "Nessun segnale di danni",
            "damage_unknown": "Dati non disponibili",
            "mineral_reason_template": "Occorrenza documentata più vicina: {distance:.0f} km; punteggio contestualizzato per magnitudo e profondità.",
            "image_attribution": "Licenza",
            "qwen_error": "Non è stato possibile completare l’analisi AI.",
            "insight_time": "Data",
            "insight_location": "Località",
            "insight_magnitude": "Magnitudo",
            "chart_events": "Numero di terremoti",
            "chart_value": "Valore",
            "chart_latitude": "Latitudine",
            "chart_temperature": "Temperatura (°C)",
            "language_selector": "Lingua",
            "demo_account": "Account demo: `student` / `student-demo`",
            "auth_mode": "Accesso",
            "login_tab": "Accedi",
            "register_tab": "Registrati",
            "registration_success": "Account creato. Ora puoi accedere.",
            "invalid_username": "Usa da 3 a 24 caratteri: lettere, numeri, punto, trattino o underscore.",
            "invalid_password": "La password deve contenere da 8 a 128 caratteri.",
            "username_taken": "Questo nome utente è già in uso.",
            "registration_error": "Non è stato possibile creare l’account. Riprova.",
            "account_storage_error": "Servizio account temporaneamente non disponibile.",
            "delete_account": "Elimina account",
            "delete_warning": "Questa azione elimina definitivamente il tuo account. Non può essere annullata.",
            "delete_password": "Password attuale",
            "delete_confirm": "Confermo l’eliminazione definitiva del mio account",
            "delete_submit": "Elimina definitivamente",
            "delete_confirm_required": "Seleziona la conferma per continuare.",
            "account_deleted": "Account eliminato. Puoi registrarti di nuovo quando vuoi.",
            "delete_wrong_password": "Password errata: account non eliminato.",
            "delete_error": "Non è stato possibile eliminare l’account. Riprova.",
        },
        "English": {
            "caption": "A live atlas for earthquakes, rocks and climate.",
            "seismic": "Recent seismicity",
            "climate": "World climate atlas",
            "chat": "Ask Qwen",
            "events": "Events",
            "depth": "Average depth",
            "temperature": "Temperature",
            "gallery": "Authentic mineral images",
            "source_usgs": "Live source: USGS. Colors: green, yellow, orange, red and purple based on magnitude.",
            "no_events": "No events match the selected filters.",
            "event_detail": "Seismic event detail",
            "location": "Location",
            "magnitude": "Magnitude",
            "depth_label": "Depth",
            "coordinates": "Coordinates",
            "nearest_mineral": "Nearest mineral",
            "source_climate": "Live source: Open-Meteo. The map shows the current global temperature.",
            "climate_unavailable": "The climate grid is not available right now.",
            "question_placeholder": "Ask a question...",
            "assistant_waiting": "Qwen is preparing the answer...",
            "login_intro": "An interactive atlas of the planet with live data and a local AI tutor.",
            "login_button": "Log in",
            "invalid_credentials": "Invalid credentials",
            "logout": "Log out",
            "language": "Language",
            "time_window": "Time window (days)",
            "minimum_magnitude": "Minimum magnitude",
            "ask_limit": "Unlimited questions. Ask about seismology, physical geography or geology of the planet.",
            "username": "Username",
            "password": "Password",
            "dashboard_title": "GeoLite",
            "table_time": "Time",
            "table_magnitude": "Magnitude",
            "table_place": "Location",
            "table_depth": "Depth (km)",
            "table_mineral": "Mineral",
            "table_country": "Mineral country",
            "damage": "Damage",
            "damage_reason": "Damage evidence",
            "mineral_candidates": "Candidate minerals",
            "mineral_distance": "Mineral distance (km)",
            "mineral_reason": "Mineral reasoning",
            "map_hint": "Hover over the points to see damage status and candidate minerals.",
            "damage_reason_reported_or_probable_damage": "USGS reports felt reports, strong shaking, or an elevated alert level.",
            "damage_reason_no_damage_signal": "USGS data contains no signal of damaging effects for this event.",
            "damage_reason_unavailable": "USGS does not provide enough information to assess damage.",
            "mineral_score_label": "Mineral score",
            "live_images": "Mineral images from Wikimedia Commons",
            "ai_insights": "AI Insights",
            "ai_caption": "Analysis, charts, and alerts based on available seismic and climate data.",
            "analysis_mode": "Analysis type",
            "mode_overview": "Overview",
            "mode_risk": "Seismic risk",
            "mode_climate": "Climate",
            "generate_insight": "Generate AI analysis",
            "empty_analysis": "There is no recent seismic data to analyze.",
            "alert_seismic": "High seismic alert: M{magnitude:.1f} near {place}.",
            "alert_activity": "Seismic activity is elevated compared with recent data.",
            "alert_climate": "Climate alert: grid average temperature is {temperature:.1f} °C.",
            "damage_reported": "Reported or probable damage",
            "damage_none": "No damage signal",
            "damage_unknown": "Data unavailable",
            "mineral_reason_template": "Nearest documented occurrence: {distance:.0f} km; score contextualized by magnitude and depth.",
            "image_attribution": "License",
            "qwen_error": "The AI analysis could not be completed.",
            "insight_time": "Date",
            "insight_location": "Location",
            "insight_magnitude": "Magnitude",
            "chart_events": "Earthquake count",
            "chart_value": "Value",
            "chart_latitude": "Latitude",
            "chart_temperature": "Temperature (°C)",
            "language_selector": "Language",
            "demo_account": "Demo account: `student` / `student-demo`",
            "auth_mode": "Account access",
            "login_tab": "Log in",
            "register_tab": "Register",
            "registration_success": "Account created. You can now log in.",
            "invalid_username": "Use 3–24 characters: letters, numbers, period, hyphen, or underscore.",
            "invalid_password": "Password must be 8–128 characters long.",
            "username_taken": "That username is already in use.",
            "registration_error": "Could not create the account. Please try again.",
            "account_storage_error": "The account service is temporarily unavailable.",
            "delete_account": "Delete account",
            "delete_warning": "This permanently deletes your account. This action cannot be undone.",
            "delete_password": "Current password",
            "delete_confirm": "I confirm the permanent deletion of my account",
            "delete_submit": "Delete permanently",
            "delete_confirm_required": "Select the confirmation box to continue.",
            "account_deleted": "Account deleted. You can register again at any time.",
            "delete_wrong_password": "Incorrect password. Account was not deleted.",
            "delete_error": "Could not delete the account. Please try again.",
        },
        "Español": {
            "caption": "Un atlas en directo de sismos, rocas y clima.",
            "seismic": "Sismicidad reciente",
            "climate": "Atlas climático mundial",
            "chat": "Pregunta a Qwen",
            "events": "Eventos",
            "depth": "Profundidad media",
            "temperature": "Temperatura",
            "gallery": "Imágenes auténticas de minerales",
            "source_usgs": "Fuente en vivo: USGS. Colores: verde, amarillo, naranja, rojo y morado según la magnitud.",
            "no_events": "No hay eventos que coincidan con los filtros seleccionados.",
            "event_detail": "Detalle del evento sísmico",
            "location": "Lugar",
            "magnitude": "Magnitud",
            "depth_label": "Profundidad",
            "coordinates": "Coordenadas",
            "nearest_mineral": "Mineral más cercano",
            "source_climate": "Fuente en vivo: Open-Meteo. El mapa muestra la temperatura global actual.",
            "climate_unavailable": "La cuadrícula climática no está disponible en este momento.",
            "question_placeholder": "Escribe una pregunta...",
            "assistant_waiting": "Qwen está preparando la respuesta...",
            "login_intro": "Un atlas interactivo del planeta con datos en vivo y un tutor AI local.",
            "login_button": "Iniciar sesión",
            "invalid_credentials": "Credenciales no válidas",
            "logout": "Cerrar sesión",
            "language": "Idioma",
            "time_window": "Periodo de tiempo (días)",
            "minimum_magnitude": "Magnitud mínima",
            "ask_limit": "Preguntas ilimitadas. Pregunta sobre sismología, geografía física o geología del planeta.",
            "username": "Usuario",
            "password": "Contraseña",
            "dashboard_title": "GeoLite",
            "table_time": "Hora",
            "table_magnitude": "Magnitud",
            "table_place": "Ubicación",
            "table_depth": "Profundidad (km)",
            "table_mineral": "Mineral",
            "table_country": "País del mineral",
            "damage": "Daños",
            "damage_reason": "Evidencia de daños",
            "mineral_candidates": "Minerales candidatos",
            "mineral_distance": "Distancia del mineral (km)",
            "mineral_reason": "Razón del mineral",
            "map_hint": "Pasa el cursor sobre los puntos para ver daños y minerales candidatos.",
            "damage_reason_reported_or_probable_damage": "USGS informa de personas que sintieron el sismo, sacudidas fuertes o un nivel de alerta elevado.",
            "damage_reason_no_damage_signal": "Los datos de USGS no muestran indicios de efectos dañinos para este evento.",
            "damage_reason_unavailable": "USGS no proporciona información suficiente para evaluar los daños.",
            "mineral_score_label": "Puntuación del mineral",
            "live_images": "Imágenes de minerales de Wikimedia Commons",
            "ai_insights": "Análisis de IA",
            "ai_caption": "Análisis, gráficos y alertas basados en los datos sísmicos y climáticos disponibles.",
            "analysis_mode": "Tipo de análisis",
            "mode_overview": "Resumen",
            "mode_risk": "Riesgo sísmico",
            "mode_climate": "Clima",
            "generate_insight": "Generar análisis de IA",
            "empty_analysis": "No hay datos sísmicos recientes para analizar.",
            "alert_seismic": "Alerta sísmica elevada: M{magnitude:.1f} cerca de {place}.",
            "alert_activity": "La actividad sísmica es elevada en comparación con los datos recientes.",
            "alert_climate": "Aviso climático: la temperatura media de la cuadrícula es {temperature:.1f} °C.",
            "damage_reported": "Daños notificados o probables",
            "damage_none": "Sin indicios de daños",
            "damage_unknown": "Datos no disponibles",
            "mineral_reason_template": "Ocurrencia documentada más cercana: {distance:.0f} km; puntuación contextualizada por magnitud y profundidad.",
            "image_attribution": "Licencia",
            "qwen_error": "No se pudo completar el análisis de IA.",
            "insight_time": "Fecha",
            "insight_location": "Ubicación",
            "insight_magnitude": "Magnitud",
            "chart_events": "Número de terremotos",
            "chart_value": "Valor",
            "chart_latitude": "Latitud",
            "chart_temperature": "Temperatura (°C)",
            "language_selector": "Idioma",
            "demo_account": "Cuenta de demostración: `student` / `student-demo`",
            "auth_mode": "Acceso a la cuenta",
            "login_tab": "Iniciar sesión",
            "register_tab": "Registrarse",
            "registration_success": "Cuenta creada. Ya puedes iniciar sesión.",
            "invalid_username": "Usa de 3 a 24 caracteres: letras, números, punto, guion o guion bajo.",
            "invalid_password": "La contraseña debe tener entre 8 y 128 caracteres.",
            "username_taken": "Ese nombre de usuario ya está en uso.",
            "registration_error": "No se pudo crear la cuenta. Inténtalo de nuevo.",
            "account_storage_error": "El servicio de cuentas no está disponible temporalmente.",
            "delete_account": "Eliminar cuenta",
            "delete_warning": "Esto eliminará tu cuenta de forma permanente. No se puede deshacer.",
            "delete_password": "Contraseña actual",
            "delete_confirm": "Confirmo la eliminación permanente de mi cuenta",
            "delete_submit": "Eliminar definitivamente",
            "delete_confirm_required": "Marca la casilla de confirmación para continuar.",
            "account_deleted": "Cuenta eliminada. Puedes volver a registrarte cuando quieras.",
            "delete_wrong_password": "Contraseña incorrecta. La cuenta no se eliminó.",
            "delete_error": "No se pudo eliminar la cuenta. Inténtalo de nuevo.",
        },
        "Polski": {
            "caption": "Na żywo atlas trzęsień ziemi, skał i klimatu.",
            "seismic": "Ostatnie trzęsienia ziemi",
            "climate": "Światowy atlas klimatu",
            "chat": "Zapytaj Qwen",
            "events": "Wydarzenia",
            "depth": "Średnia głębokość",
            "temperature": "Temperatura",
            "gallery": "Autentyczne zdjęcia minerałów",
            "source_usgs": "Źródło na żywo: USGS. Kolory: zielony, żółty, pomarańczowy, czerwony i fioletowy według magnitudo.",
            "no_events": "Brak zdarzeń pasujących do wybranych filtrów.",
            "event_detail": "Szczegóły trzęsienia ziemi",
            "location": "Lokalizacja",
            "magnitude": "Magnitudo",
            "depth_label": "Głębokość",
            "coordinates": "Współrzędne",
            "nearest_mineral": "Najbliższy minerał",
            "source_climate": "Źródło na żywo: Open-Meteo. Mapa pokazuje aktualną temperaturę globalną.",
            "climate_unavailable": "Siatka klimatyczna jest obecnie niedostępna.",
            "question_placeholder": "Napisz pytanie...",
            "assistant_waiting": "Qwen przygotowuje odpowiedź...",
            "login_intro": "Interaktywny atlas planety z danymi na żywo i lokalnym nauczycielem AI.",
            "login_button": "Zaloguj się",
            "invalid_credentials": "Nieprawidłowe dane logowania",
            "logout": "Wyloguj",
            "language": "Język",
            "time_window": "Zakres czasu (dni)",
            "minimum_magnitude": "Minimalne magnitudo",
            "ask_limit": "Nielimitowane pytania. Pytaj o sejsmologię, geografię fizyczną lub geologię planety.",
            "username": "Nazwa użytkownika",
            "password": "Hasło",
            "dashboard_title": "GeoLite",
            "table_time": "Czas",
            "table_magnitude": "Magnitudo",
            "table_place": "Lokalizacja",
            "table_depth": "Głębokość (km)",
            "table_mineral": "Minerał",
            "table_country": "Kraj minerału",
            "damage": "Uszkodzenia",
            "damage_reason": "Dowody uszkodzeń",
            "mineral_candidates": "Minerały kandydujące",
            "mineral_distance": "Odległość minerału (km)",
            "mineral_reason": "Uzasadnienie minerału",
            "map_hint": "Najedź kursorem na punkty, aby zobaczyć szkody i proponowane minerały.",
            "damage_reason_reported_or_probable_damage": "USGS odnotowuje zgłoszenia odczuwalnych wstrząsów, silne drgania lub podwyższony poziom alarmu.",
            "damage_reason_no_damage_signal": "Dane USGS nie wskazują na szkodliwe skutki tego zdarzenia.",
            "damage_reason_unavailable": "USGS nie udostępnia wystarczających informacji do oceny szkód.",
            "mineral_score_label": "Wynik minerału",
            "live_images": "Zdjęcia minerałów z Wikimedia Commons",
            "ai_insights": "Analiza AI",
            "ai_caption": "Analiza, wykresy i alerty na podstawie dostępnych danych sejsmicznych i klimatycznych.",
            "analysis_mode": "Rodzaj analizy",
            "mode_overview": "Przegląd",
            "mode_risk": "Ryzyko sejsmiczne",
            "mode_climate": "Klimat",
            "generate_insight": "Utwórz analizę AI",
            "empty_analysis": "Brak aktualnych danych sejsmicznych do analizy.",
            "alert_seismic": "Wysoki alert sejsmiczny: M{magnitude:.1f} w pobliżu {place}.",
            "alert_activity": "Aktywność sejsmiczna jest podwyższona w porównaniu z ostatnimi danymi.",
            "alert_climate": "Alert klimatyczny: średnia temperatura siatki wynosi {temperature:.1f} °C.",
            "damage_reported": "Zgłoszone lub prawdopodobne szkody",
            "damage_none": "Brak sygnałów o szkodach",
            "damage_unknown": "Brak dostępnych danych",
            "mineral_reason_template": "Najbliższe udokumentowane wystąpienie: {distance:.0f} km; wynik uwzględnia magnitudo i głębokość.",
            "image_attribution": "Licencja",
            "qwen_error": "Nie udało się ukończyć analizy AI.",
            "insight_time": "Data",
            "insight_location": "Lokalizacja",
            "insight_magnitude": "Magnitudo",
            "chart_events": "Liczba trzęsień ziemi",
            "chart_value": "Wartość",
            "chart_latitude": "Szerokość geograficzna",
            "chart_temperature": "Temperatura (°C)",
            "language_selector": "Język",
            "demo_account": "Konto demonstracyjne: `student` / `student-demo`",
            "auth_mode": "Dostęp do konta",
            "login_tab": "Zaloguj się",
            "register_tab": "Zarejestruj się",
            "registration_success": "Konto utworzone. Możesz się teraz zalogować.",
            "invalid_username": "Użyj 3–24 znaków: liter, cyfr, kropki, łącznika lub podkreślenia.",
            "invalid_password": "Hasło musi mieć od 8 do 128 znaków.",
            "username_taken": "Ta nazwa użytkownika jest już zajęta.",
            "registration_error": "Nie udało się utworzyć konta. Spróbuj ponownie.",
            "account_storage_error": "Usługa kont jest tymczasowo niedostępna.",
            "delete_account": "Usuń konto",
            "delete_warning": "Konto zostanie trwale usunięte. Tej operacji nie można cofnąć.",
            "delete_password": "Obecne hasło",
            "delete_confirm": "Potwierdzam trwałe usunięcie mojego konta",
            "delete_submit": "Usuń trwale",
            "delete_confirm_required": "Zaznacz potwierdzenie, aby kontynuować.",
            "account_deleted": "Konto usunięte. Możesz zarejestrować się ponownie w dowolnym momencie.",
            "delete_wrong_password": "Nieprawidłowe hasło. Konto nie zostało usunięte.",
            "delete_error": "Nie udało się usunąć konta. Spróbuj ponownie.",
        },
        "中文": {
            "caption": "实时地震、岩石和气候地图集。",
            "seismic": "近期地震活动",
            "climate": "全球气候地图集",
            "chat": "询问 Qwen",
            "events": "事件",
            "depth": "平均深度",
            "temperature": "温度",
            "gallery": "真实矿物图像",
            "source_usgs": "实时数据源：USGS。颜色按震级显示：绿色、黄色、橙色、红色和紫色。",
            "no_events": "没有符合当前筛选条件的事件。",
            "event_detail": "地震事件详情",
            "location": "地点",
            "magnitude": "震级",
            "depth_label": "深度",
            "coordinates": "坐标",
            "nearest_mineral": "最近矿物",
            "source_climate": "实时数据源：Open-Meteo。地图显示当前全球温度。",
            "climate_unavailable": "气候网格当前不可用。",
            "question_placeholder": "输入问题...",
            "assistant_waiting": "Qwen 正在生成回答...",
            "login_intro": "一个结合实时数据和本地 AI 助手的互动式地球地图集。",
            "login_button": "登录",
            "invalid_credentials": "凭据无效",
            "logout": "退出",
            "language": "语言",
            "time_window": "时间范围（天）",
            "minimum_magnitude": "最低震级",
            "ask_limit": "无限提问。可询问地震学、自然地理或地球地质相关内容。",
            "username": "用户名",
            "password": "密码",
            "dashboard_title": "GeoLite",
            "table_time": "时间",
            "table_magnitude": "震级",
            "table_place": "地点",
            "table_depth": "深度（km）",
            "table_mineral": "矿物",
            "table_country": "矿物国家",
            "damage": "损害",
            "damage_reason": "损害证据",
            "mineral_candidates": "候选矿物",
            "mineral_distance": "矿物距离（km）",
            "mineral_reason": "矿物判断依据",
            "map_hint": "将鼠标悬停在地图点上可查看损害状态和候选矿物。",
            "damage_reason_reported_or_probable_damage": "USGS 收到震感报告、记录到强烈震动或发布了较高级别警报。",
            "damage_reason_no_damage_signal": "USGS 数据未显示此次事件造成损害的迹象。",
            "damage_reason_unavailable": "USGS 未提供足够信息来评估损害情况。",
            "mineral_score_label": "矿物评分",
            "live_images": "来自 Wikimedia Commons 的矿物图片",
            "ai_insights": "AI 分析",
            "ai_caption": "根据现有地震和气候数据生成分析、图表和提醒。",
            "analysis_mode": "分析类型",
            "mode_overview": "概览",
            "mode_risk": "地震风险",
            "mode_climate": "气候",
            "generate_insight": "生成 AI 分析",
            "empty_analysis": "没有可供分析的近期地震数据。",
            "alert_seismic": "地震高级警报：{place} 附近发生 M{magnitude:.1f} 地震。",
            "alert_activity": "与近期数据相比，地震活动较为活跃。",
            "alert_climate": "气候提醒：网格平均温度为 {temperature:.1f} °C。",
            "damage_reported": "已报告或可能存在损害",
            "damage_none": "没有损害迹象",
            "damage_unknown": "暂无数据",
            "mineral_reason_template": "最近的已记录矿点距离 {distance:.0f} 公里；评分结合震级和深度。",
            "image_attribution": "许可协议",
            "qwen_error": "无法完成 AI 分析。",
            "insight_time": "日期",
            "insight_location": "地点",
            "insight_magnitude": "震级",
            "chart_events": "地震数量",
            "chart_value": "数值",
            "chart_latitude": "纬度",
            "chart_temperature": "温度（°C）",
            "language_selector": "语言",
            "demo_account": "演示账户：`student` / `student-demo`",
            "auth_mode": "账户访问",
            "login_tab": "登录",
            "register_tab": "注册",
            "registration_success": "账户已创建，现在可以登录。",
            "invalid_username": "用户名需为 3–24 个字符，可使用字母、数字、点、连字符或下划线。",
            "invalid_password": "密码长度必须为 8–128 个字符。",
            "username_taken": "该用户名已被使用。",
            "registration_error": "无法创建账户，请重试。",
            "account_storage_error": "账户服务暂时不可用。",
            "delete_account": "删除账户",
            "delete_warning": "此操作将永久删除账户，且无法撤销。",
            "delete_password": "当前密码",
            "delete_confirm": "我确认永久删除我的账户",
            "delete_submit": "永久删除",
            "delete_confirm_required": "请勾选确认框后继续。",
            "account_deleted": "账户已删除。你可以随时重新注册。",
            "delete_wrong_password": "密码错误，账户未删除。",
            "delete_error": "无法删除账户，请重试。",
        },
    }
    text = dict(translations.get(language, translations["Italiano"]))
    text.update(VOLCANO_TEXT.get(language, VOLCANO_TEXT["Italiano"]))
    return text


def _handle_registration_submit() -> None:
    try:
        register_user(
            st.session_state.get("register_username", ""),
            st.session_state.get("register_password", ""),
        )
        st.session_state["auth_mode"] = "login"
        st.session_state["registration_success"] = True
        st.session_state.pop("auth_error", None)
    except RegistrationError as error:
        st.session_state["auth_error"] = error.code
    except (OSError, sqlite3.Error):
        st.session_state["auth_error"] = "account_storage_error"
    finally:
        st.session_state.pop("register_password", None)


def _handle_login_submit() -> None:
    try:
        user = authenticate(
            st.session_state.get("login_username", ""),
            st.session_state.get("login_password", ""),
        )
        if user:
            st.session_state["user"] = user
            st.session_state.pop("auth_error", None)
        else:
            st.session_state["auth_error"] = "invalid_credentials"
    except (OSError, sqlite3.Error):
        st.session_state["auth_error"] = "account_storage_error"
    finally:
        st.session_state.pop("login_password", None)


def ask_qwen(question: str, earthquakes: pd.DataFrame, minerals: pd.DataFrame, language: str) -> str:
    event_columns = ["time", "magnitude", "place", "depth_km", "lat", "lon"]
    mineral_columns = ["mineral", "country", "note"]
    recent_events = earthquakes[event_columns].nlargest(min(50, len(earthquakes)), "magnitude").to_dict("records") if not earthquakes.empty else []
    mineral_records = minerals[mineral_columns].head(16).to_dict("records") if not minerals.empty else []
    lang_code = LANGUAGE_CODES.get(language, "it")
    prompt = (
        f"You are a factual data assistant. Answer only in language code {lang_code}. "
        "Answer the user's exact question in 2-5 concise sentences. Do not create multiple-choice questions, "
        "answer options, summaries of data that are not present, or claims about weather forecasts. "
        "Use only the CONTEXT below. If the context does not contain the requested information, say exactly "
        "that the data is unavailable and do not guess. Never claim that the context contains facts it does not contain.\n\n"
        f"CONTEXT - recent USGS earthquake records: {recent_events}\n"
        f"CONTEXT - educational mineral records: {mineral_records}\n\n"
        f"USER QUESTION: {question}\n"
        "ANSWER:"
    )
    return load_qwen().generate(prompt, max_new_tokens=420)


def build_ai_insight(language: str, earthquakes: pd.DataFrame, climate_grid: pd.DataFrame, insight_mode: str) -> dict[str, object]:
    text = get_text(language)
    if earthquakes.empty:
        return {
            "summary": text["empty_analysis"],
            "table": pd.DataFrame(columns=["time", "place", "magnitude"]),
            "chart": pd.DataFrame(columns=["date", "events"]),
            "chart_kind": "line",
            "alerts": [],
        }

    event_copy = earthquakes.copy()
    event_copy["date"] = pd.to_datetime(event_copy["time"]).dt.date.astype(str)
    event_counts = (
        event_copy.groupby("date", as_index=False)["magnitude"]
        .agg(events="count", max_magnitude="max")
        .sort_values("date")
    )
    top_events = event_copy.nlargest(5, "magnitude")[["time", "place", "magnitude", "depth_km"]].copy()
    top_events = top_events.rename(columns={"time": "time", "place": "location", "magnitude": "magnitude", "depth_km": "depth_km"})

    climate_summary = climate_grid.copy() if not climate_grid.empty else pd.DataFrame(columns=["lat", "temperature_c"])
    if not climate_summary.empty:
        climate_summary = climate_summary[["lat", "temperature_c"]].sort_values("lat").reset_index(drop=True)

    if insight_mode == "risk":
        question = (
            "Analyze the recent seismic dataset and identify the strongest risk signals. "
            "Highlight the highest-magnitude events, explain likely geological significance, and provide a brief risk summary."
        )
    elif insight_mode == "climate":
        question = (
            "Analyze the climate grid, identify temperature anomalies, and explain the main global patterns shown by the data. "
            "Keep the answer concise but useful for a scientific dashboard."
        )
    else:
        question = (
            "Review the seismic and climate data and provide a concise but expert trend analysis. "
            "Answer in a clear, practical way and mention the strongest patterns and outliers."
        )

    summary = ask_qwen(
        question=f"{question}\n\nRecent seismic pattern summary: {event_counts.to_dict('records')}\nTop events: {top_events.to_dict('records')}\nClimate values: {climate_summary.to_dict('records') if not climate_summary.empty else 'not available'}",
        earthquakes=event_copy.nlargest(10, "magnitude"),
        minerals=pd.DataFrame(columns=["mineral", "country", "note"]),
        language=language,
    )

    alerts = detect_alerts(earthquakes, climate_grid, language)
    top_events = top_events.rename(columns={
        "time": text["insight_time"],
        "location": text["insight_location"],
        "magnitude": text["insight_magnitude"],
    })
    if insight_mode == "risk":
        chart_kind = "bar"
        chart = top_events[[text["insight_location"], text["insight_magnitude"]]].rename(columns={text["insight_location"]: text["insight_location"], text["insight_magnitude"]: text["chart_value"]})
    elif insight_mode == "climate" and not climate_summary.empty:
        chart_kind = "scatter"
        chart = climate_summary.rename(columns={"lat": text["chart_latitude"], "temperature_c": text["chart_temperature"]})
    else:
        chart_kind = "line"
        chart = event_counts[["date", "events"]].rename(columns={"date": text["insight_time"], "events": text["chart_events"]})
    return {"summary": summary, "table": top_events, "chart": chart, "chart_kind": chart_kind, "alerts": alerts}


def detect_alerts(earthquakes: pd.DataFrame, climate_grid: pd.DataFrame, language: str = "Italiano") -> list[str]:
    text = get_text(language)
    alerts: list[str] = []
    if not earthquakes.empty:
        strongest = earthquakes.nlargest(1, "magnitude")
        strongest_value = float(strongest.iloc[0]["magnitude"])
        strongest_place = strongest.iloc[0]["place"]
        if strongest_value >= 5.5:
            alerts.append(text["alert_seismic"].format(magnitude=strongest_value, place=strongest_place))
        if earthquakes["magnitude"].mean() >= 4.5:
            alerts.append(text["alert_activity"])
    if not climate_grid.empty:
        avg_temp = float(climate_grid["temperature_c"].mean())
        if avg_temp > 24:
            alerts.append(text["alert_climate"].format(temperature=avg_temp))
    return alerts


def render_dashboard(language: str, days: int, min_magnitude: float) -> None:
    text = get_text(language)
    st.title(text["dashboard_title"])
    st.caption(text["caption"])

    earthquakes = load_earthquakes(days, min_magnitude)
    minerals = load_minerals()
    climate_grid = load_world_climate()
    seismic = seismic_points(earthquakes, minerals)

    avg_depth = f"{earthquakes['depth_km'].mean():.1f} km" if not earthquakes.empty else "n/d"
    avg_temp = f"{climate_grid['temperature_c'].mean():.1f} °C" if not climate_grid.empty else "n/d"

    metric_1, metric_2, metric_3 = st.columns(3)
    metric_1.metric(text["events"], len(earthquakes))
    metric_2.metric(text["depth"], avg_depth)
    metric_3.metric(text["temperature"], avg_temp)

    st.divider()
    st.header(text["seismic"])
    st.caption(text["source_usgs"])
    if seismic.empty:
        st.info(text["no_events"])
    else:
        st.caption(text["map_hint"])
        display_seismic = localize_seismic_display(seismic, language, text)
        st_folium(seismic_hover_map(display_seismic, language, text), use_container_width=True, height=420, returned_objects=[])
        event_labels = [f"{row['time']} · M{row['magnitude']} · {row['place']}" for _, row in seismic.iterrows()]
        selected_label = st.selectbox(text["event_detail"], event_labels)
        selected_index = event_labels.index(selected_label)
        selected_event = display_seismic.iloc[selected_index]
        source_event = seismic.iloc[selected_index]
        detail, image = st.columns([2, 1])
        with detail:
            st.write(f"**{text['location']}:** {selected_event['place']}")
            st.write(f"**{text['magnitude']}:** {selected_event['magnitude']} · **{text['depth_label']}:** {selected_event['depth_km']} km")
            st.write(f"**{text['coordinates']}:** {selected_event['lat']:.4f}, {selected_event['lon']:.4f}")
            st.write(f"**{text['nearest_mineral']}:** {selected_event['mineral']} ({selected_event['mineral_country']})")
            st.write(f"**{text['damage']}:** {selected_event.get('damage_status', 'unavailable')}")
            st.write(f"**{text['damage_reason']}:** {selected_event.get('damage_reason', 'Unavailable')}")
            st.write(f"**{text['mineral_candidates']}:** {selected_event.get('mineral_candidates', selected_event['mineral'])}")
            st.write(f"**{text['mineral_reason']}:** {selected_event.get('mineral_reason', 'Unavailable')}")
            st.write(selected_event["mineral_note"])
        with image:
            st.image(source_event["mineral_image_url"], caption=f"{selected_event['mineral']} · Wikimedia Commons", use_container_width=True)
        candidate_names = str(source_event.get("mineral_candidates", source_event["mineral"])).split(",")
        live_images = search_candidate_mineral_images(candidate_names, limit=16)
        if live_images:
            st.caption(text["live_images"])
            image_columns = st.columns(4)
            for image_index, mineral_image in enumerate(live_images):
                with image_columns[image_index % 4]:
                    st.image(
                        mineral_image["image_url"],
                        caption=f"{localize_mineral(mineral_image['mineral'], language)} · {text['image_attribution']}: {mineral_image['license']}",
                        use_container_width=True,
                    )
        dataframe = display_seismic[["time", "magnitude", "place", "depth_km", "damage_status", "mineral", "mineral_country", "mineral_distance_km", "mineral_candidates"]].rename(
            columns={
                "time": text["table_time"],
                "magnitude": text["table_magnitude"],
                "place": text["table_place"],
                "depth_km": text["table_depth"],
                "mineral": text["table_mineral"],
                "mineral_country": text["table_country"],
                "damage_status": text["damage"],
                "mineral_distance_km": text["mineral_distance"],
                "mineral_candidates": text["mineral_candidates"],
            }
        )
        st.dataframe(dataframe, use_container_width=True, hide_index=True)

    st.divider()
    st.header(text["climate"])
    st.caption(text["source_climate"])
    if climate_grid.empty:
        st.warning(text["climate_unavailable"])
    else:
        st_folium(climate_choropleth(climate_grid), use_container_width=True, height=560, returned_objects=[])

    st.divider()
    st.header(text["ai_insights"])
    st.caption(text["ai_caption"])
    mode_labels = {text["mode_overview"]: "overview", text["mode_risk"]: "risk", text["mode_climate"]: "climate"}
    selected_mode = st.selectbox(text["analysis_mode"], list(mode_labels))
    insight_mode = mode_labels[selected_mode]
    if st.button(text["generate_insight"]):
        insight = build_ai_insight(language, earthquakes, climate_grid, insight_mode)
        st.session_state["last_ai_insight"] = insight
        for alert in insight["alerts"]:
            st.warning(alert)
    if "last_ai_insight" in st.session_state:
        insight = st.session_state["last_ai_insight"]
        st.markdown(insight["summary"])
        if not insight["chart"].empty:
            chart = insight["chart"]
            if insight["chart_kind"] == "bar":
                st.bar_chart(chart.set_index(text["insight_location"])[text["chart_value"]])
            elif insight["chart_kind"] == "scatter":
                st.scatter_chart(chart, x=text["chart_latitude"], y=text["chart_temperature"])
            else:
                st.line_chart(chart.set_index(text["insight_time"])[text["chart_events"]])
        if not insight["table"].empty:
            st.dataframe(insight["table"], use_container_width=True, hide_index=True)

def render_qwen_chat(language: str, earthquakes: pd.DataFrame, minerals: pd.DataFrame) -> None:
    text = get_text(language)
    st.divider()
    st.header(text["chat"])
    st.caption(text["ask_limit"])
    messages_key = "qwen-messages"
    st.session_state.setdefault(messages_key, [])
    for message in st.session_state[messages_key]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    question = st.chat_input(text["question_placeholder"])
    if question:
        st.session_state[messages_key].append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner(text["assistant_waiting"]):
                try:
                    answer = ask_qwen(question, earthquakes, minerals, language)
                    st.markdown(answer)
                    st.session_state[messages_key].append({"role": "assistant", "content": answer})
                except Exception as error:
                    st.error(text["qwen_error"])


def render_volcanology(language: str) -> None:
    text = get_text(language)
    st.header(text["volcanology_view"])
    volcano_types = {
        text["stratovolcano"]: "stratovolcano",
        text["shield_volcano"]: "shield",
        text["caldera"]: "caldera",
    }
    selected_type = st.session_state.get("volcano_type_selection", text["stratovolcano"])
    volcano_type = volcano_types.get(selected_type, "stratovolcano")
    labels = {key: text[key] for key in (
        "model_name", "controls", "load_error", "crater", "layers", "conduit", "chamber", "flank",
        "volcano_name", "eruption_date", "source",
    )}
    st.iframe(
        volcano_scene_html(labels, volcano_type,
                           st.session_state.get("volcano_pressure", 55),
                           st.session_state.get("volcano_gas", 60),
                           st.session_state.get("volcano_viscosity", 40)),
        width="stretch",
        height=760,
    )
    st.caption(text["didactic_notice"])
    st.header(text["simulation_controls"])
    selected_type = st.selectbox(text["volcano_type"], list(volcano_types), key="volcano_type_selection")
    controls = st.columns(3)
    with controls[0]:
        pressure = st.slider(text["pressure"], min_value=0, max_value=100, value=55, key="volcano_pressure")
    with controls[1]:
        gas_content = st.slider(text["gas_content"], min_value=0, max_value=100, value=60, key="volcano_gas")
    with controls[2]:
        viscosity = st.slider(text["viscosity"], min_value=0, max_value=100, value=40, key="volcano_viscosity")

    part_columns = st.columns(5)
    for index, key in enumerate(("crater", "layers", "conduit", "chamber", "flank"), start=1):
        part_columns[index - 1].markdown(f"**{index:02d} · {text[key]}**")

    st.divider()
    st.header(text["eruption_events"])
    st.caption(text["eruption_caption"])
    events = load_volcano_events()
    if events.empty:
        st.info(text["feed_empty"])
    else:
        st.metric(text["event_count"], len(events))
        st_folium(volcano_event_map(events, text), use_container_width=True, height=540, returned_objects=[])
        table = events[["title", "date"]].rename(columns={
            "title": text["table_title"],
            "date": text["table_date"],
        })
        st.dataframe(table, use_container_width=True, hide_index=True)


def main() -> None:
    apply_cartoon_theme()
    if "user" not in st.session_state:
        st.session_state.user = None
    st.session_state.setdefault("language", "Italiano")
    st.session_state.setdefault("auth_mode", "login")

    if st.session_state.user is None:
        st.title("GeoLite")
        login_language = st.selectbox(get_text(st.session_state["language"])["language_selector"], LANGUAGE_OPTIONS, index=LANGUAGE_OPTIONS.index(st.session_state["language"]))
        st.session_state["language"] = login_language
        login_text = get_text(login_language)
        st.write(login_text["login_intro"])
        if st.session_state.pop("account_deleted", False):
            st.success(login_text["account_deleted"])
        if st.session_state.pop("registration_success", False):
            st.success(login_text["registration_success"])
        auth_error = st.session_state.pop("auth_error", None)
        if auth_error:
            error_message = {
                "invalid_credentials": login_text["invalid_credentials"],
                "invalid_username": login_text["invalid_username"],
                "invalid_password": login_text["invalid_password"],
                "username_taken": login_text["username_taken"],
                "account_storage_error": login_text["account_storage_error"],
            }.get(auth_error, login_text["registration_error"])
            st.error(error_message)
        auth_labels = {"login": login_text["login_tab"], "register": login_text["register_tab"]}
        st.radio(
            login_text["auth_mode"],
            options=list(auth_labels),
            format_func=lambda mode: auth_labels[mode],
            horizontal=True,
            key="auth_mode",
            label_visibility="collapsed",
        )
        if st.session_state.pop("registration_success", False):
            st.success(login_text["registration_success"])
        auth_mode = st.session_state["auth_mode"]
        with st.form(f"{auth_mode}_form"):
            username = st.text_input(login_text["username"], key=f"{auth_mode}_username")
            password = st.text_input(login_text["password"], type="password", key=f"{auth_mode}_password")
            submit_label = login_text["login_button"] if auth_mode == "login" else login_text["register_tab"]
            callback = _handle_login_submit if auth_mode == "login" else _handle_registration_submit
            st.form_submit_button(submit_label, type="primary", on_click=callback)
        return

    with st.sidebar:
        st.write(f"**{st.session_state.user['username']}**")
        language = st.selectbox(get_text(st.session_state.get("language", "Italiano"))["language_selector"], LANGUAGE_OPTIONS, index=LANGUAGE_OPTIONS.index(st.session_state.get("language", "Italiano")))
        st.session_state["language"] = language
        text = get_text(language)
        days = st.slider(text["time_window"], min_value=1, max_value=30, value=7)
        min_magnitude = st.slider(text["minimum_magnitude"], min_value=0.0, max_value=7.0, value=2.5, step=0.1)
        if st.button(text["logout"]):
            logout()
            st.rerun()
        with st.expander(text["delete_account"]):
            st.warning(text["delete_warning"])
            with st.form("delete_account_form"):
                delete_password = st.text_input(text["delete_password"], type="password")
                confirmed = st.checkbox(text["delete_confirm"])
                if st.form_submit_button(text["delete_submit"], type="primary"):
                    if not confirmed:
                        st.error(text["delete_confirm_required"])
                    else:
                        try:
                            deleted = delete_account(st.session_state.user["username"], delete_password)
                            if deleted:
                                st.session_state["account_deleted"] = True
                                logout()
                                st.rerun()
                            st.error(text["delete_wrong_password"])
                        except (OSError, sqlite3.Error):
                            st.error(text["delete_error"])
    render_dashboard(language, days, min_magnitude)
    render_volcanology(language)
    render_qwen_chat(language, load_earthquakes(days, min_magnitude), load_minerals())


if __name__ == "__main__":
    main()
