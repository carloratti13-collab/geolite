"""Dataset didattico di minerali (riuso della collezione di v0.1, chiavi normalizzate)."""
from __future__ import annotations

import math

# Codici di ragione per il ranking "minerali nel terreno": li traduce l'app.
REASON_NEARBY = "nearby"        # giacimento noto a < 800 km
REASON_REGIONAL = "regional"    # giacimento noto a < 2000 km
REASON_HYDROTHERMAL = "hydrothermal"  # crosta superficiale: mineralizzazioni idrotermali
REASON_MANTLE = "mantle"        # sismicità profonda: litologie mantelliche
REASON_CRUST = "crust"          # minerale ubiquo della crosta

# Associazioni per ambiente di giacitura (didattiche, basate sulla profondità focale).
_HYDROTHERMAL_NAMES = {"Pirite", "Galena", "Rame", "Malachite", "Ematite", "Zolfo nativo"}
_MANTLE_NAMES = {"Olivina"}

_HAVERSINE_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distanza di cerchio massimo in km tra due punti (lat/lon in gradi)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _HAVERSINE_KM * math.asin(min(1.0, math.sqrt(a)))


def minerals_for_location(lat: float, lon: float, depth_km: float | None = None) -> list[dict]:
    """Classifica il dataset didattico per plausibilità nel sottosuolo di un sito.

    Ritorna una copia dei minerali ordinata per rilevanza decrescente, con chiavi
    extra: ``distance_km`` (distanza dal giacimento noto più vicino) e
    ``reasons`` (lista di codici REASON_* da localizzare nell'UI).
    Stima didattica basata su giacitura tipica + profondità, non una mappatura reale.
    """
    ranked: list[tuple[float, dict, list[str]]] = []
    depth = float(depth_km) if depth_km is not None else None
    for item in _MINERALS:
        score = 0.0
        reasons: list[str] = []
        distance = haversine_km(lat, lon, item["lat"], item["lon"])
        if distance <= 800.0:
            score += 3.0
            reasons.append(REASON_NEARBY)
        elif distance <= 2000.0:
            score += 1.0
            reasons.append(REASON_REGIONAL)
        if depth is not None:
            if depth < 60.0:
                if item["name"] in _HYDROTHERMAL_NAMES:
                    score += 2.0
                    reasons.append(REASON_HYDROTHERMAL)
                if item["name"] == "Quarzo":
                    score += 1.5
                    reasons.append(REASON_CRUST)
            elif depth < 300.0:
                if item["name"] in _MANTLE_NAMES:
                    score += 2.0
                    reasons.append(REASON_MANTLE)
                if item["name"] == "Quarzo":
                    score += 0.5
                    reasons.append(REASON_CRUST)
            else:
                if item["name"] in _MANTLE_NAMES:
                    score += 3.0
                    reasons.append(REASON_MANTLE)
        else:
            if item["name"] in _MANTLE_NAMES:
                score += 0.5
            if item["name"] == "Quarzo":
                score += 0.5
        record = dict(item)
        record["distance_km"] = round(distance, 1)
        record["reasons"] = reasons
        ranked.append((score, record, reasons))
    ranked.sort(key=lambda entry: (-entry[0], entry[1]["distance_km"]))
    return [record for _, record, _ in ranked]


_MINERALS: list[dict] = [
    {
        "name": "Zolfo nativo",
        "formula": "S",
        "hardness": 2.0,
        "color": "Giallo limone",
        "occurrence": "Fumarole e zone vulcaniche (Es. Sicilia, Indonesia)",
        "country": "Italia",
        "lat": 37.5,
        "lon": 14.0,
        "description": "Minerale giallo limone tipico dei depositi fumarolici in ambiente vulcanico.",
        "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/c/c3/Native_sulfur_%28GeoDIL_number_-_861%29.jpg/500px-Native_sulfur_%28GeoDIL_number_-_861%29.jpg",
    },
    {
        "name": "Olivina",
        "formula": "(Mg,Fe)2SiO4",
        "hardness": 6.5,
        "color": "Verde oliva",
        "occurrence": "Rocce basaltiche e ultramafiche (Es. Islanda)",
        "country": "Islanda",
        "lat": 64.0,
        "lon": -20.5,
        "description": "Silicato di Mg-Fe tipico dei basalti e delle rocce del mantello.",
        "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/05/Olivine-Dunit.jpg/330px-Olivine-Dunit.jpg",
    },
    {
        "name": "Rame",
        "formula": "Cu",
        "hardness": 3.0,
        "color": "Rosso ramato",
        "occurrence": "Mineralizzazioni ossidate (Es. Cile)",
        "country": "Cile",
        "lat": -27.3,
        "lon": -69.8,
        "description": "Elemento nativo dalla caratteristica patina ossidata verde-bluastra.",
        "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/14/Cuivre_Michigan.jpg/330px-Cuivre_Michigan.jpg",
    },
    {
        "name": "Quarzo",
        "formula": "SiO2",
        "hardness": 7.0,
        "color": "Incolore/vario",
        "occurrence": "Rocce metamorfiche e filoni idrotermali (Es. Giappone)",
        "country": "Giappone",
        "lat": 36.2,
        "lon": 137.2,
        "description": "Ossido di silicio, tra i minerali più diffusi della crosta terrestre.",
        "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/14/Quartz%2C_Tibet.jpg/330px-Quartz%2C_Tibet.jpg",
    },
    {
        "name": "Pirite",
        "formula": "FeS2",
        "hardness": 6.0,
        "color": "Giallo oro",
        "occurrence": "Filoni idrotermali e rocce sedimentarie (Es. Toscana)",
        "country": "Italia",
        "lat": 42.8,
        "lon": 10.7,
        "description": "Solfuro di ferro detto 'oro degli sciocchi' per il colore metallico.",
        "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/5c/Pyrite_elbe.jpg/330px-Pyrite_elbe.jpg",
    },
    {
        "name": "Ematite",
        "formula": "Fe2O3",
        "hardness": 5.5,
        "color": "Grigio acciaio/rosso mattone",
        "occurrence": "Formazioni ferrifere (Es. Minas Gerais, Brasile)",
        "country": "Brasile",
        "lat": -19.9,
        "lon": -43.9,
        "description": "Ossido di ferro principale minerale di ferro, anche usato come pigmento.",
        "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/6f/Pyrit-with-hematite-01.jpg/330px-Pyrit-with-hematite-01.jpg",
    },
    {
        "name": "Malachite",
        "formula": "Cu2(CO3)(OH)2",
        "hardness": 3.5,
        "color": "Verde intenso",
        "occurrence": "Zone di ossidazione dei giacimenti di rame (Es. Australia)",
        "country": "Australia",
        "lat": -31.9,
        "lon": 141.5,
        "description": "Carbonato di rame idrato dal tipico verde bandato, usato come gemma e pigmento.",
        "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/9/92/Malachite-213235.jpg/330px-Malachite-213235.jpg",
    },
    {
        "name": "Galena",
        "formula": "PbS",
        "hardness": 2.5,
        "color": "Grigio piombo",
        "occurrence": "Filoni idrotermali (Es. Perù)",
        "country": "Perù",
        "lat": -13.5,
        "lon": -72.0,
        "description": "Solfuro di piombo, principale minerale di piombo, spesso con argento associato.",
        "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/60/Galena%2C_Quartz-236400.jpg/330px-Galena%2C_Quartz-236400.jpg",
    },
]


def mineral_occurrences() -> list[dict]:
    """Elenco didattico di minerali con chiavi normalizzate (name, formula, ...)."""
    return [dict(item) for item in _MINERALS]
