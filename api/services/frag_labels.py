"""
Planche d'étiquettes des boutures (A4, 3 × 8 étiquettes de 70 × 37 mm) :
QR code vers la fiche du lot, référence, espèce, n° CITES et prix.
"""

import io
from typing import Optional
from urllib.parse import quote

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from models.frag import Frag

COLUMNS, ROWS = 3, 8
LABEL_W, LABEL_H = 70 * mm, 37 * mm
MARGIN_X = (A4[0] - COLUMNS * LABEL_W) / 2
MARGIN_Y = (A4[1] - ROWS * LABEL_H) / 2
QR_SIZE = 26 * mm


def frag_url(base_url: str, frag: Frag) -> str:
    return f"{base_url.rstrip('/')}/frags?ref={quote(frag.reference)}"


def _fit(c: canvas.Canvas, text: str, font: str, size: float, width: float) -> str:
    """Coupe le texte avec « … » pour tenir dans la largeur."""
    if c.stringWidth(text, font, size) <= width:
        return text
    while text and c.stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text + "…"


def _price(value: Optional[float]) -> str:
    return f"{value:,.2f} €".replace(",", " ").replace(".", ",") if value is not None else ""


def render_labels(frags: list[Frag], base_url: str, per_unit: bool = False) -> bytes:
    """per_unit : une étiquette par bouture disponible (sinon une par lot)."""
    labels = [frag for frag in frags for _ in range(max(frag.quantity, 1) if per_unit else 1)]
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle("Étiquettes des boutures")
    c.setAuthor("AquasManager")
    for index, frag in enumerate(labels):
        slot = index % (COLUMNS * ROWS)
        if index and slot == 0:
            c.showPage()
        col, row = slot % COLUMNS, slot // COLUMNS
        x = MARGIN_X + col * LABEL_W
        y = A4[1] - MARGIN_Y - (row + 1) * LABEL_H

        # Repère de découpe léger
        c.setStrokeColor(colors.HexColor("#e0e0e0"))
        c.setLineWidth(0.3)
        c.rect(x, y, LABEL_W, LABEL_H)

        widget = QrCodeWidget(frag_url(base_url, frag), barLevel="M")
        x1, y1, x2, y2 = widget.getBounds()
        drawing = Drawing(QR_SIZE, QR_SIZE, transform=[QR_SIZE / (x2 - x1), 0, 0, QR_SIZE / (y2 - y1), 0, 0])
        drawing.add(widget)
        renderPDF.draw(drawing, c, x + 2 * mm, y + (LABEL_H - QR_SIZE) / 2)

        text_x = x + QR_SIZE + 4 * mm
        width = LABEL_W - QR_SIZE - 6 * mm
        top = y + LABEL_H - 6 * mm
        c.setFillColor(colors.HexColor("#1565c0"))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(text_x, top, frag.reference)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(text_x, top - 5 * mm, _fit(c, frag.name, "Helvetica-Bold", 10, width))
        if frag.scientific_name:
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(text_x, top - 9.5 * mm, _fit(c, frag.scientific_name, "Helvetica-Oblique", 8, width))
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#555555"))
        c.drawString(text_x, top - 14 * mm, _fit(c, f"CITES {frag.cites or '—'}", "Helvetica", 7, width))
        if frag.price is not None:
            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(text_x, y + 4 * mm, _price(frag.price))
    if not labels:
        c.setFont("Helvetica", 12)
        c.drawString(20 * mm, A4[1] - 30 * mm, "Aucune bouture disponible.")
    c.save()
    return buffer.getvalue()
