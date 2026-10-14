import io
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from middleware.database import SessionLocal
from routes import backup as backup_routes
from services import backup as svc
from services import notify

TZ = ZoneInfo("Europe/Paris")


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """Base copiée, uploads et dossiers de sauvegarde dans un dossier temporaire."""
    db_copy = tmp_path / "base" / "aquarium.db"
    db_copy.parent.mkdir()
    shutil.copyfile(svc._db_path(), db_copy)
    uploads = tmp_path / "uploads"
    for folder, name in (("aquariums/1", "photo.jpg"), ("icp", "1.pdf"), ("purchase_documents/2", "facture.pdf")):
        (uploads / folder).mkdir(parents=True)
        (uploads / folder / name).write_bytes(b"v1")
    external = tmp_path / "nfs"
    external.mkdir()
    monkeypatch.setattr(svc, "_db_path", lambda: db_copy)
    monkeypatch.setattr(svc, "_uploads_dir", lambda: uploads)
    monkeypatch.setattr(svc.engine, "dispose", lambda: None)
    monkeypatch.setattr(backup_routes, "_restart_process", lambda: None)
    monkeypatch.setattr(notify, "dispatch_alert", lambda *a, **k: None)
    with SessionLocal() as db:
        conf = svc.get_backup_settings(db)
        for field, value in dict(enabled=False, frequency="daily", hour=3, weekday=0, keep_count=7, include_photos=True,
                                 include_icp=True, include_documents=True, include_certificates=True,
                                 destination="local", external_path=None, last_run_at=None).items():
            setattr(conf, field, value)
        db.commit()
    return {"uploads": uploads, "external": external, "local": db_copy.parent / "backups"}


def _names(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as zf:
        return set(zf.namelist())


def test_settings_destination_and_parts(api, client, sandbox):
    assert api.get("/backup/settings")["destination"] == "local"
    api.put("/backup/settings", {"destination": "external", "external_path": "/nexiste/pas"}, code=400)
    api.put("/backup/settings", {"destination": "external", "external_path": "relatif"}, code=400)
    assert api.post("/backup/test-destination", {"path": str(sandbox["external"])})["ok"] is True
    conf = api.put("/backup/settings", {"destination": "external", "external_path": str(sandbox["external"]),
                                        "include_certificates": False, "include_documents": False})
    assert conf["external_ok"] is True

    # Sauvegarde manuelle rangée sur le partage, contenu des réglages
    created = api.post("/backup/create", {}, code=201)
    assert created["location"] == "external" and created["label"] == "manual" and created["parts"] == ["photos", "icp"]
    names = _names(sandbox["external"] / created["filename"])
    assert {"aquarium.db", "manifest.json", "uploads/aquariums/1/photo.jpg", "uploads/icp/1.pdf"} <= names
    assert not any(n.startswith("uploads/purchase_documents") for n in names)

    # Contenu choisi pour cette sauvegarde, dans le dossier local
    only_docs = api.post("/backup/create", {"parts": ["documents", "certificates"], "location": "local"}, code=201)
    names = _names(sandbox["local"] / only_docs["filename"])
    assert "uploads/purchase_documents/2/facture.pdf" in names and not any("aquariums" in n for n in names)

    listed = {(b["location"], b["filename"]) for b in api.get("/backup/")}
    assert ("external", created["filename"]) in listed and ("local", only_docs["filename"]) in listed

    # Export : téléchargé, pas rangé dans la liste
    before = len(api.get("/backup/"))
    export = client.post("/backup/export", json={"parts": ["photos"]}, headers=api.headers)
    assert export.status_code == 200 and "aquarium.db" in zipfile.ZipFile(io.BytesIO(export.content)).namelist()
    assert len(api.get("/backup/")) == before

    # Téléchargement et suppression depuis la liste ; pas de chemin dans le nom
    assert client.get(f"/backup/external/{created['filename']}", headers=api.headers).status_code == 200
    assert client.get("/backup/local/..%2Faquarium.db", headers=api.headers).status_code == 404
    api.delete(f"/backup/external/{created['filename']}")
    assert not (sandbox["external"] / created["filename"]).exists()

    # Partage démonté (dossier vide sur le disque local) : fichier témoin absent, refusé
    (sandbox["external"] / svc.DESTINATION_MARKER).unlink()
    assert api.get("/backup/settings")["external_ok"] is False
    api.post("/backup/create", {"location": "external"}, code=400)


def test_import_then_partial_restore(api, client, sandbox):
    # Sauvegarde contenant seulement la base et les rapports ICP
    archive = api.post("/backup/create", {"parts": ["icp"], "location": "local"}, code=201)
    uploads = sandbox["uploads"]
    (uploads / "icp" / "1.pdf").write_bytes(b"v2")
    (uploads / "icp" / "nouveau.pdf").write_bytes(b"v2")
    (uploads / "aquariums" / "1" / "photo.jpg").write_bytes(b"v2")

    restored = client.post(f"/backup/local/{archive['filename']}/restore", headers=api.headers)
    assert restored.status_code == 200 and "rapports icp" in restored.json()["message"]
    assert (uploads / "icp" / "1.pdf").read_bytes() == b"v1" and not (uploads / "icp" / "nouveau.pdf").exists()
    # Les photos n'étaient pas dans l'archive : intactes
    assert (uploads / "aquariums" / "1" / "photo.jpg").read_bytes() == b"v2"
    # Filet de sécurité complet avant restauration
    assert any(b["label"] == "before_restore" for b in api.get("/backup/"))

    # Import : vérifiée, rangée, non restaurée
    data = (sandbox["local"] / archive["filename"]).read_bytes()
    imported = client.post("/backup/import", headers=api.headers, files={"file": ("ma-sauvegarde.zip", data, "application/zip")})
    assert imported.status_code == 201 and imported.json()["label"] == "imported"
    bad = client.post("/backup/import", headers=api.headers, files={"file": ("x.zip", b"pas un zip", "application/zip")})
    assert bad.status_code == 400

    # Ancienne archive (sans manifeste) : base + tout le dossier uploads
    legacy = sandbox["local"] / "aquarium_20250101_120000_manual.zip"
    with zipfile.ZipFile(legacy, "w") as zf:
        zf.write(svc._db_path(), "aquarium.db")
        zf.writestr("uploads/aquariums/1/photo.jpg", b"legacy")
    row = next(b for b in api.get("/backup/") if b["filename"] == legacy.name)
    assert row["legacy"] is True and set(row["parts"]) == {"photos", "icp", "documents"}
    client.post(f"/backup/local/{legacy.name}/restore", headers=api.headers)
    assert (uploads / "aquariums" / "1" / "photo.jpg").read_bytes() == b"legacy"


def test_scheduled_backup_and_retention(sandbox, monkeypatch):
    with SessionLocal() as db:
        conf = svc.get_backup_settings(db)
        conf.enabled, conf.keep_count, conf.include_certificates = True, 2, False
        db.commit()
    day = datetime(2026, 9, 28, 3, 5, tzinfo=TZ)
    assert svc.run_scheduled_backup_if_due(day) is not None  # créneau de 3 h passé
    assert svc.run_scheduled_backup_if_due(day.replace(minute=30)) is None  # déjà fait
    assert svc.run_scheduled_backup_if_due(day.replace(day=29, hour=2)) is None  # avant le créneau
    for d in (29, 30):
        monkeypatch.setattr(svc, "_archive_name", lambda label, d=d: f"aquarium_202609{d}_030500_{label}_abcdef.zip")
        assert svc.run_scheduled_backup_if_due(day.replace(day=d)) is not None
    autos = [f for f in sandbox["local"].glob("*_auto_*.zip")]
    assert len(autos) == 2  # conservation : les 2 plus récentes

    # Partage externe indisponible : sauvegarde de secours en local, état « error »
    with SessionLocal() as db:
        conf = svc.get_backup_settings(db)
        conf.destination, conf.external_path = "external", str(sandbox["external"] / "absent")
        db.commit()
    path = svc.run_scheduled_backup_if_due(datetime(2026, 10, 1, 4, 0, tzinfo=TZ))
    assert path is not None and path.parent == sandbox["local"]
    with SessionLocal() as db:
        conf = svc.get_backup_settings(db)
        assert conf.last_status == "error" and "local" in conf.last_message

    # Hebdomadaire : lundi 3 h
    with SessionLocal() as db:
        conf = svc.get_backup_settings(db)
        conf.frequency, conf.weekday = "weekly", 0
        nxt = svc.next_run(conf, datetime(2026, 10, 1, 12, 0, tzinfo=TZ))  # un jeudi
    assert nxt.weekday() == 0 and nxt.hour == 3 and nxt.day == 5


def test_manifest_content(sandbox):
    path = svc.create_backup("manual", ["photos"], "local")
    with zipfile.ZipFile(path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["parts"] == ["database", "photos"] and manifest["label"] == "manual"
