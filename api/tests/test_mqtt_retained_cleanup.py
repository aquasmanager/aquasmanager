from types import SimpleNamespace

from drivers.mqtt import mqtt_driver
from tests.helpers import equipment_payload


def test_stale_retained_messages_are_cleared(api, aquarium, controller, uid, monkeypatch):
    pump = api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"Pompe {uid}"), code=201)
    sent = []
    monkeypatch.setattr(mqtt_driver.client, "publish", lambda topic, payload, qos=0, retain=False: sent.append((topic, payload, retain)))
    prefix = mqtt_driver.topic_prefix
    ctrl = controller["technical_name"]

    def receive(topic, payload=b"ON", retain=True):
        mqtt_driver.on_message(None, None, SimpleNamespace(topic=topic, payload=payload, retain=retain))

    # Ancien nom (renommé puis reflashé) : effacé du broker
    receive(f"{prefix}/{ctrl}/switch/osmolateur_ancien_{uid}/state")
    receive(f"{prefix}/{ctrl}/sensor/niveau_ancien_{uid}/state", b"1")
    assert sent == [(f"{prefix}/{ctrl}/switch/osmolateur_ancien_{uid}/state", b"", True),
                    (f"{prefix}/{ctrl}/sensor/niveau_ancien_{uid}/state", b"", True)]

    sent.clear()
    receive(f"{prefix}/{ctrl}/switch/{pump['technical_name']}/state")  # équipement connu
    receive(f"{prefix}/autre-installation/switch/inconnu/state")  # contrôleur d'ailleurs
    receive(f"{prefix}/{ctrl}/switch/inconnu_{uid}/state", retain=False)  # message en direct
    receive(f"{prefix}/{ctrl}/switch/inconnu_{uid}/state", payload=b"")  # effacement déjà fait
    assert sent == []
