def test_inventory_opened_on(api, aquarium, uid):
    item = api.post("/inventory-items/", {"aquarium_id": aquarium["id"], "name": f"Test KH {uid}", "unit": "tests",
                                          "quantity": 50, "opened_on": "2026-09-01"}, code=201)
    assert item["opened_on"] == "2026-09-01"
    assert api.patch(f"/inventory-items/{item['id']}", {"opened_on": "2026-09-29"})["opened_on"] == "2026-09-29"
    assert api.patch(f"/inventory-items/{item['id']}", {"opened_on": None})["opened_on"] is None
