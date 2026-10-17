import sqlite3

import pytest

from ai.chat import (
    DEPRECATED_MODEL_REPLACEMENTS,
    _resolve_base_url,
    ai_configured,
    ai_model_name,
    build_context_messages,
    clear_ai_config,
    set_ai_config,
)
from auth.auth import RegistrationError, authenticate, delete_account, register_user
from auth.user_settings import delete_ai_settings, load_ai_settings, save_ai_settings
from data.climate import _first_of_month, _parse_colormap, _png_has_data
from data.earthquakes import _parse_feature
from data.minerals import (
    REASON_CRUST,
    REASON_HYDROTHERMAL,
    REASON_MANTLE,
    REASON_NEARBY,
    haversine_km,
    mineral_occurrences,
    minerals_for_location,
)


def test_registered_account_persists_and_authenticates(tmp_path):
    database = tmp_path / "users.sqlite3"
    account = register_user("Geo_User", "secure-password", database)

    assert account == {"username": "geo_user", "tier": "student"}
    assert authenticate("GEO_USER", "secure-password", database) == account
    assert authenticate("geo_user", "incorrect-password", database) is None


def test_registration_rejects_duplicate_username(tmp_path):
    database = tmp_path / "users.sqlite3"
    register_user("geo_user", "secure-password", database)

    with pytest.raises(RegistrationError, match="username_taken"):
        register_user("GEO_USER", "another-password", database)


def test_password_is_not_stored_in_plaintext(tmp_path):
    database = tmp_path / "users.sqlite3"
    password = "secure-password"
    register_user("geo_user", password, database)

    with sqlite3.connect(database) as connection:
        stored_salt, stored_hash = connection.execute(
            "SELECT salt, password_hash FROM users WHERE username = ?", ("geo_user",)
        ).fetchone()

    assert password.encode() not in stored_hash
    assert len(stored_salt) == 16
    assert len(stored_hash) == 64


def test_account_deletion_requires_password_and_removes_account(tmp_path):
    database = tmp_path / "users.sqlite3"
    register_user("geo_user", "secure-password", database)

    assert not delete_account("geo_user", "incorrect-password", database)
    assert authenticate("geo_user", "secure-password", database) is not None
    assert delete_account("GEO_USER", "secure-password", database)
    assert authenticate("geo_user", "secure-password", database) is None


@pytest.mark.parametrize(
    ("username", "password", "error_code"),
    [
        ("ab", "secure-password", "invalid_username"),
        ("geo user", "secure-password", "invalid_username"),
        ("geo_user", "short", "invalid_password"),
    ],
)
def test_registration_validates_credentials(tmp_path, username, password, error_code):
    with pytest.raises(RegistrationError, match=error_code):
        register_user(username, password, tmp_path / "users.sqlite3")


def test_local_dataset_shapes():
    minerals = mineral_occurrences()
    assert len(minerals) >= 8
    first = minerals[0]
    assert {"name", "formula", "hardness", "description"}.issubset(first)
    assert isinstance(first["hardness"], float)


def test_parse_usgs_feature():
    feature = {
        "id": "us7000abcd",
        "type": "Feature",
        "properties": {
            "mag": 5.3,
            "place": "15 km SE of Norcia, Italy",
            "time": 1728429600000,
            "updated": 1728430000000,
            "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000abcd",
            "detail": "",
            "felt": 12,
            "alert": "green",
            "status": "reviewed",
            "tsunami": 0,
            "magType": "mb",
            "type": "earthquake",
        },
        "geometry": {"type": "Point", "coordinates": [13.15, 42.72, 10.4]},
    }
    event = _parse_feature(feature)

    assert event is not None
    assert event["id"] == "us7000abcd"
    assert event["magnitude"] == 5.3
    assert event["depth_km"] == 10.4
    assert event["lat"] == 42.72
    assert event["lon"] == 13.15
    assert event["felt"] == 12
    assert event["alert"] == "green"
    assert event["mag_type"] == "mb"
    assert event["tsunami"] is False
    assert event["time"].startswith("2024-10-08T")
    assert "Norcia" in event["place"]


def test_parse_usgs_feature_missing_coordinates():
    assert _parse_feature({"id": "x", "properties": {"mag": 4.0}, "geometry": {}}) is None
    assert _parse_feature({"id": "x", "properties": {"time": 1}, "geometry": {"coordinates": [1, 2]}}) is None
    assert _parse_feature({"id": "x", "properties": {"time": 1, "mag": None}, "geometry": {"coordinates": [1, 2, 3]}}) is None


SAMPLE_COLORMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ColorMap>
  <ColorMapEntry rgb="0,0,0" transparent="true" label="No Data" value="[-INF,INF)"/>
  <ColorMapEntry rgb="10,20,30" transparent="false" label="-1.5 to -1.0" value="[-1.5,-1.0)"/>
  <ColorMapEntry rgb="40,50,60" transparent="false" label="-0.5 to 0.5" value="[-0.5,0.5)"/>
  <ColorMapEntry rgb="70,80,90" transparent="false" label="1.0 to INF" value="[1.0,INF)"/>
</ColorMap>
"""


def test_parse_colormap_midpoints_and_no_data():
    mapping = _parse_colormap(SAMPLE_COLORMAP_XML)

    # La prima entry "No Data" (transparent) deve essere saltata.
    assert (0, 0, 0) not in mapping
    assert len(mapping) == 3
    # Midpoint = (lo + hi) / 2
    assert mapping[(10, 20, 30)] == pytest.approx(-1.25)
    assert mapping[(40, 50, 60)] == pytest.approx(0.0)
    # INF viene clampato a +/-2.5 m/s -> midpoint (1.0 + 2.5) / 2
    assert mapping[(70, 80, 90)] == pytest.approx(1.75)


def test_parse_colormap_invalid_xml_returns_empty():
    assert _parse_colormap("not xml at all") == {}


def test_build_context_messages_earthquake_it():
    context = {
        "kind": "earthquake",
        "magnitude": 5.3,
        "depth_km": 10.4,
        "place": "15 km SE of Norcia, Italy",
        "time": "2024-10-09T00:00:00+00:00",
        "lat": 42.72,
        "lon": 13.15,
        "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000abcd",
        "felt": 12,
        "alert": "green",
        "mag_type": "mb",
        "tsunami": False,
    }
    messages = build_context_messages(context, "it")

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    system = messages[0]["content"]
    user = messages[1]["content"]
    # Il prompt di sistema deve essere in italiano.
    assert "geologo senior" in system
    assert "italiano" in system
    # I dati chiave devono comparire come righe leggibili nel messaggio utente.
    assert "Norcia" in user
    assert "5.3" in user
    assert "10.4" in user
    # Non JSON grezzo.
    assert '"place"' not in user
    # Dovrebbe chiedere un contesto tettonico.
    assert "tettonic" in user or "sismolog" in user


def test_build_context_messages_earthquake_en():
    context = {
        "kind": "earthquake",
        "magnitude": 4.1,
        "depth_km": 33.0,
        "place": "Nevada",
        "time": "2024-10-09T00:00:00+00:00",
        "lat": 39.0,
        "lon": -117.0,
        "url": "",
        "felt": None,
        "alert": None,
        "mag_type": "ml",
        "tsunami": False,
    }
    messages = build_context_messages(context, "en")
    system = messages[0]["content"]
    assert "senior geologist" in system
    assert "Answer in English" in messages[1]["content"]


def test_ai_configured_respects_env(monkeypatch):
    monkeypatch.delenv("GEOBRAIN_AI_API_KEY", raising=False)
    assert ai_configured() is False

    monkeypatch.setenv("GEOBRAIN_AI_API_KEY", "  ")
    assert ai_configured() is False

    monkeypatch.setenv("GEOBRAIN_AI_API_KEY", "gsk_test_key_123")
    assert ai_configured() is True


# ---------------------------------------------------------------------------
# Minerali "nel terreno"
# ---------------------------------------------------------------------------

def test_haversine_known_distance():
    # Norcia → Roma ~ 90-110 km a seconda del punto esatto.
    d = haversine_km(42.79, 13.09, 41.90, 12.50)
    assert 70 < d < 140


def test_minerals_for_location_shallow_crust():
    # Norcia (Italia): crosta superficiale → idrotermali + quarzo, con la
    # pirite toscana (vicina + idrotermale) nettamente in cima.
    items = minerals_for_location(42.79, 13.09, depth_km=10.0)
    assert len(items) == len(mineral_occurrences())
    assert items[0]["name"] == "Pirite"
    assert REASON_NEARBY in items[0]["reasons"]
    assert REASON_HYDROTHERMAL in items[0]["reasons"]
    quartz = next(m for m in items if m["name"] == "Quarzo")
    assert REASON_CRUST in quartz["reasons"]
    nearby = [m for m in items if REASON_NEARBY in m["reasons"]]
    assert any(m["name"] == "Pirite" for m in nearby)  # Toscana dista < 800 km
    for item in items:
        assert item["distance_km"] > 0
        assert isinstance(item["reasons"], list)


def test_minerals_for_location_deep_mantle():
    # Fiji profondo: l'olivina (litologia mantellica) deve dominare la classifica.
    items = minerals_for_location(-17.7, -178.1, depth_km=560.0)
    assert items[0]["name"] == "Olivina"
    assert REASON_MANTLE in items[0]["reasons"]
    assert REASON_HYDROTHERMAL not in items[0]["reasons"]


def test_minerals_for_location_no_depth_still_works():
    items = minerals_for_location(0.0, 0.0, depth_km=None)
    assert len(items) == len(mineral_occurrences())


# ---------------------------------------------------------------------------
# Impostazioni AI per utente
# ---------------------------------------------------------------------------

def test_ai_settings_roundtrip_and_isolation(tmp_path):
    database = tmp_path / "users.sqlite3"
    register_user("alice", "secure-password", database)
    register_user("bob", "secure-password", database)
    save_ai_settings("alice", api_key="gsk_alice", base_url="", model="m1", db_path=database)

    alice = load_ai_settings("alice", database)
    assert alice == {"api_key": "gsk_alice", "base_url": "", "model": "m1"}
    # Case-insensitive come gli account, isolata per utente.
    assert load_ai_settings("ALICE", database)["api_key"] == "gsk_alice"
    assert load_ai_settings("bob", database)["api_key"] == ""

    save_ai_settings("alice", api_key="gsk_new", model="m2", db_path=database)
    assert load_ai_settings("alice", database)["api_key"] == "gsk_new"

    delete_ai_settings("alice", db_path=database)
    assert load_ai_settings("alice", database)["api_key"] == ""


def test_ai_settings_deleted_with_account(tmp_path):
    database = tmp_path / "users.sqlite3"
    register_user("carol", "secure-password", database)
    save_ai_settings("carol", api_key="gsk_carol", db_path=database)
    delete_account("carol", "secure-password", database)
    delete_ai_settings("carol", db_path=database)

    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT COUNT(*) FROM user_ai_settings WHERE username = ?", ("carol",)
        ).fetchone()
    assert rows[0] == 0


def test_ai_runtime_config_overrides_env(monkeypatch):
    monkeypatch.delenv("GEOBRAIN_AI_API_KEY", raising=False)
    clear_ai_config()
    assert ai_configured() is False

    set_ai_config(api_key="gsk_runtime", model="custom-model")
    assert ai_configured() is True
    assert ai_model_name() == "custom-model"

    set_ai_config(api_key="gsk_runtime", base_url="https://example.com/v1", model="custom-model")
    monkeypatch.setenv("GEOBRAIN_AI_MODEL", "env-model")
    # Il modello runtime vince; senza runtime vincerebbe l'ambiente.
    assert ai_model_name() == "custom-model"

    clear_ai_config()
    assert ai_configured() is False
    assert ai_model_name() == "env-model"


def test_ai_model_default_and_deprecated_migration(monkeypatch):
    """Default attuale di Groq e rimappatura silenziosa degli id dismessi."""
    monkeypatch.delenv("GEOBRAIN_AI_MODEL", raising=False)
    clear_ai_config()
    assert ai_model_name() == "openai/gpt-oss-120b"

    # Id dismessi (chiavi salvate nel DB o env datate) vengono migrati.
    for old in (
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "qwen/qwen3-32b",
        "meta-llama/llama-4-scout-17b-16e-instruct",
    ):
        set_ai_config(api_key="k", model=old)
        assert ai_model_name() == DEPRECATED_MODEL_REPLACEMENTS[old]
        assert ai_model_name() != old
    clear_ai_config()

    # Un modello custom NON toccato dalla mappa passa invariato.
    monkeypatch.setenv("GEOBRAIN_AI_MODEL", "my-own-model")
    assert ai_model_name() == "my-own-model"
    monkeypatch.delenv("GEOBRAIN_AI_MODEL", raising=False)


def test_base_url_and_model_input_normalization(monkeypatch):
    """Input digitati a mano diventano utilizzabili: schema mancante, alias
    dei siti web più digitati, spazi nel nome del modello."""
    clear_ai_config()
    monkeypatch.delenv("GEOBRAIN_AI_BASE_URL", raising=False)

    # Default senza alcun override.
    assert _resolve_base_url() == "https://api.groq.com/openai/v1"

    # Schema mancante e slash finale.
    set_ai_config(api_key="k", base_url=" api.moonshot.ai/v1/ ")
    assert _resolve_base_url() == "https://api.moonshot.ai/v1"

    # Alias: chi digita il sito web invece dell'endpoint API.
    set_ai_config(api_key="k", base_url="kimi.ai")
    assert _resolve_base_url() == "https://api.moonshot.ai/v1"
    set_ai_config(api_key="k", base_url="WWW.Groq.com")
    assert _resolve_base_url() == "https://api.groq.com/openai/v1"

    # Vale anche via variabile d'ambiente.
    clear_ai_config()
    monkeypatch.setenv("GEOBRAIN_AI_BASE_URL", "openai.com")
    assert _resolve_base_url() == "https://api.openai.com/v1"
    monkeypatch.delenv("GEOBRAIN_AI_BASE_URL", raising=False)

    # Nome modello con spazi interni (es. «kimi k3») → trattini.
    set_ai_config(api_key="k", model="  kimi  k3 ")
    assert ai_model_name() == "kimi-k3"
    clear_ai_config()


def test_first_of_month():
    """Primo del mese con lag: formato fisso e attraversamento dell'anno."""
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc)
    for lag in (0, 1, 3, 12, 13, 25):
        value = _first_of_month(lag)
        assert value.endswith("-01") and len(value) == 10
        month = today.month - lag
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        assert value == f"{year:04d}-{month:02d}-01"


def test_png_has_data():
    """PNG tutto trasparente (data GIBS mancante) vs PNG con pixel opachi."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (64, 32), (0, 0, 0, 0)).save(buf, format="PNG")
    assert _png_has_data(buf.getvalue()) is False

    buf = io.BytesIO()
    Image.new("RGBA", (64, 32), (254, 231, 150, 255)).save(buf, format="PNG")
    assert _png_has_data(buf.getvalue()) is True

    assert _png_has_data(b"non un png") is False


def test_parse_colormap_legend():
    """Leggenda dalla scala colori GIBS: gradiente CSS e estremi in °C."""
    from data.climate import _parse_colormap_legend

    xml = """<?xml version="1.0"?>
    <ColorMaps>
      <ColorMap title="Temperature">
        <ColorMapEntry rgb="0,0,255" transparent="true" value="[-INF,220)"/>
        <ColorMapEntry rgb="0,0,255" value="[220,240)"/>
        <ColorMapEntry rgb="0,255,255" value="[240,265)"/>
        <ColorMapEntry rgb="255,255,0" value="[265,290)"/>
        <ColorMapEntry rgb="255,0,0" value="[290,310)"/>
        <ColorMapEntry rgb="255,0,0" value="[310,+INF)"/>
      </ColorMap>
    </ColorMaps>"""
    bar = _parse_colormap_legend(xml)
    assert bar is not None
    assert bar["gradient"].startswith("linear-gradient(to right, ")
    assert "#0000ff" in bar["gradient"] and "#ff0000" in bar["gradient"]
    assert bar["min_c"] == round(220 - 273.15)
    assert bar["max_c"] == round(310 - 273.15)

    assert _parse_colormap_legend("non xml") is None
