"""
demo.py

Instance de démonstration publique (réglage demo: true, ex. demo.aquasmanager.fr) :
- données fictives créées au démarrage puis remises à zéro chaque nuit ;
- compte « demo » (mot de passe affiché sur la page de connexion) ;
- pas de broker MQTT : un contrôleur simulé répond aux commandes et les
  sondes publient des valeurs plausibles ;
- tout ce qui touche au serveur, aux comptes, aux notifications ou au réseau
  (sauvegardes, flash, caméras, assistant...) est refusé.

Les données sont créées en appelant l'API elle-même : broches, noms techniques
et cartes du tableau de bord sont cohérents avec une vraie installation.
"""

import logging
import math
import random
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import bcrypt
from sqlalchemy import text
from starlette.responses import JSONResponse

from middleware.database import Base, SessionLocal, engine
from models.controller import Controller
from models.sensor import Sensor
from models.sensor_reading import SensorReading
from models.user import User, UserRole
from settings import settings

logger = logging.getLogger(__name__)

DEMO_CONTROLLER = "esp-salon"
# Photos du domaine public (Wikimedia Commons), voir demo/photos/CREDITS.md
PHOTOS_DIR = Path(__file__).resolve().parent.parent / "demo" / "photos"
UPLOADS_DIR = Path("uploads")

# --- Garde-fous ---

# (méthodes, motif du chemin) refusés dans la démo ; None = toutes les méthodes
_BLOCKED = [
    (None, r"/backup(/.*)?"),
    (None, r"/assistant(/.*)?"),
    (None, r"/chat(/.*)?"),
    (None, r"/notification-settings(/.*)?"),
    (None, r"/push/.*"),
    (None, r"/register"),
    (None, r"/change-password"),
    (None, r"/license(/.*)?"),
    ({"POST", "PUT", "PATCH", "DELETE"}, r"/users(/.*)?"),
    ({"POST", "PUT", "PATCH", "DELETE"}, r"/cameras(/.*)?"),
    ({"POST", "PUT", "PATCH", "DELETE"}, r"/controllers/[^/]+/flash"),
    ({"PUT", "PATCH"}, r"/me/.*"),
    # Annonces réelles sur le hub de l'éditeur : pas depuis la démo publique
    ({"POST", "PUT", "PATCH", "DELETE"}, r"/group-orders(/.*)?"),
]
_BLOCKED_RE = [(methods, re.compile(f"^{pattern}/?$")) for methods, pattern in _BLOCKED]
# Lectures faites par l'appli à l'ouverture
_ALLOWED = [
    ("GET", re.compile(r"^/license/?$")),
    # État de l'assistant (lu à l'ouverture de l'appli : « indisponible »)
    ("GET", re.compile(r"^/assistant/status/?$")),
    ("PUT", re.compile(r"^/me/language/?$")),
    # Commandes groupées : choisir ses départements (annonces d'exemple, voir demo_group_orders_hub)
    ("PUT", re.compile(r"^/group-orders/settings/?$")),
]

BLOCKED_DETAIL = "Indisponible dans la démo : installe AquasManager chez toi pour l'utiliser."


def is_blocked(method: str, path: str) -> bool:
    if any(method == m and r.match(path) for m, r in _ALLOWED):
        return False
    return any((methods is None or method in methods) and r.match(path) for methods, r in _BLOCKED_RE)


class DemoGuardMiddleware:
    """Refuse (403) les routes indisponibles dans la démo."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and is_blocked(scope["method"], scope["path"]):
            response = JSONResponse({"detail": BLOCKED_DETAIL}, status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


# --- Contrôleur simulé ---


def echo_command(driver, topic: str, payload) -> None:
    """Réponse du contrôleur simulé à une commande publiée (marche/arrêt, mode)."""
    parts = topic.split("/")
    value = payload.decode() if isinstance(payload, bytes) else str(payload)
    # <préfixe>/<contrôleur>/switch/<nom>/command -> .../state
    if len(parts) == 5 and parts[2] == "switch" and parts[4] == "command" and value in ("ON", "OFF"):
        _inject(driver, "/".join(parts[:4] + ["state"]), value)
    # <préfixe>/<contrôleur>/switch/<nom>/mode/set -> .../mode
    elif len(parts) == 6 and parts[2] == "switch" and parts[4:] == ["mode", "set"]:
        _inject(driver, "/".join(parts[:4] + ["mode"]), value)


def _inject(driver, topic: str, value: str) -> None:
    try:
        driver.on_message(None, None, SimpleNamespace(topic=topic, payload=value.encode()))
    except Exception:
        logger.exception("Démo : réponse simulée à %s", topic)


def _probe_value(sensor: Sensor, when: datetime) -> Optional[float]:
    """Valeur plausible : température qui suit le jour et la nuit, flotteur au niveau haut."""
    if sensor.type == "binary_sensor":
        return 1.0
    hour = when.hour + when.minute / 60
    base = 25.4 if sensor.id % 2 else 24.6
    return round(base + 0.35 * math.sin((hour - 9) / 24 * 2 * math.pi) + random.uniform(-0.05, 0.05), 2)


def simulate_sensors(driver) -> None:
    """Une mesure par sonde, enregistrée et diffusée comme si elle venait du contrôleur."""
    db = SessionLocal()
    try:
        now = datetime.now()
        for sensor in db.query(Sensor).all():
            value = _probe_value(sensor, now)
            if value is None:
                continue
            sensor_id, final = driver._save_sensor_reading(db, sensor.controller_id, sensor.technical_name, value)
            if sensor_id:
                driver._broadcast_to_ws({
                    "type": "SENSOR_READING",
                    "sensor_id": sensor_id,
                    "controller_id": str(sensor.controller_id),
                    "sensor_name": sensor.technical_name,
                    "value": final,
                })
        controller = db.query(Controller).filter(Controller.name == DEMO_CONTROLLER).first()
        if controller and controller.status != "ONLINE":
            controller.status = "ONLINE"
            db.commit()
    finally:
        db.close()


# --- Remise à zéro ---


def _wipe() -> None:
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        if conn.execute(text("SELECT 1 FROM sqlite_master WHERE name = 'sqlite_sequence'")).first():
            conn.execute(text("DELETE FROM sqlite_sequence"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
    if UPLOADS_DIR.is_dir():
        for entry in UPLOADS_DIR.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)


def _restore_catalog() -> None:
    """Catalogue d'espèces d'origine (les visiteurs ont pu le modifier), puis catalogue en ligne."""
    from services.catalog_sync import sync_catalog, sync_enabled
    from services.species_catalog import seed_species_catalog

    db = SessionLocal()
    try:
        seed_species_catalog(db)
        if sync_enabled():
            try:
                sync_catalog(db)
            except Exception:
                logger.warning("Démo : catalogue en ligne indisponible, catalogue intégré seulement")
    finally:
        db.close()


def _create_users() -> int:
    """Compte admin inutilisable (mot de passe aléatoire) et compte de démonstration."""
    import secrets

    db = SessionLocal()
    try:
        def hashed(password: str) -> str:
            return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        admin = User(username="admin", password=hashed(secrets.token_urlsafe(24)), role=UserRole.admin,
                     must_change_password=False)
        demo = User(username=settings.demo_username, password=hashed(settings.demo_password),
                    role=UserRole.manager, must_change_password=False)
        db.add_all([admin, demo])
        db.commit()
        return admin.id
    finally:
        db.close()


def reset_demo(app) -> None:
    """Efface tout et recrée les données de démonstration."""
    from fastapi.testclient import TestClient
    from middleware.auth import create_access_token

    logger.info("Démo : remise à zéro des données")
    _wipe()
    _restore_catalog()
    admin_id = _create_users()
    token = create_access_token(admin_id, "admin", "admin")
    client = TestClient(app, raise_server_exceptions=True)
    client.headers["Authorization"] = f"Bearer {token}"
    seed(_Api(client))
    _backfill_sensor_history()
    logger.info("Démo : données prêtes")


def seconds_until_reset(now: Optional[datetime] = None) -> float:
    """Délai jusqu'à la prochaine remise à zéro (demo_reset_hour, heure locale de l'installation)."""
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(settings.timezone)
    now = now or datetime.now(tz)
    target = now.replace(hour=settings.demo_reset_hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


class _Api:
    def __init__(self, client):
        self.client = client

    def _check(self, response):
        if response.status_code >= 400:
            raise RuntimeError(f"Démo : {response.request.method} {response.request.url.path} -> "
                               f"{response.status_code} {response.text[:300]}")
        return response.json() if response.content else None

    def get(self, url, **params):
        return self._check(self.client.get(url, params=params))

    def post(self, url, body=None):
        return self._check(self.client.post(url, json=body))

    def put(self, url, body=None):
        return self._check(self.client.put(url, json=body))

    def patch(self, url, body=None):
        return self._check(self.client.patch(url, json=body))

    def upload(self, url, field, files):
        return self._check(self.client.post(url, files=[(field, f) for f in files]))


def _days_ago(days: float, hour: int = 19) -> str:
    when = datetime.now() - timedelta(days=days)
    return when.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


def seed(api: _Api) -> dict:
    """Deux aquariums complets, un contrôleur, des relevés sur deux mois."""
    random.seed(42)
    reef = api.post("/aquariums/", {"name": "Récif", "volume": 450, "water_type": "sea", "biotope": "Récif mixte",
                                    "date_creation": _days_ago(400)[:10]})
    planted = api.post("/aquariums/", {"name": "Bac planté", "volume": 180, "water_type": "pure",
                                       "biotope": "Amazonien", "date_creation": _days_ago(250)[:10]})

    ctrl = api.post("/controllers/", {"name": DEMO_CONTROLLER, "type": "ESP32", "zone": "Salon", "ip": "192.168.1.60"})
    api.patch(f"/controllers/{ctrl['id']}", {"rtc_model": "DS3231"})
    pins = {p["pin_number"]: p["id"] for p in api.get(f"/controllers/{ctrl['id']}/pins")["controller_pins"]
            if p["module_id"] is None}

    # Sondes et flotteur
    def sensor(aquarium, name, pin, **extra):
        return api.post("/sensors/", {"aquarium_id": aquarium["id"], "controller_id": ctrl["id"], "name": name,
                                      "pin_id": pins[pin], **extra})

    temp_reef = sensor(reef, "Température", "4", type="sensor", unit="temperature", address="0x28aa1c7e0b00004f")
    temp_planted = sensor(planted, "Température", "4", type="sensor", unit="temperature",
                          address="0x28ff3d9a0c000012")
    level = sensor(reef, "Niveau décantation", "14", type="binary_sensor", unit="level")

    # Équipements
    def equipment(aquarium, name, pin, category, status="ON", **extra):
        return api.post("/equipments/", {"name": name, "aquarium_id": aquarium["id"], "controller_id": ctrl["id"],
                                         "pin_id": pins[pin], "physical_contact": "NO", "status": status,
                                         "mode": "AUTO", "category": category, **extra})

    pump = equipment(reef, "Brassage", "5", "BRASSAGE")
    skimmer = equipment(reef, "Écumeur", "13", "ECUMOR")
    osmo = equipment(reef, "Osmolateur", "18", "OSMOLATOR", status="OFF", max_duration_seconds=45)
    heater = equipment(reef, "Chauffage", "19", "HEATER", status="OFF")
    planted_filter = equipment(planted, "Filtre", "23", "PUMP")
    co2 = equipment(planted, "CO2", "32", "OTHER")

    # Groupes : tout arrêter d'un geste (changement d'eau)
    api.post("/equipment-groups/", {"name": "Maintenance", "equipment_ids": [pump["id"], skimmer["id"], osmo["id"],
                                                                           heater["id"]]})
    api.post("/equipment-groups/", {"name": "Maintenance", "equipment_ids": [planted_filter["id"], co2["id"]]})

    api.post("/rules/", {"name": "Pause nourrissage", "action": "OFF", "equipment_id": pump["id"],
                         "revert_on_exit": True,
                         "conditions": [{"condition_type": "TIME_RANGE", "start_time": "12:00", "end_time": "12:15"}]})
    api.post("/rules/", {"name": "Appoint d'eau osmosée", "action": "ON", "equipment_id": osmo["id"],
                         "revert_on_exit": True,
                         "conditions": [{"condition_type": "SENSOR_STATE", "sensor_id": level["id"],
                                         "trigger_state": "LOW"}]})

    # Éclairage : lever et coucher progressifs
    def schedule(peak, start=600, end=1290):
        mid = (start + end) // 2
        return [{"minute": start, "intensity": 0}, {"minute": start + 90, "intensity": peak // 2},
                {"minute": mid, "intensity": peak}, {"minute": end - 90, "intensity": peak // 2},
                {"minute": end, "intensity": 0}]

    reef_light = api.post("/lights/", {"name": "Rampe LED", "aquarium_id": reef["id"], "controller_id": ctrl["id"]})
    for name, pin, color, spectrum, peak in (("Bleus", "25", "#3b5bff", "royal_blue", 80),
                                             ("Blancs", "26", "#f5f7ff", "white", 55)):
        light = api.post(f"/lights/{reef_light['id']}/channels",
                         {"name": name, "pin_id": pins[pin], "color": color, "spectrum": spectrum})
        channel = next(c for c in light["channels"] if c["name"] == name)
        api.put(f"/lights/channels/{channel['id']}/schedule", schedule(peak))
    planted_light = api.post("/lights/", {"name": "Rampe", "aquarium_id": planted["id"], "controller_id": ctrl["id"]})
    light = api.post(f"/lights/{planted_light['id']}/channels",
                     {"name": "Blanc", "pin_id": pins["27"], "color": "#fff6e0", "spectrum": "white"})
    api.put(f"/lights/channels/{light['channels'][0]['id']}/schedule", schedule(70, start=660, end=1260))

    # Paramètres d'eau : deux mois de tests, nitrates qui montent doucement
    # (nom, unité, valeur moyenne, écart, dérive par jour, favori, cible)
    reef_params = [("KH", "°dKH", 8.2, 0.25, 0, True, None), ("Ca", "mg/l", 425, 8, 0, True, None),
                   ("Mg", "mg/l", 1340, 25, 0, False, None), ("NO3", "mg/l", 6, 1.2, 0.09, True, None),
                   ("PO4", "mg/l", 0.06, 0.015, 0, True, None),
                   # Oligo-éléments (comme un ICP), un peu bas : calculateur de dosage
                   ("Mn", "µg/l", 0.35, 0.05, 0, False, None), ("I", "µg/l", 46, 3, 0, False, None)]
    planted_params = [("pH", None, 6.9, 0.1, 0, True, (6.5, 7.2)), ("GH", "°dGH", 7, 0.5, 0, True, (5, 10)),
                      ("KH", "°dKH", 4, 0.4, 0, False, (3, 6)), ("NO3", "mg/l", 15, 3, 0, True, (5, 25))]
    for aquarium, params, every in ((reef, reef_params, 3), (planted, planted_params, 7)):
        for name, unit, mid, spread, drift, pinned, target in params:
            param = api.post("/water-parameters/", {
                "aquarium_id": aquarium["id"], "name": name, "unit": unit, "pinned": pinned,
                "target_min": target[0] if target else None, "target_max": target[1] if target else None})
            # Marche aléatoire ramenée vers la moyenne : des courbes réalistes, pas du bruit
            offset = 0.0
            for days in range(60, -1, -every):
                offset = 0.6 * offset + random.gauss(0, spread * 0.5)
                value = mid + drift * (60 - days) + max(-spread, min(spread, offset))
                api.post(f"/water-parameters/{param['id']}/readings",
                         {"value": round(value, 3 if mid < 1 else 1), "timestamp": _days_ago(days)})
    api.post(f"/water-parameters/apply-default-targets?aquarium_id={reef['id']}")

    # Vivant
    # (photo, entité) ajoutées ensuite
    photos: list[tuple[str, str, int]] = [("reef", "aquariums", reef["id"]), ("planted", "aquariums", planted["id"])]
    corals = {}
    for coral in (
        ("acropora", "Acropora millepora", "Acropora millepora", "Acroporidae", "SPS", (8, 13), (6, 9), 3, CITES[0]),
        ("euphyllia", "Euphyllia paraancora", "Euphyllia paraancora", "Euphylliidae", "LPS", (3, 6), (3, 6), 7, CITES[1]),
        ("zoanthus", "Zoanthus Utter Chaos", "Zoanthus sp.", "Zoanthidae", "MOU", (2, 7), (2, 6), 4, ""),
        ("montipora", "Montipora digitata", "Montipora digitata", "Acroporidae", "SPS", (6, 11), (5, 8), 2, CITES[2]),
    ):
        key, name, scientific, family, kind, light_range, flow, aggressiveness, cites = coral
        created = api.post("/corals/", {
            "aquarium_id": reef["id"], "name": name, "type": kind, "scientific_name": scientific,
            "family": family, "origin": "Mariculture", "cites": cites,
            "acquired_from": "Récif Passion" if cites else "Bourse aux boutures",
            "light_range": {"min": light_range[0], "max": light_range[1]},
            "brewing_range": {"min": flow[0], "max": flow[1]},
            "aggressiveness_level": aggressiveness, "resistance_level": 5, "location_level": 6,
            "date_acquisition": _days_ago(random.randint(30, 300))[:10]})
        corals[key] = created
        photos.append((key, "corals", created["id"]))
    fishes = {}
    for key, aquarium, name, scientific, family, quantity, height, volume in (
        ("clownfish", reef, "Poisson-clown", "Amphiprion ocellaris", "Pomacentridae", 2, 8, 80),
        ("tang", reef, "Chirurgien jaune", "Zebrasoma flavescens", "Acanthuridae", 1, 20, 400),
        ("neon", planted, "Néon bleu", "Paracheirodon innesi", "Characidae", 15, 4, 60),
        ("corydoras", planted, "Corydoras sterbai", "Corydoras sterbai", "Callichthyidae", 6, 5, 60),
    ):
        created = api.post("/fishes/", {"aquarium_id": aquarium["id"], "name": name, "quantity": quantity,
                                        "scientific_name": scientific, "family": family, "origin": "Élevage",
                                        "max_height": height, "min_volume": volume, "reef_safe": True,
                                        "date_acquisition": _days_ago(random.randint(30, 300))[:10]})
        fishes[key] = created
        photos.append((key, "fishes", created["id"]))
    for key, aquarium, name, scientific, family, quantity in (
        (None, reef, "Crevette nettoyeuse", "Lysmata amboinensis", "Lysmatidae", 2),
        (None, reef, "Escargot Turbo", "Turbo fluctuosa", "Turbinidae", 5),
        ("amano", planted, "Crevette Amano", "Caridina multidentata", "Atyidae", 8),
    ):
        created = api.post("/invertebrates/", {"aquarium_id": aquarium["id"], "name": name, "quantity": quantity,
                                               "scientific_name": scientific, "family": family, "origin": "Élevage",
                                               "date_acquisition": _days_ago(random.randint(30, 300))[:10]})
        if key:
            photos.append((key, "invertebrates", created["id"]))
    for key, name, scientific, family, growing, location, height in (
        ("anubias", "Anubias nana", "Anubias barteri var. nana", "Araceae", "slow", "front", 10),
        ("crypto", "Cryptocoryne wendtii", "Cryptocoryne wendtii", "Araceae", "slow", "middle", 15),
        ("rotala", "Rotala rotundifolia", "Rotala rotundifolia", "Lythraceae", "fast", "back", 40),
    ):
        created = api.post("/plants/", {"aquarium_id": planted["id"], "name": name, "scientific_name": scientific,
                                        "family": family, "origin": "Culture in vitro",
                                        "light_range": {"min": 3, "max": 7},
                                        "temperature_range": {"min": 22, "max": 28}, "growing": growing,
                                        "resistance_level": 7, "max_height": height, "location": location,
                                        "date_acquisition": _days_ago(random.randint(30, 200))[:10]})
        photos.append((key, "plants", created["id"]))

    for key, entity, entity_id in photos:
        path = PHOTOS_DIR / f"{key}.jpg"
        if path.exists():
            api.upload(f"/photos/{entity}/{entity_id}", "file", [(path.name, path.read_bytes(), "image/jpeg")])
    # Acropora : une photo plus ancienne en plus (comparaison « avant / après »)
    before = PHOTOS_DIR / "acropora_before.jpg"
    if before.exists():
        api.client.post(f"/photos/corals/{corals['acropora']['id']}",
                        files=[("file", (before.name, before.read_bytes(), "image/jpeg"))],
                        data={"taken_at": _days_ago(95, hour=20)})

    _purchase_documents(api, corals, fishes)
    _frags(api, corals)

    # Entretien et stock
    tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    for aquarium, title, recurrence, days, due in (
        (reef, "Changement d'eau 10 %", "weekly", None, tomorrow),
        (reef, "Nettoyer le godet de l'écumeur", "custom_days", 3, datetime.now().replace(hour=8, minute=0)),
        (reef, "Tester KH et calcium", "custom_days", 3, tomorrow),
        (planted, "Taille des plantes", "custom_days", 14, tomorrow + timedelta(days=4)),
        (planted, "Changement d'eau 30 %", "weekly", None, tomorrow + timedelta(days=2)),
    ):
        api.post("/maintenance-tasks/", {"aquarium_id": aquarium["id"], "title": title, "recurrence": recurrence,
                                         "recurrence_days": days, "next_due_at": due.isoformat()})
    for aquarium, name, unit, quantity, threshold in (
        (reef, "Sel récifal", "kg", 25, 5),
        (reef, "Réactif KH", "tests", 8, 10),
        (reef, "Nourriture congelée", "plaquettes", 22, 6),
        (planted, "Engrais liquide", "mL", 380, 100),
    ):
        api.post("/inventory-items/", {"aquarium_id": aquarium["id"], "name": name, "unit": unit,
                                       "quantity": quantity, "low_stock_threshold": threshold})

    # Tableau de bord du récif : température, niveau, pilotage
    for card in (
        {"title": "Température", "type": "temperature", "icon": "thermostat", "sensor_id": temp_reef["id"],
         "unit": "°C", "period": "24h", "target_min": 24.5, "target_max": 26.5},
        {"title": "Décantation", "type": "binary_level", "icon": "water", "sensor_id": level["id"],
         "normal_state": "HIGH"},
        {"title": "Pilotage", "type": "equipment", "icon": "toggle_on", "equipment_ids": [pump["id"], osmo["id"]]},
    ):
        api.post("/dashboard-cards/", {"aquarium_id": reef["id"], **card})
    api.post("/dashboard-cards/", {"aquarium_id": planted["id"], "title": "Température", "type": "temperature",
                                   "icon": "thermostat", "sensor_id": temp_planted["id"], "unit": "°C",
                                   "period": "24h", "target_min": 23.5, "target_max": 26})
    _journal(api, reef, planted)
    _group_order_links()
    return {"reef": reef, "planted": planted, "controller": ctrl}


# Numéros CITES fictifs (format français), repris par la facture du magasin
CITES = ["FR2601234567", "FR2601234568", "FR2601234569"]


def _pdf(title: str, issuer: str, lines: list[tuple[str, str, str]], footer: str) -> bytes:
    """Document PDF fictif, marqué comme tel sur chaque page."""
    import io

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    c.saveState()
    c.setFont("Helvetica-Bold", 46)
    c.setFillColor(colors.Color(0.85, 0.2, 0.2, alpha=0.18))
    c.translate(width / 2, height / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, "DOCUMENT FICTIF")
    c.restoreState()
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 70, issuer)
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 88, "Entreprise fictive - démonstration AquasManager")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 130, title)
    y = height - 170
    c.setFont("Helvetica-Bold", 10)
    for x, label in ((50, "Désignation"), (330, "N° CITES"), (480, "Montant")):
        c.drawString(x, y, label)
    c.line(50, y - 4, width - 50, y - 4)
    c.setFont("Helvetica", 10)
    for name, cites, price in lines:
        y -= 20
        c.drawString(50, y, name)
        c.drawString(330, y, cites)
        c.drawRightString(width - 50, y, price)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, 60, footer)
    c.showPage()
    c.save()
    return buffer.getvalue()


def _purchase_documents(api: _Api, corals: dict, fishes: dict) -> None:
    """Facture CITES (liée aux coraux par leurs numéros), certificat de cession, facture de poissons."""
    invoice = api.post("/purchase-documents/", {
        "title": "Facture Récif Passion", "supplier": "Récif Passion (magasin fictif)",
        "purchase_date": _days_ago(120)[:10], "reference": "FA-2026-0412", "cites_numbers": CITES,
        "notes": "Coraux de mariculture, permis CITES joints à la facture."})
    api.upload(f"/purchase-documents/{invoice['id']}/files", "files", [("facture-recif-passion.pdf", _pdf(
        "Facture FA-2026-0412", "Récif Passion",
        [("Acropora millepora (bouture)", CITES[0], "45,00 EUR"), ("Euphyllia paraancora", CITES[1], "60,00 EUR"),
         ("Montipora digitata (bouture)", CITES[2], "30,00 EUR")],
        "Document fictif créé pour la démonstration d'AquasManager."), "application/pdf")])
    certificate = api.post("/purchase-documents/", {
        "title": "Certificat de cession bourse de printemps", "supplier": "Club récifal (exemple)",
        "purchase_date": _days_ago(200)[:10], "reference": "CC-0098",
        "links": [{"entity_type": "corals", "entity_id": corals["zoanthus"]["id"]}]})
    api.upload(f"/purchase-documents/{certificate['id']}/files", "files", [("certificat-cession.pdf", _pdf(
        "Certificat de cession CC-0098", "Club récifal (exemple)",
        [("Zoanthus Utter Chaos (bouture, 5 polypes)", "-", "cession gratuite")],
        "Document fictif créé pour la démonstration d'AquasManager."), "application/pdf")])
    fish_invoice = api.post("/purchase-documents/", {
        "title": "Facture Aqua Nature", "supplier": "Aqua Nature (animalerie fictive)",
        "purchase_date": _days_ago(90)[:10], "reference": "AN-55321",
        "links": [{"entity_type": "fish", "entity_id": fishes["clownfish"]["id"]},
                  {"entity_type": "fish", "entity_id": fishes["tang"]["id"]}]})
    api.upload(f"/purchase-documents/{fish_invoice['id']}/files", "files", [("facture-aqua-nature.pdf", _pdf(
        "Facture AN-55321", "Aqua Nature",
        [("Amphiprion ocellaris x2 (élevage)", "-", "58,00 EUR"), ("Zebrasoma flavescens", "-", "89,00 EUR")],
        "Document fictif créé pour la démonstration d'AquasManager."), "application/pdf")])


def _frags(api: _Api, corals: dict) -> None:
    """Deux lots de boutures détachés des pieds mères du récif, prêts pour une bourse."""
    for key, quantity, price, days, note in (
        ("acropora", 3, 25, 24, "Bouturé à la pince, collé sur plug céramique"),
        ("zoanthus", 6, 10, 10, "Polypes séparés en petits rochers"),
    ):
        frag = api.post("/frags/", {"mother_coral_id": corals[key]["id"], "quantity": quantity, "price": price,
                                    "cut_date": _days_ago(days)[:10], "notes": note})
        path = PHOTOS_DIR / f"{key}.jpg"
        if path.exists():
            api.upload(f"/photos/frags/{frag['id']}", "file", [(path.name, path.read_bytes(), "image/jpeg")])


# --- Commandes groupées d'exemple ---
# Les vraies annonces vivent sur le hub de l'éditeur, partagé par toutes les
# installations : la démo n'y écrit jamais. Elle sert ces exemples à la place,
# dans le premier département suivi.

DEMO_DEPARTMENT = "35"
_OWNER_TOKEN = "demo-organisateur"
_MEMBER_TOKEN = "demo-participant"
_DEMO_ORDERS = [
    {"id": "demo-coraux", "title": "Coraux de mariculture : envoi groupé", "shop": "Récif Passion (exemple)",
     "area": "Rennes", "days": 12, "organizer": "Démo",
     "description": "Franco de port à 300 € : on partage les frais d'envoi. Boutures SPS et LPS, "
                    "livraison chez moi puis remise en main propre.",
     "members": [("Camille", "camille@example.org", "Merci pour l'organisation !",
                  [("Acropora tenuis (bouture)", 2), ("Euphyllia paraancora (tête)", 1)]),
                 ("Léo", "06 00 00 00 00", None, [("Zoanthus Utter Chaos (lot)", 1)])]},
    {"id": "demo-sel", "title": "Sel et additifs en seaux de 25 kg", "shop": "Aqua Fournitures (exemple)",
     "area": "Saint-Malo", "days": 6, "organizer": "Camille",
     "description": "Remise à partir de 10 seaux de sel. Retrait chez moi le samedi.",
     "members": [("Démo", "demo@example.org", None, [("Sel récifal, seau de 25 kg", 1), ("Additif KH 1 L", 2)])]},
    {"id": "demo-plantes", "title": "Plantes in vitro pour bacs plantés", "shop": "Jardin Aquatique (exemple)",
     "area": "Vitré", "days": 20, "organizer": "Léo",
     "description": "Commande de plantes in vitro, minimum 15 pots pour l'envoi gratuit.",
     "members": [("Sacha", "sacha@example.org", "Pour un 120 L planté", [("Monte Carlo in vitro", 3)])]},
]


def _order_public(order: dict, department: str) -> dict:
    created = datetime.now() - timedelta(days=3)
    return {"id": order["id"], "title": order["title"], "shop": order["shop"], "shop_url": None,
            "department": department, "area": order["area"],
            "deadline": (datetime.now() + timedelta(days=order["days"])).date().isoformat(),
            "organizer": order["organizer"], "description": order["description"], "status": "open",
            "participants": len(order["members"]), "created_at": created.isoformat()}


def _members(order: dict) -> list[dict]:
    return [{"id": f"{order['id']}-{i}", "name": name, "contact": contact, "message": message,
             "items": [{"name": item, "url": None, "quantity": quantity} for item, quantity in items],
             "created_at": (datetime.now() - timedelta(days=2, hours=i)).isoformat()}
            for i, (name, contact, message, items) in enumerate(order["members"])]


def demo_group_orders_hub(method: str, path: str, token: Optional[str] = None, **kwargs):
    """Remplace le hub dans la démo : annonces d'exemple, en lecture seule."""
    from fastapi import HTTPException

    if method != "GET":
        raise HTTPException(status_code=403, detail=BLOCKED_DETAIL)
    if path == "":
        wanted = [d for d in str((kwargs.get("params") or {}).get("departments", "")).split(",") if d]
        return [_order_public(o, wanted[0]) for o in _DEMO_ORDERS] if wanted else []
    order = next((o for o in _DEMO_ORDERS if path == f"/{o['id']}"), None)
    if order is None:
        raise HTTPException(status_code=404, detail="Commande groupée introuvable.")
    db = SessionLocal()
    try:
        from models.group_order import GroupOrderSettings

        conf = db.get(GroupOrderSettings, 1)
        department = (conf.departments or [DEMO_DEPARTMENT])[0] if conf else DEMO_DEPARTMENT
    finally:
        db.close()
    result = {**_order_public(order, department), "role": None, "contact": None, "members": []}
    members = _members(order)
    if token == _OWNER_TOKEN and order["organizer"] == "Démo":
        result.update(role="owner", contact="demo@example.org", members=members)
    elif token == _MEMBER_TOKEN:
        mine = [m for m in members if m["name"] == "Démo"]
        if mine:
            result.update(role="participant", contact=f"{order['organizer'].lower()}@example.org", members=mine)
    return result


def _group_order_links() -> None:
    """Département suivi, une annonce organisée et une commande rejointe (« Mes commandes »)."""
    from models.group_order import GroupOrderLink, GroupOrderSettings

    db = SessionLocal()
    try:
        conf = db.get(GroupOrderSettings, 1) or GroupOrderSettings(id=1)
        conf.departments = [DEMO_DEPARTMENT]
        conf.seen_ids = [o["id"] for o in _DEMO_ORDERS]
        db.merge(conf)
        db.add_all([
            GroupOrderLink(hub_id="demo-coraux", role="owner", token=_OWNER_TOKEN, title=_DEMO_ORDERS[0]["title"],
                           known_members=len(_DEMO_ORDERS[0]["members"])),
            GroupOrderLink(hub_id="demo-sel", role="participant", token=_MEMBER_TOKEN, participant_id="demo-sel-0",
                           title=_DEMO_ORDERS[1]["title"]),
        ])
        db.commit()
    finally:
        db.close()


def _journal(api: _Api, reef: dict, planted: dict) -> None:
    """Changements d'eau (sel décompté), produits de dosage, observations ; les ajouts de vivants
    et les changements d'eau s'inscrivent d'eux-mêmes au journal."""
    items = {i["name"]: i for i in api.get("/inventory-items/")}
    salt = items.get("Sel récifal")
    for days in range(56, 0, -7):
        api.post("/water-changes/", {"aquarium_id": reef["id"], "performed_at": _days_ago(days, hour=10),
                                     "volume_l": 45, "salt_item_id": salt["id"] if salt else None,
                                     "salt_amount": 1.6 if salt else None})
    for days in range(50, 0, -14):
        api.post("/water-changes/", {"aquarium_id": planted["id"], "performed_at": _days_ago(days, hour=11),
                                     "volume_l": 55, "note": "avec taille des plantes"})
    kh_stock = api.post("/inventory-items/", {"aquarium_id": reef["id"], "name": "Bicarbonate de sodium",
                                              "unit": "g", "quantity": 900, "low_stock_threshold": 200})
    api.post("/dosing/products", {"name": "Bicarbonate de sodium (NaHCO₃)", "parameter": "KH", "dose_amount": 1,
                                  "dose_unit": "g", "raises": 0.33, "per_volume_l": 100,
                                  "inventory_item_id": kh_stock["id"]})
    api.post("/dosing/products", {"name": "Chlorure de calcium dihydraté (CaCl₂·2H₂O)", "parameter": "Ca",
                                  "dose_amount": 1, "dose_unit": "g", "raises": 2.73, "per_volume_l": 100})
    for aquarium, days, category, note in (
        (reef, 45, "dosing", "KH+ : dosage passé de 15 à 20 mL par jour"),
        (reef, 38, "note", "Nourriture augmentée : congelé deux fois par jour"),
        (reef, 21, "problem", "Cyanobactéries sur le sable, brassage réorienté"),
        (reef, 9, "maintenance", "Nettoyage de l'écumeur et de la pompe de remontée"),
        (planted, 33, "dosing", "Engrais liquide : 5 mL deux fois par semaine"),
        (planted, 12, "note", "Rotala en pleine forme, première taille"),
    ):
        api.post("/journal/", {"aquarium_id": aquarium["id"], "category": category,
                               "occurred_at": _days_ago(days, hour=18), "text": note})


def _backfill_sensor_history(days: int = 7, step_minutes: int = 15) -> None:
    """Une semaine de mesures passées, pour des courbes pleines dès l'ouverture."""
    db = SessionLocal()
    try:
        now = datetime.now()
        for sensor in db.query(Sensor).all():
            rows = []
            when = now - timedelta(days=days)
            while when < now:
                value = _probe_value(sensor, when)
                if value is not None:
                    rows.append(SensorReading(sensor_id=sensor.id, value=value, timestamp=when))
                when += timedelta(minutes=step_minutes)
            db.add_all(rows)
            last = _probe_value(sensor, now)
            sensor.last_value = last
            sensor.last_reading_at = now
        controller = db.query(Controller).filter(Controller.name == DEMO_CONTROLLER).first()
        if controller:
            controller.status = "ONLINE"
            controller.is_dirty = False
        db.commit()
    finally:
        db.close()
