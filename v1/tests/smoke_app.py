"""Smoke test end-to-end di app.py con streamlit.testing.v1.AppTest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from streamlit.testing.v1 import AppTest

from auth.auth import register_user

DB = Path("/tmp/geolite_smoke_users.sqlite3")
if DB.exists():
    DB.unlink()

register_user("smoke_user", "smoke-password-123", DB)
import os
os.environ["GEOBRAIN_DB_PATH"] = str(DB)

ROOT = Path(__file__).resolve().parent.parent
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
at.run()
print("== auth gate ==")
print("exception:", at.exception)
assert not at.exception

# Login
at.text_input(key="login_user").set_value("smoke_user")
at.text_input(key="login_pass").set_value("smoke-password-123")
at.get_by_key("login_submit").click()
at.run()
print("== dopo login ==")
print("exception:", at.exception)
print("session user:", at.session_state.get("user"))
assert not at.exception
assert at.session_state.get("user", {}).get("username") == "smoke_user"

for section in ["seismic", "volcanoes", "currents", "climate"]:
    at.session_state["section"] = section
    at.run()
    print(f"== sezione {section} == exception:", at.exception)
    if at.exception:
        print(at.exception)
    assert not at.exception

# Selezione di un terremoto → pannello minerali nel terreno
fake_eq = {
    "kind": "earthquake",
    "id": "smoke1",
    "lat": 42.7,
    "lon": 13.2,
    "depth_km": 10.0,
    "magnitude": 5.5,
    "place": "Smoke Test, Italy",
    "time": "2026-10-09T00:00:00+00:00",
}
at.session_state["section"] = "seismic"
at.session_state["details"] = fake_eq
at.session_state["eq_selected_id"] = None
at.run()
print("== minerali nel terreno == exception:", at.exception)
assert not at.exception

# Selezione da componente (click sul globo): pending applicato al run dopo,
# senza toccare la chiave del widget dopo la sua istanziazione.
import data.earthquakes as eq_mod
real_events = eq_mod.earthquake_events(days=7, min_magnitude=2.5)
if real_events:
    picked = real_events[0]
    at.session_state["pending_eq_select"] = picked["id"]
    at.run()
    print("== selezione da globo == exception:", at.exception)
    assert not at.exception
    details = at.session_state.get("details") or {}
    assert details.get("id") == picked["id"], details.get("id")
    assert at.session_state.get("eq_selected_id") == picked["id"]

# Cambio lingua
at.session_state["locale"] = "en"
at.session_state["section"] = "seismic"
at.run()
print("== locale en == exception:", at.exception)
assert not at.exception

print("SMOKE OK")
