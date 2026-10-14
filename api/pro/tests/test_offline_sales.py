import uuid

from pro.tests.helpers import set_seller_profile as _seller
from tests.helpers import PNG


def test_offline_sale_synced(api, client, admin_headers, aquarium, uid):
    _seller(api)
    frag = api.post("/frags/", {"name": f"Hors ligne {uid}", "aquarium_id": aquarium["id"], "quantity": 2, "price": 10}, code=201)
    sale = {
        "items": [{"frag_id": frag["id"], "quantity": 3}],  # une de plus que le stock connu
        "location_name": f"Bourse de Morlaix {uid}",
        "buyer": {"first_name": "Lou", "last_name": "Hors", "address": "3 rue", "postal_code": "29600", "city": "Morlaix"},
        "signature": PNG,
        "signed_at": "2026-10-03T15:42:00",
        "accept": True,
    }
    headers = {**admin_headers, "Idempotency-Key": str(uuid.uuid4())}
    created = client.post("/transfer-certificates/offline", json=sale, headers=headers)
    assert created.status_code == 201, created.text
    cert = created.json()
    assert cert["status"] == "signed" and cert["signed_at"].startswith("2026-10-03T15:42") and cert["total_quantity"] == 3
    assert cert["total_price"] == 30.0 and "payment_method" not in cert
    # Synchronisation rejouée : pas de deuxième certificat
    again = client.post("/transfer-certificates/offline", json=sale, headers=headers)
    assert again.json()["id"] == cert["id"]
    lot = api.get(f"/frags/{frag['id']}")
    assert (lot["quantity"], lot["transferred_quantity"], lot["status"]) == (0, 3, "transferred")
    assert any("hors connexion" in (m["note"] or "") for m in api.get(f"/frags/{frag['id']}/movements"))
