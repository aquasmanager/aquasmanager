import httpx

from middleware.database import SessionLocal
from models.catalog_sync import CatalogSyncState
from models.species import CoralSpecies
from services import catalog_sync
from services.catalog_sync import apply_catalog, mark_customized_builtins, sync_catalog


def _coral(name, **extra):
    return {"common_name": name, "scientific_name": "Euphyllia sp.", "type": "LPS", "light_min": 4, "light_max": 8,
            "brewing_min": 2, "brewing_max": 5, "aggressiveness_level": 5, "resistance_level": 6, "location_level": 3,
            **extra}


def _get(db, name):
    return db.query(CoralSpecies).filter(CoralSpecies.common_name == name).one_or_none()


def test_apply_adds_updates_and_spares_local_changes(api, uid):
    db = SessionLocal()
    try:
        apply_catalog(db, {"format": 1, "corals": [_coral(f"Ajout {uid}"), _coral(f"Perso {uid}"), _coral(f"Modif {uid}")]})
        added = _get(db, f"Ajout {uid}")
        assert added.builtin and not added.customized and added.light_max == 8
        added_id = added.id

        # Fiche modifiée dans l'appli (PATCH) : marquée, plus jamais écrasée
        modified = _get(db, f"Modif {uid}")
        api.patch(f"/species/corals/{modified.id}", {"notes": "Ma remarque"})
        db.expire_all()
        assert _get(db, f"Modif {uid}").customized
        # Fiche créée par l'utilisateur (sa proposition, acceptée puis corrigée par l'éditeur)
        personal = _get(db, f"Perso {uid}")
        personal.builtin = False
        personal.type = "SPS"
        personal.notes = "Achetée en bourse"
        db.commit()

        result = apply_catalog(db, {"format": 1, "corals": [
            _coral(f"ajout  {uid}", light_max=10),  # casse et espaces ignorés
            _coral(f"Perso {uid}", light_max=10),
            _coral(f"Modif {uid}", light_max=10),
            _coral(f"Nouveau {uid}"),
            {"common_name": f"Invalide {uid}", "scientific_name": "X"},  # champs manquants
        ]})
        db.expire_all()
        # Même fiche (nom retrouvé sans casse ni espaces), valeurs et nom du catalogue appliqués
        refreshed = db.get(CoralSpecies, added_id)
        assert refreshed.light_max == 10 and refreshed.common_name == f"ajout  {uid}"
        # ... rattachée au catalogue : ses valeurs, notes locales gardées (le catalogue n'en a pas)
        personal = _get(db, f"Perso {uid}")
        assert personal.builtin and not personal.customized
        assert personal.light_max == 10 and personal.type.value == "LPS" and personal.notes == "Achetée en bourse"
        assert _get(db, f"Modif {uid}").light_max == 8 and _get(db, f"Modif {uid}").notes == "Ma remarque"
        assert _get(db, f"Nouveau {uid}").builtin
        assert result.updated == [f"ajout  {uid}"] and result.added == [f"Nouveau {uid}"]
        assert result.adopted == [f"Perso {uid}"]
        assert result.invalid == [f"corals:Invalide {uid}"]
    finally:
        db.close()


def test_rename_follows_previous_names(uid):
    db = SessionLocal()
    try:
        apply_catalog(db, {"format": 1, "corals": [_coral(f"Ancien {uid}")]})
        old_id = _get(db, f"Ancien {uid}").id
        apply_catalog(db, {"format": 1, "corals": [_coral(f"Nouveau nom {uid}", previous_names=[f"Ancien {uid}"])]})
        db.expire_all()
        assert _get(db, f"Ancien {uid}") is None
        assert _get(db, f"Nouveau nom {uid}").id == old_id
    finally:
        db.close()


def test_sync_uses_etag_and_keeps_errors(monkeypatch, uid):
    monkeypatch.setattr(catalog_sync.settings, "hub_url", "https://hub.test")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers.get("If-None-Match"))
        if request.headers.get("If-None-Match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, json={"format": 1, "corals": [_coral(f"Hub {uid}")]}, headers={"ETag": '"v1"'})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    db = SessionLocal()
    try:
        db.query(CatalogSyncState).delete()
        db.commit()
        state = sync_catalog(db, client=client)
        assert state.etag == '"v1"' and state.error is None and "1 ajoutée" in state.result
        assert _get(db, f"Hub {uid}") is not None
        sync_catalog(db, client=client)  # inchangé : 304
        assert calls == [None, '"v1"']

        failing = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
        state = sync_catalog(db, client=failing)
        assert state.error and state.etag == '"v1"'  # erreur notée, catalogue appliqué gardé
    finally:
        db.close()


def test_mark_customized_builtins_detects_local_edits():
    db = SessionLocal()
    try:
        duncan = _get(db, "Duncan")
        duncan.customized = False
        duncan.notes = "Modifiée avant la synchronisation"
        acro = _get(db, "Acropora tenuis")
        acro.customized = False
        db.commit()
        mark_customized_builtins(db)
        db.expire_all()
        assert _get(db, "Duncan").customized
        assert not _get(db, "Acropora tenuis").customized
    finally:
        db.close()


def test_catalog_status_routes(api):
    status = api.get("/species/catalog/status")
    assert status["enabled"] is False  # hub_url « none » en test
    api.post("/species/catalog/sync", {}, code=409)
