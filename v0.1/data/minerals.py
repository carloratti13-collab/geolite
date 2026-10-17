"""Open sample of mineral occurrences for the unified app."""
from __future__ import annotations

import pandas as pd


def mineral_occurrences() -> pd.DataFrame:
    return pd.DataFrame([
        {"mineral": "Zolfo nativo", "country": "Italia", "lat": 37.5, "lon": 14.0, "note": "Area vulcanica e fumarolica", "color": [44, 160, 91, 230], "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/c/c3/Native_sulfur_%28GeoDIL_number_-_861%29.jpg/500px-Native_sulfur_%28GeoDIL_number_-_861%29.jpg"},
        {"mineral": "Olivina", "country": "Islanda", "lat": 64.0, "lon": -20.5, "note": "Rocce basaltiche", "color": [35, 125, 110, 230], "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/05/Olivine-Dunit.jpg/330px-Olivine-Dunit.jpg"},
        {"mineral": "Rame", "country": "Cile", "lat": -27.3, "lon": -69.8, "note": "Cintura metallogenica andina", "color": [218, 119, 48, 230], "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/14/Cuivre_Michigan.jpg/330px-Cuivre_Michigan.jpg"},
        {"mineral": "Quarzo", "country": "Giappone", "lat": 36.2, "lon": 137.2, "note": "Zone metamorfiche", "color": [88, 116, 209, 230], "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/14/Quartz%2C_Tibet.jpg/330px-Quartz%2C_Tibet.jpg"},
        {"mineral": "Pirite", "country": "Italia", "lat": 42.8, "lon": 10.7, "note": "Distretto minerario toscano", "color": [211, 181, 51, 230], "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/5c/Pyrite_elbe.jpg/330px-Pyrite_elbe.jpg"},
        {"mineral": "Ematite", "country": "Brasile", "lat": -19.9, "lon": -43.9, "note": "Formazioni ferrifere del Minas Gerais", "color": [164, 67, 52, 230], "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/6f/Pyrit-with-hematite-01.jpg/330px-Pyrit-with-hematite-01.jpg"},
        {"mineral": "Malachite", "country": "Australia", "lat": -31.9, "lon": 141.5, "note": "Mineralizzazione di rame", "color": [29, 145, 119, 230], "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/9/92/Malachite-213235.jpg/330px-Malachite-213235.jpg"},
        {"mineral": "Galena", "country": "Peru", "lat": -13.5, "lon": -72.0, "note": "Filoni idrotermali andini", "color": [90, 98, 105, 230], "image_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/60/Galena%2C_Quartz-236400.jpg/330px-Galena%2C_Quartz-236400.jpg"},
    ])
