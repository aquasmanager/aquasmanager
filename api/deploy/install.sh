#!/usr/bin/env bash
# =============================================================================
# AquasManager — installation interactive
#
#   curl -fsSL <adresse>/install.sh | sudo bash
#   ou : sudo bash install.sh [options]
#
# Systèmes : Debian, Ubuntu, Raspberry Pi OS (64 bits : PC x86_64 ou ARM64).
# Installe Docker si besoin, demande les réglages essentiels, génère la
# configuration (docker-compose.yml, .env), démarre l'application et installe
# la commande « aquasmanager » (mise à jour, sauvegarde, journaux...).
#
# Options :
#   --dir DOSSIER     dossier d'installation (défaut : /opt/aquasmanager)
#   --answers FICHIER réponses pré-remplies (variables ANSWER_*, voir plus bas)
#   --yes             sans questions : valeurs par défaut / fichier de réponses
#   --plain           questions en texte simple (sans fenêtres whiptail)
#   --dry-run         écrit seulement les fichiers (ni root, ni Docker)
#   --reconfigure     reprendre une installation existante
#   -h, --help        cette aide
# =============================================================================
set -Eeuo pipefail

INSTALLER_VERSION="1.0"
DEFAULT_DIR="/opt/aquasmanager"
API_IMAGE_DEFAULT="${AQUAS_API_IMAGE:-ghcr.io/aquasmanager/api:latest}"
UI_IMAGE_DEFAULT="${AQUAS_UI_IMAGE:-ghcr.io/aquasmanager/ui:latest}"
# Adresse où récupérer la dernière version de ce script (commande « aquasmanager reconfigure »)
INSTALLER_URL="${AQUAS_INSTALLER_URL:-https://raw.githubusercontent.com/aquasmanager/aquasmanager/main/api/deploy/install.sh}"
MIN_DISK_MB=3000

DIR="$DEFAULT_DIR"
ANSWERS_FILE=""
ASSUME_YES=false
PLAIN=false
DRY_RUN=false
RECONFIGURE=false

# --- Affichage ---------------------------------------------------------------

if [ -t 1 ]; then
  C_BLUE=$'\e[1;34m'; C_GREEN=$'\e[1;32m'; C_YELLOW=$'\e[1;33m'; C_RED=$'\e[1;31m'; C_RESET=$'\e[0m'
else
  C_BLUE=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_RESET=""
fi

step() { printf '\n%s==> %s%s\n' "$C_BLUE" "$*" "$C_RESET"; }
ok() { printf '%s  ✔ %s%s\n' "$C_GREEN" "$*" "$C_RESET"; }
warn() { printf '%s  ! %s%s\n' "$C_YELLOW" "$*" "$C_RESET" >&2; }
die() {
  printf '\n%s✘ %s%s\n' "$C_RED" "$*" "$C_RESET" >&2
  exit 1
}
trap 'die "Erreur inattendue (ligne $LINENO). Rien n est perdu : relance le script pour reprendre."' ERR

usage() { sed -n '2,22p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//' || true; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIR="${2:?--dir attend un dossier}"; shift 2 ;;
    --answers) ANSWERS_FILE="${2:?--answers attend un fichier}"; shift 2 ;;
    --yes | -y) ASSUME_YES=true; shift ;;
    --plain) PLAIN=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --reconfigure) RECONFIGURE=true; shift ;;
    -h | --help) usage; exit 0 ;;
    *) die "Option inconnue : $1 (voir --help)" ;;
  esac
done

# --- Questions (fenêtres whiptail ou texte simple) ---------------------------

# Script lancé via « curl | bash » : les réponses se lisent sur le terminal
TTY=/dev/tty
if ! $ASSUME_YES && ! { [ -r "$TTY" ] && : <"$TTY"; } 2>/dev/null; then
  die "Aucun terminal pour poser les questions : relance avec --yes (et --answers FICHIER)."
fi
USE_WHIPTAIL=false
if ! $ASSUME_YES && ! $PLAIN && command -v whiptail >/dev/null 2>&1; then
  USE_WHIPTAIL=true
fi
TITLE="Installation d'AquasManager"

# ask VARIABLE "Question" "défaut" [validateur]
ask() {
  local __var="$1" question="$2" default="${3:-}" validator="${4:-}" answer
  while true; do
    if $ASSUME_YES; then
      answer="$default"
    elif $USE_WHIPTAIL; then
      answer=$(whiptail --title "$TITLE" --inputbox "$question" 12 74 "$default" 3>&1 1>&2 2>&3 <"$TTY") ||
        die "Installation annulée."
    else
      printf '\n%b' "$question" >"$TTY"
      [ -n "$default" ] && printf ' [%s]' "$default" >"$TTY"
      printf ' : ' >"$TTY"
      IFS= read -r answer <"$TTY" || answer=""
      [ -z "$answer" ] && answer="$default"
    fi
    if [ -z "$validator" ] || "$validator" "$answer"; then
      printf -v "$__var" '%s' "$answer"
      return 0
    fi
    $ASSUME_YES && die "Valeur invalide pour « $question » : $answer"
    msg "Valeur invalide : « $answer ». $VALIDATION_HINT"
  done
}

# ask_secret VARIABLE "Question" (vide autorisé)
ask_secret() {
  local __var="$1" question="$2" answer=""
  if $ASSUME_YES; then
    answer="${!__var:-}"
  elif $USE_WHIPTAIL; then
    answer=$(whiptail --title "$TITLE" --passwordbox "$question" 12 74 3>&1 1>&2 2>&3 <"$TTY") ||
      die "Installation annulée."
  else
    printf '\n%b : ' "$question" >"$TTY"
    IFS= read -rs answer <"$TTY" || answer=""
    printf '\n' >"$TTY"
  fi
  printf -v "$__var" '%s' "$answer"
}

# confirm "Question" (défaut : oui) -> code de retour
confirm() {
  local question="$1" answer
  $ASSUME_YES && return 0
  if $USE_WHIPTAIL; then
    whiptail --title "$TITLE" --yesno "$question" 14 74 <"$TTY" 3>&1 1>&2 2>&3
    return $?
  fi
  printf '\n%b [O/n] : ' "$question" >"$TTY"
  IFS= read -r answer <"$TTY" || answer=""
  case "${answer,,}" in n | non | no) return 1 ;; *) return 0 ;; esac
}

msg() {
  if $ASSUME_YES; then
    printf '%b\n' "$1"
  elif $USE_WHIPTAIL; then
    whiptail --title "$TITLE" --msgbox "$1" 16 74 <"$TTY" 3>&1 1>&2 2>&3 || true
  else
    printf '\n%b\n' "$1" >"$TTY"
  fi
}

# Choix des composants : « nom|libellé|ON/OFF » ; résultat dans SELECTED (liste séparée par des espaces)
choose_components() {
  local items=("$@") item name label state answer
  SELECTED=""
  if $ASSUME_YES; then
    for item in "${items[@]}"; do
      IFS='|' read -r name label state <<<"$item"
      if [ "$state" = ON ]; then SELECTED="$SELECTED $name"; fi
    done
    return 0
  fi
  if $USE_WHIPTAIL; then
    local args=()
    for item in "${items[@]}"; do
      IFS='|' read -r name label state <<<"$item"
      args+=("$name" "$label" "$state")
    done
    answer=$(whiptail --title "$TITLE" --separate-output --checklist \
      "Composants à installer (Espace pour cocher, Entrée pour valider).\nL'API et l'interface sont toujours installées." \
      18 78 6 "${args[@]}" 3>&1 1>&2 2>&3 <"$TTY") || die "Installation annulée."
    SELECTED=" $(printf '%s' "$answer" | tr '\n' ' ')"
    return 0
  fi
  printf '\nComposants (l API et l interface sont toujours installées) :\n' >"$TTY"
  for item in "${items[@]}"; do
    IFS='|' read -r name label state <<<"$item"
    local def="O/n"
    [ "$state" = OFF ] && def="o/N"
    printf '  %s ? [%s] : ' "$label" "$def" >"$TTY"
    IFS= read -r answer <"$TTY" || answer=""
    case "${answer,,}" in
      o | oui | y | yes) SELECTED="$SELECTED $name" ;;
      n | non | no) ;;
      *) if [ "$state" = ON ]; then SELECTED="$SELECTED $name"; fi ;;
    esac
  done
  return 0
}

selected() { case " $SELECTED " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

# --- Validateurs --------------------------------------------------------------

VALIDATION_HINT=""
valid_ipv4() {
  VALIDATION_HINT="Adresse IPv4 attendue, ex : 192.168.1.10."
  local IFS=. part count=0
  [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 1
  for part in $1; do
    [ "$part" -le 255 ] || return 1
    count=$((count + 1))
  done
  [ "$count" -eq 4 ]
}
valid_port() {
  VALIDATION_HINT="Port entre 1 et 65535."
  [[ "$1" =~ ^[0-9]+$ ]] && [ "$1" -ge 1 ] && [ "$1" -le 65535 ]
}
valid_http_port() {
  valid_port "$1" || return 1
  VALIDATION_HINT="Ce port est déjà utilisé sur cette machine : choisis-en un autre."
  port_free "$1"
}
valid_name() {
  VALIDATION_HINT="Lettres, chiffres, point, tiret ou souligné (3 à 30 caractères)."
  [[ "$1" =~ ^[A-Za-z0-9._-]{3,30}$ ]]
}
valid_domain() {
  VALIDATION_HINT="Nom de domaine attendu, ex : aquarium.mondomaine.fr."
  [[ "$1" =~ ^([A-Za-z0-9-]+\.)+[A-Za-z]{2,}$ ]]
}
valid_email() {
  VALIDATION_HINT="Adresse e-mail attendue."
  [[ "$1" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]]
}
valid_timezone() {
  VALIDATION_HINT="Fuseau horaire attendu, ex : Europe/Paris."
  [ -e "/usr/share/zoneinfo/$1" ] || [[ "$1" =~ ^[A-Za-z]+/[A-Za-z_+-]+(/[A-Za-z_+-]+)?$ ]]
}
valid_any() { return 0; }
valid_host() {
  VALIDATION_HINT="Adresse IP ou nom du NAS attendu, ex : 192.168.1.20 ou nas.local."
  [[ "$1" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]]
}
valid_nfs_export() {
  VALIDATION_HINT="Chemin du partage attendu, commençant par / (ex : /volume1/aquasmanager)."
  [[ "$1" =~ ^/[^[:space:]]*$ ]]
}

# --- Utilitaires système ------------------------------------------------------

random_secret() {
  # 32 caractères alphanumériques (pas de caractère spécial : .env et YAML)
  tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c "${1:-32}" || true
}

port_free() {
  $DRY_RUN && return 0
  if command -v ss >/dev/null 2>&1; then
    ! ss -ltnH 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]$1\$"
  else
    return 0
  fi
}

detect_ip() {
  local found=""
  command -v ip >/dev/null 2>&1 &&
    found=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i <= NF; i++) if ($i == "src") { print $(i + 1); exit }}' || true)
  [ -z "$found" ] && found=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
  printf '%s' "$found"
}

detect_gateway() {
  command -v ip >/dev/null 2>&1 || return 0
  ip -4 route 2>/dev/null | awk '/^default/ {print $3; exit}' || true
}

# Masque du réseau de l'adresse donnée (ex : 255.255.255.0), /24 si inconnu
detect_netmask() {
  local prefix=""
  command -v ip >/dev/null 2>&1 &&
    prefix=$(ip -o -f inet addr show 2>/dev/null | awk -v ip="$1" '{split($4, a, "/"); if (a[1] == ip) {print a[2]; exit}}' || true)
  prefix="${prefix:-24}"
  local mask=$((0xffffffff << (32 - prefix) & 0xffffffff))
  printf '%d.%d.%d.%d' $((mask >> 24 & 255)) $((mask >> 16 & 255)) $((mask >> 8 & 255)) $((mask & 255))
}

detect_timezone() {
  local tz=""
  command -v timedatectl >/dev/null 2>&1 && tz=$(timedatectl show -p Timezone --value 2>/dev/null || true)
  [ -z "$tz" ] && [ -r /etc/timezone ] && tz=$(cat /etc/timezone)
  printf '%s' "${tz:-Europe/Paris}"
}

# Valeur d'une clé du .env (sans exécuter le fichier ; « $$ » redevient « $ »)
env_value() {
  [ -r "$1" ] || return 0
  sed -n "s/^$2=//p" "$1" | tail -n 1 | sed 's/\$\$/$/g'
}

# Valeur saisie écrite dans le .env : Docker Compose interprète « $ », doublé ici
env_escape() { printf '%s' "${1//\$/\$\$}"; }

# --- 1. Vérifications ---------------------------------------------------------

check_system() {
  step "Vérification du système"
  if $DRY_RUN; then
    warn "Mode essai (--dry-run) : seuls les fichiers de configuration sont écrits dans $DIR"
    return 0
  fi
  [ "$(id -u)" -eq 0 ] || die "Lance le script en administrateur : curl -fsSL … | sudo bash  (ou sudo bash install.sh)"

  local os_id="" os_like="" os_name=""
  if [ -r /etc/os-release ]; then
    os_id=$(. /etc/os-release && printf '%s' "${ID:-}")
    os_like=$(. /etc/os-release && printf '%s' "${ID_LIKE:-}")
    os_name=$(. /etc/os-release && printf '%s' "${PRETTY_NAME:-$ID}")
  fi
  case "$os_id" in
    debian | ubuntu | raspbian) ok "Système : $os_name" ;;
    *)
      if [[ " $os_like " == *" debian "* ]]; then
        warn "Système dérivé de Debian ($os_name) : non testé, mais devrait fonctionner."
      else
        die "Système non pris en charge ($os_name). Utilise Debian, Ubuntu ou Raspberry Pi OS."
      fi
      ;;
  esac

  case "$(uname -m)" in
    x86_64 | amd64) ok "Processeur : PC 64 bits" ;;
    aarch64 | arm64) ok "Processeur : ARM 64 bits (Raspberry Pi 4/5...)" ;;
    armv7l | armv6l) die "Système 32 bits détecté : installe Raspberry Pi OS 64 bits (Raspberry Pi 3, 4 ou 5)." ;;
    *) die "Processeur non pris en charge : $(uname -m)." ;;
  esac

  local parent="$DIR" free_mb
  while [ ! -d "$parent" ]; do parent=$(dirname "$parent"); done
  free_mb=$(df -Pm "$parent" | awk 'NR == 2 {print $4}')
  [ "${free_mb:-0}" -ge "$MIN_DISK_MB" ] || die "Espace disque insuffisant dans $parent : ${free_mb} Mo libres, $MIN_DISK_MB Mo nécessaires."
  ok "Espace disque : ${free_mb} Mo libres"

  local mem_mb
  mem_mb=$(awk '/MemTotal/ {print int($2 / 1024)}' /proc/meminfo 2>/dev/null || echo 0)
  if [ "$mem_mb" -lt 900 ]; then
    warn "Mémoire faible (${mem_mb} Mo) : 1 Go minimum conseillé (la compilation des ESP32 est gourmande)."
  else
    ok "Mémoire : ${mem_mb} Mo"
  fi

  if ! command -v curl >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq curl >/dev/null
  fi
}

# --- 2. Docker ------------------------------------------------------------------

ensure_docker() {
  step "Docker"
  $DRY_RUN && { ok "(essai) Docker non vérifié"; return 0; }
  if ! command -v docker >/dev/null 2>&1; then
    confirm "Docker n'est pas installé sur cette machine.\n\nL'installer maintenant (script officiel get.docker.com) ?" ||
      die "Docker est nécessaire. Installe-le puis relance ce script."
    curl -fsSL https://get.docker.com | sh || die "Échec de l'installation de Docker."
    systemctl enable --now docker >/dev/null 2>&1 || true
    ok "Docker installé"
  else
    ok "Docker présent ($(docker --version | awk '{print $3}' | tr -d ,))"
  fi
  if ! docker compose version >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq docker-compose-plugin >/dev/null ||
      die "Docker Compose introuvable : installe le paquet docker-compose-plugin."
  fi
  ok "Docker Compose présent ($(docker compose version --short 2>/dev/null || echo '?'))"
  docker info >/dev/null 2>&1 || die "Le service Docker ne répond pas (systemctl status docker)."
}

# --- 3. Questions -----------------------------------------------------------------

load_previous_answers() {
  # Réponses d'une installation précédente, puis fichier --answers : valeurs par défaut
  # shellcheck disable=SC1090
  [ -r "$DIR/aquasmanager.conf" ] && . "$DIR/aquasmanager.conf"
  # shellcheck disable=SC1090
  [ -n "$ANSWERS_FILE" ] && { [ -r "$ANSWERS_FILE" ] || die "Fichier de réponses introuvable : $ANSWERS_FILE"; . "$ANSWERS_FILE"; }
  return 0
}

ask_questions() {
  step "Réglages"
  local detected_ip gateway
  detected_ip=$(detect_ip || true)
  gateway=$(detect_gateway || true)

  local default_components="${ANSWER_COMPONENTS- mqtt backup}"  # vide = aucun composant optionnel
  choose_components \
    "mqtt|Broker MQTT Mosquitto (recommandé, sauf si tu en as déjà un)|$(case " $default_components " in *" mqtt "*) echo ON ;; *) echo OFF ;; esac)" \
    "backup|Sauvegarde automatique chaque nuit (réglable ensuite dans l'appli)|$(case " $default_components " in *" backup "*) echo ON ;; *) echo OFF ;; esac)" \
    "nfs|Sauvegardes sur un partage NFS (NAS)|$(case " $default_components " in *" nfs "*) echo ON ;; *) echo OFF ;; esac)" \
    "https|HTTPS avec certificat gratuit (il faut un nom de domaine)|$(case " $default_components " in *" https "*) echo ON ;; *) echo OFF ;; esac)" \
    "ntfy|Serveur de notifications ntfy (en plus des notifications de l'appli)|$(case " $default_components " in *" ntfy "*) echo ON ;; *) echo OFF ;; esac)" \
    "cameras|Caméras IP (service vidéo go2rtc, pour Reolink, Tapo…)|$(case " $default_components " in *" cameras "*) echo ON ;; *) echo OFF ;; esac)"
  # shellcheck disable=SC2034  # lue par write_files (aquasmanager.conf, via ${!name})
  COMPONENTS="$SELECTED"

  ask SERVER_IP "Adresse IP de ce serveur sur ton réseau (les ESP32 s'y connectent).\nElle doit rester fixe (réservation DHCP sur ta box)." \
    "${ANSWER_SERVER_IP:-$detected_ip}" valid_ipv4

  if selected https; then
    ask DOMAIN "Nom de domaine qui pointe vers ce serveur (ports 80 et 443 ouverts vers lui)" "${ANSWER_DOMAIN:-}" valid_domain
    ask ACME_EMAIL "E-mail pour le certificat HTTPS (avertissements d'expiration)" "${ANSWER_ACME_EMAIL:-}" valid_email
    HTTP_PORT=443
    PUBLIC_URL="https://$DOMAIN"
  else
    ask HTTP_PORT "Port de l'interface web" "${ANSWER_HTTP_PORT:-8080}" valid_http_port
    PUBLIC_URL="http://$SERVER_IP:$HTTP_PORT"
    [ "$HTTP_PORT" = 80 ] && PUBLIC_URL="http://$SERVER_IP"
  fi

  ask ADMIN_USER "Identifiant du compte administrateur" "${ANSWER_ADMIN_USER:-admin}" valid_name
  ask TIMEZONE "Fuseau horaire" "${ANSWER_TIMEZONE:-$(detect_timezone)}" valid_timezone

  if selected mqtt; then
    MQTT_HOST="mosquitto"
    MQTT_PORT=1883
    MQTT_USER="${ANSWER_MQTT_USER:-aquasmanager}"
    MQTT_DEVICE_HOST="$SERVER_IP"
  else
    msg "Broker MQTT existant : l'API et les ESP32 doivent pouvoir le joindre avec ces informations."
    ask MQTT_HOST "Adresse du broker MQTT (IP ou nom)" "${ANSWER_MQTT_HOST:-}" valid_any
    ask MQTT_PORT "Port du broker MQTT" "${ANSWER_MQTT_PORT:-1883}" valid_port
    ask MQTT_USER "Utilisateur MQTT" "${ANSWER_MQTT_USER:-}" valid_any
    MQTT_PASSWORD="${MQTT_PASSWORD:-${ANSWER_MQTT_PASSWORD:-}}"
    ask_secret MQTT_PASSWORD "Mot de passe MQTT"
    MQTT_DEVICE_HOST="$MQTT_HOST"
  fi

  msg "Wi-Fi des contrôleurs ESP32 : il est écrit dans leur programme au moment du flash.\nTu pourras le changer plus tard avec « aquasmanager reconfigure »."
  ask WIFI_SSID "Nom du réseau Wi-Fi (SSID) des ESP32" "${ANSWER_WIFI_SSID:-}" valid_any
  WIFI_PASSWORD="${WIFI_PASSWORD:-${ANSWER_WIFI_PASSWORD:-}}"
  ask_secret WIFI_PASSWORD "Mot de passe de ce Wi-Fi (laisser vide pour le garder inchangé)"
  [ -z "$WIFI_PASSWORD" ] && WIFI_PASSWORD="$(env_value "$DIR/.env" AQUAS_ESP__PASSWORD)"

  local base="${SERVER_IP%.*}"
  ask GATEWAY "Passerelle (adresse de ta box)" "${ANSWER_GATEWAY:-${gateway:-$base.1}}" valid_ipv4
  NETMASK="${ANSWER_NETMASK:-$(detect_netmask "$SERVER_IP")}"
  ask IP_START "Première IP fixe réservée aux ESP32" "${ANSWER_IP_START:-$base.50}" valid_ipv4
  ask IP_END "Dernière IP fixe réservée aux ESP32" "${ANSWER_IP_END:-$base.99}" valid_ipv4

  if selected nfs; then
    msg "Partage NFS : le NAS doit autoriser ce serveur ($SERVER_IP) en lecture/écriture sur le partage."
    ask NFS_SERVER "Adresse du NAS (serveur NFS)" "${ANSWER_NFS_SERVER:-}" valid_host
    ask NFS_EXPORT "Chemin du partage NFS sur le NAS" "${ANSWER_NFS_EXPORT:-}" valid_nfs_export
  fi

  if selected ntfy; then
    ask NTFY_PORT "Port du serveur ntfy" "${ANSWER_NTFY_PORT:-8090}" valid_http_port
    NTFY_TOPIC="${ANSWER_NTFY_TOPIC:-aquas-$(random_secret 10 | tr 'A-Z' 'a-z')}"
  fi
}

summary() {
  local lines
  lines="Dossier : $DIR
Adresse : $PUBLIC_URL
Compte administrateur : $ADMIN_USER
Fuseau horaire : $TIMEZONE
MQTT : $([ "$MQTT_HOST" = mosquitto ] && echo "Mosquitto installé ici (port 1883)" || echo "$MQTT_HOST:$MQTT_PORT")
Wi-Fi des ESP32 : ${WIFI_SSID:-(à renseigner plus tard)}
IP des ESP32 : $IP_START → $IP_END (passerelle $GATEWAY)
Sauvegarde automatique : $(selected backup && echo "oui, chaque nuit (réglable dans l'appli)" || echo "non")
Partage NFS : $(selected nfs && echo "$NFS_SERVER:$NFS_EXPORT" || echo "non")
HTTPS : $(selected https && echo "oui ($DOMAIN)" || echo "non")
ntfy : $(selected ntfy && echo "oui (port $NTFY_PORT)" || echo "non")
Caméras IP : $(selected cameras && echo "oui (service go2rtc)" || echo "non")"
  if $ASSUME_YES; then
    printf '%b\n' "$lines"
  else
    confirm "Récapitulatif :\n\n$lines\n\nInstaller avec ces réglages ?" || die "Installation annulée : rien n'a été modifié."
  fi
}

# --- 4. Fichiers -----------------------------------------------------------------

write_files() {
  step "Écriture de la configuration dans $DIR"
  mkdir -p "$DIR/data/base" "$DIR/data/uploads"

  # Secrets : repris d'une installation existante (les ESP32 déjà flashés gardent leur mot de passe MQTT)
  local previous="$DIR/.env"
  if selected mqtt; then
    MQTT_PASSWORD="$(env_value "$previous" AQUAS_MQTT__PASSWORD)"
    [ -z "$MQTT_PASSWORD" ] && MQTT_PASSWORD="$(random_secret 32)"
  fi
  ADMIN_PASSWORD="$(env_value "$previous" AQUAS_DEFAULT_ADMIN_PASSWORD)"
  [ -z "$ADMIN_PASSWORD" ] && ADMIN_PASSWORD="$(random_secret 12)"
  local api_image ui_image
  api_image="$(env_value "$previous" AQUAS_API_IMAGE)"
  ui_image="$(env_value "$previous" AQUAS_UI_IMAGE)"

  umask 077
  cat >"$DIR/.env" <<EOF
# AquasManager — généré par install.sh le $(date '+%d/%m/%Y %H:%M').
# Pour changer ces réglages : aquasmanager reconfigure

AQUAS_API_IMAGE=${api_image:-$API_IMAGE_DEFAULT}
AQUAS_UI_IMAGE=${ui_image:-$UI_IMAGE_DEFAULT}

# Accès
AQUAS_HTTP_PORT=$HTTP_PORT
AQUAS_PUBLIC_URL=$PUBLIC_URL
AQUAS_AUTH__COOKIE_SECURE=$(selected https && echo true || echo false)
# Compte créé au premier démarrage ; un nouveau mot de passe est demandé à la première connexion
AQUAS_DEFAULT_ADMIN_USERNAME=$ADMIN_USER
AQUAS_DEFAULT_ADMIN_PASSWORD=$ADMIN_PASSWORD

# MQTT (API et ESP32)
AQUAS_MQTT__HOST=$MQTT_HOST
AQUAS_MQTT__PORT=$MQTT_PORT
AQUAS_MQTT__USER=$(env_escape "$MQTT_USER")
AQUAS_MQTT__PASSWORD=$(env_escape "$MQTT_PASSWORD")
AQUAS_MQTT__DEVICE_HOST=$MQTT_DEVICE_HOST
AQUAS_MQTT__TOPIC_PREFIX=aquarium

# Réseau des ESP32 (écrit dans leur programme)
AQUAS_ESP__SSID=$(env_escape "$WIFI_SSID")
AQUAS_ESP__PASSWORD=$(env_escape "$WIFI_PASSWORD")
AQUAS_NETWORK__GATEWAY=$GATEWAY
AQUAS_NETWORK__SUBNET=$NETMASK
AQUAS_NETWORK__DNS1=$GATEWAY
AQUAS_NETWORK__START=$IP_START
AQUAS_NETWORK__END=$IP_END

# Sauvegardes : réglages initiaux (ensuite : Configuration › Sauvegarde)
AQUAS_BACKUP_AUTO_DEFAULT=$(selected backup && echo true || echo false)
AQUAS_BACKUP_EXTERNAL_PATH=$(selected nfs && echo /backups-nfs || true)

# Caméras IP : service vidéo go2rtc interne (vide = caméras désactivées)
AQUAS_GO2RTC_URL=$(selected cameras && echo http://go2rtc:1984 || true)

# Divers
AQUAS_TIMEZONE=$TIMEZONE
EOF
  chmod 600 "$DIR/.env"
  umask 022

  write_compose
  if selected mqtt; then
    mkdir -p "$DIR/mosquitto" "$DIR/data/mosquitto"
    cat >"$DIR/mosquitto/mosquitto.conf" <<'EOF'
listener 1883
allow_anonymous false
password_file /mosquitto/config/passwd
persistence true
persistence_location /mosquitto/data/
log_dest stdout
EOF
  fi
  if selected https; then
    mkdir -p "$DIR/data/caddy"
    cat >"$DIR/Caddyfile" <<EOF
{
	email $ACME_EMAIL
}

$DOMAIN {
	encode gzip
	reverse_proxy ui:80
}
EOF
  fi

  # Réponses (sans secret) : valeurs par défaut de « aquasmanager reconfigure »
  {
    printf '# Réponses de la dernière installation (install.sh %s), sans secret\n' "$INSTALLER_VERSION"
    local name
    for name in COMPONENTS SERVER_IP HTTP_PORT DOMAIN ACME_EMAIL ADMIN_USER TIMEZONE MQTT_HOST MQTT_PORT MQTT_USER \
      WIFI_SSID GATEWAY NETMASK IP_START IP_END NTFY_PORT NTFY_TOPIC NFS_SERVER NFS_EXPORT; do
      printf 'ANSWER_%s=%q\n' "$name" "${!name:-}"
    done
  } >"$DIR/aquasmanager.conf"

  # Copie locale du script (pour « aquasmanager reconfigure » sans Internet)
  if [ -f "${BASH_SOURCE[0]:-}" ] && [ "$(readlink -f "${BASH_SOURCE[0]}")" != "$(readlink -f "$DIR/install.sh" 2>/dev/null || true)" ]; then
    cp "${BASH_SOURCE[0]}" "$DIR/install.sh"
    chmod 755 "$DIR/install.sh"
  fi
  ok "Configuration écrite (.env protégé en lecture pour root seulement)"
}

write_compose() {
  local f="$DIR/docker-compose.yml"
  local nfs_volume=""
  if selected nfs; then
    # rslave : le partage monté à la demande par l'hôte apparaît dans le conteneur
    nfs_volume="      - type: bind\n        source: ./data/nfs\n        target: /backups-nfs\n        bind:\n          propagation: rslave"
  fi
  {
    cat <<'EOF'
# AquasManager — généré par install.sh (relancer « aquasmanager reconfigure » pour le modifier)
name: aquasmanager

services:
  api:
    image: ${AQUAS_API_IMAGE}
    restart: unless-stopped
    env_file: .env
    environment:
      ENV: docker
      AQUAS_ENV: docker
      AQUAS_DEBUG: "false"
      AQUAS_ROOT_PATH: /api
      AQUAS_FRONTEND_URLS: '["${AQUAS_PUBLIC_URL}"]'
      AQUAS_AUTH__COOKIE_SAMESITE: lax
    volumes:
      - ./data/base:/app/base
      - ./data/uploads:/app/uploads
#NFS_VOLUME#
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
EOF
    if selected mqtt; then
      cat <<'EOF'
    depends_on:
      - mosquitto
EOF
    fi
    cat <<'EOF'

  ui:
    image: ${AQUAS_UI_IMAGE}
    restart: unless-stopped
    environment:
      AQUAS_API_URL: /api
      AQUAS_API_UPSTREAM: http://api:8000
    depends_on:
      - api
EOF
    if ! selected https; then
      cat <<'EOF'
    ports:
      - "${AQUAS_HTTP_PORT}:80"
EOF
    fi
    if selected mqtt; then
      cat <<'EOF'

  mosquitto:
    image: eclipse-mosquitto:2
    restart: unless-stopped
    # Compte MQTT créé au démarrage à partir de .env (le même que l'API et les ESP32).
    # Droits donnés à l'utilisateur mosquitto (le démarrage standard de l'image est remplacé ici)
    entrypoint: >
      sh -c 'mosquitto_passwd -b -c /mosquitto/config/passwd "$$MQTT_USER" "$$MQTT_PASSWORD"
      && chown mosquitto:mosquitto /mosquitto/config/passwd && chmod 0700 /mosquitto/config/passwd
      && chown -R mosquitto:mosquitto /mosquitto/data
      && exec mosquitto -c /mosquitto/config/mosquitto.conf'
    environment:
      MQTT_USER: ${AQUAS_MQTT__USER}
      MQTT_PASSWORD: ${AQUAS_MQTT__PASSWORD}
    volumes:
      - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
      - ./data/mosquitto:/mosquitto/data
    ports:
      - "1883:1883"
EOF
    fi
    if selected https; then
      cat <<'EOF'

  caddy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./data/caddy:/data
    depends_on:
      - ui
EOF
    fi
    if selected ntfy; then
      cat <<EOF

  ntfy:
    image: binwiederhier/ntfy
    restart: unless-stopped
    command: serve
    environment:
      NTFY_BASE_URL: http://$SERVER_IP:$NTFY_PORT
      NTFY_CACHE_FILE: /var/cache/ntfy/cache.db
    volumes:
      - ./data/ntfy:/var/cache/ntfy
    ports:
      - "$NTFY_PORT:80"
EOF
    fi
    if selected cameras; then
      cat <<'EOF'

  go2rtc:
    image: alexxit/go2rtc:1.9.13
    restart: unless-stopped
    # Aucun port publié : son API (sans mot de passe) n'est jointe que par l'API
    # d'AquasManager, qui y déclare les caméras et relaie images et direct.
    command:
      - go2rtc
      - -config
      - '{"api":{"listen":":1984"},"rtsp":{"listen":""},"webrtc":{"listen":""},"log":{"level":"warn"}}'
EOF
    fi
  } >"$f"
  if [ -n "$nfs_volume" ]; then
    sed -i "s|^#NFS_VOLUME#$|$nfs_volume|" "$f"
  else
    sed -i '/^#NFS_VOLUME#$/d' "$f"
  fi
}

# --- 5. Commande « aquasmanager » et sauvegarde automatique ------------------------

install_cli() {
  step "Commande « aquasmanager »"
  local target="/usr/local/bin/aquasmanager"
  $DRY_RUN && target="$DIR/aquasmanager"
  cat >"$target" <<EOF
#!/usr/bin/env bash
# Commande d'administration d'AquasManager (installée par install.sh)
set -euo pipefail
DIR="$DIR"
INSTALLER_URL="$INSTALLER_URL"
EOF
  cat >>"$target" <<'EOF'
cd "$DIR"
compose() { docker compose "$@"; }
need_root() { [ "$(id -u)" -eq 0 ] || { echo "Lance cette commande avec sudo : sudo aquasmanager $*" >&2; exit 1; }; }
public_url() { sed -n 's/^AQUAS_PUBLIC_URL=//p' .env; }

backup() {
  echo "Sauvegarde (contenu et destination réglés dans l'appli)..."
  compose exec -T api python -c "from services.backup import create_backup; print(create_backup('manual'))" |
    sed -e "s#^/app/base#$DIR/data/base#" -e "s#^/backups-nfs#$DIR/data/nfs#"
}

case "${1:-help}" in
  status)
    compose ps
    echo
    echo "Interface : $(public_url)"
    ;;
  logs) shift; compose logs -f --tail=200 "$@" ;;
  start | stop | restart) need_root "$1"; compose "$1" ;;
  backup) need_root backup; backup ;;
  update)
    need_root update
    backup || echo "Sauvegarde impossible (application arrêtée ?) : mise à jour quand même." >&2
    compose pull
    compose up -d --remove-orphans
    docker image prune -f >/dev/null
    echo "À jour. Interface : $(public_url)"
    ;;
  reconfigure)
    need_root reconfigure
    if [ -f "$DIR/install.sh" ]; then
      exec bash "$DIR/install.sh" --dir "$DIR" --reconfigure "${@:2}"
    fi
    curl -fsSL "$INSTALLER_URL" -o /tmp/aquasmanager-install.sh
    exec bash /tmp/aquasmanager-install.sh --dir "$DIR" --reconfigure "${@:2}"
    ;;
  uninstall)
    need_root uninstall
    read -r -p "Arrêter et supprimer AquasManager (conteneurs, commande) ? [o/N] " answer </dev/tty
    case "${answer,,}" in o | oui | y | yes) ;; *) echo "Annulé."; exit 0 ;; esac
    compose down --remove-orphans
    systemctl disable --now aquasmanager-backup.timer >/dev/null 2>&1 || true
    rm -f /etc/systemd/system/aquasmanager-backup.service /etc/systemd/system/aquasmanager-backup.timer
    systemctl daemon-reload >/dev/null 2>&1 || true
    read -r -p "Supprimer aussi les données ($DIR : base, photos, sauvegardes) ? [o/N] " answer </dev/tty
    case "${answer,,}" in
      o | oui | y | yes) rm -rf "$DIR"; echo "Données supprimées." ;;
      *) echo "Données conservées dans $DIR." ;;
    esac
    rm -f /usr/local/bin/aquasmanager
    echo "AquasManager est désinstallé."
    ;;
  *)
    cat <<HELP
Utilisation : aquasmanager <commande>

  status        état des services et adresse de l'interface
  logs [svc]    journaux en direct (api, ui, mosquitto...)
  update        sauvegarde puis mise à jour vers la dernière version
  backup        sauvegarde immédiate (contenu et destination réglés dans l'appli)
  start|stop|restart
  reconfigure   relancer les questions de l'installation (réglages, composants)
  uninstall     désinstaller (les données peuvent être gardées)
HELP
    ;;
esac
EOF
  chmod 755 "$target"
  ok "Commande installée : $target"

  if $DRY_RUN || ! command -v systemctl >/dev/null 2>&1; then
    return 0
  fi
  # La sauvegarde automatique est faite par l'application (Configuration › Sauvegarde) :
  # l'ancien minuteur systemd des versions précédentes est retiré
  if [ -f /etc/systemd/system/aquasmanager-backup.timer ]; then
    systemctl disable --now aquasmanager-backup.timer >/dev/null 2>&1 || true
    rm -f /etc/systemd/system/aquasmanager-backup.service /etc/systemd/system/aquasmanager-backup.timer
    systemctl daemon-reload
  fi
  setup_nfs_mount
}

# Partage NFS monté par l'hôte, à la demande (x-systemd.automount) : l'application
# démarre même si le NAS est éteint, et le partage revient tout seul avec lui.
setup_nfs_mount() {
  local mountpoint="$DIR/data/nfs" tag="# aquasmanager-nfs"
  if ! selected nfs; then
    if grep -q "$tag" /etc/fstab 2>/dev/null; then
      umount "$mountpoint" >/dev/null 2>&1 || true
      sed -i "\|$tag|d" /etc/fstab
      systemctl daemon-reload
    fi
    return 0
  fi
  if ! command -v mount.nfs >/dev/null 2>&1; then
    step "Client NFS"
    if command -v apt-get >/dev/null 2>&1; then
      DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nfs-common >/dev/null || die "Installation de nfs-common impossible."
    else
      die "Client NFS absent : installe le paquet nfs-common (ou nfs-utils) puis relance."
    fi
  fi
  mkdir -p "$mountpoint"
  sed -i "\|$tag|d" /etc/fstab
  printf '%s:%s %s nfs nofail,_netdev,x-systemd.automount,x-systemd.mount-timeout=15,soft,timeo=150,retrans=2 0 0 %s\n' \
    "$NFS_SERVER" "$NFS_EXPORT" "$mountpoint" "$tag" >>/etc/fstab
  systemctl daemon-reload
  systemctl restart "$(systemd-escape -p --suffix=automount "$mountpoint")" >/dev/null 2>&1 || true
  if timeout 20 ls "$mountpoint" >/dev/null 2>&1 && mountpoint -q "$mountpoint"; then
    ok "Partage NFS monté : $NFS_SERVER:$NFS_EXPORT → $mountpoint"
  else
    warn "Partage NFS injoignable pour l'instant ($NFS_SERVER:$NFS_EXPORT). Il sera monté dès qu'il répond ;"
    warn "d'ici là, les sauvegardes restent dans le dossier local."
  fi
}

# --- 6. Démarrage ------------------------------------------------------------------

start_services() {
  step "Démarrage"
  if $DRY_RUN; then
    ok "(essai) docker compose non lancé"
    return 0
  fi
  cd "$DIR"
  echo "  Téléchargement des images (quelques minutes la première fois)..."
  if ! docker compose pull --quiet; then
    die "Téléchargement des images impossible. Vérifie la connexion Internet ; sur Raspberry Pi, que les images existent en version ARM64."
  fi
  docker compose up -d --remove-orphans
  printf '  Attente du démarrage de l API'
  local _
  for _ in $(seq 1 60); do
    if docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" >/dev/null 2>&1; then
      printf '\n'
      ok "Application démarrée"
      return 0
    fi
    printf '.'
    sleep 3
  done
  printf '\n'
  warn "L'API met du temps à démarrer. Consulte les journaux : aquasmanager logs api"
}

final_message() {
  local first_admin=""
  [ ! -f "$DIR/data/base/.installed" ] && first_admin="yes"
  $DRY_RUN || touch "$DIR/data/base/.installed"
  printf '\n%s============================================================%s\n' "$C_GREEN" "$C_RESET"
  printf '%s  AquasManager est prêt !%s\n' "$C_GREEN" "$C_RESET"
  printf '%s============================================================%s\n\n' "$C_GREEN" "$C_RESET"
  printf '  Ouvre : %s\n' "$PUBLIC_URL"
  if [ -n "$first_admin" ]; then
    printf '  Identifiant : %s\n' "$ADMIN_USER"
    printf '  Mot de passe provisoire : %s   (à changer à la première connexion)\n' "$ADMIN_PASSWORD"
  fi
  printf '\n  Ensuite, dans l application :\n'
  printf '   1. Contrôleurs → Ajouter : ton ESP32 (le premier flash se fait par câble USB)\n'
  printf '   2. Mes aquariums → ajoute ton bac, ses équipements et capteurs\n'
  if selected ntfy; then
    printf '   3. Notifications → canal ntfy, serveur http://%s:%s, sujet %s\n' "$SERVER_IP" "$NTFY_PORT" "$NTFY_TOPIC"
    printf '      (application ntfy sur le téléphone : abonne-toi au même serveur et sujet)\n'
  fi
  if selected https; then
    printf '\n  HTTPS : le certificat est obtenu au premier accès à %s\n' "$PUBLIC_URL"
    printf '  (le domaine doit pointer vers ce serveur, ports 80 et 443 ouverts).\n'
  fi
  printf '\n  Administration : aquasmanager status | update | backup | logs | reconfigure\n'
  printf '  Données : %s/data   (sauvegardes : data/base/backups%s)\n' "$DIR" "$(selected nfs && printf ' et partage NFS' || true)"
  printf '  Sauvegardes : Configuration › Sauvegarde dans l'"'"'application (fréquence, contenu, destination)\n\n'
}

# --- Déroulé ---------------------------------------------------------------------------

main() {
  printf '%s\n  AquasManager — installation (%s)%s\n' "$C_BLUE" "$INSTALLER_VERSION" "$C_RESET"
  check_system
  if [ -f "$DIR/.env" ] && ! $RECONFIGURE && ! $ASSUME_YES; then
    confirm "AquasManager est déjà installé dans $DIR.\n\nReprendre les réglages (données conservées) ?\n\nPour une simple mise à jour : sudo aquasmanager update" ||
      die "Rien n'a été modifié."
  fi
  load_previous_answers
  ensure_docker
  ask_questions
  summary
  write_files
  install_cli
  start_services
  final_message
}

main
