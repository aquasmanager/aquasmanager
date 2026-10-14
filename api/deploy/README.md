# Installer AquasManager avec Docker

Trois conteneurs : l'API (FastAPI + ESPHome pour flasher les ESP32),
l'interface (nginx, qui relaie aussi l'API sous `/api`) et un broker MQTT
(Mosquitto) auquel se connectent l'API et les contrôleurs.

## Installation automatique (recommandé)

Sur la machine qui hébergera AquasManager (Debian, Ubuntu ou Raspberry Pi OS
64 bits), une seule commande :

```sh
curl -fsSL https://raw.githubusercontent.com/aquasmanager/aquasmanager/main/api/deploy/install.sh | sudo bash
# ou, après avoir téléchargé le fichier :
sudo bash install.sh
```

Le script :

1. vérifie le système (version, processeur 64 bits, espace disque, mémoire) ;
2. installe Docker s'il manque (après accord) ;
3. propose les composants : API et interface (toujours), broker MQTT
   Mosquitto, sauvegarde automatique chaque nuit, HTTPS avec certificat
   gratuit (nom de domaine requis), serveur de notifications ntfy ;
4. pose les questions essentielles, avec des valeurs détectées : IP du
   serveur, port, compte administrateur, fuseau horaire, Wi-Fi et plage d'IP
   des ESP32. Les mots de passe techniques (MQTT, clé de session) sont générés ;
5. démarre l'application et affiche l'adresse et le mot de passe provisoire
   de l'administrateur.

Tout est installé dans `/opt/aquasmanager` (option `--dir`). Les questions
s'affichent en fenêtres (whiptail) ou en texte simple (`--plain`).

### Administration

```sh
aquasmanager status          # état et adresse de l'interface
sudo aquasmanager update     # sauvegarde puis mise à jour
sudo aquasmanager backup     # sauvegarde (data/base/backups, 5 dernières gardées)
aquasmanager logs api        # journaux en direct
sudo aquasmanager reconfigure  # changer les réglages ou les composants
sudo aquasmanager uninstall  # désinstaller (les données peuvent être gardées)
```

Une reconfiguration garde les mots de passe existants (les ESP32 déjà
flashés continuent de se connecter au broker).

### Installation sans questions

Pour réinstaller à l'identique ou automatiser, fournis un fichier de réponses :

```sh
sudo bash install.sh --yes --answers reponses.conf
```

```sh
# reponses.conf
ANSWER_COMPONENTS=" mqtt backup"      # ajouter https et/ou ntfy si besoin
ANSWER_SERVER_IP=192.168.1.10
ANSWER_HTTP_PORT=8080
ANSWER_ADMIN_USER=admin
ANSWER_TIMEZONE=Europe/Paris
ANSWER_WIFI_SSID="MonWifi"
ANSWER_WIFI_PASSWORD='mot-de-passe-wifi'
ANSWER_GATEWAY=192.168.1.1
ANSWER_IP_START=192.168.1.50
ANSWER_IP_END=192.168.1.99
# HTTPS : ANSWER_DOMAIN=aquarium.mondomaine.fr  ANSWER_ACME_EMAIL=moi@exemple.fr
# Broker existant (sans « mqtt » dans les composants) :
#   ANSWER_MQTT_HOST=192.168.1.5  ANSWER_MQTT_USER=...  ANSWER_MQTT_PASSWORD='...'
```

`--dry-run` écrit seulement les fichiers (sans root ni Docker) pour vérifier
la configuration produite.

## Installation manuelle

### Prérequis

- Docker et Docker Compose sur une machine du réseau local (NAS, mini-PC,
  Raspberry Pi 4/5 en 64 bits).
- Une IP fixe pour cette machine : les ESP32 s'y connectent (broker MQTT).

### Étapes

```sh
mkdir aquasmanager && cd aquasmanager
# récupérer docker-compose.yml, .env.example et mosquitto/mosquitto.conf
cp .env.example .env
nano .env          # adresse du serveur, mots de passe, Wi-Fi des ESP32
docker compose up -d
```

Ouvre ensuite `http://<ip-du-serveur>:8080` et connecte-toi avec le compte
administrateur défini dans `.env` : un nouveau mot de passe est demandé à la
première connexion.

## Données et sauvegardes

Tout est dans `./data` : base SQLite (`data/base`), photos
(`data/uploads`), données du broker. La page **Sauvegarde** de l'application
exporte base et photos en une archive `.zip`.

Mise à jour : `docker compose pull && docker compose up -d` (les migrations
de la base sont appliquées au démarrage).

## HTTPS

Derrière un proxy HTTPS (Traefik, Caddy, Nginx Proxy Manager...), pointe le
proxy vers le port de l'interface puis passe dans `.env` :

```
AQUAS_PUBLIC_URL=https://aquas.mondomaine.fr
AQUAS_AUTH__COOKIE_SECURE=true
```

## Bon à savoir

- **Recherche des contrôleurs sur le réseau** (mDNS) : elle ne traverse pas
  le réseau Docker par défaut. Ajoute l'ESP32 à la main (son IP), ou passe le
  service `api` en `network_mode: host` (retire alors `AQUAS_MQTT__HOST`,
  remplacé par l'IP du serveur).
- **Flash des ESP32** : le premier flash d'un contrôleur compile tout le
  firmware (plusieurs minutes) ; les suivants sont bien plus rapides.
- Toutes les options sont des variables `AQUAS_*` (niveaux séparés par
  `__`, ex. `AQUAS_MQTT__PASSWORD`) : voir `settings.py`.
