import asyncio
import json
import socket
import threading

import pytest
from aiohttp import web

from services import camera as svc
from settings import settings

JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


class FakeGo2rtc:
    """go2rtc minimal : flux en mémoire, image JPEG, websocket MSE."""

    def __init__(self):
        self.streams: dict[str, str] = {}
        self.ws_messages: list[str] = []
        self.loop = asyncio.new_event_loop()
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]

    async def patch(self, request):
        src = request.query["src"]
        if src.startswith("exec:"):
            return web.Response(status=400, text="streams: source from insecure producer")
        self.streams[request.query["name"]] = src
        return web.Response()

    async def delete(self, request):
        self.streams.pop(request.query["src"], None)
        return web.Response()

    async def frame(self, request):
        src = self.streams.get(request.query["src"], "")
        if "wrong" in src or "192.0.2." in src:
            # Comme go2rtc : 200 sans image, motif dans ses journaux seulement
            return web.Response(status=200, body=b"")
        return web.Response(body=JPEG, content_type="image/jpeg")

    async def ws(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for msg in ws:
            self.ws_messages.append(msg.data)
            await ws.send_str(json.dumps({"type": "mse", "value": 'video/mp4; codecs="avc1.640029"'}))
            await ws.send_bytes(b"\x00\x00\x00\x18ftyp")
        return ws

    def start(self):
        app = web.Application()
        app.router.add_patch("/api/streams", self.patch)
        app.router.add_delete("/api/streams", self.delete)
        app.router.add_get("/api/frame.jpeg", self.frame)
        app.router.add_get("/api/ws", self.ws)
        runner = web.AppRunner(app)

        def run():
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(runner.setup())
            self.loop.run_until_complete(web.TCPSite(runner, "127.0.0.1", self.port).start())
            self.loop.run_forever()

        threading.Thread(target=run, daemon=True).start()
        return self


@pytest.fixture(scope="module")
def go2rtc():
    return FakeGo2rtc().start()


@pytest.fixture()
def cameras_on(go2rtc, monkeypatch):
    monkeypatch.setattr(settings, "go2rtc_url", f"http://127.0.0.1:{go2rtc.port}")
    svc._snapshots.clear()
    return go2rtc


def _user(api, client, uid, role):
    api.post("/register", {"username": f"cam{role}{uid}", "password": "Password123!", "role": role,
                           "must_change_password": False}, code=201)
    token = client.post("/login", data={"username": f"cam{role}{uid}", "password": "Password123!"}).json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


def _camera(api, aquarium, **extra):
    return api.post("/cameras/", {"aquarium_id": aquarium["id"], "name": "Vue de face", "brand": "tapo",
                                  "host": "192.168.1.50", "username": "cam user", "password": "p@ss:w/rd",
                                  "main_path": "stream1", "sub_path": "stream2", **extra}, code=201)


def test_disabled_by_default(api, monkeypatch):
    monkeypatch.setattr(settings, "go2rtc_url", "")
    status = api.get("/cameras/status")
    assert status["enabled"] is False and status["presets"]["reolink"]["sub"] == "h264Preview_01_sub"


def test_camera_crud_and_secret(api, client, aquarium, cameras_on):
    cam = _camera(api, aquarium)
    assert cam["has_password"] is True and "password" not in cam and "password_encrypted" not in cam
    # Même nom refusé dans le même aquarium
    api.post("/cameras/", {"aquarium_id": aquarium["id"], "name": "vue de FACE", "host": "10.0.0.2", "main_path": "a"}, code=400)
    # Champs dangereux refusés (source go2rtc construite côté serveur)
    api.post("/cameras/", {"aquarium_id": aquarium["id"], "name": "X", "host": "rtsp://x", "main_path": "a"}, code=400)
    api.post("/cameras/", {"aquarium_id": aquarium["id"], "name": "Y", "host": "10.0.0.2", "main_path": "a#exec:sh"}, code=400)

    # Identifiants encodés dans l'URL RTSP remise à go2rtc
    assert client.get(f"/cameras/{cam['id']}/snapshot", headers=api.headers).status_code == 200
    assert cameras_on.streams[f"aquas_cam_{cam['id']}_sub"] == "rtsp://cam%20user:p%40ss%3Aw%2Frd@192.168.1.50:554/stream2"

    # Mise à jour sans mot de passe : conservé ; clear_password : retiré
    body = {k: cam[k] for k in ("name", "brand", "host", "port", "username", "main_path", "sub_path")}
    assert api.put(f"/cameras/{cam['id']}", {**body, "port": 8554})["has_password"] is True
    assert api.put(f"/cameras/{cam['id']}", {**body, "clear_password": True})["has_password"] is False

    assert [c["id"] for c in api.get("/cameras/", params={"aquarium_id": aquarium["id"]})] == [cam["id"]]
    api.delete(f"/cameras/{cam['id']}")
    assert f"aquas_cam_{cam['id']}_sub" not in cameras_on.streams


def test_snapshot_test_and_capture(api, client, aquarium, cameras_on):
    cam = _camera(api, aquarium)
    image = client.get(f"/cameras/{cam['id']}/snapshot", headers=api.headers)
    assert image.status_code == 200 and image.content == JPEG and image.headers["content-type"] == "image/jpeg"

    assert api.post("/cameras/test", {"host": "192.168.1.50", "path": "stream1", "camera_id": cam["id"]})["ok"] is True
    # Caméra joignable (port ouvert) mais pas d'image : identifiants ou chemin
    refused = api.post("/cameras/test", {"host": "127.0.0.1", "port": cameras_on.port, "username": "wrong", "path": "s"}, code=502)
    assert "mot de passe" in refused["detail"]
    unreachable = api.post("/cameras/test", {"host": "192.0.2.1", "path": "stream1"}, code=502)
    assert "injoignable" in unreachable["detail"]
    assert not [n for n in cameras_on.streams if n.startswith("aquas_test_")]  # flux de test retirés

    photo = api.post(f"/cameras/{cam['id']}/capture", code=201)
    assert photo["entity_type"] == "aquariums" and photo["entity_id"] == aquarium["id"]
    assert cameras_on.streams[f"aquas_cam_{cam['id']}_main"].endswith("/stream1")


def test_roles_and_live_relay(api, client, aquarium, cameras_on, uid):
    cam = _camera(api, aquarium)
    seller_token, seller = _user(api, client, uid, "seller")
    care_token, caretaker = _user(api, client, uid, "caretaker")
    assert client.get("/cameras/", headers=seller).status_code == 403
    assert client.get(f"/cameras/{cam['id']}/snapshot", headers=caretaker).status_code == 200
    assert client.post("/cameras/", json={"aquarium_id": aquarium["id"], "name": "Z", "host": "10.0.0.3", "main_path": "a"},
                       headers=caretaker).status_code == 403

    # Direct : jeton en premier message, puis protocole MSE relayé tel quel
    with client.websocket_connect(f"/cameras/{cam['id']}/live") as ws:
        ws.send_text(json.dumps({"type": "auth", "token": care_token}))
        ws.send_text(json.dumps({"type": "mse", "value": "avc1.640029"}))
        assert json.loads(ws.receive_text())["type"] == "mse"
        assert ws.receive_bytes().endswith(b"ftyp")
    assert json.loads(cameras_on.ws_messages[-1]) == {"type": "mse", "value": "avc1.640029"}

    for token in (seller_token, "invalide"):
        with client.websocket_connect(f"/cameras/{cam['id']}/live") as ws:
            ws.send_text(json.dumps({"type": "auth", "token": token}))
            message = ws.receive()
            assert message["type"] == "websocket.close" and message["code"] in (4401, 4403)
