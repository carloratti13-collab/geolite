"""Client AI verso API esterna OpenAI-compatible (default Groq) + prompt esperti IT/EN."""
from __future__ import annotations

import json
import os
import time as _time
from typing import Iterator

import requests

ENV_KEY = "GEOBRAIN_AI_API_KEY"
ENV_BASE_URL = "GEOBRAIN_AI_BASE_URL"
ENV_MODEL = "GEOBRAIN_AI_MODEL"
ENV_MAX_TOKENS = "GEOBRAIN_AI_MAX_TOKENS"
ENV_TEMPERATURE = "GEOBRAIN_AI_TEMPERATURE"

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
# llama-3.3-70b-versatile è stato dismesso da Groq il 16/08/2026; il
# sostituto raccomandato è openai/gpt-oss-120b (vedi
# https://console.groq.com/docs/deprecations).
DEFAULT_MODEL = "openai/gpt-oss-120b"
_DEFAULT_MAX_TOKENS = "1024"
_DEFAULT_TEMPERATURE = "0.3"

# Modello dismessi da Groq e relativo sostituto: vale per chiavi salvate nel
# DB e per variabili d'ambiente con id datati (mappatura silenziosa).
DEPRECATED_MODEL_REPLACEMENTS = {
    "llama-3.3-70b-versatile": DEFAULT_MODEL,
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama3-70b-8192": DEFAULT_MODEL,
    "llama3-8b-8192": "openai/gpt-oss-20b",
    "qwen/qwen3-32b": DEFAULT_MODEL,
    "meta-llama/llama-4-scout-17b-16e-instruct": DEFAULT_MODEL,
    "meta-llama/llama-4-maverick-17b-128e-instruct": DEFAULT_MODEL,
    "moonshotai/kimi-k2-instruct": DEFAULT_MODEL,
    "moonshotai/kimi-k2-instruct-0905": DEFAULT_MODEL,
    "qwen/qwen3.6-27b": "qwen/qwen3.8-27b",
}

_TIMEOUT = 90
_STREAM_TIMEOUT = 120

# Domini radice dei provider noti: chi digita il sito web (o un suo
# sottodominio, tipo console.groq.com) senza path viene rimandato
# all'endpoint API OpenAI-compatible corretto.
_BASE_URL_DOMAIN_FALLBACK = {
    "groq.com": "https://api.groq.com/openai/v1",
    "kimi.ai": "https://api.moonshot.ai/v1",
    "moonshot.ai": "https://api.moonshot.ai/v1",
    "openai.com": "https://api.openai.com/v1",
    "openrouter.ai": "https://openrouter.ai/api/v1",
    "deepseek.com": "https://api.deepseek.com/v1",
}


def _normalize_base_url(url: str) -> str:
    """Rende utilizzabile un base URL digitato a mano: schema https://
    mancante, spazi e slash finali rimossi, domini noti senza path
    (es. «console.groq.com») rimappati all'endpoint API."""
    from urllib.parse import urlsplit

    url = url.strip().rstrip("/")
    if not url:
        return ""
    if not url.startswith(("https://", "http://")):
        url = "https://" + url
    parts = urlsplit(url)
    labels = parts.netloc.lower().split(".")
    root = ".".join(labels[-2:]) if len(labels) >= 2 else labels[0]
    if parts.path in ("", "/") and root in _BASE_URL_DOMAIN_FALLBACK:
        return _BASE_URL_DOMAIN_FALLBACK[root]
    return url.rstrip("/")

# Configurazione runtime (es. chiavi inserite dall'utente nell'app): ha
# priorità sulle variabili d'ambiente. Chiavi: api_key, base_url, model.
_runtime_config: dict[str, str] = {}


def set_ai_config(api_key: str = "", base_url: str = "", model: str = "") -> None:
    """Imposta (o sostituisce) la configurazione AI di sessione."""
    _runtime_config.clear()
    if api_key.strip():
        _runtime_config["api_key"] = api_key.strip()
    if base_url.strip():
        _runtime_config["base_url"] = base_url.strip()
    if model.strip():
        _runtime_config["model"] = model.strip()


def clear_ai_config() -> None:
    """Rimuove la configurazione runtime (si torna alle variabili d'ambiente)."""
    _runtime_config.clear()


class AiError(Exception):
    """Errore AI con un messaggio già pronto da mostrare all'utente."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _t(key: str, locale: str, **kwargs: object) -> str:
    it = locale == "it"
    templates: dict[str, tuple[str, str]] = {
        "not_configured": (
            "L'assistente AI non è configurato. Imposta la variabile d'ambiente GEOBRAIN_AI_API_KEY.",
            "The AI assistant is not configured. Set the GEOBRAIN_AI_API_KEY environment variable.",
        ),
        "network": (
            "Impossibile contattare il servizio AI (errore di rete: {reason}). "
            "Riprova tra poco; se il problema persiste, verifica Base URL e chiave in «API AI».",
            "Cannot reach the AI service (network error: {reason}). "
            "Please try again shortly; if it persists, check the Base URL and API key in 'AI settings'.",
        ),
        "http": (
            "Il servizio AI ha risposto con un errore (HTTP {status}).{detail} Riprova più tardi.",
            "The AI service returned an error (HTTP {status}).{detail} Please try again later.",
        ),
        "malformed": (
            "Risposta inattesa dal servizio AI. Riprova.",
            "Unexpected response from the AI service. Please try again.",
        ),
    }
    template = templates[key][0 if it else 1]
    return template.format(**kwargs)


def ai_configured() -> bool:
    """True se la chiave API è presente (runtime o variabile d'ambiente)."""
    if _runtime_config.get("api_key"):
        return True
    return bool(os.environ.get(ENV_KEY, "").strip())


def ai_model_name() -> str:
    """Nome del modello effettivo: config (runtime/env) con migrazione
    silenziosa degli id dismessi da Groq. Spazi interni (es. «kimi k3»
    digitato a mano) diventano trattini, come negli id reali."""
    model = _runtime_config.get("model") or os.environ.get(ENV_MODEL, "").strip() or DEFAULT_MODEL
    model = " ".join(model.split()).replace(" ", "-")
    return DEPRECATED_MODEL_REPLACEMENTS.get(model, model)


def _system_prompt(locale: str) -> str:
    """Persona: geologo senior (sismologo/vulcanologo/climatologo/mineralogo)."""
    if locale == "it":
        return (
            "Sei un geologo senior con competenze di sismologo, vulcanologo, climatologo e "
            "mineralogista. Rispondi SEMPRE in italiano, con la terminologia tecnica "
            "internazionale (inglese) tra parentesi alla prima occorrenza.\n"
            "Regole:\n"
            "- Precisione scientifica: distingui sempre le osservazioni (dati misurati) "
            "dalle interpretazioni (modelli, ipotesi).\n"
            "- Dai range numerici tipici quando citi grandezze fisiche (es. magnitudo, "
            "profondità focale, temperature, velocità di corrente).\n"
            "- Quando citi dati aggiornati periodicamente, indica esplicitamente il "
            "riferimento temporale (mese/giorno del dato) e non presentare mai uno "
            "snapshot storico come una condizione in tempo reale.\n"
            "- Non generare mai allarmismo: per rischi naturali indica sempre che il "
            "prodotto non è un sistema di allerta.\n"
            "- Risposte concise di default (max ~350 parole), salvo richiesta esplicita "
            "di approfondimento. Usa elenchi puntati quando aiuta la chiarezza."
        )
    return (
        "You are a senior geologist with expertise in seismology, volcanology, climatology "
        "and mineralogy. ALWAYS answer in English.\n"
        "Rules:\n"
        "- Scientific precision: always separate observations (measured data) from "
        "interpretations (models, hypotheses).\n"
        "- Give typical numeric ranges when citing physical quantities (magnitude, focal "
        "depth, temperatures, current speeds).\n"
        "- When citing periodically updated data, always state its temporal reference "
        "(month/day of the data) and never present a historical snapshot as a real-time "
        "condition.\n"
        "- Never generate alarmism: for natural hazards, state that this product is not "
        "an early-warning system.\n"
        "- Concise by default (max ~350 words) unless a deeper analysis is requested. Use "
        "bullet lists when they improve clarity."
    )


def _fmt(value: object) -> str:
    if value is None or value == "":
        return "n/d"
    return str(value)


def build_context_messages(context: dict, locale: str) -> list[dict]:
    """Costruisce i messaggi [system, user] da un contesto strutturato del componente.

    Context supportati: "earthquake", "volcano", "globe"/"climate", "mineral", "currents".
    """
    kind = (context.get("kind") or "").lower()
    if locale == "it":
        lang = "Rispondi in italiano."
    else:
        lang = "Answer in English."

    if kind == "earthquake":
        lines = [
            f"- Magnitudo: {_fmt(context.get('magnitude'))}",
            f"- Profondità focale: {_fmt(context.get('depth_km'))} km",
            f"- Luogo: {_fmt(context.get('place'))}",
            f"- Data/ora: {_fmt(context.get('time'))}",
            f"- Coordinate: {_fmt(context.get('lat'))}, {_fmt(context.get('lon'))}",
            f"- Segnalazioni di avvertimento: {_fmt(context.get('felt'))}",
            f"- Allerta USGS: {_fmt(context.get('alert'))}",
            f"- Tipo di magnitudo: {_fmt(context.get('mag_type'))}",
            f"- Tsunami: {_fmt(context.get('tsunami'))}",
            f"- Fonte: {_fmt(context.get('url'))}",
        ]
        question = (
            "Spiega da esperto sismologo questo evento: contesto tettonico, meccanismo "
            "focale probabile, pericolarità e confronto con i range tipici di profondità "
            "e magnitudo. {lang}"
        )
    elif kind == "volcano":
        lines = [
            f"- Vulcano: {_fmt(context.get('title'))}",
            f"- Coordinate: {_fmt(context.get('lat'))}, {_fmt(context.get('lon'))}",
            f"- Data evento: {_fmt(context.get('date'))}",
            f"- Categorie: {_fmt(', '.join(context.get('categories') or []))}",
            f"- Fonte: {_fmt(context.get('link'))}",
        ]
        question = (
            "Spiega da esperto vulcanologo questo evento vulcanico: tipo di attività "
            "probabile in base al setting geografico, rischi tipici e come leggere i dati "
            "di monitoraggio. {lang}"
        )
    elif kind == "globe":
        lines = [
            f"- Coordinate: {_fmt(context.get('lat'))}, {_fmt(context.get('lon'))}",
        ]
        question = (
            "Descrivi da esperto climatologo e geologo la regione di Terra a queste "
            "coordinate: geologia superficiale, clima, eventi naturali tipici. {lang}"
        )
    elif kind == "climate":
        lines = [
            f"- Coordinate: {_fmt(context.get('lat'))}, {_fmt(context.get('lon'))}",
            f"- Mappa mostrata: temperatura dell'aria a 2 m (MERRA-2, NASA), mese {_fmt(context.get('date'))}",
        ]
        question = (
            "Descrivi da esperto climatologo la regione a queste coordinate interpretando "
            "la mappa termica: temperatura attesa in quella zona e confronto con il colore "
            "mostrato. Ricorda che la mappa mostra temperature ASSOLUTE (scala circa "
            "-53/+37 °C), quindi zone tropicali e estive boreali sono normalmente "
            "arancio/rosse senza che ciò indichi un riscaldamento anomalo. {lang}"
        )
    elif kind == "mineral":
        lines = [
            f"- Minerale: {_fmt(context.get('name'))}",
            f"- Formula: {_fmt(context.get('formula'))}",
            f"- Durezza: {_fmt(context.get('hardness'))}",
            f"- Colore: {_fmt(context.get('color'))}",
            f"- Ambiente di giacitura: {_fmt(context.get('occurrence'))}",
            f"- Descrizione: {_fmt(context.get('description'))}",
        ]
        question = (
            "Spiega da esperto mineralogista questo minerale: chimica, cristallochimica, "
            "ambiente di formazione e giacimenti tipici. {lang}"
        )
    elif kind == "currents":
        date = _fmt(context.get("date"))
        lines = [
            f"- Data dello snapshot delle correnti: {date}",
            "- Richiesta: panoramica sui principali sistemi di correnti oceaniche.",
        ]
        question = (
            "Descrivi i principali sistemi di correnti oceaniche globali (Gulf Stream, "
            "Kuroshio, corrente circumpolare antartica, upwelling costieri): meccanismi "
            "di formazione e portata tipica. Ricorda che i dati OSCAR mostrati sono uno "
            "snapshot del {date}, non dati in tempo reale. {{lang}}"
        ).format(date=date, lang="{lang}")
    else:
        lines = [f"- Dati: {_fmt(context)}"]
        question = "Fornisci una breve spiegazione geologica dei dati sopra. {lang}"

    bullets = "\n".join(lines)
    question_text = question.format(lang=lang)
    if locale == "it":
        user = f"Contesto (dati strutturati dal dashboard GeoLite):\n{bullets}\n\n{question_text}"
    else:
        user = f"Context (structured data from the GeoLite dashboard):\n{bullets}\n\n{question_text}"
    return [
        {"role": "system", "content": _system_prompt(locale)},
        {"role": "user", "content": user},
    ]


def _request_payload(messages: list[dict]) -> dict:
    max_tokens = os.environ.get(ENV_MAX_TOKENS, _DEFAULT_MAX_TOKENS)
    temperature = os.environ.get(ENV_TEMPERATURE, _DEFAULT_TEMPERATURE)
    try:
        max_tokens = int(max_tokens)
    except ValueError:
        max_tokens = int(_DEFAULT_MAX_TOKENS)
    try:
        temperature = float(temperature)
    except ValueError:
        temperature = float(_DEFAULT_TEMPERATURE)
    return {
        "model": ai_model_name(),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }


def _runtime_key() -> str:
    return _runtime_config.get("api_key") or os.environ.get(ENV_KEY, "").strip()


def _resolve_base_url() -> str:
    base_url = _runtime_config.get("base_url") or os.environ.get(ENV_BASE_URL, "")
    return _normalize_base_url(base_url) or DEFAULT_BASE_URL


def _network_reason(exc: requests.RequestException) -> str:
    """Motivo breve e leggibile dell'errore di rete, per il messaggio in UI."""
    if exc.response is not None:
        return f"HTTP {exc.response.status_code}"
    if exc.args:
        text = str(exc.args[0]).replace("\n", " ").strip()
        if text:
            return text[:140]
    return exc.__class__.__name__


def _post_chat(payload: dict, timeout: int, stream: bool) -> requests.Response:
    """POST a {base}/chat/completions con un retry su 5xx/429 (backoff 2 s)."""
    url = f"{_resolve_base_url()}/chat/completions"
    last_error: requests.RequestException | None = None
    for attempt in range(2):
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {_runtime_key()}"},
                timeout=timeout,
                stream=stream,
            )
            if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                _time.sleep(2.0)
                continue
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt == 0:
                _time.sleep(2.0)
    raise last_error if last_error is not None else AiError("network")


def _error_detail(response: requests.Response) -> str:
    """Messaggio d'errore del provider (es. chiave non valida, modello
    dismesso), troncato per la UI; stringa vuota se non decodificabile."""
    try:
        error = response.json().get("error")
        if isinstance(error, dict) and error.get("message"):
            return " " + str(error["message"])[:220]
    except (ValueError, AttributeError):
        pass
    return ""


def ask(messages: list[dict], locale: str = "it") -> str:
    """Interroga il modello e ritorna il testo della risposta.

    Solleva AiError con messaggio localizzato in caso di chiave mancante,
    errore HTTP o risposta malformata.
    """
    if not ai_configured():
        raise AiError(_t("not_configured", locale))
    payload = _request_payload(messages)
    try:
        response = _post_chat(payload, timeout=_TIMEOUT, stream=False)
    except requests.RequestException as exc:
        raise AiError(_t("network", locale, reason=_network_reason(exc))) from None
    if response.status_code != 200:
        raise AiError(_t("http", locale, status=response.status_code,
                         detail=_error_detail(response)))
    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise AiError(_t("malformed", locale)) from None
    if not isinstance(content, str) or not content.strip():
        raise AiError(_t("malformed", locale))
    return content


def ask_stream(messages: list[dict], locale: str = "it") -> Iterator[str]:
    """Versione streaming: yield dei frammenti di testo via SSE.

    Se lo stream fallisce a metà, ricade in modo trasparente su ask() e ne
    ritorna il testo completo.
    """
    if not ai_configured():
        raise AiError(_t("not_configured", locale))
    payload = _request_payload(messages)
    payload["stream"] = True
    try:
        response = _post_chat(payload, timeout=_STREAM_TIMEOUT, stream=True)
        if response.status_code != 200:
            raise AiError(_t("http", locale, status=response.status_code,
                             detail=_error_detail(response)))
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            payload_text = line[len("data:"):].strip()
            if payload_text == "[DONE]":
                return
            try:
                chunk = json.loads(payload_text)
                delta = chunk["choices"][0].get("delta") or {}
                piece = delta.get("content")
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            if piece:
                yield piece
    except AiError:
        raise
    except (requests.RequestException, OSError):
        # Stream interrotto: fallback trasparente sulla risposta completa.
        payload["stream"] = False
        yield ask(messages, locale=locale)
