import io
import zipfile
from datetime import date

from middleware.database import SessionLocal
from pro.models.transfer_certificate import TransferCertificate
from pro.tests.helpers import set_seller_profile as _seller
from services.frags import get_seller_profile
from services.privacy import anonymize_expired, retention_cutoff
from tests.helpers import PNG, make_coral as _coral

BUYER = {"first_name": "Camille", "last_name": "Récif", "address": "3 quai des Coraux", "postal_code": "29200",
         "city": "Brest", "email": "camille@example.org"}


def _signed_certificate(api, client, aquarium, uid, **extra):
    coral = _coral(api, aquarium, uid)
    frag = api.post("/frags/", {"mother_coral_id": coral["id"], "quantity": 3}, code=201)
    cert = api.post("/transfer-certificates/", {"items": [{"frag_id": frag["id"], "quantity": 1}], "notes": "Pour Camille", **extra}, code=201)
    assert client.post(f"/public/certificates/{cert['sign_token']}/sign",
                       json={"buyer": BUYER, "signature": PNG, "accept": True}).status_code == 200
    return cert


def test_privacy_notice_and_anonymization(api, client, aquarium, uid):
    _seller(api)
    profile = api.put("/seller-profile/", {**api.get("/seller-profile/"), "privacy_notice": "", "buyer_retention_years": 5})
    assert "5 ans après la cession" in profile["effective_privacy_notice"]
    cert = _signed_certificate(api, client, aquarium, uid)
    assert "5 ans" in cert["privacy_notice"]
    assert "5 ans" in client.get(f"/public/certificates/{cert['sign_token']}").json()["privacy_notice"]

    custom = api.put("/seller-profile/", {**api.get("/seller-profile/"), "privacy_notice": "Mes données, mes règles."})
    assert custom["effective_privacy_notice"] == "Mes données, mes règles."

    done = api.post(f"/transfer-certificates/{cert['id']}/anonymize", {})
    assert done["anonymized_at"] and done["buyer"] == {"first_name": "Acquéreur", "last_name": "anonymisé"}
    assert done["notes"] is None and done["buyer_name"] == "Acquéreur anonymisé"
    api.post(f"/transfer-certificates/{cert['id']}/anonymize", {}, code=409)
    pdf = client.get(f"/transfer-certificates/{cert['id']}/pdf", headers=api.headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    with SessionLocal() as db:
        assert db.get(TransferCertificate, cert["id"]).buyer_signature is None


def test_automatic_anonymization_after_retention(api, client, aquarium, uid):
    _seller(api)
    api.put("/seller-profile/", {**api.get("/seller-profile/"), "buyer_retention_years": 5})
    old = _signed_certificate(api, client, aquarium, uid, transfer_date="2019-03-01")
    recent = _signed_certificate(api, client, aquarium, uid + 1000)
    assert api.get("/seller-profile/retention-preview", params={"years": 5})["count"] >= 1
    assert api.get("/seller-profile/retention-preview", params={"years": 0}) == {"cutoff": None, "count": 0}
    assert retention_cutoff(1, date(2024, 2, 29)) == date(2023, 2, 28)
    with SessionLocal() as db:
        profile = get_seller_profile(db)
        profile.buyer_retention_years = 0
        assert anonymize_expired(db, profile) == 0
        profile.buyer_retention_years = 5
        assert anonymize_expired(db, profile) >= 1
        assert db.get(TransferCertificate, old["id"]).anonymized_at is not None
        assert db.get(TransferCertificate, recent["id"]).anonymized_at is None
        db.rollback()


def test_certificates_zip(api, client, aquarium, uid):
    _seller(api)
    cert = _signed_certificate(api, client, aquarium, uid, location_name=f"Bourse ZIP {uid}")
    res = client.get("/transfer-certificates/export.zip", params={"location_id": cert["location_id"]}, headers=api.headers)
    assert res.status_code == 200 and res.headers["content-type"] == "application/zip"
    assert f"bourse-zip-{uid}" in res.headers["content-disposition"]
    names = zipfile.ZipFile(io.BytesIO(res.content)).namelist()
    assert f"bourse-zip-{uid}/certificat-{cert['number']}.pdf" in names and "cessions.csv" in names
    assert client.get("/transfer-certificates/export.zip", params={"date_from": "2099-01-01"}, headers=api.headers).status_code == 404
