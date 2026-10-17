"""GeoLite v1 — dashboard geologico professionale.

Streamlit (auth gate + layout fisso a pannelli) + componente custom Three.js
(globi 3D, tasto destro "Chiedi all'AI"). AI via API esterna OpenAI-compatible.
"""
from __future__ import annotations

import json

import streamlit as st

from ai.chat import (
    AiError,
    ai_configured,
    ai_model_name,
    ask_stream,
    build_context_messages,
    clear_ai_config,
    set_ai_config,
)
from auth.auth import RegistrationError, authenticate, delete_account, register_user
from auth.user_settings import delete_ai_settings, load_ai_settings, save_ai_settings
from data.climate import (
    base_texture_url,
    climate_texture_url,
    heat_colormap_bar,
    heat_texture_url,
    ocean_currents,
)
from data.earthquakes import earthquake_events
from data.minerals import (
    REASON_CRUST,
    REASON_HYDROTHERMAL,
    REASON_MANTLE,
    REASON_NEARBY,
    REASON_REGIONAL,
    minerals_for_location,
)
from data.volcanoes import volcano_events
from globe_component import globes

st.set_page_config(
    page_title="GeoLite",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

SECTIONS = ["seismic", "volcanoes", "currents", "climate"]

# ---------------------------------------------------------------------------
# Testi UI
# ---------------------------------------------------------------------------

TEXT: dict[str, dict[str, str]] = {
    "it": {
        "app_title": "🌍 GeoLite",
        "tagline": "Dashboard geologico — sismologia, vulcanologia, clima, mineralogia",
        "nav_seismic": "Sismicità",
        "nav_volcanoes": "Vulcani",
        "nav_currents": "Correnti",
        "nav_climate": "Clima",
        "title_seismic": "Sismicità globale — ultimi eventi USGS",
        "title_volcanoes": "Eventi vulcanici in corso — NASA EONET",
        "title_currents": "Correnti — temperatura superficiale del mare (MUR) + correnti OSCAR",
        "title_climate": "Clima — temperatura dell'aria a 2 m (MERRA-2, mensile)",
        "days": "Finestra temporale (giorni)",
        "min_magnitude": "Magnitudo minima",
        "eq_select": "Terremoto",
        "show_currents": "Mostra correnti oceaniche",
        "currents_explain": "✨ Spiegami le correnti",
        "currents_asked": "Panoramica sulle correnti oceaniche (snapshot OSCAR del {date})",
        "sst_note": "SST MUR: aggiornamento circa ogni 2 giorni",
        "heat_note": "Temperatura dell'aria a 2 m (MERRA-2, NASA) — mappa mensile; mese: {date}. Dato climatico mensile, non in tempo reale.",
        "c_heat_label": "temperatura aria a 2 m (MERRA-2)",
        "gm_title": "Minerali nel terreno",
        "gm_hint": (
            "Stima didattica basata su giacitura tipica, vicinanza di giacimenti noti "
            "e profondità focale: non è una mappatura reale del sottosuolo."
        ),
        "gm_no_selection": "Seleziona un terremoto (click sul globo o menu a tendina) per vedere i minerali plausibili nel terreno di quel sito.",
        "gm_reason_nearby": "giacimento noto nella regione (~{km:.0f} km)",
        "gm_reason_regional": "giacimento noto a ~{km:.0f} km",
        "gm_reason_hydrothermal": "crosta superficiale: tipico delle mineralizzazioni idrotermali",
        "gm_reason_mantle": "sismicità profonda: litologie del mantello (olivina-dominate)",
        "gm_reason_crust": "ubiquo nelle rocce della crosta",
        "gm_details": "Dettagli",
        "ai_settings": "API AI",
        "ai_key_label": "Chiave API",
        "ai_base_label": "Base URL",
        "ai_model_label": "Modello",
        "ai_save": "Salva",
        "ai_saved": "Impostazioni AI salvate per il tuo account.",
        "ai_remove": "Rimuovi chiave",
        "ai_removed": "Chiave AI rimossa. L'assistente usa ora solo le variabili d'ambiente.",
        "ai_where_stored": "Salvata localmente in questo dispositivo, collegata al tuo account.",
        "ai_configured_user": "configurata",
        "data_unavailable": "Dati non disponibili in questo momento (problema di rete o fonte non raggiungibile).",
        "eonet_note": "Fonte: NASA EONET v3, eventi con stato «open».",
        "details_title": "Dettagli selezione",
        "no_selection": "Seleziona un elemento sul globo (click sinistro) per vederne i dettagli, oppure usa il tasto destro → «Chiedi all'AI».",
        "d_magnitude": "Magnitudo",
        "d_depth": "Profondità focale",
        "d_place": "Luogo",
        "d_time": "Data/ora (UTC)",
        "d_felt": "Segnalazioni",
        "d_alert": "Allerta USGS",
        "d_mag_type": "Tipo magnitudo",
        "d_tsunami": "Tsunami",
        "d_url": "Scheda USGS",
        "d_categories": "Categorie",
        "d_sources": "Fonti",
        "d_link": "Pagina EONET",
        "d_coords": "Coordinate",
        "d_date": "Data evento",
        "d_type": "Tipo",
        "d_formula": "Formula",
        "d_hardness": "Durezza (Mohs)",
        "d_color": "Colore",
        "d_occurrence": "Giacitura",
        "d_description": "Descrizione",
        "d_mineral_page": "Scheda minerale",
        "yes": "Sì",
        "no": "No",
        "n_a": "n/d",
        "ask_from_details": "✨ Chiedi all'AI",
        "chat_title": "Assistente AI",
        "chat_sub_configured": "Geologo senior · {model}",
        "chat_sub_guest": "non configurato",
        "chat_placeholder": "Chiedi qualcosa su dati, geologia, eventi…",
        "ai_thinking": "L'assistente sta ragionando…",
        "greeting": (
            "Ciao! Sono l'assistente geologico di GeoLite. "
            "Fai click con il tasto destro su un terremoto, un vulcano, un punto del globo o un minerale "
            "per farmi una domanda contestuale, oppure scrivimi qui."
        ),
        "ai_setup_title": "Assistente AI non configurato",
        "ai_setup_body": (
            "Per attivare l'assistente apri il pulsante «API AI» nella barra in alto e "
            "inserisci la chiave di un servizio OpenAI-compatible (default Groq: "
            "`https://api.groq.com/openai/v1`). In alternativa usa le variabili "
            "d'ambiente `GEOBRAIN_AI_API_KEY` / `GEOBRAIN_AI_BASE_URL` / `GEOBRAIN_AI_MODEL`."
        ),
        "oscare_note": "Correnti OSCAR: snapshot storico (dati fermi a ~lug 2024), non una previsione.",
        "not_alert": "Prodotto didattico: non è un sistema di allerta per rischi naturali.",
        # Component labels
        "c_details": "Dettagli",
        "c_ask_ai": "✨ Chiedi all'AI",
        "c_currents_label": "Correnti oceaniche OSCAR",
        "c_sst_label": "SST MUR · NASA GIBS",
        "c_loading": "Caricamento texture…",
        "c_base_label": "NASA Blue Marble",
        "c_no_features": "Nessun evento nel periodo selezionato.",
        # Auth
        "login_title": "Accedi a GeoLite",
        "username": "Nome utente",
        "password": "Password",
        "login_button": "Accedi",
        "login_error": "Credenziali non valide.",
        "register_title": "Crea un account",
        "register_button": "Registrati",
        "registration_success": "Account creato. Ora puoi accedere.",
        "invalid_username": "Da 3 a 24 caratteri: lettere, numeri, punto, trattino o underscore.",
        "invalid_password": "La password deve contenere da 8 a 128 caratteri.",
        "username_taken": "Questo nome utente è già in uso.",
        "registration_error": "Non è stato possibile creare l'account. Riprova.",
        "account_storage_error": "Servizio account temporaneamente non disponibile.",
        "account_deleted": "Account eliminato. Puoi registrarti di nuovo quando vuoi.",
        "account": "Account",
        "logout": "Esci",
        "delete_account": "Elimina account",
        "delete_warning": "Questa azione elimina definitivamente il tuo account. Non può essere annullata.",
        "delete_password": "Password attuale",
        "delete_confirm": "Confermo l'eliminazione definitiva del mio account",
        "delete_submit": "Elimina definitivamente",
        "delete_confirm_required": "Seleziona la conferma per continuare.",
        "delete_done": "Account eliminato.",
        # Riepiloghi per eventi ask_ai
        "sum_earthquake": "🌋 Terremoto M {mag} — {place}",
        "sum_volcano": "🌋 Evento vulcanico: {title}",
        "sum_globe": "📍 Regione {lat:.2f}°, {lon:.2f}°",
        "sum_climate": "🌊 Punto oceanico {lat:.2f}°, {lon:.2f}° (clima)",
        "sum_mineral": "💎 Minerale: {name}",
        "error_generic": "Qualcosa è andato storto. Riprova.",
    },
    "en": {
        "app_title": "🌍 GeoLite",
        "tagline": "Geology dashboard — seismology, volcanology, climate, mineralogy",
        "nav_seismic": "Seismicity",
        "nav_volcanoes": "Volcanoes",
        "nav_currents": "Currents",
        "nav_climate": "Climate",
        "title_seismic": "Global seismicity — recent USGS events",
        "title_volcanoes": "Ongoing volcanic events — NASA EONET",
        "title_currents": "Currents — sea surface temperature (MUR) + OSCAR currents",
        "title_climate": "Climate — 2 m air temperature (MERRA-2, monthly)",
        "days": "Time window (days)",
        "min_magnitude": "Minimum magnitude",
        "eq_select": "Earthquake",
        "show_currents": "Show ocean currents",
        "currents_explain": "✨ Explain the currents",
        "currents_asked": "Overview of global ocean currents (OSCAR snapshot of {date})",
        "sst_note": "MUR SST: updated roughly every 2 days",
        "heat_note": "2 m air temperature (MERRA-2, NASA) — monthly map; month: {date}. Monthly climate data, not real time.",
        "c_heat_label": "2 m air temperature (MERRA-2)",
        "gm_title": "Minerals in the ground",
        "gm_hint": (
            "Teaching estimate based on typical occurrence, proximity of known deposits "
            "and focal depth: not a real subsurface mapping."
        ),
        "gm_no_selection": "Select an earthquake (globe click or dropdown) to see plausible minerals in the ground at that site.",
        "gm_reason_nearby": "known deposit in the region (~{km:.0f} km away)",
        "gm_reason_regional": "known deposit ~{km:.0f} km away",
        "gm_reason_hydrothermal": "shallow crust: typical of hydrothermal mineralization",
        "gm_reason_mantle": "deep seismicity: mantle lithologies (olivine-dominated)",
        "gm_reason_crust": "ubiquitous in crustal rocks",
        "gm_details": "Details",
        "ai_settings": "AI API",
        "ai_key_label": "API key",
        "ai_base_label": "Base URL",
        "ai_model_label": "Model",
        "ai_save": "Save",
        "ai_saved": "AI settings saved for your account.",
        "ai_remove": "Remove key",
        "ai_removed": "AI key removed. The assistant now uses environment variables only.",
        "ai_where_stored": "Stored locally on this device, linked to your account.",
        "ai_configured_user": "configured",
        "data_unavailable": "Data unavailable right now (network issue or source unreachable).",
        "eonet_note": "Source: NASA EONET v3, events with «open» status.",
        "details_title": "Selection details",
        "no_selection": "Select an item on the globe (left click) to see its details, or right-click → «Ask AI».",
        "d_magnitude": "Magnitude",
        "d_depth": "Focal depth",
        "d_place": "Place",
        "d_time": "Date/time (UTC)",
        "d_felt": "Felt reports",
        "d_alert": "USGS alert",
        "d_mag_type": "Magnitude type",
        "d_tsunami": "Tsunami",
        "d_url": "USGS event page",
        "d_categories": "Categories",
        "d_sources": "Sources",
        "d_link": "EONET page",
        "d_coords": "Coordinates",
        "d_date": "Event date",
        "d_type": "Type",
        "d_formula": "Formula",
        "d_hardness": "Hardness (Mohs)",
        "d_color": "Color",
        "d_occurrence": "Occurrence",
        "d_description": "Description",
        "d_mineral_page": "Mineral page",
        "yes": "Yes",
        "no": "No",
        "n_a": "n/a",
        "ask_from_details": "✨ Ask AI",
        "chat_title": "AI assistant",
        "chat_sub_configured": "Senior geologist · {model}",
        "chat_sub_guest": "not configured",
        "chat_placeholder": "Ask about data, geology, events…",
        "ai_thinking": "The assistant is thinking…",
        "greeting": (
            "Hi! I'm the GeoLite geology assistant. "
            "Right-click an earthquake, volcano, spot on the globe or a mineral to ask me a contextual "
            "question, or just type here."
        ),
        "ai_setup_title": "AI assistant not configured",
        "ai_setup_body": (
            "To enable the assistant, open the «AI API» button in the top bar and enter "
            "the key of an OpenAI-compatible service (default Groq: "
            "`https://api.groq.com/openai/v1`). Alternatively use the environment "
            "variables `GEOBRAIN_AI_API_KEY` / `GEOBRAIN_AI_BASE_URL` / `GEOBRAIN_AI_MODEL`."
        ),
        "oscare_note": "OSCAR currents: historical snapshot (data frozen at ~July 2024), not a forecast.",
        "not_alert": "Educational product: not a natural-hazard early-warning system.",
        "c_details": "Details",
        "c_ask_ai": "✨ Ask AI",
        "c_currents_label": "OSCAR ocean currents",
        "c_sst_label": "MUR SST · NASA GIBS",
        "c_loading": "Loading texture…",
        "c_base_label": "NASA Blue Marble",
        "c_no_features": "No events in the selected period.",
        "login_title": "Sign in to GeoLite",
        "username": "Username",
        "password": "Password",
        "login_button": "Sign in",
        "login_error": "Invalid credentials.",
        "register_title": "Create an account",
        "register_button": "Register",
        "registration_success": "Account created. You can now sign in.",
        "invalid_username": "Use 3–24 characters: letters, numbers, period, hyphen, or underscore.",
        "invalid_password": "Password must be 8–128 characters long.",
        "username_taken": "That username is already in use.",
        "registration_error": "Could not create the account. Please try again.",
        "account_storage_error": "The account service is temporarily unavailable.",
        "account_deleted": "Account deleted. You can register again at any time.",
        "account": "Account",
        "logout": "Sign out",
        "delete_account": "Delete account",
        "delete_warning": "This permanently deletes your account. This action cannot be undone.",
        "delete_password": "Current password",
        "delete_confirm": "I confirm the permanent deletion of my account",
        "delete_submit": "Delete permanently",
        "delete_confirm_required": "Select the confirmation box to continue.",
        "delete_done": "Account deleted.",
        "sum_earthquake": "🌋 Earthquake M {mag} — {place}",
        "sum_volcano": "🌋 Volcanic event: {title}",
        "sum_globe": "📍 Region {lat:.2f}°, {lon:.2f}°",
        "sum_climate": "🌊 Ocean point {lat:.2f}°, {lon:.2f}° (climate)",
        "sum_mineral": "💎 Mineral: {name}",
        "error_generic": "Something went wrong. Please try again.",
    },
}


def T(locale: str, key: str, **kwargs: object) -> str:
    template = TEXT.get(locale, TEXT["it"]).get(key, key)
    return template.format(**kwargs) if kwargs else template


# ---------------------------------------------------------------------------
# CSS — layout fisso 100vh, niente scroll di pagina
# ---------------------------------------------------------------------------

def inject_css() -> None:
    st.markdown(
        """
        <style>
        header[data-testid="stHeader"], footer, [data-testid="stToolbar"] { display: none; }
        .block-container {
            max-width: 100%;
            padding: 0.6rem 0.9rem 0.4rem 0.9rem;
            min-height: 100vh;
        }
        [data-testid="stVerticalBlock"] { gap: 0.45rem; }
        [data-testid="stHorizontalBlock"] { gap: 0.8rem; align-items: flex-start; }
        .gb-title { font-size: 1.25rem; font-weight: 800; letter-spacing: 0.01em;
                    padding-top: 0.15rem; white-space: nowrap; }
        .gb-panel-title { font-size: 0.82rem; font-weight: 700; color: #8ea0b8;
                          text-transform: uppercase; letter-spacing: 0.06em; margin: 0.1rem 0 0.2rem 0; }
        .gb-note { font-size: 0.75rem; color: #6b7b91; }
        div[data-testid="stContainer"] details { border: 1px solid #263248; border-radius: 8px; }
        .stChatMessage { background: transparent; }
        /* Card minerali "nel terreno" */
        .gb-min-card { border: 1px solid #263248; border-radius: 10px; background: #121a28;
                       padding: 8px 8px 6px 8px; height: 100%; }
        .gb-min-card img { width: 100%; aspect-ratio: 1 / 1; object-fit: cover;
                           border-radius: 7px; display: block; background: #0c1119; }
        .gb-min-name { font-weight: 700; font-size: 0.85rem; margin-top: 6px; }
        .gb-min-formula { color: #8ea0b8; font-size: 0.78rem; }
        .gb-min-reason { color: #6b7b91; font-size: 0.74rem; margin-top: 4px; line-height: 1.35; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def init_state() -> None:
    defaults = {
        "locale": "it",
        "section": "seismic",
        "user": None,
        "messages": [],
        "details": None,
        "last_event_token": None,
        "eq_selected_id": None,
        "ai_settings": {"api_key": "", "base_url": "", "model": ""},
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    # I widget possono arrivare vuoti da un rerun innescato dal componente
    # (il frontend li risincronizza): ripristina valori validi PRIMA che i
    # widget vengano istanziati, altrimenti titolo, controlli di sezione e
    # minerali spariscono dopo un click sul globo.
    if st.session_state.get("section") not in SECTIONS:
        st.session_state["section"] = "seismic"
    if st.session_state.get("locale") not in ("it", "en"):
        st.session_state["locale"] = "it"


def apply_ai_settings() -> None:
    """Sincronizza il modulo ai.chat con le impostazioni della sessione."""
    cfg = st.session_state.get("ai_settings") or {}
    if (cfg.get("api_key") or "").strip():
        set_ai_config(cfg.get("api_key", ""), cfg.get("base_url", ""), cfg.get("model", ""))
    else:
        clear_ai_config()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _login_submit() -> None:
    user = authenticate(
        st.session_state.get("login_user", ""),
        st.session_state.get("login_pass", ""),
    )
    if user:
        st.session_state["user"] = user
        st.session_state["ai_settings"] = load_ai_settings(user["username"])
        st.session_state["_ai_inputs_reset"] = True
        apply_ai_settings()
        st.session_state.pop("auth_error", None)
    else:
        st.session_state["auth_error"] = "login_error"


def _register_submit() -> None:
    try:
        register_user(
            st.session_state.get("reg_user", ""),
            st.session_state.get("reg_pass", ""),
        )
        st.session_state["auth_mode"] = "login"
        st.session_state["registration_success"] = True
        st.session_state.pop("auth_error", None)
    except RegistrationError as error:
        st.session_state["auth_error"] = error.code
    except Exception:
        st.session_state["auth_error"] = "account_storage_error"


def render_auth(locale: str) -> None:
    text_key = lambda k, **kw: T(locale, k, **kw)
    if st.session_state.pop("account_deleted", None):
        st.success(text_key("account_deleted"))

    st.session_state.setdefault("auth_mode", "login")
    _, center, _ = st.columns([1, 1.1, 1])
    with center:
        st.markdown(f"## {text_key('app_title')}")
        st.caption(text_key("tagline"))
        st.write("")

        if st.session_state["auth_mode"] == "login":
            if st.session_state.pop("registration_success", None):
                st.success(text_key("registration_success"))
            with st.form("login_form", clear_on_submit=True):
                st.markdown(f"**{text_key('login_title')}**")
                st.text_input(text_key("username"), key="login_user")
                st.text_input(text_key("password"), type="password", key="login_pass")
                submitted = st.form_submit_button(text_key("login_button"), use_container_width=True, key="login_submit")
            if submitted:
                _login_submit()
            if st.session_state.get("auth_error") == "login_error":
                st.error(text_key("login_error"))
            if st.button(text_key("register_title"), use_container_width=True):
                st.session_state["auth_mode"] = "register"
                st.session_state.pop("auth_error", None)
                st.rerun()
        else:
            with st.form("register_form", clear_on_submit=True):
                st.markdown(f"**{text_key('register_title')}**")
                st.text_input(text_key("username"), key="reg_user")
                st.text_input(text_key("password"), type="password", key="reg_pass")
                submitted = st.form_submit_button(text_key("register_button"), use_container_width=True, key="register_submit")
            if submitted:
                _register_submit()
            error = st.session_state.get("auth_error")
            if error and error != "login_error":
                st.error(text_key(error) if error in TEXT[locale] else text_key("registration_error"))
            if st.button(text_key("login_title"), use_container_width=True):
                st.session_state["auth_mode"] = "login"
                st.session_state.pop("auth_error", None)
                st.rerun()


# ---------------------------------------------------------------------------
# Riepiloghi eventi → messaggio chat
# ---------------------------------------------------------------------------

def summarize_context(context: dict, locale: str) -> str:
    kind = (context.get("kind") or "").lower()
    if kind == "earthquake":
        return T(locale, "sum_earthquake", mag=context.get("magnitude"), place=context.get("place"))
    if kind == "volcano":
        return T(locale, "sum_volcano", title=context.get("title"))
    if kind == "climate":
        return T(locale, "sum_climate", lat=context.get("lat") or 0.0, lon=context.get("lon") or 0.0)
    if kind == "globe":
        return T(locale, "sum_globe", lat=context.get("lat") or 0.0, lon=context.get("lon") or 0.0)
    if kind == "mineral":
        return T(locale, "sum_mineral", name=context.get("name"))
    if kind == "currents":
        return T(locale, "currents_asked", date=context.get("date") or "n/d")
    return json.dumps(context, ensure_ascii=False)[:300]


# ---------------------------------------------------------------------------
# Dettagli selezione
# ---------------------------------------------------------------------------

def _row(label: str, value: object) -> str:
    shown = T(st.session_state["locale"], "n_a") if value in (None, "") else str(value)
    return f"**{label}:** {shown}  \n"


def render_details(details: dict, locale: str) -> None:
    kind = (details.get("kind") or "").lower()
    if kind == "earthquake":
        when = str(details.get("time") or "")
        when = (when[:16].replace("T", " ") + " UTC") if when else ""
        st.markdown(
            _row(T(locale, "d_place"), details.get("place"))
            + _row(T(locale, "d_magnitude"), details.get("magnitude"))
            + _row(T(locale, "d_depth"), f"{details.get('depth_km')} km" if details.get("depth_km") is not None else None)
            + _row(T(locale, "d_time"), when)
            + _row(T(locale, "d_coords"), f"{details.get('lat')}, {details.get('lon')}")
            + _row(T(locale, "d_mag_type"), details.get("mag_type"))
            + _row(T(locale, "d_felt"), details.get("felt"))
            + _row(T(locale, "d_alert"), details.get("alert"))
            + _row(T(locale, "d_tsunami"),
                   T(locale, "yes") if details.get("tsunami") else T(locale, "no"))
        )
        if details.get("url"):
            st.link_button(T(locale, "d_url"), details["url"], use_container_width=True)
    elif kind == "volcano":
        st.markdown(
            _row(T(locale, "d_type"), details.get("title"))
            + _row(T(locale, "d_date"), str(details.get("date") or "")[:16].replace("T", " "))
            + _row(T(locale, "d_coords"), f"{details.get('lat')}, {details.get('lon')}")
            + _row(T(locale, "d_categories"), ", ".join(details.get("categories") or []))
            + _row(T(locale, "d_sources"), ", ".join(details.get("sources") or []))
        )
        if details.get("link"):
            st.link_button(T(locale, "d_link"), details["link"], use_container_width=True)
    elif kind == "mineral":
        image = details.get("image_url")
        if image:
            st.image(image, use_container_width=True)
        st.markdown(
            _row(T(locale, "d_formula"), details.get("formula"))
            + _row(T(locale, "d_hardness"), details.get("hardness"))
            + _row(T(locale, "d_color"), details.get("color"))
            + _row(T(locale, "d_occurrence"), details.get("occurrence"))
            + _row(T(locale, "d_description"), details.get("description"))
        )
        page = details.get("page_url")
        if page:
            st.link_button(T(locale, "d_mineral_page"), page, use_container_width=True)
    else:
        st.markdown(_row(T(locale, "d_coords"), f"{details.get('lat')}, {details.get('lon')}"))


# ---------------------------------------------------------------------------
# Spec del componente per sezione
# ---------------------------------------------------------------------------

def component_labels(locale: str) -> dict:
    return {
        "details": T(locale, "c_details"),
        "ask_ai": T(locale, "c_ask_ai"),
        "currents_label": T(locale, "c_currents_label"),
        "sst_label": T(locale, "c_sst_label"),
        "heat_label": T(locale, "c_heat_label"),
        "loading": T(locale, "c_loading"),
        "base_label": T(locale, "c_base_label"),
        "no_features": T(locale, "c_no_features"),
    }


def build_spec(section: str, locale: str) -> dict:
    spec: dict = {
        "mode": section,
        "locale": locale,
        "labels": component_labels(locale),
        "height": 640,
        "autoHeight": True,
        "globe": {"showGraticule": False, "autoRotate": False},
    }

    if section in {"seismic", "volcanoes"}:
        spec["globe"]["textureUrl"] = base_texture_url() or ""
    if section == "seismic":
        days = st.session_state.get("eq_days", 7)
        min_mag = st.session_state.get("eq_mag", 2.5)
        spec["earthquakes"] = earthquake_events(days=days, min_magnitude=min_mag)
        spec["selectedId"] = st.session_state.get("eq_selected_id") or None
    elif section == "volcanoes":
        spec["volcanoes"] = volcano_events()
    elif section == "currents":
        spec["climate"] = {
            "textureUrl": climate_texture_url() or "",
            "showCurrents": bool(st.session_state.get("cl_currents", True)),
            "currents": [],
            "currentsDate": None,
        }
        currents = ocean_currents()
        if currents.get("grid"):
            spec["climate"]["currents"] = currents["grid"]
            spec["climate"]["currentsDate"] = currents.get("date")
    elif section == "climate":
        heat = heat_texture_url()
        spec["globe"]["textureUrl"] = heat["url"] or ""
        spec["globe"]["showGraticule"] = True
        if heat.get("date"):
            spec["heat"] = {"date": heat["date"]}
            spec["labels"]["heat_label"] = f'{spec["labels"]["heat_label"]} · {heat["date"]}'
    return spec


# ---------------------------------------------------------------------------
# Controlli per sezione (barra sopra il globo)
# ---------------------------------------------------------------------------

def render_section_controls(section: str, locale: str) -> None:
    if section == "seismic":
        c1, c2, c3 = st.columns([1, 1, 2.2])
        c1.slider(T(locale, "days"), 1, 30, 7, key="eq_days")
        c2.slider(T(locale, "min_magnitude"), 0.0, 7.0, 2.5, step=0.1, key="eq_mag")
        events = earthquake_events(
            days=st.session_state.get("eq_days", 7),
            min_magnitude=st.session_state.get("eq_mag", 2.5),
        )[:100]
        ids = [e["id"] for e in events]
        # Selezione arrivata dal componente (click sul globo): applicata QUI,
        # prima che il selectbox venga istanziato in questo run.
        pending = st.session_state.pop("pending_eq_select", None)
        if pending:
            st.session_state["eq_selected_id"] = pending
            eq = next((e for e in events if e["id"] == pending), None)
            if eq:
                st.session_state["details"] = {"kind": "earthquake", **eq}
            st.session_state["eq_synced_id"] = pending
        if st.session_state.get("eq_selected_id") not in ids:
            # Evento uscito dalla finestra/filtri: la tendina torna a vuota.
            st.session_state["eq_selected_id"] = None
        c3.selectbox(
            T(locale, "eq_select"),
            ids,
            index=None,
            format_func=lambda eid: _eq_option_label(next((e for e in events if e["id"] == eid), None)),
            placeholder="—",
            key="eq_selected_id",
        )
        # La tendina è la sorgente di verità solo quando il suo valore CAMBIA:
        # così non sovrascriviamo i dettagli di altre selezioni (es. minerali).
        picked = st.session_state.get("eq_selected_id")
        if picked != st.session_state.get("eq_synced_id"):
            st.session_state["eq_synced_id"] = picked
            if picked:
                eq = next((e for e in events if e["id"] == picked), None)
                if eq:
                    st.session_state["details"] = {"kind": "earthquake", **eq}
    elif section == "volcanoes":
        st.caption(T(locale, "eonet_note"))
    elif section == "currents":
        c1, c2 = st.columns([1, 1])
        c1.checkbox(T(locale, "show_currents"), True, key="cl_currents")
        c2.caption(T(locale, "sst_note"))
        if st.button(T(locale, "currents_explain"), key="btn_currents_ai"):
            currents = ocean_currents()
            st.session_state["pending_ai"] = {
                "kind": "currents",
                "date": currents.get("date") or "n/d",
            }
            st.rerun()
    elif section == "climate":
        heat = heat_texture_url()
        st.caption(T(locale, "heat_note", date=heat.get("date") or "n/d"))
        bar = heat_colormap_bar()
        if bar:
            st.markdown(
                '<div style="display:flex;align-items:center;gap:10px;max-width:540px;'
                'font-size:0.74rem;color:#8ea0b8;padding-bottom:0.15rem;">'
                f'<span>{bar["min_c"]}\u00b0C</span>'
                f'<div style="flex:1;height:12px;border-radius:6px;background:{bar["gradient"]};"></div>'
                f'<span>{bar["max_c"]}\u00b0C</span></div>',
                unsafe_allow_html=True,
            )


def _eq_option_label(eq: dict | None) -> str:
    if not eq:
        return "—"
    place = eq.get("place") or "?"
    if len(place) > 58:
        place = place[:55] + "…"
    return f"M {eq.get('magnitude')} · {place}"


# ---------------------------------------------------------------------------
# Minerali "nel terreno" del terremoto selezionato (sotto il globo)
# ---------------------------------------------------------------------------

def _reason_text(code: str, distance_km: float, locale: str) -> str:
    if code == REASON_NEARBY:
        return T(locale, "gm_reason_nearby", km=distance_km)
    if code == REASON_REGIONAL:
        return T(locale, "gm_reason_regional", km=distance_km)
    if code == REASON_HYDROTHERMAL:
        return T(locale, "gm_reason_hydrothermal")
    if code == REASON_MANTLE:
        return T(locale, "gm_reason_mantle")
    if code == REASON_CRUST:
        return T(locale, "gm_reason_crust")
    return code


def _mineral_ctx(item: dict) -> dict:
    return {
        "kind": "mineral",
        "name": item.get("name"),
        "formula": item.get("formula"),
        "hardness": item.get("hardness"),
        "color": item.get("color"),
        "occurrence": item.get("occurrence"),
        "description": item.get("description"),
        "image_url": item.get("image_url") or "",
        "page_url": item.get("page_url") or "",
    }


def render_ground_minerals(locale: str) -> None:
    st.markdown(f'<div class="gb-panel-title">{T(locale, "gm_title")}</div>', unsafe_allow_html=True)
    details = st.session_state.get("details")
    if isinstance(details, dict) and details.get("kind") == "earthquake" \
            and details.get("lat") is not None and details.get("lon") is not None:
        # Ancora il pannello al terremoto: resta visibile anche quando i
        # dettagli mostrano altro (es. un minerale aperto con «Dettagli»).
        st.session_state["last_eq"] = details
    eq = details
    if not (isinstance(eq, dict) and eq.get("kind") == "earthquake"
            and eq.get("lat") is not None and eq.get("lon") is not None):
        eq = st.session_state.get("last_eq")
    if not (isinstance(eq, dict) and eq.get("lat") is not None and eq.get("lon") is not None):
        st.caption(T(locale, "gm_no_selection"))
        return

    items = minerals_for_location(eq["lat"], eq["lon"], eq.get("depth_km"))
    depth = eq.get("depth_km")
    st.caption(
        f"**M {eq.get('magnitude')}** — {eq.get('place')} · "
        f"{depth} km · {T(locale, 'gm_hint')}"
    )
    per_row = 4
    for start in range(0, len(items), per_row):
        cols = st.columns(per_row, gap="small")
        for col, item in zip(cols, items[start:start + per_row]):
            with col:
                reasons = " · ".join(
                    _reason_text(code, item.get("distance_km", 0.0), locale)
                    for code in item.get("reasons") or []
                )
                st.markdown(
                    '<div class="gb-min-card">'
                    f'<img src="{item.get("image_url") or ""}" alt="" loading="lazy"/>'
                    f'<div class="gb-min-name">{item.get("name", "")}</div>'
                    f'<div class="gb-min-formula">{item.get("formula", "")}</div>'
                    f'<div class="gb-min-reason">{reasons}</div>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                b1, b2 = st.columns(2, gap="small")
                idx = f"{start}_{item.get('name', '')}"
                if b1.button(T(locale, "gm_details"), key=f"gm_det_{idx}", use_container_width=True):
                    st.session_state["details"] = _mineral_ctx(item)
                    st.rerun()
                if b2.button(T(locale, "ask_from_details"), key=f"gm_ai_{idx}", use_container_width=True):
                    st.session_state["pending_ai"] = _mineral_ctx(item)
                    st.rerun()


# ---------------------------------------------------------------------------
# Pannello AI
# ---------------------------------------------------------------------------

def system_message(locale: str) -> dict:
    return build_context_messages({"kind": "ping"}, locale)[0]


def render_ai_panel(locale: str) -> None:
    configured = ai_configured()
    model = ai_model_name()
    st.markdown(
        f'<div class="gb-panel-title">{T(locale, "chat_title")} · '
        + (T(locale, "chat_sub_configured", model=model) if configured else T(locale, "chat_sub_guest"))
        + "</div>",
        unsafe_allow_html=True,
    )

    if not configured:
        st.info(f"**{T(locale, 'ai_setup_title')}**\n\n" + T(locale, "ai_setup_body", model=model))
        return

    messages = st.session_state["messages"]
    if not messages:
        messages.append({"role": "assistant", "content": T(locale, "greeting")})

    with st.container(height=520, key="chat_scroll"):
        for message in messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    prompt = st.chat_input(T(locale, "chat_placeholder"))
    if prompt:
        messages.append({"role": "user", "content": prompt})
        st.session_state["pending_free_text"] = True
        st.rerun()

    # Risponde a domande contestuali (tasto destro / bottoni)
    pending = st.session_state.pop("pending_ai", None)
    free_text = st.session_state.pop("pending_free_text", None)
    if pending:
        messages.append({"role": "user", "content": summarize_context(pending, locale)})
        api_messages = build_context_messages(pending, locale)
        with st.chat_message("assistant"):
            with st.spinner(T(locale, "ai_thinking")):
                try:
                    full = st.write_stream(ask_stream(api_messages, locale))
                except AiError as error:
                    full = error.message
                    st.markdown(full)
        messages.append({"role": "assistant", "content": full})
        st.rerun()
    elif free_text:
        api_messages = [system_message(locale)] + messages[-11:-1]
        with st.chat_message("assistant"):
            with st.spinner(T(locale, "ai_thinking")):
                try:
                    full = st.write_stream(ask_stream(api_messages, locale))
                except AiError as error:
                    full = error.message
                    st.markdown(full)
        messages.append({"role": "assistant", "content": full})
        st.rerun()


# ---------------------------------------------------------------------------
# Eventi dal componente
# ---------------------------------------------------------------------------

def handle_component_event(event: object, locale: str) -> None:
    if not isinstance(event, dict):
        return
    etype = event.get("type")
    context = event.get("context") or {}
    token = f"{etype}:{json.dumps(context, sort_keys=True, default=str)}"
    if token == st.session_state.get("last_event_token"):
        return
    st.session_state["last_event_token"] = token

    if etype == "ask_ai":
        st.session_state["pending_ai"] = context
        st.rerun()
    elif etype == "select":
        st.session_state["details"] = context
        if context.get("kind") == "earthquake" and context.get("id"):
            # Non scrivere eq_selected_id qui: il selectbox con lo stesso key
            # è già stato istanziato in questo run e Streamlit lo vieta. La
            # selezione viene applicata all'inizio del run successivo.
            st.session_state["pending_eq_select"] = context["id"]
            st.rerun()


# ---------------------------------------------------------------------------
# Popover impostazioni AI (topbar)
# ---------------------------------------------------------------------------

def render_ai_settings_popover(locale: str) -> None:
    configured = bool((st.session_state.get("ai_settings") or {}).get("api_key", "").strip()) \
        or bool(ai_configured())
    badge = "" if configured else " ⚠️"
    with st.popover(f"🔑 {T(locale, 'ai_settings')}{badge}"):
        st.markdown(f"**{T(locale, 'ai_settings')}**")
        st.caption(T(locale, "ai_where_stored"))
        cfg = st.session_state.get("ai_settings") or {}
        # Con value= + key= Streamlit ignora value dopo la prima istanziazione:
        # quando le impostazioni cambiano lato server (login con altro
        # account, «Rimuovi chiave») le caselle devono essere riallineate
        # eliminando le chiavi dei widget, non riassegnando value.
        if st.session_state.pop("_ai_inputs_reset", None):
            for input_key in ("ai_key_in", "ai_base_in", "ai_model_in"):
                st.session_state.pop(input_key, None)
        with st.form("ai_settings_form"):
            st.text_input(
                T(locale, "ai_key_label"),
                value=cfg.get("api_key", ""),
                type="password",
                key="ai_key_in",
            )
            st.text_input(
                T(locale, "ai_base_label"),
                value=cfg.get("base_url", ""),
                placeholder="https://api.groq.com/openai/v1",
                key="ai_base_in",
            )
            st.text_input(
                T(locale, "ai_model_label"),
                value=cfg.get("model", ""),
                placeholder=ai_model_name(),
                key="ai_model_in",
            )
            saved = st.form_submit_button(T(locale, "ai_save"), use_container_width=True)
        if saved:
            settings = {
                "api_key": st.session_state.get("ai_key_in", "").strip(),
                "base_url": st.session_state.get("ai_base_in", "").strip(),
                "model": st.session_state.get("ai_model_in", "").strip(),
            }
            st.session_state["ai_settings"] = settings
            save_ai_settings(
                st.session_state["user"]["username"],
                api_key=settings["api_key"],
                base_url=settings["base_url"],
                model=settings["model"],
            )
            apply_ai_settings()
            st.toast(T(locale, "ai_saved"))
            st.rerun()
        if (st.session_state.get("ai_settings") or {}).get("api_key"):
            if st.button(T(locale, "ai_remove"), use_container_width=True, key="ai_remove_btn"):
                user = st.session_state["user"] or {}
                delete_ai_settings(user.get("username", ""))
                st.session_state["ai_settings"] = {"api_key": "", "base_url": "", "model": ""}
                st.session_state["_ai_inputs_reset"] = True
                apply_ai_settings()
                st.toast(T(locale, "ai_removed"))
                st.rerun()


# ---------------------------------------------------------------------------
# Account popover (topbar)
# ---------------------------------------------------------------------------

def render_account_popover(locale: str) -> None:
    user = st.session_state["user"] or {}
    with st.popover(f"👤 {user.get('username', '')}"):
        st.markdown(f"**{T(locale, 'account')}** — {user.get('username', '')}")
        if st.button(T(locale, "logout"), use_container_width=True):
            for key in ("user", "messages", "details", "pending_ai", "pending_free_text",
                        "ai_settings", "eq_selected_id", "last_eq"):
                st.session_state.pop(key, None)
            clear_ai_config()
            st.rerun()
        st.divider()
        st.markdown(f"**{T(locale, 'delete_account')}**")
        st.caption(T(locale, "delete_warning"))
        with st.form("delete_account_form"):
            password = st.text_input(T(locale, "delete_password"), type="password")
            confirm = st.checkbox(T(locale, "delete_confirm"))
            submitted = st.form_submit_button(T(locale, "delete_submit"), key="delete_submit")
        if submitted:
            if not confirm:
                st.error(T(locale, "delete_confirm_required"))
            elif delete_account(user.get("username", ""), password):
                delete_ai_settings(user.get("username", ""))
                for key in ("user", "messages", "details", "ai_settings", "eq_selected_id", "last_eq"):
                    st.session_state.pop(key, None)
                clear_ai_config()
                st.session_state["account_deleted"] = True
                st.rerun()
            else:
                st.error(T(locale, "login_error"))


# ---------------------------------------------------------------------------
# App principale
# ---------------------------------------------------------------------------

def render_app(locale: str) -> None:
    text = lambda k, **kw: T(locale, k, **kw)
    section = st.session_state["section"]

    # Topbar
    c_title, c_nav, c_lang, c_ai, c_user = st.columns([1.5, 4.2, 1.0, 0.8, 1.0])
    with c_title:
        st.markdown(f'<div class="gb-title">{text("app_title")}</div>', unsafe_allow_html=True)
    with c_nav:
        st.pills(
            "sezione",
            options=SECTIONS,
            format_func=lambda s: text(f"nav_{s}"),
            key="section",
            label_visibility="collapsed",
        )
    with c_lang:
        st.segmented_control(
            "lingua",
            options=["it", "en"],
            format_func=lambda l: "🇮🇹" if l == "it" else "🇬🇧",
            key="locale",
            label_visibility="collapsed",
        )
    with c_ai:
        render_ai_settings_popover(locale)
    with c_user:
        render_account_popover(locale)

    st.markdown(f'<div class="gb-panel-title">{text(f"title_{section}")}</div>', unsafe_allow_html=True)

    main_col, ai_col = st.columns([0.60, 0.40], gap="medium")

    with main_col:
        render_section_controls(section, locale)
        spec = build_spec(section, locale)
        if section == "seismic" and not spec.get("earthquakes"):
            st.caption(text("data_unavailable"))
        event = globes(spec=spec, key="geolite-globe", default=None)
        handle_component_event(event, locale)
        if section == "seismic":
            render_ground_minerals(locale)
        if section == "currents":
            st.caption(f"{text('oscare_note')} · {text('not_alert')}")
        if section == "climate":
            st.caption(f"{text('heat_note', date=heat_texture_url().get('date') or 'n/d')} · {text('not_alert')}")

    with ai_col:
        details = st.session_state.get("details")
        st.markdown(f'<div class="gb-panel-title">{text("details_title")}</div>', unsafe_allow_html=True)
        with st.container(height=170, key="details_scroll"):
            if details:
                render_details(details, locale)
                if st.button(text("ask_from_details"), key="ask_from_details"):
                    st.session_state["pending_ai"] = details
                    st.rerun()
            else:
                st.caption(text("no_selection"))
        render_ai_panel(locale)


def main() -> None:
    init_state()
    inject_css()
    apply_ai_settings()
    locale = st.session_state["locale"]
    if not st.session_state.get("user"):
        render_auth(locale)
        return
    render_app(locale)


main()
