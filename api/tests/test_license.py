from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import services.license as license_service
from settings import settings
from tests.license_helpers import make_key


def _without_env_key(fn):
    """Exécute fn sans la clé de test de la variable d'environnement."""
    saved = settings.license_key
    settings.license_key = ""
    license_service.invalidate_cache()
    try:
        return fn()
    finally:
        settings.license_key = saved
        license_service.invalidate_cache()


def test_status_and_bourse_locked_without_key(api, client):
    status = api.get("/license/")
    assert status["valid"] and {"bourse", "assistant"} <= set(status["features"]) and status["source"] == "env"
    assert {"bourse", "assistant"} <= set(status["paid_features"]) and status["instance_id"]

    def locked():
        info = api.get("/license/")
        assert not info["valid"] and info["features"] == []
        # Vente (bourse) refusée (connecté ou public) ; gestion des boutures ouverte
        # Étiquettes QR des boutures : outil de vente en bourse
        for url in ("/transfer-certificates/", "/showcase/settings", "/seller-profile/", "/sale-locations/",
                    "/frags/labels.pdf?base_url=https://aquas.example.org"):
            response = client.get(url, headers=api.headers)
            assert response.status_code == 403 and response.headers["X-Aquas-Feature"] == "bourse", url
        assert client.get("/public/showcase/").status_code == 403
        for url in ("/frags/", "/purchase-documents/", "/aquariums/"):
            assert client.get(url, headers=api.headers).status_code == 200, url
        # Assistant : réglages et questions refusés, statut « désactivé »
        response = client.get("/assistant/settings", headers=api.headers)
        assert response.status_code == 403 and response.headers["X-Aquas-Feature"] == "assistant"
        assert client.post("/chat/", json={"prompt": "Bonjour"}, headers=api.headers).status_code == 403
        assert client.get("/assistant/status", headers=api.headers).json()["enabled"] is False

    _without_env_key(locked)
    assert client.get("/transfer-certificates/", headers=api.headers).status_code == 200


def test_pasted_key_checks(api):
    instance = api.get("/license/")["instance_id"]

    def run():
        # Signature d'une autre clé privée, autre installation, expirée : refusées
        api.put("/license/", {"key": make_key(["bourse"], private=Ed25519PrivateKey.generate())}, code=400)
        api.put("/license/", {"key": make_key(["bourse"], instance="autre-installation")}, code=400)
        api.put("/license/", {"key": make_key(["bourse"], expires="2020-01-01")}, code=400)
        api.put("/license/", {"key": "AQM1.illisible"}, code=400)
        # Clé altérée (fonctionnalité ajoutée sans re-signer) : refusée
        good = make_key([], instance=instance)
        head, body, sig = good.split(".")
        forged = make_key(["bourse"], instance=instance).split(".")[1]
        api.put("/license/", {"key": f"{head}.{forged}.{sig}"}, code=400)

        saved = api.put("/license/", {"key": make_key(["bourse"], instance=instance, client="Moi")})
        assert saved["valid"] and saved["source"] == "app" and saved["client"] == "Moi"
        assert api.get("/transfer-certificates/") is not None
        api.get("/assistant/settings", code=403)
        cleared = api.delete("/license/", code=200)
        assert not cleared["valid"]
        api.get("/transfer-certificates/", code=403)

    _without_env_key(run)


def test_license_requires_login(client):
    # Sans authentification : refusé
    assert client.get("/license/").status_code == 401
    assert client.put("/license/", json={"key": "AQM1.x.y"}).status_code == 401
