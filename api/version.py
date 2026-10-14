"""
Version d'AquasManager (API et interface portent le même numéro, SemVer).

Le numéro vient des tags git vX.Y.Z (scripts/version.sh) : « 0.6.1 » pour une
livraison en prod, « 0.6.2-dev.12 » en recette. Dans l'image Docker, la CI le
passe en argument de build (AQUAS_VERSION), avec le commit (AQUAS_BUILD).
"""

import os
import subprocess
from pathlib import Path


def _from_git() -> str:
    """Calcul local (développement) : même script que la CI."""
    root = Path(__file__).resolve().parent
    try:
        result = subprocess.run(
            ["sh", str(root / "scripts" / "version.sh")], cwd=root, capture_output=True, text=True, timeout=5, check=True
        )
        return result.stdout.strip() or "0.0.0-dev"
    except (OSError, subprocess.SubprocessError):
        return "0.0.0-dev"


__version__ = os.environ.get("AQUAS_VERSION") or _from_git()

# Commit de l'image (argument de build GIT_SHA, voir Dockerfile) ; « dev » en local
BUILD = os.environ.get("AQUAS_BUILD", "dev")[:7]
