"""
Spectres de canaux et profils d'éclairage prédéfinis.

Un profil donne, pour chaque famille de spectre, une courbe de 24 h en
points (minute depuis minuit, intensité %). Les canaux reçoivent la courbe de
leur famille ; un canal sans courbe dans le profil reste éteint.
"""

from typing import NamedTuple

Curve = list[tuple[int, int]]


class Spectrum(NamedTuple):
    label: str
    color: str


SPECTRA: dict[str, Spectrum] = {
    "white": Spectrum("Blanc", "#f5f5f0"),
    "royal_blue": Spectrum("Bleu royal", "#2a3cff"),
    "blue": Spectrum("Bleu", "#1e88e5"),
    "uv": Spectrum("UV", "#7b1fa2"),
    "violet": Spectrum("Violet", "#9c27b0"),
    "cyan": Spectrum("Cyan", "#00bcd4"),
    "red": Spectrum("Rouge", "#e53935"),
    "green": Spectrum("Vert", "#43a047"),
    "yellow": Spectrum("Jaune", "#fdd835"),
    "other": Spectrum("Autre", "#9e9e9e"),
}


def _h(hour: float) -> int:
    return int(round(hour * 60))


def _plateau(start: float, full: float, end_full: float, end: float, level: int) -> Curve:
    """Rampe montante start -> full, palier à level %, rampe descendante end_full -> end."""
    return [(_h(start), 0), (_h(full), level), (_h(end_full), level), (_h(end), 0)]


class Profile(NamedTuple):
    label: str
    description: str
    curves: dict[str, Curve]


PROFILES: dict[str, Profile] = {
    "reef": Profile(
        "Récifal",
        "Lever progressif des bleus, blancs en milieu de journée, coucher bleuté.",
        {
            "royal_blue": _plateau(9, 11, 19, 21.5, 85),
            "blue": _plateau(9.5, 11.5, 18.5, 21, 75),
            "uv": _plateau(10, 12, 18, 20.5, 60),
            "violet": _plateau(10, 12, 18, 20.5, 60),
            "cyan": _plateau(10.5, 12.5, 17.5, 20, 45),
            "white": _plateau(11, 13, 17, 19, 55),
            "red": _plateau(11.5, 13.5, 16.5, 18.5, 25),
            "green": _plateau(11.5, 13.5, 16.5, 18.5, 20),
            "yellow": _plateau(11.5, 13.5, 16.5, 18.5, 20),
        },
    ),
    "reef_soft": Profile(
        "Récifal doux",
        "Même rythme que le récifal, intensités réduites (coraux mous, LPS, bac jeune).",
        {
            "royal_blue": _plateau(9, 11, 19, 21.5, 55),
            "blue": _plateau(9.5, 11.5, 18.5, 21, 45),
            "uv": _plateau(10, 12, 18, 20.5, 35),
            "violet": _plateau(10, 12, 18, 20.5, 35),
            "cyan": _plateau(10.5, 12.5, 17.5, 20, 25),
            "white": _plateau(11, 13, 17, 19, 30),
            "red": _plateau(11.5, 13.5, 16.5, 18.5, 15),
            "green": _plateau(11.5, 13.5, 16.5, 18.5, 10),
            "yellow": _plateau(11.5, 13.5, 16.5, 18.5, 10),
        },
    ),
    "planted": Profile(
        "Eau douce plantée",
        "Blancs et rouges dominants pour la photosynthèse, 8 h de plein éclairage.",
        {
            "white": _plateau(9, 10, 18, 19, 80),
            "red": _plateau(9.5, 10.5, 17.5, 18.5, 65),
            "blue": _plateau(9, 10, 18, 19, 35),
            "royal_blue": _plateau(9, 10, 18, 19, 30),
            "green": _plateau(9.5, 10.5, 17.5, 18.5, 30),
            "yellow": _plateau(9.5, 10.5, 17.5, 18.5, 30),
            "cyan": _plateau(9.5, 10.5, 17.5, 18.5, 20),
        },
    ),
    "fish_only": Profile(
        "Poissons (sans coraux)",
        "Éclairage d'agrément, lumière chaude et modérée.",
        {
            "white": _plateau(10, 11, 19, 20, 50),
            "royal_blue": _plateau(9.5, 10.5, 20, 21, 40),
            "blue": _plateau(9.5, 10.5, 20, 21, 35),
            "red": _plateau(10, 11, 19, 20, 25),
            "yellow": _plateau(10, 11, 19, 20, 25),
            "green": _plateau(10, 11, 19, 20, 15),
        },
    ),
}

def profile_bounds(profile: Profile) -> tuple[int, int]:
    """Début (premier point allumé ou non) et fin du programme, en minutes depuis minuit."""
    minutes = [m for curve in profile.curves.values() for m, _ in curve]
    return min(minutes), max(minutes)


def shifted_curves(profile: Profile, start: int | None) -> dict[str, Curve]:
    """Courbes du profil décalées pour commencer à start (minutes) ; passage de minuit géré."""
    if start is None:
        return profile.curves
    offset = start - profile_bounds(profile)[0]
    return {key: [((m + offset) % 1440, v) for m, v in curve] for key, curve in profile.curves.items()}


MOONLIGHT_SPECTRA = ("royal_blue", "blue")
DEFAULT_MOONLIGHT_INTENSITY = 2
