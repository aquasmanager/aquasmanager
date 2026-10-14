def test_water_change_records_salt_task_and_journal(api, aquarium, uid):
    salt = api.post("/inventory-items/", {"aquarium_id": aquarium["id"], "name": f"Sel {uid}", "unit": "kg",
                                          "quantity": 20}, code=201)
    task = api.post("/maintenance-tasks/", {"aquarium_id": aquarium["id"], "title": f"Changement d'eau {uid}",
                                            "recurrence": "weekly", "next_due_at": "2026-10-01T09:00:00"}, code=201)
    change = api.post("/water-changes/", {"aquarium_id": aquarium["id"], "volume_l": 20, "salt_item_id": salt["id"],
                                          "salt_amount": 0.7, "complete_task_id": task["id"],
                                          "performed_at": "2026-10-05T10:00:00Z"}, code=201)
    assert change["salt_item_name"] == f"Sel {uid}" and change["percent"] is not None
    assert abs(api.get(f"/inventory-items/{salt['id']}/movements")[0]["delta"] + 0.7) < 1e-9
    items = {i["id"]: i for i in api.get("/inventory-items/", params={"aquarium_id": aquarium["id"]})}
    assert items[salt["id"]]["quantity"] == 19.3  # arrondi (pas 19.299999999999997)
    tasks = {t["id"]: t for t in api.get("/maintenance-tasks/", params={"aquarium_id": aquarium["id"]})}
    assert tasks[task["id"]]["next_due_at"].startswith("2026-10-12")  # hebdomadaire : une semaine après
    notes = api.get("/journal/", params={"aquarium_id": aquarium["id"]})
    assert any(n["category"] == "water_change" and "20 L" in n["text"] and f"Sel {uid}" in n["text"] for n in notes)

    api.delete(f"/water-changes/{change['id']}")
    items = {i["id"]: i for i in api.get("/inventory-items/", params={"aquarium_id": aquarium["id"]})}
    assert abs(items[salt["id"]]["quantity"] - 20) < 1e-9  # sel recrédité
    assert not any(n["category"] == "water_change" and f"Sel {uid}" in n["text"]
                   for n in api.get("/journal/", params={"aquarium_id": aquarium["id"]}))
    assert api.get("/water-changes/", params={"aquarium_id": aquarium["id"]}) == []
    api.post("/water-changes/", {"aquarium_id": aquarium["id"], "volume_l": 20, "salt_item_id": salt["id"]}, code=422)


def test_dosing_products_and_apply(api, aquarium, uid):
    assert any(p["parameter"] == "KH" for p in api.get("/dosing/presets"))
    stock = api.post("/inventory-items/", {"aquarium_id": aquarium["id"], "name": f"KH+ {uid}", "unit": "mL",
                                           "quantity": 500}, code=201)
    product = api.post("/dosing/products", {"name": f"KH+ {uid}", "parameter": "KH", "dose_amount": 10,
                                            "dose_unit": "mL", "raises": 1, "per_volume_l": 100,
                                            "inventory_item_id": stock["id"]}, code=201)
    result = api.post("/dosing/apply", {"aquarium_id": aquarium["id"], "product_id": product["id"], "total": 60,
                                        "days": 3, "current": 7.2, "target": 8.5, "create_tasks": True,
                                        "consume_stock": True})
    assert result["tasks"] == 3 and result["per_day"] == 20 and result["stock_left"] == 440
    titles = [t["title"] for t in api.get("/maintenance-tasks/", params={"aquarium_id": aquarium["id"]})]
    assert f"Doser 20 mL de KH+ {uid} (2/3)" in titles
    assert any("7,2 → 8,5" in n["text"] for n in api.get("/journal/", params={"aquarium_id": aquarium["id"]}))
    api.delete(f"/dosing/products/{product['id']}")
    assert product["id"] not in [p["id"] for p in api.get("/dosing/products")]


def test_trace_element_product_by_concentration(api, aquarium, uid):
    presets = {p["parameter"]: p for p in api.get("/dosing/presets")}
    assert presets["Mn"]["concentration"] == 27.76 and presets["Mn"]["raises"] == 2.776  # 1 g / 100 L → mg/l
    product = api.post("/dosing/products", {"name": f"Manganèse {uid}", "parameter": "Mn", "dose_amount": 1,
                                            "dose_unit": "mL", "raises": 5, "per_volume_l": 100,
                                            "concentration": 0.5, "concentration_unit": "mg/mL"}, code=201)
    assert product["concentration"] == 0.5 and product["concentration_unit"] == "mg/mL"
    api.post("/dosing/products", {"name": "x", "parameter": "Mn", "dose_amount": 1, "dose_unit": "mL",
                                  "raises": 5, "per_volume_l": 100, "concentration": 1,
                                  "concentration_unit": "ppm"}, code=422)


def test_stock_quantity_rounded_after_decimal_movements(api, aquarium, uid):
    salt = api.post("/inventory-items/", {"aquarium_id": aquarium["id"], "name": f"Sel arrondi {uid}", "unit": "kg",
                                          "quantity": 25}, code=201)
    for _ in range(8):
        item = api.post(f"/inventory-items/{salt['id']}/movements", {"delta": -1.6}, code=201)
    assert item["quantity"] == 12.2


def test_dosing_brand_and_readable_quantity(api, aquarium, uid):
    product = api.post("/dosing/products", {"name": f"Iode {uid}", "brand": "  Fauna Marin ", "parameter": "I",
                                            "dose_amount": 1, "dose_unit": "mL", "raises": 0.5,
                                            "per_volume_l": 100}, code=201)
    assert product["brand"] == "Fauna Marin"
    assert api.put(f"/dosing/products/{product['id']}", {**product, "brand": " "})["brand"] is None
    api.put(f"/dosing/products/{product['id']}", {**product, "brand": "Fauna Marin"})
    api.post("/dosing/apply", {"aquarium_id": aquarium["id"], "product_id": product["id"], "total": 1250,
                               "days": 1, "create_tasks": True})
    titles = [t["title"] for t in api.get("/maintenance-tasks/", params={"aquarium_id": aquarium["id"]})]
    assert f"Doser 1,25 L de Iode {uid} (Fauna Marin)" in titles
