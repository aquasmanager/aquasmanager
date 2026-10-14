"""
Référentiel des paramètres d'eau : noms complets et cibles par défaut
(aquarium récifal).

Clé = nom du paramètre en majuscules (symboles des rapports ICP ATI) ;
unités alignées sur ces rapports (µg/l pour les éléments traces).
"""

from typing import NamedTuple, Optional


class TargetDefault(NamedTuple):
    unit: str
    target_min: float
    target_max: float


TARGET_DEFAULTS: dict[str, TargetDefault] = {
    # Base / majeurs
    "SAL. TOTAL": TargetDefault("PSU", 34, 35.5),
    "KH": TargetDefault("°dKH", 7, 9),
    "CA": TargetDefault("mg/l", 400, 450),
    "MG": TargetDefault("mg/l", 1250, 1400),
    "CL": TargetDefault("mg/l", 18500, 20500),
    "NA": TargetDefault("mg/l", 10300, 11300),
    "S": TargetDefault("mg/l", 850, 950),
    "K": TargetDefault("mg/l", 380, 420),
    "BR": TargetDefault("mg/l", 60, 75),
    "SR": TargetDefault("mg/l", 7, 9),
    "B": TargetDefault("mg/l", 4, 5),
    # Nutriments
    "NO3": TargetDefault("mg/l", 2, 10),
    "PO4": TargetDefault("mg/l", 0.03, 0.1),
    "P": TargetDefault("µg/l", 10, 35),
    # Mineurs
    "LI": TargetDefault("µg/l", 150, 250),
    "SI": TargetDefault("µg/l", 50, 200),
    "I": TargetDefault("µg/l", 50, 80),
    "BA": TargetDefault("µg/l", 5, 30),
    "MO": TargetDefault("µg/l", 10, 20),
    "NI": TargetDefault("µg/l", 0, 2),
    "MN": TargetDefault("µg/l", 0.5, 3),
    "AS": TargetDefault("µg/l", 0, 2),
    "BE": TargetDefault("µg/l", 0, 0.5),
    "CR": TargetDefault("µg/l", 0, 1),
    "CO": TargetDefault("µg/l", 0, 0.5),
    "FE": TargetDefault("µg/l", 0.3, 3),
    "CU": TargetDefault("µg/l", 0, 1.5),
    "SE": TargetDefault("µg/l", 0, 1),
    "AG": TargetDefault("µg/l", 0, 0.5),
    "V": TargetDefault("µg/l", 1, 3),
    "ZN": TargetDefault("µg/l", 1.5, 5),
    "SN": TargetDefault("µg/l", 0, 5),
    # Polluants
    "AL": TargetDefault("µg/l", 0, 15),
    "SB": TargetDefault("µg/l", 0, 0.5),
    "BI": TargetDefault("µg/l", 0, 0.5),
    "PB": TargetDefault("µg/l", 0, 0.5),
    "CD": TargetDefault("µg/l", 0, 0.5),
    "LA": TargetDefault("µg/l", 0, 0.1),
    "TL": TargetDefault("µg/l", 0, 0.2),
    "TI": TargetDefault("µg/l", 0, 0.5),
    "W": TargetDefault("µg/l", 0, 0.1),
    "HG": TargetDefault("µg/l", 0, 0.05),
}


def normalize_unit(unit: Optional[str]) -> str:
    return (unit or "").strip().lower().replace("ug/", "µg/").replace(" ", "")


def default_target_for(name: str, unit: Optional[str] = None) -> Optional[TargetDefault]:
    """Cible par défaut ; si une unité est fournie elle doit correspondre (mg/l ≠ µg/l)."""
    default = TARGET_DEFAULTS.get(name.strip().upper())
    if default is None:
        return None
    if unit and normalize_unit(unit) != normalize_unit(default.unit):
        return None
    return default


# Nom complet affiché à côté du symbole (clé = symbole en majuscules)
PARAMETER_FULL_NAMES: dict[str, str] = {
    "KH": "Dureté carbonatée",
    "GH": "Dureté totale",
    "NO3": "Nitrate",
    "NO2": "Nitrite",
    "NH3": "Ammoniac",
    "NH4": "Ammonium",
    "PO4": "Phosphate",
    "CA": "Calcium",
    "MG": "Magnésium",
    "SR": "Strontium",
    "NA": "Sodium",
    "CL": "Chlorure",
    "K": "Potassium",
    "S": "Soufre",
    "BR": "Brome",
    "B": "Bore",
    "LI": "Lithium",
    "SI": "Silicium",
    "I": "Iode",
    "BA": "Baryum",
    "MO": "Molybdène",
    "NI": "Nickel",
    "MN": "Manganèse",
    "AS": "Arsenic",
    "BE": "Béryllium",
    "CR": "Chrome",
    "CO": "Cobalt",
    "FE": "Fer",
    "CU": "Cuivre",
    "SE": "Sélénium",
    "AG": "Argent",
    "V": "Vanadium",
    "ZN": "Zinc",
    "SN": "Étain",
    "P": "Phosphore",
    "AL": "Aluminium",
    "SB": "Antimoine",
    "BI": "Bismuth",
    "PB": "Plomb",
    "CD": "Cadmium",
    "LA": "Lanthane",
    "TL": "Thallium",
    "TI": "Titane",
    "W": "Tungstène",
    "HG": "Mercure",
    "SAL. TOTAL": "Salinité",
}


def full_name_for(name: str) -> Optional[str]:
    return PARAMETER_FULL_NAMES.get(name.strip().upper())
