"""
services/icp_import.py

Extraction des valeurs d'un rapport d'analyse ICP (labo externe) pour
pré-remplir des relevés de paramètres d'eau. Chaque labo a sa propre mise
en page de rapport : un parseur dédié par labo, choisi via le paramètre
`lab`. Seul ATI est supporté pour le moment (labos suivants à ajouter dès
qu'un exemple de rapport est disponible).

Le parsing est volontairement "best effort" : le résultat est toujours
présenté à l'utilisateur pour relecture/correction avant import réel (voir
routes/water_parameter.py), donc une extraction imparfaite n'écrase jamais
directement les données.
"""

import io
import re
import logging
from typing import Optional, TypedDict

import pdfplumber
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class IcpRow(TypedDict):
    name: str
    label: str
    value: float
    unit: Optional[str]
    target: Optional[float]
    status: Optional[str]


def extract_pdf_text(content: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        logger.warning("ICP import : échec d'ouverture/lecture du PDF (%d octets) : %s", len(content), exc)
        raise HTTPException(status_code=400, detail=f"Impossible de lire ce PDF ({exc}).") from exc


# (symbole utilisé comme nom de WaterParameter, libellé français recherché dans le rapport)
ATI_ELEMENTS: list[tuple[str, str]] = [
    ("Sal. total", "Salinité"),
    ("Cl", "Chlorure"),
    ("Na", "Sodium"),
    ("Mg", "Magnésium"),
    ("S", "Soufre"),
    ("Ca", "Calcium"),
    ("K", "Potassium"),
    ("Br", "Brome"),
    ("Sr", "Strontium"),
    ("B", "Bore"),
    ("Li", "Lithium"),
    ("Si", "Silicium"),
    ("I", "Iode"),
    ("Ba", "Baryum"),
    ("Mo", "Molybdène"),
    ("Ni", "Nickel"),
    ("Mn", "Manganèse"),
    ("As", "Arsenic"),
    ("Be", "Béryllium"),
    ("Cr", "Chrome"),
    ("Co", "Cobalt"),
    ("Fe", "Fer"),
    ("Cu", "Cuivre"),
    ("Se", "Sélénium"),
    ("Ag", "Argent"),
    ("V", "Vanadium"),
    ("Zn", "Zinc"),
    ("Sn", "Étain"),
    ("P", "Phosphore"),
    ("PO4", "Phosphate"),
    ("Al", "Aluminium"),
    ("Sb", "Antimoine"),
    ("Bi", "Bismuth"),
    ("Pb", "Plomb"),
    ("Cd", "Cadmium"),
    ("La", "Lanthane"),
    ("Tl", "Thallium"),
    ("Ti", "Titane"),
    ("W", "Tungstène"),
    ("Hg", "Mercure"),
]


def parse_ati_report(text: str) -> list[IcpRow]:
    """
    Layout réel observé (via pdfplumber, confirmé sur un rapport ATI réel —
    le rapport visuel a 3 "colonnes" par ligne mais le texte extrait est
    sérialisé sur 2 lignes par élément, chacune concaténant ses colonnes) :
        <Symbole>[.] <valeur ou "---"> <unité> <statut...>
        <Nom français> Valeur idéale: <valeur idéale> <unité> <description...>
    Le symbole et le nom sont donc recherchés indépendamment (ancrés en
    début de ligne), plutôt que de supposer un bloc séquentiel : ça reste
    robuste tant que chaque paire (symbole+valeur) et (nom+idéale) est sur
    une seule ligne, peu importe leur ordre relatif l'une par rapport à
    l'autre.
    """
    rows: list[IcpRow] = []
    for symbol, french_name in ATI_ELEMENTS:
        # "Al." / "La." : le rapport ATI suffixe parfois le symbole d'un point.
        # Le reste de la ligne après la valeur est capturé en bloc : son
        # découpage dépend de si une valeur a été mesurée ou non (voir
        # plus bas), car "---" n'est jamais suivi d'une unité.
        value_pattern = re.compile(
            rf"^{re.escape(symbol)}\.?\s+(---|\d+(?:[.,]\d+)?)\s+(.*)$",
            re.MULTILINE,
        )
        ideal_pattern = re.compile(
            rf"^{re.escape(french_name)}\s+Valeur id[ée]ale\s*:\s*(\d+(?:[.,]\d+)?)\s*(\S*)",
            re.MULTILINE | re.IGNORECASE,
        )
        value_match = value_pattern.search(text)
        ideal_match = ideal_pattern.search(text)
        if not value_match or not ideal_match:
            continue

        raw_value, rest = value_match.groups()
        rest = rest.strip()
        if raw_value == "---":
            # Pas de mesure au-dessus du seuil de détection = valeur nulle
            # (et non une absence de donnée) : le reste de la ligne est
            # directement le statut ATI ("TOP", "INSUFFISANT"...).
            value = 0.0
            unit = None
            status_word = rest or None
        else:
            value = float(raw_value.replace(",", "."))
            parts = rest.split(maxsplit=1)
            unit = parts[0] if parts else None
            status_word = parts[1] if len(parts) > 1 else None

        raw_target, target_unit = ideal_match.groups()
        rows.append(
            {
                "name": symbol,
                "label": french_name,
                "value": value,
                "unit": (unit or target_unit or "").strip() or None,
                "target": float(raw_target.replace(",", ".")),
                "status": status_word,
            }
        )
    return rows


PARSERS = {
    "ati": parse_ati_report,
}


def parse_icp_report(lab: str, content: bytes) -> list[IcpRow]:
    logger.info("ICP import : requête reçue (lab=%s, %d octets)", lab, len(content))
    parser = PARSERS.get(lab)
    if parser is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Labo '{lab}' non encore supporté pour l'import automatique.",
        )

    text = extract_pdf_text(content)
    rows = parser(text)
    if not rows:
        # Journalisé pour pouvoir ajuster le parseur sur le texte brut réel :
        # l'extraction PDF peut réordonner les colonnes différemment de ce à
        # quoi le regex s'attend selon la mise en page exacte du fichier.
        logger.warning("ICP import (lab=%s) : aucune valeur reconnue. Texte extrait :\n%s", lab, text[:8000])
        raise HTTPException(
            status_code=422,
            detail=(
                "Aucune valeur reconnue dans ce rapport. Le fichier ne correspond peut-être pas "
                "au format attendu pour ce labo."
            ),
        )
    return rows

