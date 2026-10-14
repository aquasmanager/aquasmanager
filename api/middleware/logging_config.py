"""
Journaux de l'API au format JSON, enrichis du contexte de la requête en cours.
"""

import logging
import os
import sys
from pythonjsonlogger import json
from settings import settings
from logging.handlers import RotatingFileHandler
from middleware.context import request_context

LOG_DIR = "logs/"
LOG_FILE = os.path.join(LOG_DIR, "app.json.log")


class CustomJsonFormatter(json.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        ctx = request_context.get({})
        log_record["client_ip"] = ctx.get("client_ip", "-")
        log_record["method"] = ctx.get("method", "-")
        log_record["path"] = ctx.get("path", "-")


def setup_logging():
    # Créer le dossier logs s'il n'existe pas
    os.makedirs(LOG_DIR, exist_ok=True)

    # Niveau de log
    log_level = settings.log_level.upper()

    # Format JSON
    formatter = CustomJsonFormatter("%(asctime)s [%(levelname)s] % (name)s: %(message)s")

    # Handler console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Handler fichier
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=5)
    file_handler.setFormatter(formatter)

    # Logger global
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    if settings.env == "prod":
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Une ligne par requête HTTP sortante, URL comprise : celle du flux d'une caméra
    # (go2rtc) contient ses identifiants RTSP
    logging.getLogger("httpx").setLevel(logging.WARNING)
