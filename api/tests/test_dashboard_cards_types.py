from tests.helpers import equipment_payload


def test_equipment_card_period_and_normal_state(api, aquarium, controller, uid):
    pump = api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"Remontée {uid}"), code=201)
    card = api.post("/dashboard-cards/", {"aquarium_id": aquarium["id"], "title": "Remontée", "type": "equipment",
                                          "icon": "power", "equipment_id": pump["id"]}, code=201)
    assert card["type"] == "equipment" and card["equipment_id"] == pump["id"]

    level = api.post("/dashboard-cards/", {"aquarium_id": aquarium["id"], "title": "Niveau décante", "type": "binary_level",
                                           "normal_state": "LOW"}, code=201)
    assert level["normal_state"] == "LOW" and level["period"] is None

    temp = api.post("/dashboard-cards/", {"aquarium_id": aquarium["id"], "title": "Température", "type": "temperature",
                                          "period": "7d"}, code=201)
    assert api.patch(f"/dashboard-cards/{temp['id']}", {"period": "30d"})["period"] == "30d"
    api.patch(f"/dashboard-cards/{temp['id']}", {"period": "1y"}, code=422)
    api.post("/dashboard-cards/", {"aquarium_id": aquarium["id"], "title": "X", "type": "binary_level",
                                   "normal_state": "MAYBE"}, code=422)
    kinds = {c["type"] for c in api.get("/dashboard-cards/", params={"aquarium_id": aquarium["id"]})}
    assert {"equipment", "binary_level", "temperature"} <= kinds


def test_reorder_cards_and_activations_since(api, aquarium, controller, uid):
    from datetime import datetime, timedelta

    from middleware.database import SessionLocal
    from models.equipment_activation import EquipmentActivation

    ids = [api.post("/dashboard-cards/", {"aquarium_id": aquarium["id"], "title": f"C{i}", "type": "temperature"}, code=201)["id"]
           for i in range(3)]
    reordered = api.put("/dashboard-cards/order", {"aquarium_id": aquarium["id"], "ids": [ids[2], ids[0], ids[1]]})
    assert [c["id"] for c in reordered][:3] == [ids[2], ids[0], ids[1]]
    listed = [c["id"] for c in api.get("/dashboard-cards/", params={"aquarium_id": aquarium["id"]}) if c["id"] in ids]
    assert listed == [ids[2], ids[0], ids[1]]
    api.put("/dashboard-cards/order", {"aquarium_id": aquarium["id"], "ids": [999999]}, code=400)

    pump = api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"Pompe {uid}"), code=201)
    now = datetime.now()
    with SessionLocal() as db:
        for days in (1, 10, 40):
            start = now - timedelta(days=days)
            db.add(EquipmentActivation(equipment_id=pump["id"], started_at=start, ended_at=start + timedelta(seconds=30),
                                       duration_seconds=30))
        db.commit()
    assert len(api.get(f"/equipments/{pump['id']}/activations", params={"limit": 500})) == 3
    since = (now - timedelta(days=15)).isoformat()
    assert len(api.get(f"/equipments/{pump['id']}/activations", params={"limit": 500, "since": since})) == 2


def test_water_trend_card_and_multi_equipment(api, aquarium, controller, uid):
    # Nouvel aquarium : l'évolution des paramètres est une carte, en tête
    cards = api.get("/dashboard-cards/", params={"aquarium_id": aquarium["id"]})
    trend = [c for c in cards if c["type"] == "water_trend"]
    assert len(trend) == 1 and trend[0]["col_span"] == 12 and cards[0]["id"] == trend[0]["id"]

    pumps = [api.post("/equipments/", equipment_payload(aquarium, controller, pin, f"Pompe {pin} {uid}"), code=201)["id"]
             for pin in ("13", "14")]
    card = api.post("/dashboard-cards/", {"aquarium_id": aquarium["id"], "title": "Équipements", "type": "equipment",
                                          "icon": "power", "equipment_ids": pumps}, code=201)
    assert card["equipment_ids"] == pumps
    assert api.patch(f"/dashboard-cards/{card['id']}", {"equipment_ids": pumps[::-1]})["equipment_ids"] == pumps[::-1]
