from tests.helpers import make_coral as _coral


def test_frag_inherits_coral_provenance(api, aquarium, uid):
    coral = _coral(api, aquarium, uid)
    coral = api.patch(f"/corals/{coral['id']}", {"acquired_from": "Récif at Home"})
    frag = api.post("/frags/", {"mother_coral_id": coral["id"], "quantity": 3}, code=201)
    assert frag["acquired_from"] == "Récif at Home" and frag["origin"] == "Mariculture Indonésie"


def test_frags_move_between_aquariums_is_traced(api, aquarium, uid):
    other = api.post("/aquariums/", {"name": f"Bac boutures {uid}", "volume": 60, "water_type": "sea",
                                     "biotope": "récifal", "date_creation": "2026-01-01"}, code=201)
    coral = _coral(api, aquarium, uid)
    a = api.post("/frags/", {"mother_coral_id": coral["id"], "quantity": 2}, code=201)
    b = api.post("/frags/", {"mother_coral_id": coral["id"], "quantity": 1}, code=201)
    assert a["aquarium_id"] == aquarium["id"]  # par défaut : le bac du pied mère

    moved = api.post("/frags/move", {"frag_ids": [a["id"], b["id"]], "aquarium_id": other["id"]})
    assert {f["aquarium_id"] for f in moved} == {other["id"]}
    history = api.get(f"/frags/{a['id']}/movements")
    assert history[0]["reason"] == "moved" and history[0]["delta"] == 0
    assert history[0]["note"] == f"{aquarium['name']} → {other['name']}"
    # Déplacement unitaire (modification du lot) : tracé aussi
    api.patch(f"/frags/{b['id']}", {"aquarium_id": aquarium["id"]})
    assert api.get(f"/frags/{b['id']}/movements")[0]["reason"] == "moved"
    api.post("/frags/move", {"frag_ids": [999999], "aquarium_id": other["id"]}, code=404)
