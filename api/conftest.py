"""
Fixtures des tests de l'API (tests/ et pro/tests/), sur une base SQLite jetable
(config/test.yaml).

L'application est importée une seule fois : migrations, compte admin par
défaut et catalogue d'espèces sont créés comme au démarrage réel.
"""

import os
import sys
from itertools import count

import pytest

os.environ["ENV"] = "test"
# Les tests ignorent le .env du développeur
os.environ["AQUAS_ENV_FILE"] = "/nonexistent/.env"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEST_DB = "/tmp/aquasmanager-tests.db"
# Base neuve à chaque session, une seule fois : un test qui importe
# « conftest » ne doit pas supprimer la base déjà ouverte par l'appli
if os.environ.get("AQUAS_TEST_DB_RESET") != "1":
    os.environ["AQUAS_TEST_DB_RESET"] = "1"
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from tests.license_helpers import TEST_PUBLIC_KEY, make_key  # noqa: E402
import services.license as license_service  # noqa: E402
from settings import settings as app_settings  # noqa: E402

# Licence de test : clé publique de test, bourse et assistant ouverts (variable d'environnement)
license_service.PUBLIC_KEYS = [TEST_PUBLIC_KEY]
app_settings.license_key = make_key(["bourse", "assistant"])
license_service.invalidate_cache()

_ids = count(1)


@pytest.fixture(scope="session")
def client():
    return TestClient(main.app)


@pytest.fixture(scope="session")
def admin_headers(client):
    response = client.post("/login", data={"username": "admin", "password": "ChangeMe123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def uid():
    """Suffixe unique : chaque test crée ses propres éléments dans la base partagée."""
    return next(_ids)


def check(response, code=200):
    assert response.status_code == code, (response.status_code, response.text)
    return response.json() if response.content else None


@pytest.fixture()
def api(client, admin_headers):
    """Raccourcis get/post/patch/delete authentifiés en admin, avec code attendu."""

    class Api:
        # En-têtes admin, pour les appels directs (fichiers, téléchargements)
        headers = admin_headers

        def get(self, url, code=200, **kw):
            return check(client.get(url, headers=admin_headers, **kw), code)

        def post(self, url, json=None, code=200, **kw):
            return check(client.post(url, json=json, headers=admin_headers, **kw), code)

        def patch(self, url, json=None, code=200):
            return check(client.patch(url, json=json, headers=admin_headers), code)

        def put(self, url, json=None, code=200):
            return check(client.put(url, json=json, headers=admin_headers), code)

        def delete(self, url, code=204):
            return check(client.delete(url, headers=admin_headers), code)

    return Api()


@pytest.fixture()
def aquarium(api, uid):
    return api.post(
        "/aquariums/",
        {"name": f"Bac test {uid}", "volume": 300, "water_type": "sea", "biotope": "récifal", "date_creation": "2026-01-01"},
        code=201,
    )


@pytest.fixture()
def controller(api, uid):
    ctrl = api.post(
        "/controllers/",
        {"name": f"esp-test-{uid}", "type": "ESP32", "zone": "bac", "ip": f"192.168.1.{100 + uid}"},
        code=201,
    )
    pins = api.get(f"/controllers/{ctrl['id']}/pins")["controller_pins"]
    ctrl["pins"] = {p["pin_number"]: p["id"] for p in pins if p["module_id"] is None}
    return ctrl
