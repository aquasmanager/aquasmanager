import io
import zipfile

from tests.helpers import make_coral as _coral, seller_headers as _seller_headers

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def test_purchase_documents(api, client, aquarium, uid):
    coral = _coral(api, aquarium, uid)
    specimens = api.get("/purchase-documents/specimens")
    assert any(s["entity_type"] == "corals" and s["entity_id"] == coral["id"] for s in specimens)

    doc = api.post("/purchase-documents/", {"title": f"Facture Récif Shop {uid}", "supplier": "Récif Shop",
                                           "purchase_date": "2026-05-02", "reference": "F-123", "cites_number": "FR26-9",
                                           "links": [{"entity_type": "corals", "entity_id": coral["id"]}]}, code=201)
    assert doc["links"][0]["label"].startswith(coral["name"]) and doc["links"][0]["aquarium_id"] == aquarium["id"]
    api.post("/purchase-documents/", {"title": "x", "links": [{"entity_type": "corals", "entity_id": 999999}]}, code=400)

    up = client.post(f"/purchase-documents/{doc['id']}/files", headers=api.headers, files=[
        ("files", ("facture.pdf", io.BytesIO(PDF), "application/pdf")),
        ("files", ("recto.jpg", io.BytesIO(JPEG), "image/jpeg")),
    ])
    assert up.status_code == 201, up.text
    fake = client.post(f"/purchase-documents/{doc['id']}/files", headers=api.headers,
                       files=[("files", ("piege.pdf", io.BytesIO(b"<html>"), "application/pdf"))])
    assert fake.status_code == 400
    bad = client.post(f"/purchase-documents/{doc['id']}/files", headers=api.headers,
                      files=[("files", ("script.svg", io.BytesIO(b"<svg/>"), "image/svg+xml"))])
    assert bad.status_code == 400

    full = api.get(f"/purchase-documents/{doc['id']}")
    assert [f["original_name"] for f in full["files"]] == ["facture.pdf", "recto.jpg"]
    pdf_file = full["files"][0]
    got = client.get(f"/purchase-documents/{doc['id']}/files/{pdf_file['id']}", headers=api.headers)
    assert got.status_code == 200 and got.content == PDF and got.headers["x-content-type-options"] == "nosniff"
    assert client.get(f"/purchase-documents/{doc['id']}/files/{pdf_file['id']}").status_code == 401  # pas sans compte

    by_coral = api.get("/purchase-documents/", params={"entity_type": "corals", "entity_id": coral["id"]})
    assert [d["id"] for d in by_coral] == [doc["id"]]
    assert api.get("/purchase-documents/", params={"q": "F-123"})[0]["id"] == doc["id"]

    archive = client.get("/purchase-documents/export.zip", params={"entity_type": "corals", "entity_id": coral["id"]}, headers=api.headers)
    names = zipfile.ZipFile(io.BytesIO(archive.content)).namelist()
    assert "index.csv" in names and any(n.endswith("facture.pdf") for n in names)

    # Compte bourse : consultation (contrôle sur un stand), pas de modification
    h = _seller_headers(api, client, uid)
    assert client.get(f"/purchase-documents/{doc['id']}/files/{pdf_file['id']}", headers=h).status_code == 200
    assert client.patch(f"/purchase-documents/{doc['id']}", json={"title": "x"}, headers=h).status_code == 403

    updated = api.patch(f"/purchase-documents/{doc['id']}", {"links": []})
    assert updated["links"] == [] and updated["title"] == f"Facture Récif Shop {uid}"
    api.delete(f"/purchase-documents/{doc['id']}/files/{pdf_file['id']}")
    api.delete(f"/purchase-documents/{doc['id']}")
    api.get(f"/purchase-documents/{doc['id']}", code=404)


def test_document_several_cites_numbers_and_auto_links(api, aquarium, uid):
    """Plusieurs numéros CITES par document ; coraux liés automatiquement dans les deux sens."""
    def coral(name, cites):
        return api.post("/corals/", {
            "aquarium_id": aquarium["id"], "name": name, "cites": cites, "type": "LPS",
            "scientific_name": "Euphyllia", "family": "Euphylliidae", "origin": "Mariculture",
            "light_range": {"min": 4, "max": 8}, "brewing_range": {"min": 2, "max": 5},
            "aggressiveness_level": 5, "resistance_level": 5, "location_level": 3, "date_acquisition": "2026-05-01",
        }, code=201)

    first = coral(f"Euphyllia A {uid}", f"FR-{uid}-1")
    doc = api.post("/purchase-documents/", {"title": f"Facture {uid}",
                                            "cites_numbers": [f"fr {uid} 1", f"FR-{uid}-2", f"FR-{uid}-2"]}, code=201)
    assert doc["cites_numbers"] == [f"fr {uid} 1", f"FR-{uid}-2"]  # doublon retiré
    assert doc["auto_linked"] == 1 and [link["entity_id"] for link in doc["links"]] == [first["id"]]

    # Un corail saisi ensuite avec un numéro du document y est lié
    second = coral(f"Euphyllia B {uid}", f"FR-{uid}-2")
    links = {link["entity_id"] for link in api.get("/purchase-documents/", params={"q": f"FR-{uid}-2"})[0]["links"]}
    assert links == {first["id"], second["id"]}

    # Lien retiré à la main : il ne revient pas tant que les numéros ne changent pas
    kept = api.patch(f"/purchase-documents/{doc['id']}", {"links": [{"entity_type": "corals", "entity_id": second["id"]}],
                                                          "cites_numbers": [f"fr {uid} 1", f"FR-{uid}-2"]})
    assert kept["auto_linked"] == 0 and [link["entity_id"] for link in kept["links"]] == [second["id"]]
    # Ancien champ texte toujours accepté
    legacy = api.post("/purchase-documents/", {"title": f"Ancien {uid}", "cites_number": f"X-{uid}; Y-{uid}"}, code=201)
    assert legacy["cites_numbers"] == [f"X-{uid}", f"Y-{uid}"]


def test_cites_number_suggested_for_coral_species(api, aquarium, uid):
    """Numéro CITES d'une facture rattaché à une espèce : proposé à l'ajout d'un corail de cette espèce."""
    species = api.post("/species/corals", {
        "common_name": f"Euphyllia test {uid}", "scientific_name": "Euphyllia paraancora", "type": "LPS",
        "light_min": 4, "light_max": 8, "brewing_min": 2, "brewing_max": 5, "aggressiveness_level": 5,
        "resistance_level": 6, "location_level": 3,
    }, code=201)
    other = api.post("/species/corals", {
        "common_name": f"Acropora test {uid}", "scientific_name": "Acropora tenuis", "type": "SPS",
        "light_min": 8, "light_max": 12, "brewing_min": 6, "brewing_max": 9, "aggressiveness_level": 3,
        "resistance_level": 3, "location_level": 8,
    }, code=201)
    doc = api.post("/purchase-documents/", {"title": f"Facture CITES {uid}", "purchase_date": "2026-10-01", "cites_entries": [
        {"number": f"FR-{uid}-A", "coral_species_id": species["id"]},
        {"number": f"FR-{uid}-B", "coral_species_id": other["id"]},
        {"number": f"FR-{uid}-C"},
    ]}, code=201)
    assert doc["cites_numbers"] == [f"FR-{uid}-A", f"FR-{uid}-B", f"FR-{uid}-C"]
    assert [(e["number"], e["coral_species_name"]) for e in doc["cites_entries"]] == [
        (f"FR-{uid}-A", f"Euphyllia test {uid}"), (f"FR-{uid}-B", f"Acropora test {uid}"), (f"FR-{uid}-C", None)]

    suggestions = api.get("/purchase-documents/cites-suggestions", params={"coral_species_id": species["id"]})
    assert [(s["number"], s["document_title"], s["used_by"]) for s in suggestions] == [(f"FR-{uid}-A", f"Facture CITES {uid}", [])]

    # Numéro retiré du document : son espèce aussi
    api.patch(f"/purchase-documents/{doc['id']}", {"cites_numbers": [f"FR-{uid}-B"]})
    assert api.get("/purchase-documents/cites-suggestions", params={"coral_species_id": species["id"]}) == []
    assert api.get("/purchase-documents/cites-suggestions", params={"coral_species_id": other["id"]})[0]["number"] == f"FR-{uid}-B"


def test_scan_pages_into_one_pdf(api, client, admin_headers, uid):
    """Pages photographiées réunies en un PDF attaché au document."""
    import io

    from PIL import Image

    doc = api.post("/purchase-documents/", {"title": f"Scan {uid}"}, code=201)

    def jpeg(color):
        buf = io.BytesIO()
        Image.new("RGB", (800, 1100), color).save(buf, "JPEG")
        return buf.getvalue()

    files = [("pages", ("p1.jpg", jpeg("white"), "image/jpeg")), ("pages", ("p2.jpg", jpeg("lightgray"), "image/jpeg"))]
    r = client.post(f"/purchase-documents/{doc['id']}/scan", files=files, data={"name": "Facture boutique"}, headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["original_name"] == "Facture boutique.pdf" and r.json()["content_type"] == "application/pdf"
    stored = api.get("/purchase-documents/", params={"q": f"Scan {uid}"})[0]["files"]
    assert [f["original_name"] for f in stored] == ["Facture boutique.pdf"]
    content = client.get(f"/purchase-documents/{doc['id']}/files/{stored[0]['id']}", headers=admin_headers).content
    assert content.startswith(b"%PDF") and b"/Count 2" in content  # deux pages

    bad = [("pages", ("x.jpg", b"pas une image", "image/jpeg"))]
    assert client.post(f"/purchase-documents/{doc['id']}/scan", files=bad, headers=admin_headers).status_code == 400
