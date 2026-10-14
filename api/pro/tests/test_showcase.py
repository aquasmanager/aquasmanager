from pro.routes import showcase as showcase_routes
from services import notify
from pro.tests.helpers import set_seller_profile as _seller


def test_showcase_and_reservations(api, client, aquarium, uid, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "dispatch_alert", lambda subject, message, priority="default": sent.append(message))
    showcase_routes._recent.clear()
    _seller(api)
    shown = api.post("/frags/", {"name": f"Vitrine {uid}", "aquarium_id": aquarium["id"], "quantity": 4, "price": 15}, code=201)
    hidden = api.post("/frags/", {"name": f"Cachée {uid}", "aquarium_id": aquarium["id"], "quantity": 2}, code=201)
    api.patch(f"/frags/{hidden['id']}", {"showcase_hidden": True})

    api.put("/showcase/settings", {"enabled": False})
    assert client.get("/public/showcase/").status_code == 404
    api.put("/showcase/settings", {"enabled": True, "title": "Boutures de Manu", "show_prices": False})

    public = client.get("/public/showcase/").json()
    names = {lot["name"]: lot for lot in public["lots"]}
    assert public["title"] == "Boutures de Manu" and f"Vitrine {uid}" in names and f"Cachée {uid}" not in names
    assert names[f"Vitrine {uid}"]["price"] is None  # prix masqués

    base = {"name": "Alex", "contact": "alex@example.org", "message": "Pour la bourse de Brest"}
    too_many = client.post("/public/showcase/reservations", json={**base, "items": [{"frag_id": shown["id"], "quantity": 5}]})
    assert too_many.status_code == 409
    robot = client.post("/public/showcase/reservations", json={**base, "website": "spam", "items": [{"frag_id": shown["id"], "quantity": 1}]})
    assert robot.status_code == 422
    ok = client.post("/public/showcase/reservations", json={**base, "items": [{"frag_id": shown["id"], "quantity": 3}]})
    assert ok.status_code == 201 and sent and "3 × Vitrine" in sent[-1]

    reservation = next(r for r in api.get("/showcase/reservations") if r["items"][0]["frag_id"] == shown["id"])
    cert = api.post(f"/showcase/reservations/{reservation['id']}/confirm", {"location_name": f"Bourse de Brest {uid}"})
    assert cert["status"] == "draft" and cert["total_quantity"] == 3 and "Alex" in cert["notes"]
    assert api.get(f"/frags/{shown['id']}")["quantity"] == 1
    api.post(f"/showcase/reservations/{reservation['id']}/confirm", {}, code=409)

    # Anti-abus : limite par heure
    for _ in range(showcase_routes.RESERVATIONS_PER_HOUR):
        client.post("/public/showcase/reservations", json={**base, "items": [{"frag_id": shown["id"], "quantity": 1}]})
    assert client.post("/public/showcase/reservations", json={**base, "items": [{"frag_id": shown["id"], "quantity": 1}]}).status_code == 429


def test_showcase_share_links(api, client, aquarium, uid, monkeypatch):
    from datetime import timedelta

    from pro.models.showcase import local_today
    from pro.schemas.showcase import ShowcaseSettingsBase
    from tests.helpers import PNG

    monkeypatch.setattr(notify, "dispatch_alert", lambda subject, message, priority="default": None)
    showcase_routes._recent.clear()
    _seller(api)
    assert ShowcaseSettingsBase().show_prices is False  # prix masqués par défaut
    lot = api.post("/frags/", {"name": f"Lien {uid}", "aquarium_id": aquarium["id"], "quantity": 5, "price": 10}, code=201)
    api.put("/showcase/settings", {"enabled": False, "show_prices": True, "price_label": "Participation"})
    for link in api.get("/showcase/links"):
        api.delete(f"/showcase/links/{link['id']}", code=204)
    assert client.get("/public/showcase/").status_code == 404

    today = local_today()
    bourse = api.post("/showcase/links", {
        "label": f"Bourse de Rennes {uid}", "location_name": f"Bourse de Rennes {uid}",
        "starts_on": str(today), "ends_on": str(today + timedelta(days=1)),
    }, code=201)
    assert bourse["state"] == "active" and len(bourse["token"]) >= 20 and bourse["location_name"] == f"Bourse de Rennes {uid}"

    res = client.get("/public/showcase/", params={"t": bourse["token"]})
    assert res.status_code == 200 and res.headers["X-Robots-Tag"].startswith("noindex")
    body = res.json()
    assert body["link_label"] == f"Bourse de Rennes {uid}" and body["price_label"] == "Participation"
    assert any(item["id"] == lot["id"] and item["price"] == 10 for item in body["lots"])
    assert api.get("/showcase/links")[0]["view_count"] == 1
    assert client.get("/public/showcase/", params={"t": "inconnu"}).status_code == 404
    # Sans jeton : fermé, sauf lien actif réservé aux étiquettes QR
    assert client.get("/public/showcase/").status_code == 404
    api.patch(f"/showcase/links/{bourse['id']}", {"qr_labels": True})
    assert client.get("/public/showcase/").json()["link_label"] == f"Bourse de Rennes {uid}"

    # Réservation via le lien : le lieu de la bourse est repris sur le certificat
    base = {"name": "Camille", "contact": "camille@example.org"}
    ok = client.post("/public/showcase/reservations", params={"t": bourse["token"]},
                     json={**base, "items": [{"frag_id": lot["id"], "quantity": 2}]})
    assert ok.status_code == 201
    reservation = next(r for r in api.get("/showcase/reservations") if r["link_id"] == bourse["id"])
    assert reservation["link_label"] == f"Bourse de Rennes {uid}" and reservation["link_location_id"] == bourse["location_id"]
    cert = api.post(f"/showcase/reservations/{reservation['id']}/confirm", {})
    assert cert["location_id"] == bourse["location_id"]

    # Dates, révocation
    api.post("/showcase/links", {"label": "Mauvaises dates", "starts_on": str(today), "ends_on": str(today - timedelta(days=1))}, code=400)
    later = api.post("/showcase/links", {"label": "Pour Julien", "starts_on": str(today + timedelta(days=3))}, code=201)
    assert later["state"] == "upcoming" and client.get("/public/showcase/", params={"t": later["token"]}).status_code == 404
    old = api.post("/showcase/links", {"label": "Ancienne bourse", "ends_on": str(today - timedelta(days=1))}, code=201)
    assert old["state"] == "expired" and client.get("/public/showcase/", params={"t": old["token"]}).status_code == 404
    revoked = api.patch(f"/showcase/links/{bourse['id']}", {"revoked": True})
    assert revoked["state"] == "revoked"
    assert client.get("/public/showcase/", params={"t": bourse["token"]}).status_code == 404
    assert client.get("/public/showcase/").status_code == 404
    assert client.post("/public/showcase/reservations", params={"t": bourse["token"]},
                       json={**base, "items": [{"frag_id": lot["id"], "quantity": 1}]}).status_code == 404

    # Bilan annuel : le certificat signé compte pour l'année de la cession
    before = {y["year"]: y for y in api.get("/transfer-certificates/yearly")}
    buyer = {"first_name": "Camille", "last_name": "Récifale", "address": "1 rue du Port", "postal_code": "35000",
             "city": "Rennes", "email": "camille@example.org"}
    assert client.post(f"/public/certificates/{cert['sign_token']}/sign",
                       json={"buyer": buyer, "signature": PNG, "accept": True}).status_code == 200
    after = {y["year"]: y for y in api.get("/transfer-certificates/yearly")}
    year = int(cert["transfer_date"][:4])
    prev = before.get(year, {"certificate_count": 0, "quantity": 0})
    assert after[year]["certificate_count"] == prev["certificate_count"] + 1
    assert after[year]["quantity"] == prev["quantity"] + 2 and after[year]["location_count"] >= 1
