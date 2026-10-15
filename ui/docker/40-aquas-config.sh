#!/bin/sh
# Configuration de l'interface au démarrage du conteneur nginx.
#
#   AQUAS_API_URL       adresse de l'API vue par le navigateur
#                       (ex. https://api.exemple.fr) ; défaut : /api
#   AQUAS_APP_ENV       badge affiché à côté du titre (prod, recette...)
#   AQUAS_HUB_URL       service central de l'éditeur (propositions au catalogue
#                       commun) ; défaut : hub public ; « none » = désactivé
#   AQUAS_API_UPSTREAM  si renseigné (ex. http://api:8000), nginx relaie /api
#                       vers l'API : un seul port et une seule adresse à ouvrir
set -eu

HTML=/usr/share/nginx/html
CONF=/etc/nginx/conf.d/default.conf

json_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

{
  printf 'window.__AQUAS_CONFIG__ = {'
  sep=''
  if [ -n "${AQUAS_API_URL:-}" ]; then printf '"apiUrl": "%s"' "$(json_escape "$AQUAS_API_URL")"; sep=', '; fi
  if [ -n "${AQUAS_APP_ENV:-}" ]; then printf '%s"env": "%s"' "$sep" "$(json_escape "$AQUAS_APP_ENV")"; sep=', '; fi
  if [ -n "${AQUAS_HUB_URL:-}" ]; then printf '%s"hubUrl": "%s"' "$sep" "$(json_escape "$AQUAS_HUB_URL")"; fi
  printf '};\n'
} > "$HTML/config.js"

if [ -n "${AQUAS_API_UPSTREAM:-}" ]; then
  cat > /etc/nginx/conf.d/api-proxy.inc <<CONF_EOF
    location /api/ {
        proxy_pass ${AQUAS_API_UPSTREAM%/}/;
        # Redirections de l'API (ex. /aquariums → /aquariums/) : l'API ne connaît ni le préfixe /api ni
        # le port public ; on les rend relatives pour que le navigateur reste sur la bonne adresse
        proxy_redirect ~^https?://[^/]+(/.*)\$ /api\$1;
        absolute_redirect off;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$aquas_forwarded_proto;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 1h;
        client_max_body_size 50m;
    }
CONF_EOF
else
  : > /etc/nginx/conf.d/api-proxy.inc
fi
# Nom de l'application installée : « AquasManager » en prod, « AquasManager-rec »
# en recette (deux icônes distinctes sur le téléphone)
case "${AQUAS_APP_ENV:-prod}" in
  prod | production | "") APP_NAME="AquasManager" ;;
  recette) APP_NAME="AquasManager-rec" ;;
  demo) APP_NAME="AquasManager Démo" ;;
  *) APP_NAME="AquasManager-${AQUAS_APP_ENV}" ;;
esac
if [ "$APP_NAME" != "AquasManager" ]; then
  sed -i "s/\"name\": \"AquasManager\"/\"name\": \"$APP_NAME\"/; s/\"short_name\": \"AquasManager\"/\"short_name\": \"$APP_NAME\"/" "$HTML/manifest.json"
  # index.html est minifié : attribut avec ou sans guillemets
  sed -i "s#\(apple-mobile-web-app-title\"\{0,1\} content=\)\"\{0,1\}AquasManager\"\{0,1\}#\1\"$APP_NAME\"#; s#<title>AquasManager</title>#<title>$APP_NAME</title>#" "$HTML/index.html"
fi

echo "AquasManager ($APP_NAME) : API ${AQUAS_API_URL:-/api}${AQUAS_API_UPSTREAM:+ (relais vers $AQUAS_API_UPSTREAM)}"
