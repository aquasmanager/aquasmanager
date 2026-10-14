"""
PDF d'un certificat de cession de boutures (A4, reportlab).
"""

import base64
import io
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from pro.models.transfer_certificate import TransferCertificate

PRIMARY = colors.HexColor("#1565c0")
GRID = colors.HexColor("#cfd8dc")
HEADER_BG = colors.HexColor("#e3f2fd")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], textColor=PRIMARY, fontSize=18, spaceAfter=2),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], alignment=TA_CENTER, textColor=colors.grey),
        "h": ParagraphStyle("h", parent=base["Heading4"], textColor=PRIMARY, spaceBefore=6, spaceAfter=4),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=9.5, leading=13),
        "small": ParagraphStyle("small", parent=base["Normal"], fontSize=8, leading=10, textColor=colors.grey),
        "cell": ParagraphStyle("cell", parent=base["Normal"], fontSize=8.5, leading=10.5),
        "cell_bold": ParagraphStyle("cell_bold", parent=base["Normal"], fontSize=8.5, leading=10.5, fontName="Helvetica-Bold"),
    }


def _text(value: Optional[str]) -> str:
    return escape(value or "")


def _party(title: str, person: Optional[dict], styles) -> list:
    person = person or {}
    name = " ".join(p for p in (person.get("first_name"), person.get("last_name")) if p)
    lines = [f"<b>{_text(name) or '—'}</b>"]
    if person.get("address"):
        lines.append(_text(person["address"]))
    city = " ".join(p for p in (person.get("postal_code"), person.get("city")) if p)
    if city:
        lines.append(_text(city))
    contact = " · ".join(p for p in (person.get("phone"), person.get("email")) if p)
    if contact:
        lines.append(_text(contact))
    return [Paragraph(title, styles["h"]), Paragraph("<br/>".join(lines), styles["body"])]


def _origin_cell(item) -> str:
    """Où le pied mère a été acquis (traçabilité). Les certificats antérieurs
    à ce champ gardent l'origine, seule information alors disponible."""
    acquired = getattr(item, "mother_acquired_from", None)
    if acquired:
        return _text(acquired)
    return _text(item.origin) or "—"


def _signature(data_url: Optional[str]):
    if not data_url or "," not in data_url:
        return Spacer(1, 22 * mm)
    raw = base64.b64decode(data_url.split(",", 1)[1])
    image = Image(io.BytesIO(raw))
    ratio = image.imageHeight / float(image.imageWidth or 1)
    image.drawWidth = 60 * mm
    image.drawHeight = min(60 * mm * ratio, 28 * mm)
    image.drawWidth = image.drawHeight / ratio if ratio else image.drawWidth
    return image


def _price(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f} €".replace(",", " ").replace(".", ",")


def render_certificate(certificate: TransferCertificate) -> bytes:
    styles = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Certificat de cession {certificate.number}",
        author="AquasManager",
    )
    story: list = [
        Paragraph("Certificat de cession de boutures de coraux", styles["title"]),
        Paragraph(
            f"N° {_text(certificate.number)} — cession du {certificate.transfer_date.strftime('%d/%m/%Y')}"
            + (f" — {_text(certificate.location_name)}" if certificate.location_name else ""),
            styles["subtitle"],
        ),
        Spacer(1, 6 * mm),
    ]

    buyer_block = (
        [Paragraph("Acquéreur", styles["h"]),
         Paragraph(f"<i>Données anonymisées le {certificate.anonymized_at.strftime('%d/%m/%Y')}</i>", styles["body"])]
        if certificate.anonymized_at
        else _party("Acquéreur", certificate.buyer, styles)
    )
    parties = Table(
        [[_party("Cédant", certificate.seller, styles), buyer_block]],
        colWidths=[89 * mm, 89 * mm],
    )
    parties.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [parties, Spacer(1, 4 * mm), Paragraph("Spécimens cédés", styles["h"])]

    has_price = any(item.price is not None for item in certificate.items)
    header = ["Réf.", "Espèce", "N° CITES (pied mère)", "Provenance (pied mère)", "Bouturée le", "Qté"] + (["Montant"] if has_price else [])
    rows = [[Paragraph(f"<b>{h}</b>", styles["cell"]) for h in header]]
    for item in certificate.items:
        species = f"<i>{_text(item.scientific_name)}</i><br/>{_text(item.name)}" if item.scientific_name else _text(item.name)
        row = [
            Paragraph(_text(item.reference), styles["cell_bold"]),
            Paragraph(species, styles["cell"]),
            Paragraph(_text(item.cites) or "—", styles["cell"]),
            Paragraph(_origin_cell(item), styles["cell"]),
            Paragraph(item.cut_date.strftime("%d/%m/%Y") if item.cut_date else "—", styles["cell"]),
            Paragraph(f"<b>{item.quantity}</b>", styles["cell"]),
        ]
        if has_price:
            amount = _price(item.price * item.quantity) if item.price is not None else "—"
            if item.price is not None and item.quantity > 1:
                amount += f"<br/><font size=7 color='grey'>{_price(item.price)} / u</font>"
            row.append(Paragraph(amount, styles["cell"]))
        rows.append(row)
    widths = [24 * mm, 40 * mm, 30 * mm, 34 * mm, 20 * mm, 10 * mm] + ([20 * mm] if has_price else [])
    if not has_price:
        widths[1] += 10 * mm
        widths[3] += 10 * mm
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("GRID", (0, 0), (-1, -1), 0.5, GRID),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)
    count = certificate.total_quantity
    summary = f"<b>{count} bouture{'s' if count > 1 else ''}</b>"
    if certificate.total_price is not None:
        summary += f" — total : {_price(certificate.total_price)}"
    story += [Spacer(1, 2 * mm), Paragraph(summary, styles["body"])]

    if certificate.notes:
        story += [Paragraph("Observations", styles["h"]), Paragraph(_text(certificate.notes).replace("\n", "<br/>"), styles["body"])]

    story += [
        Paragraph("Déclaration", styles["h"]),
        Paragraph(_text(certificate.legal_mention).replace("\n", "<br/>"), styles["body"]),
        Spacer(1, 5 * mm),
    ]

    place = certificate.seller.get("city") or ""
    signed = certificate.signed_at.strftime("%d/%m/%Y") if certificate.signed_at else "……/……/…………"
    signatures = Table(
        [
            [Paragraph("<b>Signature du cédant</b>", styles["body"]), Paragraph("<b>Signature de l'acquéreur</b>", styles["body"])],
            [_signature(certificate.seller_signature), _signature(certificate.buyer_signature)],
            [
                Paragraph(f"Fait à {_text(place)}, le {certificate.transfer_date.strftime('%d/%m/%Y')}", styles["small"]),
                Paragraph(f"Signé électroniquement le {signed}", styles["small"]),
            ],
        ],
        colWidths=[89 * mm, 89 * mm],
    )
    signatures.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (0, -1), 0.5, GRID),
                ("BOX", (1, 0), (1, -1), 0.5, GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story += [
        KeepTogether([signatures]),
        Spacer(1, 4 * mm),
        Paragraph(
            "Document établi en deux exemplaires, un pour chaque partie. Généré par AquasManager.", styles["small"]
        ),
    ]
    if certificate.privacy_notice:
        story += [
            Spacer(1, 2 * mm),
            Paragraph(f"<b>Données personnelles.</b> {_text(certificate.privacy_notice)}", styles["small"]),
        ]
    doc.build(story)
    return buffer.getvalue()
