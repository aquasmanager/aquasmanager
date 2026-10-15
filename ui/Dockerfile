# Compilation de l'interface sur l'architecture de la machine de build (même
# résultat pour toutes les cibles) : pas d'émulation lente pour l'image ARM64
FROM --platform=$BUILDPLATFORM node:24-bookworm AS build
WORKDIR /app
COPY . .
RUN npm install
# Adresse de l'API figée à la compilation (déploiements k8s : la CI la passe
# en --build-arg). Vide = « /api », remplaçable au démarrage du conteneur
# par AQUAS_API_URL (voir docker/40-aquas-config.sh) : une même image sert
# toutes les installations.
ARG VITE_API_URL=
ENV VITE_API_URL=${VITE_API_URL}
# Affiché dans l'IHM à côté du numéro de version, pour distinguer prod/
# recette/dev en un coup d'œil.
ARG VITE_APP_ENV=prod
ENV VITE_APP_ENV=${VITE_APP_ENV}
# Commit compilé (détection des mises à jour, /version.json) et numéro de
# version calculé par la CI à partir des tags (scripts/version.sh)
ARG VITE_APP_VERSION=
ENV VITE_APP_VERSION=${VITE_APP_VERSION}
ARG VITE_APP_SEMVER=
ENV VITE_APP_SEMVER=${VITE_APP_SEMVER}
RUN npx quasar build

FROM nginx:alpine
COPY --from=build /app/dist/spa /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Écrit config.js (adresse de l'API) et le relais /api au démarrage
COPY docker/40-aquas-config.sh /docker-entrypoint.d/40-aquas-config.sh
RUN chmod +x /docker-entrypoint.d/40-aquas-config.sh && touch /etc/nginx/conf.d/api-proxy.inc
EXPOSE 80