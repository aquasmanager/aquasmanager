"""
safe_path.py

Chemins des fichiers envoyés (photos, documents, PDF ICP) : toujours sous leur
dossier racine. Les morceaux viennent de l'URL ou de la base ; un « .. », un
chemin absolu ou un lien symbolique qui sortirait du dossier est refusé.
"""

import os

from fastapi import HTTPException


def safe_join(root: str, *parts: str) -> str:
    """Chemin absolu de root/parts..., garanti à l'intérieur de root (sinon 400)."""
    base = os.path.realpath(root)
    path = os.path.realpath(os.path.join(base, *parts))
    if not path.startswith(base + os.sep):
        raise HTTPException(status_code=400, detail="Chemin de fichier invalide.")
    return path
