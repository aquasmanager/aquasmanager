def test_caretaker_can_only_do_daily_care(api, client, aquarium, controller, uid):
    api.post("/register", {"username": f"gardien{uid}", "password": "Password123!", "role": "caretaker",
                           "must_change_password": False}, code=201)
    token = client.post("/login", data={"username": f"gardien{uid}", "password": "Password123!"}).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    task = api.post("/maintenance-tasks/", {"aquarium_id": aquarium["id"], "title": f"Nourrir {uid}", "recurrence": "daily",
                                            "next_due_at": "2030-01-01T12:00:00"}, code=201)
    param = api.post("/water-parameters/", {"aquarium_id": aquarium["id"], "name": f"KH {uid}", "unit": "dKH"}, code=201)
    item = api.post("/inventory-items/", {"aquarium_id": aquarium["id"], "name": f"Nourriture {uid}", "unit": "g", "quantity": 100}, code=201)

    # Autorisé : tâches, relevés, consommation du stock, lecture
    assert client.post(f"/maintenance-tasks/{task['id']}/complete", json={}, headers=h).status_code == 200
    assert client.post(f"/water-parameters/{param['id']}/readings", json={"value": 7.8}, headers=h).status_code == 201
    batch = client.post("/water-parameters/readings/batch", json={"aquarium_id": aquarium["id"], "values": [
        {"water_parameter_id": param["id"], "value": 7.9}]}, headers=h)
    assert batch.status_code == 201
    assert client.post(f"/inventory-items/{item['id']}/movements", json={"delta": -5}, headers=h).status_code == 201
    assert client.get("/aquariums/", headers=h).status_code == 200

    # Interdit : piloter, modifier, supprimer
    forbidden = [
        client.post(f"/controllers/{controller['id']}/flash", headers=h),
        client.patch(f"/maintenance-tasks/{task['id']}", json={"title": "x"}, headers=h),
        client.delete(f"/maintenance-tasks/{task['id']}", headers=h),
        client.post("/maintenance-tasks/", json={"aquarium_id": aquarium["id"], "title": "Nouvelle"}, headers=h),
        client.patch(f"/aquariums/{aquarium['id']}", json={"name": "x"}, headers=h),
        client.post("/frags/", json={"name": "x", "aquarium_id": aquarium["id"]}, headers=h),
    ]
    assert [r.status_code for r in forbidden] == [403] * len(forbidden)
