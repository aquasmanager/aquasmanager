import uuid


def test_idempotent_replay(api, client, admin_headers, aquarium, uid):
    frag = api.post("/frags/", {"name": f"Idem {uid}", "aquarium_id": aquarium["id"], "quantity": 5}, code=201)
    key = str(uuid.uuid4())
    headers = {**admin_headers, "Idempotency-Key": key}
    first = client.patch(f"/frags/{frag['id']}", json={"quantity": 3, "quantity_reason": "lost"}, headers=headers)
    # Rejouée (réponse perdue) : même réponse, action non refaite
    replay = client.patch(f"/frags/{frag['id']}", json={"quantity": 3, "quantity_reason": "lost"}, headers=headers)
    assert first.status_code == replay.status_code == 200 and replay.headers.get("idempotent-replay") == "true"
    assert replay.json() == first.json()
    assert len([m for m in api.get(f"/frags/{frag['id']}/movements") if m["reason"] == "lost"]) == 1
    # Même clé sur une autre requête : refusée
    other = client.patch(f"/frags/{frag['id'] + 100000}", json={"quantity": 1}, headers=headers)
    assert other.status_code == 422


def test_idempotency_key_survives_trailing_slash_redirect(api, client, admin_headers, aquarium, controller, uid):
    """POST /sensors (sans /) est redirigé vers /sensors/ avec la même clé : la création doit aboutir une seule fois."""
    headers = {**admin_headers, "Idempotency-Key": str(uuid.uuid4())}
    payload = {"aquarium_id": aquarium["id"], "controller_id": controller["id"], "type": "sensor",
               "name": f"Sonde {uid}", "pin_id": controller["pins"]["4"], "unit": "temperature"}
    created = client.post("/sensors", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    replay = client.post("/sensors/", json=payload, headers=headers)
    assert replay.status_code == 201 and replay.headers.get("idempotent-replay") == "true"
    assert replay.json()["id"] == created.json()["id"]
