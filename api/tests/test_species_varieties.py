from middleware.database import SessionLocal
from models.species import CoralSpecies
from services.species_catalog import seed_species_catalog


def test_catalog_accepts_varieties_and_refuses_same_common_name(api, uid):
    """Le catalogue est identifié par le nom commun : plusieurs variétés d'une même espèce."""
    base = {"scientific_name": f"Euphyllia {uid}", "type": "LPS", "light_min": 2, "light_max": 5, "brewing_min": 2,
            "brewing_max": 5, "aggressiveness_level": 5, "resistance_level": 7, "location_level": 3}
    first = api.post("/species/corals", {**base, "common_name": f"Marteau {uid}"}, code=201)
    second = api.post("/species/corals", {**base, "common_name": f"Gold {uid}"}, code=201)
    assert first["scientific_name"] == second["scientific_name"]
    # Même nom commun (casse différente) : refusé, à la création comme au renommage
    api.post("/species/corals", {**base, "common_name": f"GOLD {uid}"}, code=409)
    api.patch(f"/species/corals/{first['id']}", {"common_name": f"gold {uid}"}, code=409)


def test_builtin_catalog_adds_varieties_by_common_name():
    db = SessionLocal()
    try:
        seed_species_catalog(db)
        names = {name for (name,) in db.query(CoralSpecies.common_name).filter(
            CoralSpecies.scientific_name == "Euphyllia paraancora")}
        assert {"Euphyllia marteau", "Euphyllia gold"} <= names
        before = db.query(CoralSpecies).count()
        seed_species_catalog(db)  # rien de nouveau au deuxième passage
        assert db.query(CoralSpecies).count() == before
    finally:
        db.close()


def test_coral_light_scale_goes_to_15(api, uid):
    """Lumière des coraux par paliers de 50 PAR : 1 à 15 (750 PAR)."""
    base = {"common_name": f"Lumière {uid}", "scientific_name": f"Lux {uid}", "type": "SPS", "light_min": 12, "light_max": 15,
            "brewing_min": 2, "brewing_max": 5, "aggressiveness_level": 5, "resistance_level": 7, "location_level": 3}
    api.post("/species/corals", base, code=201)
    api.post("/species/corals", {**base, "common_name": f"Trop {uid}", "light_max": 16}, code=422)
    api.post("/species/corals", {**base, "common_name": f"Brassage {uid}", "brewing_max": 15}, code=422)
