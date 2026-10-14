from types import SimpleNamespace

from drivers.mqtt import mqtt_driver


def test_status_payload_is_normalized(api, controller):
    prefix = mqtt_driver.topic_prefix
    ctrl = controller["technical_name"]

    def receive(payload: bytes):
        mqtt_driver.on_message(None, None, SimpleNamespace(topic=f"{prefix}/{ctrl}/status", payload=payload, retain=True))

    # Arrêt propre d'ESPHome : « offline » en minuscules
    receive(b"offline")
    assert api.get(f"/controllers/{controller['id']}")["status"] == "OFFLINE"
    api.get("/controllers/")  # la liste reste valide

    receive(b"ONLINE")
    assert api.get(f"/controllers/{controller['id']}")["status"] == "ONLINE"

    receive(b"bizarre")  # ignoré
    assert api.get(f"/controllers/{controller['id']}")["status"] == "ONLINE"
