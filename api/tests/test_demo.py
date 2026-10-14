import json
import os
import subprocess
import sys
from pathlib import Path

from services.demo import is_blocked

ROOT = Path(__file__).resolve().parent.parent

# Remise à zéro complète, dans un processus à part (sa base, son dossier uploads)
SCRIPT = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from fastapi.testclient import TestClient
import main
from services import demo
from drivers import mqtt

demo.reset_demo(main.app)
demo.reset_demo(main.app)  # chaque nuit : même résultat
client = TestClient(main.app)
info = client.get("/public/demo/").json()
token = client.post("/login", data={"username": info["username"], "password": info["password"]}).json()["access_token"]
h = {"Authorization": f"Bearer {token}"}
aquariums = client.get("/aquariums/", headers=h).json()["aquariums"]
reef = next(a for a in aquariums if a["name"] == "Récif")
equipments = client.get("/equipments/", headers=h).json()
equipments = equipments.get("equipments", equipments) if isinstance(equipments, dict) else equipments
osmo = next(e for e in equipments if e["name"] == "Osmolateur")
client.post(f"/equipments/{osmo['id']}/toggle", json={"status": "ON"}, headers=h)
after = client.get(f"/equipments/{osmo['id']}", headers=h).json()
demo.simulate_sensors(mqtt.mqtt_driver)
sensors = client.get("/sensors/", headers=h).json()
sensors = sensors.get("sensors", sensors) if isinstance(sensors, dict) else sensors
print(json.dumps({
    "aquariums": sorted(a["name"] for a in aquariums),
    "params": len(client.get("/water-parameters/", params={"aquarium_id": reef["id"]}, headers=h).json()),
    "osmo": after["status"],
    "temps": [s["last_value"] for s in sensors if s["unit"] == "°C"],
    "backup": client.get("/backup/settings", headers=h).status_code,
    "password": client.post("/change-password", json={"old_password": "demo", "new_password": "x" * 12}, headers=h).status_code,
    "species": client.get("/species/corals", headers=h).status_code,
    "groups": sorted(g["name"] for g in client.get("/equipment-groups/", headers=h).json()),
    "documents": {d["title"]: len(d["links"]) for d in client.get("/purchase-documents/", headers=h).json()},
    "files": sum(len(d["files"]) for d in client.get("/purchase-documents/", headers=h).json()),
    "coral_photo": client.get(f"/photos/corals/1/main", headers=h).headers.get("content-type"),
    "journal": len(client.get("/journal/", params={"aquarium_id": reef["id"]}, headers=h).json()),
}))
'''


def test_demo_reset_and_guards(tmp_path):
    env = {**os.environ, "ENV": "test", "AQUAS_ENV_FILE": "/nonexistent", "AQUAS_DEMO": "true",
           "AQUAS_HUB_URL": "none", "AQUAS_DATABASE__SQLITE_PATH": str(tmp_path / "demo.db")}
    env.pop("AQUAS_TEST_DB_RESET", None)
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads" / "photo-visiteur.jpg").write_bytes(b"x")
    result = subprocess.run([sys.executable, "-c", SCRIPT, str(ROOT)], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr[-3000:]
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["aquariums"] == ["Bac planté", "Récif"]
    assert data["params"] == 7
    assert data["osmo"] == "ON"  # le contrôleur simulé répond à la commande
    assert len(data["temps"]) == 2 and all(20 < t < 30 for t in data["temps"])
    assert data["backup"] == 403 and data["password"] == 403
    assert not (tmp_path / "uploads" / "photo-visiteur.jpg").exists()
    assert data["groups"] == ["Maintenance", "Maintenance"]  # un par aquarium
    assert data["documents"]["Facture Récif Passion"] == 3  # liée aux coraux par leurs numéros CITES
    assert data["files"] == 3
    assert data["coral_photo"] == "image/jpeg"
    assert data["journal"] >= 15  # notes, changements d'eau et ajouts de vivants automatiques


def test_demo_blocked_routes():
    assert is_blocked("GET", "/backup/settings")
    assert is_blocked("POST", "/controllers/3/flash")
    assert is_blocked("PATCH", "/users/2")
    assert is_blocked("POST", "/cameras/test")
    assert is_blocked("PUT", "/license/")
    assert not is_blocked("GET", "/license/")
    assert not is_blocked("GET", "/assistant/status")
    assert is_blocked("PUT", "/assistant/settings")
    assert is_blocked("POST", "/group-orders/")
    assert not is_blocked("GET", "/group-orders/mine")
    assert not is_blocked("PUT", "/me/language")
    assert not is_blocked("GET", "/users/me")
    assert not is_blocked("POST", "/equipments/3/toggle")


def test_demo_info_absent_outside_demo(client):
    assert client.get("/public/demo/").status_code == 404
