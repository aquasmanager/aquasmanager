from datetime import date, timedelta

from tests.helpers import equipment_payload


def test_journal_entries(api, aquarium):
    entry = api.post("/journal/", {"aquarium_id": aquarium["id"], "text": "Algues brunes sur la vitre",
                                   "category": "problem", "occurred_at": "2026-09-30T08:15:00Z"}, code=201)
    assert entry["category"] == "problem" and entry["auto"] is False
    assert entry["occurred_at"].startswith("2026-09-30T08:15")
    api.post("/journal/", {"aquarium_id": aquarium["id"], "text": "Changement d'eau 10 %", "category": "water_change"},
             code=201)

    entries = api.get("/journal/", params={"aquarium_id": aquarium["id"]})
    assert [e["category"] for e in entries][:2] == ["water_change", "problem"]  # plus récentes d'abord
    period = api.get("/journal/", params={"aquarium_id": aquarium["id"], "since": "2026-09-29T00:00:00Z",
                                          "until": "2026-10-01T00:00:00Z"})
    assert [e["id"] for e in period] == [entry["id"]]

    updated = api.patch(f"/journal/{entry['id']}", {"text": "Diatomées", "category": "note"})
    assert updated["text"] == "Diatomées" and updated["category"] == "note"
    api.post("/journal/", {"aquarium_id": aquarium["id"], "text": "x", "category": "inconnue"}, code=422)
    api.delete(f"/journal/{entry['id']}")
    assert entry["id"] not in [e["id"] for e in api.get("/journal/", params={"aquarium_id": aquarium["id"]})]


def test_journal_automatic_entries(api, aquarium, controller, uid):
    acquired = (date.today() - timedelta(days=12)).isoformat()
    api.post("/fishes/", {"aquarium_id": aquarium["id"], "name": f"Poisson-clown {uid}", "quantity": 2,
                          "scientific_name": "Amphiprion ocellaris", "family": "Pomacentridae", "origin": "Élevage",
                          "max_height": 8, "min_volume": 80, "reef_safe": True, "date_acquisition": acquired}, code=201)
    pump = api.post("/equipments/", equipment_payload(aquarium, controller, "12", f"Pompe {uid}"), code=201)
    api.post(f"/aquariums/{aquarium['id']}/maintenance", {"equipment_ids": [pump["id"]], "minutes": 30})
    api.delete(f"/aquariums/{aquarium['id']}/maintenance", code=200)

    entries = api.get("/journal/", params={"aquarium_id": aquarium["id"]})
    added = next(e for e in entries if e["category"] == "livestock")
    assert added["auto"] is True and added["text"] == f"Ajout : 2 × Poisson-clown {uid}"
    assert added["occurred_at"].startswith(acquired)  # daté de l'acquisition
    maintenance = next(e for e in entries if e["category"] == "maintenance")
    assert maintenance["auto"] is True and f"Pompe {uid}" in maintenance["text"]


def test_photo_date_from_original_file(api, client, admin_headers, aquarium):
    from tests.helpers import PNG
    import base64

    png = base64.b64decode(PNG.split(",", 1)[1])
    photo = client.post(f"/photos/aquariums/{aquarium['id']}", headers=admin_headers,
                        files={"file": ("p.png", png, "image/png")}, data={"taken_at": "2025-06-01T10:00:00Z"})
    assert photo.status_code == 200, photo.text
    assert photo.json()["created_at"].startswith("2025-06-01T10:00")
    future = client.post(f"/photos/aquariums/{aquarium['id']}", headers=admin_headers,
                         files={"file": ("p.png", png, "image/png")}, data={"taken_at": "2099-01-01T00:00:00Z"})
    assert not future.json()["created_at"].startswith("2099")  # date impossible : date d'envoi
