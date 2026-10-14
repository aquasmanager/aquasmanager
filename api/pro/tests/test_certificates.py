from pro.tests.helpers import set_seller_profile as _seller
from tests.helpers import PNG, make_coral as _coral


def test_certificate_sign_flow(api, client, aquarium, uid):
    _seller(api)
    coral = _coral(api, aquarium, uid)
    lot = api.post("/frags/", {"mother_coral_id": coral["id"], "quantity": 5, "price": 20}, code=201)
    single = api.post("/frags/", {"mother_coral_id": coral["id"], "quantity": 1}, code=201)
    cert = api.post("/transfer-certificates/", {
        "items": [{"frag_id": lot["id"], "quantity": 3}, {"frag_id": single["id"], "price": 12.5}],
        "notes": "Remise en main propre",
    }, code=201)
    assert cert["status"] == "draft" and cert["total_price"] == 72.5 and cert["total_quantity"] == 4
    assert [i["quantity"] for i in cert["items"]] == [3, 1]
    reserved = api.get(f"/frags/{lot['id']}")
    assert (reserved["quantity"], reserved["reserved_quantity"], reserved["status"]) == (2, 3, "available")
    assert api.get(f"/frags/{single['id']}")["status"] == "reserved"
    # Plus que le disponible : refusé
    api.post("/transfer-certificates/", {"items": [{"frag_id": lot["id"], "quantity": 3}]}, code=409)

    token = cert["sign_token"]
    public = client.get(f"/public/certificates/{token}")
    assert public.status_code == 200 and "sign_token" not in public.json() and public.json()["seller"]["city"] == "Paris"
    assert client.get(f"/public/certificates/{token}/pdf").status_code == 409

    buyer = {"first_name": "Alex", "last_name": "Acheteur", "address": "2 avenue du Lagon", "postal_code": "69001",
             "city": "Lyon", "email": "alex@example.org"}
    assert client.post(f"/public/certificates/{token}/sign", json={"buyer": buyer, "signature": "", "accept": True}).status_code == 422
    signed = client.post(f"/public/certificates/{token}/sign", json={"buyer": buyer, "signature": PNG, "accept": True})
    assert signed.status_code == 200 and signed.json()["status"] == "signed"
    assert client.post(f"/public/certificates/{token}/sign", json={"buyer": buyer, "signature": PNG, "accept": True}).status_code == 409

    frag = api.get(f"/frags/{lot['id']}")
    assert (frag["quantity"], frag["reserved_quantity"], frag["transferred_quantity"]) == (2, 0, 3)
    assert frag["status"] == "available" and frag["certificate_number"] == cert["number"]
    assert api.get(f"/frags/{single['id']}")["status"] == "transferred"
    # Quantité modifiable à la main ; à 0 sans cession restante = épuisé
    assert api.patch(f"/frags/{lot['id']}", {"quantity": 0})["status"] == "transferred"
    pdf = client.get(f"/public/certificates/{token}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    api.delete(f"/transfer-certificates/{cert['id']}", code=409)

    # Rien de l'acquéreur ni du jeton dans le journal d'activité
    audit = api.get("/audit/", params={"limit": 50})
    entries = audit["items"] if isinstance(audit, dict) else audit
    dump = str(entries)
    assert token not in dump and "Acheteur" not in dump


def test_certificate_draft_delete_releases_frags(api, aquarium, uid):
    _seller(api)
    frag = api.post("/frags/", {"name": f"Zoanthus {uid}", "aquarium_id": aquarium["id"], "quantity": 4}, code=201)
    cert = api.post("/transfer-certificates/", {"items": [{"frag_id": frag["id"], "quantity": 4}]}, code=201)
    assert api.get(f"/frags/{frag['id']}")["status"] == "reserved"
    api.delete(f"/frags/{frag['id']}", code=409)
    api.delete(f"/transfer-certificates/{cert['id']}")
    back = api.get(f"/frags/{frag['id']}")
    assert (back["quantity"], back["status"]) == (4, "available")
    assert api.patch(f"/frags/{frag['id']}", {"quantity": 0})["status"] == "empty"
    assert api.post(f"/transfer-certificates/{cert['id']}/renew-link", code=404) is not None


def test_certificate_requires_seller_profile(api, aquarium, uid):
    api.put("/seller-profile/", {"first_name": "", "last_name": "", "address": "", "postal_code": "", "city": "",
                                 "signature": ""})
    frag = api.post("/frags/", {"name": f"Palythoa {uid}", "aquarium_id": aquarium["id"]}, code=201)
    api.post("/transfer-certificates/", {"items": [{"frag_id": frag["id"]}]}, code=400)


def test_frag_movements_and_survival(api, aquarium, uid):
    _seller(api)
    coral = _coral(api, aquarium, uid)
    lot = api.post("/frags/", {"mother_coral_id": coral["id"], "quantity": 10}, code=201)
    api.patch(f"/frags/{lot['id']}", {"quantity": 8, "quantity_reason": "lost"})
    api.patch(f"/frags/{lot['id']}", {"quantity": 7, "quantity_reason": "lost"})
    api.patch(f"/frags/{lot['id']}", {"quantity": 9, "quantity_reason": "added", "quantity_note": "2 nouvelles"})
    api.post("/transfer-certificates/", {"items": [{"frag_id": lot["id"], "quantity": 4}]}, code=201)

    movements = api.get(f"/frags/{lot['id']}/movements")
    assert [(m["reason"], m["delta"]) for m in reversed(movements)] == [
        ("created", 10), ("lost", -2), ("lost", -1), ("added", 2), ("reserved", -4)]
    # Une « perte » était en fait un don
    gift = next(m for m in movements if m["delta"] == -1)
    assert api.patch(f"/frags/{lot['id']}/movements/{gift['id']}", {"reason": "gift"})["reason"] == "gift"
    reserved = next(m for m in movements if m["reason"] == "reserved")
    api.patch(f"/frags/{lot['id']}/movements/{reserved['id']}", {"reason": "lost"}, code=409)

    row = next(r for r in api.get("/frags/stats", params={"group_by": "mother"}) if r["name"] == coral["name"])
    assert (row["produced"], row["lost"], row["gift"], row["reserved"], row["available"]) == (12, 2, 1, 4, 5)
    assert row["survival_rate"] == round(1 - 2 / 12, 3)
