import io

import pdfplumber

from pro.tests.helpers import set_seller_profile as _seller
from tests.helpers import make_coral as _coral


def test_coral_provenance_follows_frags_and_certificates(api, client, aquarium, uid):
    _seller(api)
    coral = _coral(api, aquarium, uid)
    coral = api.patch(f"/corals/{coral['id']}", {"acquired_from": "Récif at Home"})
    assert coral["acquired_from"] == "Récif at Home"

    # La bouture reprend la provenance du pied mère
    frag = api.post("/frags/", {"mother_coral_id": coral["id"], "quantity": 3}, code=201)
    assert frag["acquired_from"] == "Récif at Home" and frag["origin"] == "Mariculture Indonésie"

    # Le certificat la fige et l'imprime
    cert = api.post("/transfer-certificates/", {"items": [{"frag_id": frag["id"], "quantity": 1}]}, code=201)
    assert cert["items"][0]["mother_acquired_from"] == "Récif at Home"
    api.patch(f"/corals/{coral['id']}", {"acquired_from": "Bourse de Rennes"})
    assert api.get(f"/transfer-certificates/{cert['id']}")["items"][0]["mother_acquired_from"] == "Récif at Home"
    pdf = client.get(f"/transfer-certificates/{cert['id']}/pdf", headers=api.headers)
    with pdfplumber.open(io.BytesIO(pdf.content)) as doc:
        text = " ".join(page.extract_text() or "" for page in doc.pages)
    assert "Récif at Home" in text and "Provenance" in text
    assert "Mariculture Indonésie" not in text  # l'origine n'est plus imprimée sur le certificat
    csv = client.get("/transfer-certificates/export.csv", headers=api.headers).content.decode("utf-8-sig")
    assert "Pied mère acquis auprès de" in csv.splitlines()[0] and "Récif at Home" in csv
