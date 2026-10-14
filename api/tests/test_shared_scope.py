from middleware.database import SessionLocal
from services import notify
from services.task_reminders import send_due_today_reminders


def _aquarium(api, name):
    return api.post(
        "/aquariums/",
        {"name": name, "volume": 200, "water_type": "sea", "biotope": "récifal", "date_creation": "2026-01-01"},
        code=201,
    )


def test_item_shared_with_several_aquariums(api, uid):
    a, b, c = (_aquarium(api, f"Partage {uid} {x}") for x in "ABC")
    item = api.post("/inventory-items/", {"aquarium_id": a["id"], "name": f"Test KH {uid}", "unit": "tests",
                                          "quantity": 2, "low_stock_threshold": 5,
                                          "scope": "multiple", "aquarium_ids": [a["id"], b["id"]]}, code=201)
    assert item["scope"] == "multiple" and item["aquarium_ids"] == sorted([a["id"], b["id"]])

    listed = lambda aq: {i["id"] for i in api.get("/inventory-items/", params={"aquarium_id": aq["id"]})}  # noqa: E731
    assert item["id"] in listed(a) and item["id"] in listed(b) and item["id"] not in listed(c)

    cards = {card["id"]: card for card in api.get("/overview/")["aquariums"]}
    assert cards[a["id"]]["low_stock_items"] >= 1 and cards[b["id"]]["low_stock_items"] >= 1
    assert cards[c["id"]]["low_stock_items"] == 0

    # Un seul aquarium dans la sélection : redevient « single » sur ce bac
    item = api.patch(f"/inventory-items/{item['id']}", {"scope": "multiple", "aquarium_ids": [b["id"]]})
    assert item["scope"] == "single" and item["aquarium_id"] == b["id"] and item["aquarium_ids"] == [b["id"]]

    api.patch(f"/inventory-items/{item['id']}", {"scope": "multiple", "aquarium_ids": [999999, a["id"]]}, code=400)


def test_task_for_all_aquariums(api, uid, monkeypatch):
    a, b = (_aquarium(api, f"Tous {uid} {x}") for x in "AB")
    task = api.post("/maintenance-tasks/", {"aquarium_id": a["id"], "title": f"Membrane osmoseur {uid}",
                                            "recurrence": "none", "next_due_at": "2031-05-02T12:00:00",
                                            "scope": "all"}, code=201)
    assert task["scope"] == "all" and task["aquarium_ids"] == []

    later = _aquarium(api, f"Tous {uid} C")  # créé après : concerné aussi
    for aq in (a, b, later):
        assert task["id"] in {t["id"] for t in api.get("/maintenance-tasks/", params={"aquarium_id": aq["id"]})}

    events = api.get("/maintenance-tasks/calendar",
                     params={"start": "2031-05-01", "end": "2031-05-03", "aquarium_id": b["id"]})
    event = next(e for e in events if e["task_id"] == task["id"])
    assert event["shared"] and event["aquarium_name"] == "Tous les aquariums"

    sent = []
    monkeypatch.setattr(notify, "dispatch_alert", lambda subject, message, priority="default": sent.append(message))
    from datetime import datetime
    from zoneinfo import ZoneInfo
    db = SessionLocal()
    try:
        send_due_today_reminders(db, datetime(2031, 5, 2, 9, 0, tzinfo=ZoneInfo("Europe/Paris")))
    finally:
        db.close()
    assert any(f"Tous les aquariums — Membrane osmoseur {uid}" in m for m in sent)


def test_deleting_aquarium_keeps_shared_items(api, uid):
    a, b, c = (_aquarium(api, f"Suppr {uid} {x}") for x in "ABC")
    own = api.post("/maintenance-tasks/", {"aquarium_id": a["id"], "title": f"Propre {uid}"}, code=201)
    pair = api.post("/maintenance-tasks/", {"aquarium_id": a["id"], "title": f"Paire {uid}",
                                            "scope": "multiple", "aquarium_ids": [a["id"], b["id"]]}, code=201)
    trio = api.post("/inventory-items/", {"aquarium_id": a["id"], "name": f"Sel {uid}", "unit": "kg",
                                          "scope": "multiple", "aquarium_ids": [a["id"], b["id"], c["id"]]}, code=201)
    everyone = api.post("/inventory-items/", {"aquarium_id": a["id"], "name": f"Commun {uid}", "unit": "u",
                                              "scope": "all"}, code=201)

    api.delete(f"/aquariums/{a['id']}")

    tasks = {t["id"]: t for t in api.get("/maintenance-tasks/")}
    assert own["id"] not in tasks
    assert tasks[pair["id"]]["scope"] == "single" and tasks[pair["id"]]["aquarium_id"] == b["id"]
    items = {i["id"]: i for i in api.get("/inventory-items/")}
    assert items[trio["id"]]["aquarium_ids"] == sorted([b["id"], c["id"]])
    assert items[everyone["id"]]["scope"] == "all" and items[everyone["id"]]["aquarium_id"] != a["id"]
