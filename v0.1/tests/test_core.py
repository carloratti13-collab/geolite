import sqlite3

import pytest

from auth.auth import RegistrationError, authenticate, delete_account, register_user
from data.climate import climate_snapshot
from data.earthquakes import earthquake_feed
from data.minerals import mineral_occurrences


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


def test_fallback_data_shapes():
    earthquakes = earthquake_feed(days=1)
    minerals = mineral_occurrences()
    climate = climate_snapshot("Italia")
    assert {"magnitude", "depth_km", "lat", "lon"}.issubset(earthquakes.columns)
    assert {"mineral", "country", "lat", "lon"}.issubset(minerals.columns)
    assert "temperature_c" in climate
