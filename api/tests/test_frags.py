from datetime import date

from tests.helpers import make_coral as _coral


def test_frags_from_coral(api, aquarium, uid):
    coral = _coral(api, aquarium, uid)
    frag = api.post("/frags/", {"mother_coral_id": coral["id"], "quantity": 3, "price": 15}, code=201)
    assert frag["reference"].startswith(f"B-{date.today().year}-") and frag["quantity"] == 3
    assert (frag["cites"], frag["origin"], frag["scientific_name"], frag["coral_type"]) == (
        "FR2026ABC123", "Mariculture Indonésie", "Acropora millepora", "SPS")
    assert frag["mother_name"] == coral["name"] and frag["aquarium_id"] == aquarium["id"] and frag["status"] == "available"

    # Surcharge des infos reprises du pied mère
    other = api.post("/frags/", {"mother_coral_id": coral["id"], "origin": "Bouturage maison"}, code=201)
    assert other["origin"] == "Bouturage maison" and other["cites"] == "FR2026ABC123"

    # Suppression du pied mère : la bouture garde ses informations
    api.delete(f"/corals/{coral['id']}")
    kept = api.get(f"/frags/{frag['id']}")
    assert kept["mother_coral_id"] is None and kept["mother_name"] == coral["name"] and kept["cites"] == "FR2026ABC123"


def test_frag_labels_pdf(api, client, aquarium, uid):
    frag = api.post("/frags/", {"name": f"Étiquette {uid}", "aquarium_id": aquarium["id"], "quantity": 3, "price": 9}, code=201)
    token = client.post("/login", data={"username": "admin", "password": "ChangeMe123!"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    ok = client.get("/frags/labels.pdf", params={"base_url": "https://aquas.example.org", "ids": str(frag["id"]), "per_unit": True},
                    headers=headers)
    assert ok.status_code == 200 and ok.content.startswith(b"%PDF")
    assert client.get("/frags/labels.pdf", params={"base_url": "javascript:alert(1)"}, headers=headers).status_code == 422
