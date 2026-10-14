from datetime import datetime, timedelta

from middleware.database import SessionLocal
from models.parameter_share import ParameterShareLink


def test_public_parameters_link(api, client, aquarium):
    kh = api.post("/water-parameters/", {"aquarium_id": aquarium["id"], "name": "KH", "unit": "dKH",
                                         "target_min": 7, "target_max": 9}, code=201)
    api.post("/water-parameters/", {"aquarium_id": aquarium["id"], "name": "NO3"}, code=201)  # sans relevé : absent
    old = (datetime.now() - timedelta(days=40)).isoformat()
    api.post(f"/water-parameters/{kh['id']}/readings", {"value": 6.5, "timestamp": old}, code=201)
    api.post(f"/water-parameters/{kh['id']}/readings", {"value": 8.1}, code=201)

    link = api.post("/parameter-shares/", {"aquarium_id": aquarium["id"], "label": "Forum privé", "history_days": 30,
                                           "expires_in_days": 7}, code=201)
    assert link["state"] == "active" and len(link["token"]) >= 20
    assert [link["id"] for link in api.get("/parameter-shares/", params={"aquarium_id": aquarium["id"]})] == [link["id"]]

    # Sans compte
    response = client.get(f"/public/parameters/{link['token']}")
    assert response.status_code == 200
    assert "noindex" in response.headers["x-robots-tag"]
    data = response.json()
    assert data["aquarium"]["name"] == aquarium["name"]
    assert "Forum privé" not in response.text  # nom du lien : pour le propriétaire seulement
    assert [p["name"] for p in data["parameters"]] == ["KH"]
    shared = data["parameters"][0]
    assert shared["last_value"] == 8.1 and shared["in_target"] is True
    assert [h["value"] for h in shared["history"]] == [8.1]  # relevé de 40 jours hors période

    assert client.get("/public/parameters/inconnu").status_code == 404

    api.delete(f"/parameter-shares/{link['id']}")
    assert client.get(f"/public/parameters/{link['token']}").status_code == 404


def test_expired_parameters_link(api, client, aquarium):
    link = api.post("/parameter-shares/", {"aquarium_id": aquarium["id"], "history_days": 0, "expires_in_days": None}, code=201)
    assert link["expires_at"] is None
    with SessionLocal() as db:
        row = db.get(ParameterShareLink, link["id"])
        row.expires_at = datetime.now() - timedelta(minutes=1)
        db.commit()
    assert client.get(f"/public/parameters/{link['token']}").status_code == 404
    assert api.get("/parameter-shares/", params={"aquarium_id": aquarium["id"]})[0]["state"] == "expired"


def test_parameters_link_pinned_only(api, client, aquarium):
    for name, pinned in (("KH", True), ("Mg", False)):
        param = api.post("/water-parameters/", {"aquarium_id": aquarium["id"], "name": name, "pinned": pinned}, code=201)
        api.post(f"/water-parameters/{param['id']}/readings", {"value": 8}, code=201)
    link = api.post("/parameter-shares/", {"aquarium_id": aquarium["id"], "history_days": 0, "pinned_only": True}, code=201)
    data = client.get(f"/public/parameters/{link['token']}").json()
    assert [p["name"] for p in data["parameters"]] == ["KH"]
    assert data["parameters"][0]["history"] == []
