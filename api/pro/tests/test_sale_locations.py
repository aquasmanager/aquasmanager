from pro.tests.helpers import set_seller_profile as _seller


def _frag(api, aquarium, name, quantity=5, price=10):
    return api.post("/frags/", {"name": name, "aquarium_id": aquarium["id"], "quantity": quantity, "price": price}, code=201)


def test_certificates_by_sale_location(api, aquarium, uid):
    _seller(api)
    frag = _frag(api, aquarium, f"Zoa {uid}")
    brest = f"Bourse de Brest {uid}"

    # Lieu créé à la volée, puis retrouvé malgré la casse et les espaces
    first = api.post("/transfer-certificates/", {"items": [{"frag_id": frag["id"], "quantity": 2}], "location_name": brest}, code=201)
    second = api.post("/transfer-certificates/", {
        "items": [{"frag_id": frag["id"], "quantity": 1}], "location_name": f"  bourse DE brest   {uid} "}, code=201)
    assert first["location_id"] == second["location_id"] and second["location_name"] == brest
    home = api.post("/transfer-certificates/", {"items": [{"frag_id": frag["id"], "quantity": 1}]}, code=201)
    assert home["location_id"] is None

    location_id = first["location_id"]
    listed = api.get("/transfer-certificates/", params={"location_id": location_id})
    assert {c["id"] for c in listed} == {first["id"], second["id"]}
    assert home["id"] in {c["id"] for c in api.get("/transfer-certificates/", params={"location_id": 0})}

    stats = next(loc for loc in api.get("/sale-locations/") if loc["id"] == location_id)
    assert (stats["certificate_count"], stats["total_quantity"], stats["total_price"]) == (2, 3, 30.0)

    # Lieu ajouté après coup, puis figé une fois le certificat signé et le lieu renseigné
    updated = api.patch(f"/transfer-certificates/{home['id']}", {"location_id": location_id})
    assert updated["location_name"] == brest

    # Renommage (correction de faute), suppression refusée tant qu'il sert
    api.patch(f"/sale-locations/{location_id}", {"name": f"Bourse de Brest {uid} (Penfeld)"})
    assert api.get(f"/transfer-certificates/{first['id']}")["location_name"].endswith("(Penfeld)")
    api.delete(f"/sale-locations/{location_id}", code=409)
    unused = api.post("/sale-locations/", {"name": f"Bourse de Rennes {uid}"}, code=201)
    api.post("/sale-locations/", {"name": f"bourse de rennes {uid}"}, code=409)
    api.delete(f"/sale-locations/{unused['id']}")


def test_signed_certificate_location_locked(api, client, aquarium, uid):
    from tests.helpers import PNG

    _seller(api)
    frag = _frag(api, aquarium, f"Palys {uid}")
    cert = api.post("/transfer-certificates/", {"items": [{"frag_id": frag["id"]}], "location_name": f"Domicile {uid}"}, code=201)
    buyer = {"first_name": "A", "last_name": "B", "address": "1 rue", "postal_code": "29200", "city": "Brest"}
    client.post(f"/public/certificates/{cert['sign_token']}/sign", json={"buyer": buyer, "signature": PNG, "accept": True})
    assert client.get(f"/public/certificates/{cert['sign_token']}").json()["location_name"] == f"Domicile {uid}"
    api.patch(f"/transfer-certificates/{cert['id']}", {"location_name": "Ailleurs"}, code=409)


def test_report_and_exports(api, client, aquarium, uid):
    from datetime import date

    from tests.helpers import PNG

    _seller(api)
    frag = _frag(api, aquarium, f"Acro report {uid}", quantity=10, price=12)
    where = f"Bourse de Quimper {uid}"
    certs = [
        api.post("/transfer-certificates/", {"items": [{"frag_id": frag["id"], "quantity": q}], "location_name": where}, code=201)
        for q in (2, 1, 1)
    ]
    buyer = {"first_name": "Camille", "last_name": f"Report{uid}", "address": "1 quai", "postal_code": "29000", "city": "Quimper"}
    for cert in certs[:2]:
        client.post(f"/public/certificates/{cert['sign_token']}/sign", json={"buyer": buyer, "signature": PNG, "accept": True})


    report = api.get("/transfer-certificates/report", params={"location_id": certs[0]["location_id"]})
    assert (report["certificate_count"], report["pending_count"], report["quantity"], report["total"]) == (2, 1, 3, 36.0)
    assert "by_payment" not in report
    assert report["by_species"][0]["quantity"] == 3 and report["stock_quantity"] >= 6

    csv = client.get("/transfer-certificates/export.csv", params={"location_id": certs[0]["location_id"]},
                     headers={"Authorization": api_auth(client)})
    text = csv.content.decode("utf-8-sig")
    assert csv.status_code == 200 and text.count("\n") == 4 and f"Report{uid}" in text and "Règlement" not in text

    registry = client.get("/transfer-certificates/registry.pdf", params={"year": date.today().year},
                          headers={"Authorization": api_auth(client)})
    assert registry.status_code == 200 and registry.content.startswith(b"%PDF")


def api_auth(client):
    token = client.post("/login", data={"username": "admin", "password": "ChangeMe123!"}).json()["access_token"]
    return f"Bearer {token}"
