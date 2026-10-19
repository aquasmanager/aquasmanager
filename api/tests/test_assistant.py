import json

import httpx

from models.assistant import AssistantSettings
from services import llm_provider


def _fake_llm(monkeypatch, handler):
    """Remplace le client HTTP de l'assistant par un faux service."""
    real = httpx.AsyncClient
    seen = []

    def wrapped(request: httpx.Request):
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(wrapped), **kw))
    return seen


def test_assistant_disabled_by_default_and_key_never_returned(api, client, admin_headers):
    assert AssistantSettings.__table__.c.enabled.default.arg is False  # désactivé à l'installation
    api.put("/assistant/settings", {"enabled": False, "api_key": ""})
    assert api.get("/assistant/status") == {"enabled": False, "provider": None, "model": None, "external": False}
    assert client.post("/chat/", json={"prompt": "Salut"}, headers=admin_headers).status_code == 409

    api.put("/assistant/settings", {"enabled": True, "model": ""}, code=400)  # pas de modèle
    conf = api.put("/assistant/settings", {"provider": "openai", "base_url": "https://api.example.com/v1/", "model": "m", "api_key": "sk-secret"})
    assert conf["api_key_set"] is True and conf["base_url"] == "https://api.example.com/v1" and "sk-secret" not in json.dumps(conf)
    from middleware.database import SessionLocal
    with SessionLocal() as db:
        stored = db.get(AssistantSettings, 1).api_key_encrypted
        assert stored and "sk-secret" not in stored and llm_provider.decrypt_key(stored) == "sk-secret"
    api.put("/assistant/settings", {"base_url": "ftp://x"}, code=422)


def test_assistant_openai_compatible_with_tools(api, client, admin_headers, aquarium, monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer sk-test"
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gpt-x"}, {"id": "mistral-small"}]})
        body = json.loads(request.content)
        calls["n"] += 1
        if calls["n"] == 1:
            assert body["tools"] and body["model"] == "mistral-small"
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "list_aquariums", "arguments": "{}"}}]}}]})
        tool_msg = body["messages"][-1]
        assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "call_1" and aquarium["name"] in tool_msg["content"]
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "Tu as des bacs."}}]})

    _fake_llm(monkeypatch, handler)
    probe = {"provider": "openai", "base_url": "https://api.mistral.ai/v1", "api_key": "sk-test"}
    assert api.post("/assistant/models", probe)["models"] == ["gpt-x", "mistral-small"]
    api.put("/assistant/settings", {**probe, "model": "mistral-small", "enabled": True, "data_access": True})
    status = api.get("/assistant/status")
    assert status["enabled"] and status["external"] is True
    answer = client.post("/chat/", json={"prompt": "Mes bacs ?"}, headers=admin_headers).json()["answer"]
    assert answer == "Tu as des bacs." and calls["n"] == 2


def test_assistant_ollama_errors_and_no_data(api, client, admin_headers, monkeypatch):
    def handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
        body = json.loads(request.content)
        assert "tools" not in body  # accès aux données coupé
        if body["model"] == "absent":
            return httpx.Response(404, json={"error": "model not found"})
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "OK"}})

    _fake_llm(monkeypatch, handler)
    api.put("/assistant/settings", {"provider": "ollama", "base_url": "http://192.168.1.20:11434", "model": "qwen2.5:7b",
                                    "api_key": "", "enabled": True, "data_access": False})
    assert api.get("/assistant/status")["external"] is False
    assert api.post("/assistant/models", {})["models"] == ["qwen2.5:7b"]
    ok = api.post("/assistant/test", {})
    assert ok["ok"] is True and "OK" in ok["message"]
    ko = api.post("/assistant/test", {"model": "absent"})
    assert ko["ok"] is False and "introuvable" in ko["message"]
    assert client.post("/chat/", json={"prompt": "Salut"}, headers=admin_headers).json()["answer"] == "OK"
    api.put("/assistant/settings", {"enabled": False})


def test_is_external():
    ext = llm_provider.is_external
    assert not ext("http://localhost:11434") and not ext("http://ollama:11434") and not ext("http://10.0.0.5:1234/v1")
    assert not ext("http://ollama.ollama.svc.cluster.local:11434") and not ext("http://nas.local:11434")
    assert ext("https://api.openai.com/v1") and ext("https://8.8.8.8/v1")


def test_licenses_inventory(api):
    data = api.get("/about/licenses")
    names = {p["name"].lower(): p for p in data["python"]}
    assert "fastapi" in names and "esphome" in names and "mysql-connector-python" not in names
    assert names["pymysql"]["license"] == "MIT"
    assert names["zeroconf"]["note"] and names["fastapi"]["note"] is None
    assert any(c["name"] == "ESPHome" and "GPL-3.0" in c["license"] for c in data["external"])


def test_assistant_errors_never_echo_service_body(api, monkeypatch):
    """Les erreurs du service ne renvoient qu'un message fixe : jamais son texte brut."""
    def handler(request: httpx.Request):
        if request.url.path.endswith("/models"):
            return httpx.Response(500, text="Traceback interne : clé sk-secret-123")
        return httpx.Response(401, json={"error": "invalid key"})

    _fake_llm(monkeypatch, handler)
    api.put("/assistant/settings", {"provider": "openai", "base_url": "http://192.168.1.20:8000/v1", "model": "m",
                                    "api_key": "", "enabled": True, "data_access": False})
    models = api.post("/assistant/models", {}, code=502)
    assert "sk-secret" not in models["detail"] and "journaux" in models["detail"]
    ko = api.post("/assistant/test", {})
    assert ko == {"ok": False, "message": "Clé d'API refusée par le service.", "seconds": ko.get("seconds")}
    api.put("/assistant/settings", {"enabled": False})
