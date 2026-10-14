def test_batch_readings(api, aquarium):
    kh = api.post("/water-parameters/", {"aquarium_id": aquarium["id"], "name": "KH", "pinned": True}, code=201)
    ca = api.post("/water-parameters/", {"aquarium_id": aquarium["id"], "name": "Ca", "pinned": True}, code=201)
    readings = api.post(
        "/water-parameters/readings/batch",
        {"aquarium_id": aquarium["id"], "timestamp": "2026-09-20T12:00:00", "note": "série du dimanche",
         "values": [{"water_parameter_id": kh["id"], "value": 8.2}, {"water_parameter_id": ca["id"], "value": 430}]},
        code=201,
    )
    assert {r["water_parameter_id"] for r in readings} == {kh["id"], ca["id"]}
    assert all(r["note"] == "série du dimanche" for r in readings)
    params = {p["id"]: p for p in api.get("/water-parameters/", params={"aquarium_id": aquarium["id"]})}
    assert params[kh["id"]]["last_value"] == 8.2 and params[ca["id"]]["last_value"] == 430


def test_batch_readings_refuses_foreign_or_duplicate_parameters(api, aquarium, uid):
    other = api.post("/aquariums/", {"name": f"Autre bac {uid}", "volume": 100, "water_type": "pure", "biotope": "amazonien",
                                     "date_creation": "2026-01-01"}, code=201)
    foreign = api.post("/water-parameters/", {"aquarium_id": other["id"], "name": "GH"}, code=201)
    mine = api.post("/water-parameters/", {"aquarium_id": aquarium["id"], "name": "NO3"}, code=201)
    api.post("/water-parameters/readings/batch",
             {"aquarium_id": aquarium["id"], "values": [{"water_parameter_id": foreign["id"], "value": 5}]}, code=400)
    api.post("/water-parameters/readings/batch",
             {"aquarium_id": aquarium["id"], "values": [{"water_parameter_id": mine["id"], "value": 5},
                                                        {"water_parameter_id": mine["id"], "value": 6}]}, code=400)
