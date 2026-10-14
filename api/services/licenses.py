"""
services/licenses.py

Inventaire des composants tiers de l'API, lu dans les paquets réellement
installés (toujours à jour), et des logiciels externes utilisés à côté.
"""

import importlib.metadata as md
import re
from functools import lru_cache
from typing import Optional

# Licences à « réciprocité » (copyleft) : ce qu'elles impliquent ici
COPYLEFT_NOTES = {
    "GPL": "Utilisé comme programme séparé ou paquet non modifié ; son code source est public.",
    "LGPL": "Bibliothèque utilisée sans modification ; remplaçable par l'utilisateur.",
    "MPL": "Fichiers non modifiés ; le code source est public.",
    "EPL": "Utilisé sans modification ; le code source est public.",
}

# Logiciels livrés à côté de l'API (conteneurs, outils appelés en ligne de commande)
EXTERNAL_COMPONENTS = [
    {
        "name": "ESPHome",
        "license": "MIT (outil Python) / GPL-3.0 (code C++ du firmware)",
        "url": "https://esphome.io",
        "usage": "Compilation et envoi du firmware des contrôleurs, appelé comme programme séparé. "
        "Le firmware produit contient le code C++ d'ESPHome, sous GPL-3.0.",
    },
    {
        "name": "Eclipse Mosquitto",
        "license": "EPL-2.0 / EDL-1.0",
        "url": "https://mosquitto.org",
        "usage": "Broker MQTT, conteneur séparé (image officielle).",
    },
    {"name": "Caddy", "license": "Apache-2.0", "url": "https://caddyserver.com", "usage": "Proxy HTTPS optionnel, conteneur séparé."},
    {"name": "ntfy", "license": "Apache-2.0 / GPL-2.0", "url": "https://ntfy.sh", "usage": "Serveur de notifications optionnel, conteneur séparé."},
    {
        "name": "go2rtc",
        "license": "MIT",
        "url": "https://github.com/AlexxIT/go2rtc",
        "usage": "Service vidéo optionnel des caméras IP, conteneur séparé (image officielle, qui inclut FFmpeg "
        "sous LGPL/GPL). Le lecteur du direct de l'interface reprend la logique de son video-rtc.js (MIT).",
    },
    {"name": "nginx", "license": "BSD-2-Clause", "url": "https://nginx.org", "usage": "Sert l'interface web (image officielle)."},
    {"name": "Python", "license": "PSF-2.0", "url": "https://www.python.org", "usage": "Langage d'exécution de l'API."},
]


# Libellés de classificateurs PyPI ramenés à leur nom court
ALIASES = {
    "MIT License": "MIT",
    "BSD License": "BSD",
    "Apache Software License": "Apache",
    "ISC License (ISCL)": "ISC",
    "Python Software Foundation License": "PSF-2.0",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
}


def _license_of(dist: md.Distribution) -> str:
    name = _raw_license(dist)
    return ", ".join(ALIASES.get(part.strip(), part.strip()) for part in name.split(","))


def _raw_license(dist: md.Distribution) -> str:
    meta = dist.metadata
    expression = meta.get("License-Expression")
    if expression:
        return expression
    raw = (meta.get("License") or "").strip()
    first_line = raw.splitlines()[0][:80] if raw else ""
    if first_line and first_line.upper() != "UNKNOWN" and len(raw) < 120:
        return first_line
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    found = ", ".join(c for c in classifiers if c != "OSI Approved") or first_line
    return found or _license_from_file(dist) or "Voir le paquet"


# Texte de licence joint au paquet, quand les métadonnées ne la nomment pas
LICENSE_SIGNATURES = (
    ("Permission is hereby granted, free of charge", "MIT"),
    ("Apache License", "Apache-2.0"),
    ("Redistribution and use in source and binary forms", "BSD"),
    ("GNU LESSER GENERAL PUBLIC LICENSE", "LGPL"),
    ("GNU GENERAL PUBLIC LICENSE", "GPL"),
    ("Mozilla Public License", "MPL-2.0"),
)


def _license_from_file(dist: md.Distribution) -> Optional[str]:
    for file in dist.files or []:
        if "LICENSE" in file.name.upper() or "COPYING" in file.name.upper():
            try:
                text = file.read_text()[:4000]
            except (OSError, UnicodeDecodeError):
                continue
            for signature, name in LICENSE_SIGNATURES:
                if signature in text:
                    return name
    return None


def _homepage(dist: md.Distribution) -> Optional[str]:
    meta = dist.metadata
    if meta.get("Home-page"):
        return meta["Home-page"]
    for entry in meta.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        if label.strip().lower() in ("homepage", "home", "source", "repository", "source code"):
            return url.strip()
    return None


def copyleft_note(license_name: str) -> Optional[str]:
    upper = license_name.upper()
    for key in ("LGPL", "GPL", "MPL", "MOZILLA", "EPL", "ECLIPSE"):
        if re.search(rf"\b{key}", upper) or (key == "LGPL" and "LESSER" in upper):
            base = {"MOZILLA": "MPL", "ECLIPSE": "EPL"}.get(key, key)
            if "LESSER" in upper:
                base = "LGPL"
            return COPYLEFT_NOTES[base]
    return None


@lru_cache(maxsize=1)
def python_packages() -> list[dict]:
    rows = {}
    for dist in md.distributions():
        name = dist.metadata.get("Name")
        if not name or name.lower() in rows or name.lower() in ("pip", "setuptools", "wheel"):
            continue
        license_name = _license_of(dist)
        rows[name.lower()] = {
            "name": name,
            "version": dist.version,
            "license": license_name,
            "url": _homepage(dist),
            "note": copyleft_note(license_name),
        }
    return sorted(rows.values(), key=lambda r: r["name"].lower())
