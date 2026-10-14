"""
Exporte le catalogue d'espèces intégré (services/species_catalog.py) au format
du catalogue commun en ligne (catalogue.json du dépôt public de l'éditeur).

Usage : python scripts/export_species_catalog.py > catalogue.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.species import CoralSpecies, FishSpecies, InvertebrateSpecies, PlantSpecies  # noqa: E402
from services.catalog_sync import SUPPORTED_FORMAT, _plain  # noqa: E402
from services.species_catalog import _species_rows  # noqa: E402

KIND_OF = {FishSpecies: "fishes", CoralSpecies: "corals", PlantSpecies: "plants", InvertebrateSpecies: "invertebrates"}


def main() -> None:
    catalog: dict = {"format": SUPPORTED_FORMAT, "fishes": [], "corals": [], "plants": [], "invertebrates": []}
    for model, row in _species_rows():
        catalog[KIND_OF[model]].append({k: _plain(v) for k, v in row.items() if v is not None})
    json.dump(catalog, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
