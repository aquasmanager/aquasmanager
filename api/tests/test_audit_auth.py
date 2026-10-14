from tests.helpers import equipment_payload


def test_audit_log_records_actions_without_secrets(api, client, aquarium, controller, uid):
    eq = api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"Pompe audit {uid}"), code=201)
    api.patch(f"/equipments/{eq['id']}/mode", {"mode": "MANUAL"})
    api.delete(f"/equipments/{eq['id']}")
    api.post("/register", {"username": f"auditeur{uid}", "password": "Password123!", "role": "consult",
                           "must_change_password": False}, code=201)
    client.post("/login", data={"username": "admin", "password": "mauvais-mot-de-passe"})

    items = api.get("/audit/", params={"limit": 50})["items"]
    actions = [(item["action"], item["entity_label"]) for item in items]
    assert ("Création de l'équipement", f"Pompe audit {uid}") in actions
    assert ("Changement de mode de l'équipement", f"Pompe audit {uid}") in actions
    assert ("Suppression de l'équipement", f"Pompe audit {uid}") in actions
    assert any(action == "Échec de connexion" for action, _ in actions)
    creation = next(item for item in items if item["action"] == "Création de l'utilisateur")
    assert "Password123!" not in (creation["details"] or "")
    assert creation["username"] == "admin"


def test_audit_is_admin_only(api, client, uid):
    api.post("/register", {"username": f"lecteur{uid}", "password": "Password123!", "role": "manager",
                           "must_change_password": False}, code=201)
    token = client.post("/login", data={"username": f"lecteur{uid}", "password": "Password123!"}).json()["access_token"]
    assert client.get("/audit/", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_deleted_user_cannot_refresh(api, client, uid):
    user = api.post("/register", {"username": f"parti{uid}", "password": "Password123!", "role": "user",
                                  "must_change_password": False}, code=201)
    login = client.post("/login", data={"username": f"parti{uid}", "password": "Password123!"})
    refresh_cookie = login.cookies.get("refresh_token")
    api.delete(f"/users/{user['id']}")
    client.cookies.set("refresh_token", refresh_cookie)
    try:
        assert client.post("/refresh").status_code == 401
    finally:
        client.cookies.clear()


def test_flash_status_endpoint(api):
    assert isinstance(api.get("/controllers/flash-status"), list)


def test_login_throttled_after_repeated_failures(client, uid):
    from routes import auth as auth_routes

    try:
        for _ in range(auth_routes.LOGIN_MAX_FAILURES):
            assert client.post("/login", data={"username": f"inconnu{uid}", "password": "x"}).status_code == 400
        blocked = client.post("/login", data={"username": f"inconnu{uid}", "password": "x"})
        assert blocked.status_code == 429
        # Même bloquée, l'adresse ne peut plus tenter d'autres identifiants
        assert client.post("/login", data={"username": "admin", "password": "ChangeMe123!"}).status_code == 429
    finally:
        auth_routes._login_failures.clear()
    assert client.post("/login", data={"username": "admin", "password": "ChangeMe123!"}).status_code == 200


def test_photo_upload_sanitized(api, client, admin_headers, aquarium):
    import io

    evil = client.post(f"/photos/aquariums/{aquarium['id']}",
                       files={"file": ("../../../evil.png", io.BytesIO(b"x"), "image/png")}, headers=admin_headers)
    assert evil.status_code == 200 and "/" not in evil.json()["filename"] and ".." not in evil.json()["filename"]
    svg = client.post(f"/photos/aquariums/{aquarium['id']}",
                      files={"file": ("x.svg", io.BytesIO(b"<svg/>"), "image/svg+xml")}, headers=admin_headers)
    assert svg.status_code == 400


def test_websocket_requires_token(client, admin_headers):
    import json

    import pytest
    from starlette.websockets import WebSocketDisconnect

    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "auth", "token": "faux"}))
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_text()
        assert closed.value.code == 4401

    token = admin_headers["Authorization"].split(" ", 1)[1]
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "auth", "token": token}))
        from services.websocket import ws_manager
        import time
        for _ in range(20):
            if ws_manager.active_connections:
                break
            time.sleep(0.05)
        assert ws_manager.active_connections
