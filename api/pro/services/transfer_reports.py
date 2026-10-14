"""
Bilans et exports des cessions de boutures : bilan (par lieu / période),
export CSV (comptabilité) et registre annuel PDF (traçabilité CITES).
"""

import csv
import io
import re
import unicodedata
import zipfile
from collections import defaultdict
from datetime import date
from typing import Optional

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from models.frag import Frag
from pro.models.transfer_certificate import TransferCertificate
from pro.services.certificate_pdf import GRID, HEADER_BG, _origin_cell, _styles, _text, render_certificate


def select_certificates(
    db: Session,
    location_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    signed_only: bool = False,
) -> list[TransferCertificate]:
    """location_id : lieu (0 = sans lieu, None = tous)."""
    query = db.query(TransferCertificate)
    if location_id == 0:
        query = query.filter(TransferCertificate.location_id.is_(None))
    elif location_id is not None:
        query = query.filter(TransferCertificate.location_id == location_id)
    if date_from:
        query = query.filter(TransferCertificate.transfer_date >= date_from)
    if date_to:
        query = query.filter(TransferCertificate.transfer_date <= date_to)
    if signed_only:
        query = query.filter(TransferCertificate.status == "signed")
    return query.order_by(TransferCertificate.transfer_date, TransferCertificate.number).all()


def build_report(db: Session, certificates: list[TransferCertificate]) -> dict:
    """Bilan : certificats signés comptés, ceux en attente à part ; stock restant disponible."""
    signed = [c for c in certificates if c.status == "signed"]
    species: dict[tuple[str, str], dict] = {}
    for certificate in signed:
        for item in certificate.items:
            key = (item.scientific_name, item.name)
            entry = species.setdefault(
                key, {"name": item.name, "scientific_name": item.scientific_name, "quantity": 0, "amount": 0.0}
            )
            entry["quantity"] += item.quantity
            entry["amount"] += (item.price or 0) * item.quantity
    stock = db.query(Frag).filter(Frag.quantity > 0).all()
    return {
        "certificate_count": len(signed),
        "pending_count": len(certificates) - len(signed),
        "quantity": sum(c.total_quantity for c in signed),
        "total": round(sum(c.total_price or 0 for c in signed), 2),
        "by_species": sorted(
            ({**e, "amount": round(e["amount"], 2)} for e in species.values()), key=lambda e: -e["quantity"]
        ),
        "stock_lots": len(stock),
        "stock_quantity": sum(f.quantity for f in stock),
    }


def yearly_summary(db: Session) -> list[dict]:
    """Cessions signées par année civile (la plus récente d'abord) : nombre, boutures,
    montant, lieux et acquéreurs distincts. Sert à vérifier d'un coup d'œil que
    l'activité reste occasionnelle."""
    years: dict[int, dict] = {}
    for certificate in db.query(TransferCertificate).filter(TransferCertificate.status == "signed"):
        year = certificate.transfer_date.year
        entry = years.setdefault(
            year, {"year": year, "certificate_count": 0, "quantity": 0, "total": 0.0, "_locations": set(), "_buyers": set()}
        )
        entry["certificate_count"] += 1
        entry["quantity"] += certificate.total_quantity
        entry["total"] += certificate.total_price or 0
        if certificate.location_id is not None:
            entry["_locations"].add(certificate.location_id)
        if certificate.buyer_name:
            entry["_buyers"].add(certificate.buyer_name.strip().lower())
    result = []
    for year in sorted(years, reverse=True):
        entry = years[year]
        result.append(
            {
                "year": year,
                "certificate_count": entry["certificate_count"],
                "quantity": entry["quantity"],
                "total": round(entry["total"], 2),
                "location_count": len(entry.pop("_locations")),
                "buyer_count": len(entry.pop("_buyers")),
            }
        )
    return result


def export_csv(certificates: list[TransferCertificate]) -> bytes:
    """Une ligne par bouture cédée ; séparateur « ; » et BOM pour Excel."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Date", "Certificat", "Statut", "Lieu", "Acquéreur", "Ville acquéreur", "Réf. bouture", "Nom",
        "Nom scientifique", "N° CITES", "Provenance", "Pied mère acquis auprès de", "Quantité", "Prix unitaire", "Montant",
    ])
    for certificate in certificates:
        buyer = certificate.buyer or {}
        for item in certificate.items:
            amount = (item.price or 0) * item.quantity if item.price is not None else None
            writer.writerow([
                certificate.transfer_date.strftime("%d/%m/%Y"),
                certificate.number,
                "Signé" if certificate.status == "signed" else "En attente",
                certificate.location_name or "",
                certificate.buyer_name or "",
                buyer.get("city", ""),
                item.reference,
                item.name,
                item.scientific_name,
                item.cites,
                item.origin,
                item.mother_acquired_from or "",
                item.quantity,
                f"{item.price:.2f}".replace(".", ",") if item.price is not None else "",
                f"{amount:.2f}".replace(".", ",") if amount is not None else "",
            ])
    return ("﻿" + output.getvalue()).encode("utf-8")


def registry_pdf(certificates: list[TransferCertificate], year: int, seller: dict) -> bytes:
    """Registre des cessions signées de l'année : une ligne par bouture cédée, puis bilan par espèce."""
    styles = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"Registre des cessions {year}",
        author="AquasManager",
    )
    name = " ".join(p for p in (seller.get("first_name"), seller.get("last_name")) if p)
    story: list = [
        Paragraph(f"Registre des cessions de boutures — {year}", styles["title"]),
        Paragraph(_text(f"{name} · {seller.get('postal_code', '')} {seller.get('city', '')}".strip(" ·")), styles["subtitle"]),
        Spacer(1, 5 * mm),
    ]
    header = ["Date", "Certificat", "Lieu", "Acquéreur", "Réf.", "Espèce", "N° CITES", "Provenance (pied mère)", "Qté"]
    rows = [[Paragraph(f"<b>{h}</b>", styles["cell"]) for h in header]]
    totals: dict[str, int] = defaultdict(int)
    for certificate in certificates:
        buyer = certificate.buyer or {}
        buyer_label = f"{certificate.buyer_name or ''}<br/><font size=7 color='grey'>{_text(buyer.get('city'))}</font>"
        for item in certificate.items:
            totals[item.scientific_name or item.name] += item.quantity
            rows.append([
                Paragraph(certificate.transfer_date.strftime("%d/%m/%Y"), styles["cell"]),
                Paragraph(_text(certificate.number), styles["cell"]),
                Paragraph(_text(certificate.location_name) or "—", styles["cell"]),
                Paragraph(buyer_label, styles["cell"]),
                Paragraph(_text(item.reference), styles["cell"]),
                Paragraph(f"<i>{_text(item.scientific_name)}</i><br/>{_text(item.name)}", styles["cell"]),
                Paragraph(_text(item.cites) or "—", styles["cell"]),
                Paragraph(_origin_cell(item), styles["cell"]),
                Paragraph(f"<b>{item.quantity}</b>", styles["cell"]),
            ])
    if len(rows) == 1:
        rows.append([Paragraph("Aucune cession signée cette année.", styles["cell"])] + [""] * 8)
    table = Table(rows, colWidths=[20 * mm, 24 * mm, 30 * mm, 38 * mm, 22 * mm, 52 * mm, 32 * mm, 43 * mm, 12 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)
    if totals:
        story += [Spacer(1, 5 * mm), Paragraph("Bilan par espèce", styles["h"])]
        summary = [[Paragraph("<b>Espèce</b>", styles["cell"]), Paragraph("<b>Boutures cédées</b>", styles["cell"])]]
        summary += [
            [Paragraph(f"<i>{_text(species)}</i>", styles["cell"]), Paragraph(str(quantity), styles["cell"])]
            for species, quantity in sorted(totals.items(), key=lambda kv: -kv[1])
        ]
        summary.append([Paragraph("<b>Total</b>", styles["cell"]), Paragraph(f"<b>{sum(totals.values())}</b>", styles["cell"])])
        box = Table(summary, colWidths=[90 * mm, 35 * mm], hAlign="LEFT")
        box.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, GRID), ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG)]))
        story.append(box)
    story += [Spacer(1, 4 * mm), Paragraph(f"Généré par AquasManager — {len(certificates)} certificat(s) signé(s).", styles["small"])]
    doc.build(story)
    return buffer.getvalue()




def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", ascii_text).strip("-").lower() or "sans-nom"


def certificates_zip(certificates: list[TransferCertificate]) -> bytes:
    """Archive : un PDF par certificat, rangé dans un dossier par lieu, et le tableau CSV."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for certificate in certificates:
            folder = _slug(certificate.location_name) if certificate.location_name else "sans-lieu"
            suffix = "" if certificate.status == "signed" else "-en-attente"
            archive.writestr(f"{folder}/certificat-{certificate.number}{suffix}.pdf", render_certificate(certificate))
        archive.writestr("cessions.csv", export_csv(certificates))
    return buffer.getvalue()


def zip_filename(
    certificates: list[TransferCertificate],
    location_id: Optional[int],
    date_from: Optional[date],
    date_to: Optional[date],
) -> str:
    parts = ["certificats-cession"]
    if location_id == 0:
        parts.append("sans-lieu")
    elif location_id is not None and certificates and certificates[0].location_name:
        parts.append(_slug(certificates[0].location_name))
    if date_from or date_to:
        parts.append(f"{date_from or ''}_{date_to or ''}".strip("_"))
    return "-".join(parts) + ".zip"
