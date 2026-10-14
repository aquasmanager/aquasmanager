def _invertebrate(api, aquarium, name):
    return api.post("/invertebrates/", {"aquarium_id": aquarium["id"], "name": name, "date_acquisition": "2026-01-01",
                                        "scientific_name": "Lysmata amboinensis", "family": "Lysmatidae",
                                        "origin": "Elevage"}, code=201)


def test_invertebrates_crud_and_filter(api, aquarium, uid):
    other = api.post("/aquariums/", {"name": f"Autre bac {uid}", "volume": 100, "water_type": "sea",
                                     "biotope": "récifal", "date_creation": "2026-01-01"}, code=201)
    shrimp = _invertebrate(api, aquarium, f"Crevette {uid}")
    _invertebrate(api, other, f"Escargot {uid}")

    listed = api.get("/invertebrates/", params={"aquarium_id": aquarium["id"]})
    assert [i["id"] for i in listed["invertebrates"]] == [shrimp["id"]] and listed["total"] == 1

    assert api.patch(f"/invertebrates/{shrimp['id']}", {"origin": "Sauvage"})["origin"] == "Sauvage"
    assert api.get("/photos/invertebrates/" + str(shrimp["id"])) == []

    cards = {c["id"]: c for c in api.get("/overview/")["aquariums"]}
    assert cards[aquarium["id"]]["livestock"] == 1

    api.delete(f"/invertebrates/{shrimp['id']}")
    api.get(f"/invertebrates/{shrimp['id']}", code=404)


def test_legacy_other_alives_route_removed(api, aquarium, uid):
    shrimp = _invertebrate(api, aquarium, f"Ancienne {uid}")
    api.get("/other_alives/", params={"aquarium_id": aquarium["id"]}, code=404)
    assert [i["id"] for i in api.get("/invertebrates/", params={"aquarium_id": aquarium["id"]})["invertebrates"]] == [shrimp["id"]]


def test_living_lists_filtered_by_aquarium(api, aquarium, uid):
    fish = api.post("/fishes/", {"aquarium_id": aquarium["id"], "name": f"Clown {uid}", "date_acquisition": "2026-01-01",
                                 "scientific_name": "Amphiprion ocellaris", "family": "Pomacentridae",
                                 "origin": "Elevage", "max_height": 8, "min_volume": 100, "reef_safe": True}, code=201)
    fishes = api.get("/fishes/", params={"aquarium_id": aquarium["id"]})["fishes"]
    assert [f["id"] for f in fishes] == [fish["id"]]
    assert api.get("/corals/", params={"aquarium_id": aquarium["id"]})["corals"] == []
    assert api.get("/plants/", params={"aquarium_id": aquarium["id"]})["plants"] == []
