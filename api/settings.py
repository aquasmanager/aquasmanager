"""
Configuration de l'API : config/<ENV>.yaml, surchargé par les variables
d'environnement AQUAS_*.
"""

from pydantic import BaseModel, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os
import time
import secrets
import yaml


class DatabaseSettings(BaseModel):
    type: str = "sqlite"
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = "password"
    name: str = "AquasManager"
    sqlite_path: str = "base/AquasManager.db"

class MqttSettings(BaseModel):
    host: str = "localhost"
    port: int = 1883
    timeout: int = 60
    user: str = "user"
    password: str = "password"
    # Racine des topics MQTT. Permet de partager le même broker entre
    # environnements (ex: "aquarium" en prod, "aquarium-dev" en dev) sans
    # que l'un ne reçoive/pilote les contrôleurs de l'autre.
    topic_prefix: str = "aquarium"
    # Adresse du broker vue par les ESP32 (firmware) quand elle diffère de
    # celle utilisée par l'API (ex. Docker : l'API joint « mosquitto », les
    # ESP joignent l'IP du serveur). Vide = même adresse que host.
    device_host: str = ""

class ESPSettings(BaseModel):
    ssid: str = "SSID"
    password: str = "password"

class NetworkSettings(BaseModel):
    gateway: str = "192.168.1.254"
    subnet: str = "255.255.255.0"
    dns1: str = "192.168.1.254"
    start: str = "192.168.1.50"
    end: str = "192.168.1.99"

class SmtpSettings(BaseModel):
    enabled: bool = False
    host: str = ""
    port: int = 587
    use_tls: bool = True
    user: str = ""
    password: str = ""
    from_addr: str = ""
    to_addr: str = ""

class TelegramSettings(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""

class AuthSettings(BaseModel):
    # Cookie du jeton de rafraîchissement : Secure exige le HTTPS. Pour un
    # essai en HTTP simple (ex. http://nas:8080), passer cookie_secure à false.
    cookie_secure: bool = True
    cookie_samesite: str = "none"

    @model_validator(mode="after")
    def _samesite_needs_secure(self):
        # Les navigateurs refusent SameSite=None sans Secure : repli sur Lax en HTTP
        if not self.cookie_secure and self.cookie_samesite.lower() == "none":
            self.cookie_samesite = "lax"
        return self


class PushSettings(BaseModel):
    """Notifications push (Web Push) vers les téléphones et navigateurs abonnés."""

    enabled: bool = True
    # Contact exigé par les services de push (Google, Apple, Mozilla)
    contact: str = "mailto:admin@example.org"
    # Clé privée VAPID (PEM) ; vide : générée et gardée à côté de la base
    vapid_private_key: str = ""


class Settings(BaseSettings):
    """
    Réglages lus dans config/<ENV>.yaml (ou le fichier désigné par
    AQUAS_CONFIG_FILE), puis surchargés par les variables d'environnement
    AQUAS_* (niveaux séparés par « __ ») : c'est là que vont les secrets.
    Exemples : AQUAS_SECRET_KEY, AQUAS_MQTT__PASSWORD, AQUAS_ESP__PASSWORD,
    AQUAS_DEFAULT_ADMIN_PASSWORD, AQUAS_TELEGRAM__BOT_TOKEN.
    """

    model_config = SettingsConfigDict(
        env_prefix="AQUAS_",
        env_nested_delimiter="__",
        env_file=os.getenv("AQUAS_ENV_FILE", ".env"),
        extra="ignore",
    )

    env: str = "dev"
    debug: bool = True
    log_level: str = "INFO"
    log_day_retention: int = 30
    # Sauvegardes « avant restauration » conservées (jours)
    backup_retention_days: int = 5
    # Valeurs initiales des réglages de sauvegarde (modifiables ensuite dans l'interface) :
    # sauvegarde automatique activée, dossier externe (partage NFS monté par l'hôte)
    backup_auto_default: bool = False
    backup_external_path: str = ""
    # Caméras IP (optionnel) : adresse de l'API go2rtc, jamais exposée au
    # navigateur (ex. http://127.0.0.1:1984). Vide = fonction désactivée.
    go2rtc_url: str = ""
    # Hub de l'éditeur : catalogue commun d'espèces, synchronisé régulièrement
    # (nouvelles espèces et corrections). « none » = pas de synchronisation.
    hub_url: str = "https://hub.aquasmanager.fr"
    catalog_sync_hours: int = 6
    # Licence (optionnel) : clé signée « AQM1.… » ; une clé collée dans
    # l'appli (Configuration › Licence) passe avant celle-ci
    license_key: str = ""
    activation_retention_days: int = 90
    alert_retention_days: int = 90
    audit_retention_days: int = 365
    # Relevés des capteurs conservés (graphiques d'historique) ; 0 = sans limite
    sensor_reading_retention_days: int = 365
    # Fuseau horaire de l'installation (rappels de tâches du jour)
    timezone: str = "Europe/Paris"
    # Heure locale d'envoi du rappel des tâches du jour
    task_reminder_hour: int = 8
    # « seller » (bourse) a le niveau de la consultation, plus les droits
    # explicites sur les boutures et cessions (min_role_required(..., also=...))
    role: dict = {"consult": 1, "seller": 1, "caretaker": 1, "user": 2, "manager": 3, "admin": 4}
    # Vide : générée au premier démarrage et conservée à côté de la base
    secret_key: str = ""
    frontend_urls: list[str] = ["http://localhost:9000"]
    # Préfixe sous lequel un proxy expose l'API (ex. « /api » en installation
    # Docker) : utile à la documentation interactive (/docs)
    root_path: str = ""

    # Instance de démonstration publique (services/demo.py) : données fictives
    # remises à zéro chaque nuit, compte affiché sur la page de connexion
    demo: bool = False
    demo_username: str = "demo"
    demo_password: str = "demo"
    demo_reset_hour: int = 4

    default_admin_username: str = "admin"
    default_admin_password: str = "ChangeMe123!"

    database: DatabaseSettings = DatabaseSettings()
    auth: AuthSettings = AuthSettings()
    mqtt: MqttSettings = MqttSettings()
    esp: ESPSettings = ESPSettings()
    network: NetworkSettings = NetworkSettings()
    smtp: SmtpSettings = SmtpSettings()
    telegram: TelegramSettings = TelegramSettings()
    push: PushSettings = PushSettings()

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        # Les variables d'environnement l'emportent sur le fichier YAML
        return env_settings, dotenv_settings, init_settings, file_secret_settings


def _config_path() -> Path:
    explicit = os.getenv("AQUAS_CONFIG_FILE")
    if explicit:
        return Path(explicit)
    env = os.getenv("ENV", "dev").lower()
    return Path(__file__).parent / "config" / f"{env}.yaml"


def _ensure_secret_key(conf: Settings) -> None:
    """Sans clé fournie, en génère une et la garde à côté de la base (installation Docker simple)."""
    if conf.secret_key:
        return
    key_file = Path(conf.database.sqlite_path).resolve().parent / ".secret_key"
    if key_file.exists():
        conf.secret_key = key_file.read_text().strip()
        return
    key_file.parent.mkdir(parents=True, exist_ok=True)
    conf.secret_key = secrets.token_hex(32)
    # Créé directement en 0600 : jamais lisible par d'autres, même un instant
    fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(conf.secret_key)


def load_settings() -> Settings:
    config_path = _config_path()
    data = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}
    elif os.getenv("AQUAS_CONFIG_FILE"):
        raise FileNotFoundError(f"Le fichier de configuration {config_path} est introuvable.")
    conf = Settings(**data)
    _ensure_secret_key(conf)
    return conf


# Instance globale
settings = load_settings()

# Les dates sont stockées en UTC (datetime.now() naïf) et marquées « Z » à la
# sortie (middleware/utc_json.py). Le processus est donc forcé en UTC, même si
# le conteneur a un autre fuseau (variable TZ) ; le fuseau de l'installation
# (settings.timezone) sert seulement aux calculs « aujourd'hui » (rappels...)
os.environ["TZ"] = "UTC"
if hasattr(time, "tzset"):
    time.tzset()
