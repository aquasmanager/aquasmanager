"""
Journal d'activité (audit) : enregistre chaque requête d'écriture réussie
(POST / PUT / PATCH / DELETE) avec l'utilisateur, une action lisible,
l'élément concerné et un résumé des champs envoyés. Les tentatives de
connexion échouées sont aussi tracées.

Jamais de mot de passe ni de jeton dans le journal : les clés sensibles sont
retirées du résumé, et les envois de fichiers (photos, PDF, sauvegardes) ne
sont pas lus.
"""

import asyncio
import json
import logging
from typing import Optional
from urllib.parse import parse_qs

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.routing import Match

from middleware.database import SessionLocal
from models.audit_log import AuditLog
from settings import settings

logger = logging.getLogger(__name__)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Requêtes techniques sans intérêt pour le journal
IGNORED_PATHS = {"/refresh", "/chat/", "/chat"}
SENSITIVE_KEYS = ("password", "token", "secret", "signature", "buyer")
MAX_DETAILS_LENGTH = 1000

# Premier segment de l'URL -> (type d'élément, libellé avec article)
ENTITIES = {
    "aquariums": ("aquarium", "l'aquarium"),
    "purchase-documents": ("purchase_document", "le document d'achat"),
    "equipments": ("equipment", "l'équipement"),
    "sensors": ("sensor", "le capteur"),
    "controllers": ("controller", "le contrôleur"),
    "fishes": ("fish", "le poisson"),
    "corals": ("coral", "le corail"),
    "plants": ("plant", "la plante"),
    "invertebrates": ("invertebrate", "l'invertébré"),
    "other_alives": ("invertebrate", "l'invertébré"),  # ancienne route
    "rules": ("rule", "la règle"),
    "lights": ("light", "la lampe"),
    "equipment-groups": ("equipment_group", "le groupe"),
    "maintenance-tasks": ("task", "la tâche"),
    "inventory-items": ("inventory_item", "l'article de stock"),
    "water-parameters": ("water_parameter", "le paramètre d'eau"),
    "users": ("user", "l'utilisateur"),
    "dashboard-cards": ("dashboard_card", "la carte du tableau de bord"),
    "photos": ("photo", "une photo"),
    "species": ("species", "l'espèce"),
    "notification-settings": ("notification_settings", "les notifications"),
    "backup": ("backup", "la sauvegarde"),
    "metric-alerts": ("metric_alert", "l'alerte"),
    "faults": ("fault", "le défaut"),
    "controller-pins": ("controller_pin", "la broche"),
    "sensors-reading": ("sensor_reading", "le relevé de capteur"),
    "frags": ("frag", "la bouture"),
    "transfer-certificates": ("transfer_certificate", "le certificat de cession"),
    "seller-profile": ("seller_profile", "les informations du cédant"),
    "sale-locations": ("sale_location", "le lieu de vente"),
    "showcase": ("showcase", "la vitrine"),
    "equipment-usage": ("equipment", "l'usure de l'équipement"),
    "public": ("transfer_certificate", "le certificat de cession"),
}

# Actions particulières : (méthode, modèle de route) -> libellé
SPECIFIC_ACTIONS = {
    ("POST", "/login"): "Connexion",
    ("POST", "/public/certificates/{token}/sign"): "Signature d'un certificat de cession par l'acquéreur",
    ("POST", "/public/showcase/reservations"): "Réservation de boutures depuis la vitrine",
    ("POST", "/showcase/reservations/{reservation_id}/confirm"): "Réservation confirmée (certificat créé)",
    ("POST", "/transfer-certificates/{certificate_id}/renew-link"): "Nouveau lien de signature du certificat",
    ("POST", "/transfer-certificates/offline"): "Vente signée hors connexion synchronisée",
    ("POST", "/logout"): "Déconnexion",
    ("POST", "/change-password"): "Changement de son mot de passe",
    ("POST", "/register"): "Création de l'utilisateur",
    ("POST", "/users/{user_id}/reset-password"): "Réinitialisation du mot de passe",
    ("POST", "/equipments/{equipment_id}/toggle"): "Marche forcée de l'équipement",
    ("PATCH", "/equipments/{equipment_id}/mode"): "Changement de mode de l'équipement",
    ("POST", "/equipments/{equipment_id}/fault/clear"): "Réinitialisation du défaut de l'équipement",
    ("POST", "/controllers/{controller_id}/flash"): "Flash du contrôleur",
    ("POST", "/controllers/{controller_id}/sync_success"): "Contrôleur marqué à jour",
    ("POST", "/controllers/{ctrl_id}/modules"): "Ajout d'un module d'extension",
    ("DELETE", "/controllers/{ctrl_id}/modules/{address}"): "Suppression d'un module d'extension",
    ("POST", "/equipment-groups/{group_id}/toggle"): "Commande du groupe",
    ("POST", "/equipment-groups/{group_id}/mode"): "Changement de mode du groupe",
    ("POST", "/maintenance-tasks/{task_id}/complete"): "Tâche marquée comme faite",
    ("DELETE", "/maintenance-tasks/{task_id}/completions/{completion_id}"): "Suppression d'une réalisation de tâche",
    ("POST", "/inventory-items/{item_id}/movements"): "Mouvement de stock",
    ("POST", "/water-parameters/{param_id}/readings"): "Nouveau relevé",
    ("PATCH", "/water-parameters/{param_id}/readings/{reading_id}"): "Modification d'un relevé",
    ("DELETE", "/water-parameters/{param_id}/readings/{reading_id}"): "Suppression d'un relevé",
    ("POST", "/water-parameters/readings/batch"): "Saisie groupée de relevés",
    ("POST", "/water-parameters/apply-default-targets"): "Cibles par défaut appliquées",
    ("POST", "/water-parameters/icp-batches/"): "Import d'une analyse ICP",
    ("DELETE", "/water-parameters/icp-batches/{batch_id}"): "Suppression d'une analyse ICP",
    ("POST", "/lights/{light_id}/control"): "Commande de la lampe",
    ("POST", "/lights/{light_id}/demo"): "Démo de la lampe",
    ("DELETE", "/lights/{light_id}/demo"): "Arrêt de la démo de la lampe",
    ("POST", "/lights/{light_id}/apply-profile"): "Profil appliqué à la lampe",
    ("POST", "/lights/{light_id}/copy-schedule"): "Programme copié entre canaux",
    ("PUT", "/lights/channels/{channel_id}/schedule"): "Programme d'un canal modifié",
    ("POST", "/backup/export"): "Export d'une sauvegarde",
    ("POST", "/backup/import"): "Restauration d'une sauvegarde",
    ("POST", "/notification-settings/test"): "Test des notifications",
    ("POST", "/metric-alerts/{alert_id}/acknowledge"): "Alerte acquittée",
    ("POST", "/faults/{fault_id}/acknowledge"): "Défaut acquitté",
    ("PATCH", "/photos/{entity_type}/{entity_id}/{photo_id}/main"): "Photo principale changée",
}

VERBS = {"POST": "Création de", "PUT": "Modification de", "PATCH": "Modification de", "DELETE": "Suppression de"}


def _label_resolvers():
    """(modèle, attribut) par type d'élément, pour nommer l'élément concerné."""
    from models import (
        Aquarium, Controller, Coral, Equipment, EquipmentGroup, Fish, InventoryItem, Light,
        Frag, Invertebrate, MaintenanceTask, Plant, TransferCertificate, Rule, Sensor, User, WaterParameter, DashboardCard,
    )

    return {
        "aquarium": (Aquarium, "name"),
        "equipment": (Equipment, "name"),
        "sensor": (Sensor, "name"),
        "controller": (Controller, "name"),
        "fish": (Fish, "name"),
        "coral": (Coral, "name"),
        "plant": (Plant, "name"),
        "invertebrate": (Invertebrate, "name"),
        "rule": (Rule, "name"),
        "light": (Light, "name"),
        "equipment_group": (EquipmentGroup, "name"),
        "task": (MaintenanceTask, "title"),
        "inventory_item": (InventoryItem, "name"),
        "water_parameter": (WaterParameter, "name"),
        "user": (User, "username"),
        "dashboard_card": (DashboardCard, "title"),
        "frag": (Frag, "reference"),
        "transfer_certificate": (TransferCertificate, "number"),
    }


def _describe(method: str, template: str) -> tuple[str, Optional[str]]:
    segment = template.strip("/").split("/")[0]
    entity_type, entity_label = ENTITIES.get(segment, (None, None))
    action = SPECIFIC_ACTIONS.get((method, template))
    if action is None:
        verb = VERBS.get(method, method)
        action = f"{verb} {entity_label}" if entity_label else f"{method} {template}"
    return action[:120], entity_type


def _clean_details(data: dict) -> dict:
    cleaned = {}
    for key, value in data.items():
        if any(word in key.lower() for word in SENSITIVE_KEYS):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            cleaned[key] = value
        elif isinstance(value, list) and len(value) <= 20:
            cleaned[key] = value
        elif isinstance(value, dict):
            cleaned[key] = _clean_details(value)
    return cleaned


def _identity(request: Request) -> tuple[Optional[int], Optional[str]]:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None, None
    try:
        payload = jwt.decode(header[7:], settings.secret_key, algorithms=["HS256"])
        return payload.get("user_id"), payload.get("username")
    except jwt.PyJWTError:
        return None, None


def _write(entry: dict) -> None:
    db = SessionLocal()
    try:
        if entry.get("entity_label") is None and entry.get("entity_id") and entry.get("entity_type"):
            resolver = _label_resolvers().get(entry["entity_type"])
            if resolver:
                model, attribute = resolver
                item = db.query(model).filter(model.id == entry["entity_id"]).first()
                if item is not None:
                    entry["entity_label"] = str(getattr(item, attribute))[:120]
        if entry.get("user_id") is None and entry.get("username"):
            from models import User

            user = db.query(User).filter(User.username == entry["username"]).first()
            entry["user_id"] = user.id if user else None
        db.add(AuditLog(**entry))
        db.commit()
    except Exception:
        logger.exception("Écriture du journal d'activité impossible")
    finally:
        db.close()


def _resolve_label_before(entry: dict) -> None:
    """Nom de l'élément avant l'action (indispensable pour une suppression)."""
    resolver = _label_resolvers().get(entry.get("entity_type") or "")
    if not resolver or not entry.get("entity_id"):
        return
    model, attribute = resolver
    db = SessionLocal()
    try:
        item = db.query(model).filter(model.id == entry["entity_id"]).first()
        if item is not None:
            entry["entity_label"] = str(getattr(item, attribute))[:120]
    finally:
        db.close()


def _leaf_routes(routes):
    """Routes finales de l'application. Depuis FastAPI 0.14x, un routeur inclus reste un bloc
    (_IncludedRouter) au lieu d'être mis à plat : on descend dans son routeur d'origine. Nos routeurs
    portent leur préfixe (APIRouter(prefix=...)), leurs routes ont donc déjà le chemin complet."""
    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _leaf_routes(inner.routes)
        else:
            yield route


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in WRITE_METHODS or request.url.path in IGNORED_PATHS:
            return await call_next(request)

        template, path_params = None, {}
        for route in _leaf_routes(request.app.router.routes):
            match, child_scope = route.matches(request.scope)
            if match == Match.FULL:
                template = getattr(route, "path", None)
                path_params = child_scope.get("path_params", {})
                break
        if template is None:
            return await call_next(request)

        action, entity_type = _describe(request.method, template)
        entity_id = next((int(v) for v in path_params.values() if str(v).isdigit()), None)
        user_id, username = _identity(request)

        details: dict = {}
        content_type = request.headers.get("content-type", "")
        # Pages publiques : ni jeton (dans l'URL) ni données de l'acquéreur au journal
        public = template.startswith("/public/")
        if not public and "application/json" in content_type:
            try:
                body = json.loads(await request.body() or b"null")
                if isinstance(body, dict):
                    details = _clean_details(body)
            except (ValueError, UnicodeDecodeError):
                pass
        elif template == "/login" and "application/x-www-form-urlencoded" in content_type:
            form = parse_qs((await request.body()).decode("utf-8", "replace"))
            username = (form.get("username") or [None])[0]

        entry = {
            "user_id": user_id,
            "username": username,
            "method": request.method,
            "path": (template if public else request.url.path)[:255],
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_label": None,
            "details": None,
            "status_code": 0,
            "client_ip": request.client.host if request.client else None,
        }
        if request.method in {"PATCH", "PUT", "DELETE"} or entity_id:
            await asyncio.to_thread(_resolve_label_before, entry)
        if entry["entity_label"] is None:
            for key in ("name", "title", "username", "common_name"):
                if isinstance(details.get(key), str):
                    entry["entity_label"] = details[key][:120]
                    break

        response = await call_next(request)

        failed_login = template == "/login" and response.status_code in (400, 401)
        if response.status_code >= 400 and not failed_login:
            return response
        if failed_login:
            entry["action"] = "Échec de connexion"
        entry["status_code"] = response.status_code
        if details:
            entry["details"] = json.dumps(details, ensure_ascii=False, default=str)[:MAX_DETAILS_LENGTH]
        await asyncio.to_thread(_write, entry)
        return response
