from tests.test_invertebrates import _invertebrate


def test_livestock_quantity_and_overview(api, aquarium, uid):
    fish = api.post("/fishes/", {"aquarium_id": aquarium["id"], "name": f"Chromis {uid}", "date_acquisition": "2026-01-01",
                                 "scientific_name": "Chromis viridis", "family": "Pomacentridae", "origin": "Elevage",
                                 "max_height": 8, "min_volume": 200, "reef_safe": True, "quantity": 5}, code=201)
    assert fish["quantity"] == 5
    shrimp = _invertebrate(api, aquarium, f"Crevette {uid}")
    assert shrimp["quantity"] == 1  # par défaut
    updated = api.patch(f"/fishes/{fish['id']}", {"quantity": 4})
    assert updated["quantity"] == 4
    api.patch(f"/fishes/{fish['id']}", {"quantity": 0}, code=422)
    overview = api.get("/overview/")
    card = next(a for a in overview["aquariums"] if a["id"] == aquarium["id"])
    assert card["livestock"] == 5  # 4 poissons + 1 crevette
