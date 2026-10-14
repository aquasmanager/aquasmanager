import io

from pro.tests.helpers import set_seller_profile as _seller
from tests.helpers import PNG, make_coral as _coral, seller_headers as _seller_headers


def test_seller_manages_frags_only(api, client, aquarium, controller, uid):
    _seller(api)
    coral = _coral(api, aquarium, uid)
    h = _seller_headers(api, client, uid)

    # Lecture de tout
    assert client.get("/aquariums/", headers=h).status_code == 200
    assert client.get(f"/photos/corals/{coral['id']}", headers=h).status_code == 200
    assert client.get("/equipments/", headers=h).status_code == 200

    # Boutures et cessions : oui
    frag = client.post("/frags/", json={"mother_coral_id": coral["id"], "quantity": 5}, headers=h)
    assert frag.status_code == 201, frag.text
    frag = frag.json()
    assert client.patch(f"/frags/{frag['id']}", json={"quantity": 4}, headers=h).json()["quantity"] == 4
    photo = client.post(f"/photos/frags/{frag['id']}", files={"file": ("f.png", io.BytesIO(b"x"), "image/png")}, headers=h)
    assert photo.status_code == 200
    cert = client.post("/transfer-certificates/", json={"items": [{"frag_id": frag["id"], "quantity": 2}]}, headers=h)
    assert cert.status_code == 201
    assert client.get(f"/transfer-certificates/{cert.json()['id']}/pdf", headers=h).status_code == 200
    assert client.delete(f"/transfer-certificates/{cert.json()['id']}", headers=h).status_code == 204
    assert client.delete(f"/photos/frags/{frag['id']}/{photo.json()['id']}", headers=h).status_code == 200
    other = client.post("/frags/", json={"name": f"Lot à supprimer {uid}", "aquarium_id": aquarium["id"]}, headers=h).json()
    assert client.delete(f"/frags/{other['id']}", headers=h).status_code == 204

    # Tout le reste : non
    forbidden = [
        client.post("/corals/", json={}, headers=h),
        client.delete(f"/corals/{coral['id']}", headers=h),
        client.patch(f"/aquariums/{aquarium['id']}", json={"name": "piraté"}, headers=h),
        client.post(f"/photos/corals/{coral['id']}", files={"file": ("c.png", io.BytesIO(b"x"), "image/png")}, headers=h),
        client.post(f"/controllers/{controller['id']}/flash", headers=h),
        client.put("/seller-profile/", json={"first_name": "x", "signature": PNG}, headers=h),
        client.get("/users/", headers=h),
    ]
    assert [r.status_code for r in forbidden] == [403] * len(forbidden)
