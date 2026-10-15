<p align="center">
  <img src="ui/public/icons/favicon-128x128.png" alt="AquasManager" width="96">
</p>

<h1 align="center">AquasManager</h1>

<p align="center">
  Gestion et pilotage d’aquariums, auto-hébergé : paramètres d’eau, vivants, entretien,
  équipements et contrôleurs ESP32.<br>
  <a href="https://aquasmanager.fr">Site</a> ·
  <a href="https://aquasmanager.fr/docs/">Documentation</a> ·
  <a href="https://aquasmanager.fr/releases/">Notes de version</a>
</p>

> **English** — AquasManager is a self-hosted app to manage and automate aquariums (reef and
> freshwater): water parameters and ICP tests, livestock, maintenance, equipment and ESP32
> controllers. The interface is available in French and English; the code and its comments are in
> French. Documentation: <https://aquasmanager.fr/en/docs/>. Issues and contributions in English are
> welcome.

## Fonctionnalités

- **Aquariums et vivants** : tous vos bacs et chacun de leurs habitants, avec fiche, photos et
  historique, sur un catalogue d’espèces commun et enrichi par les utilisateurs.
- **Paramètres d’eau et analyses ICP** : relevés, cibles, courbes, tendances, import des analyses
  de laboratoire.
- **Contrôleurs ESP32** : vous décrivez le matériel dans l’interface, AquasManager génère et flashe
  le firmware ESPHome. Le contrôleur continue de fonctionner sans le serveur.
- **Règles et automatismes**, **éclairage** canal par canal, **équipements** et consommation.
- **Entretien, stock et calendrier**, **alertes** sur téléphone (Web Push, e-mail, Telegram, ntfy).
- **Boutures** en lots avec étiquettes QR, suivi de survie et justificatifs d’achat.
- **Application installable**, utilisable hors connexion.
- **Assistant IA** sur vos données, avec le modèle de votre choix, local ou externe.
- **Utilisateurs et rôles** pour partager le bac en famille ou pendant les vacances.

## Installation

Sur une machine Linux avec Docker (Raspberry Pi 4/5, mini-PC, NAS…) :

```sh
curl -fsSL https://aquasmanager.fr/install.sh -o install.sh
sudo bash install.sh
```

L’installateur pose quelques questions (adresse de la machine, Wi-Fi des contrôleurs…) et démarre
l’API, l’interface et un broker MQTT. Le détail, la mise à jour et l’installation manuelle avec
Docker Compose sont dans la [documentation](https://aquasmanager.fr/docs/demarrer/installation/).

Images publiées pour amd64 et arm64 :

- `ghcr.io/aquasmanager/api`
- `ghcr.io/aquasmanager/ui`

## Organisation du dépôt

| Dossier | Contenu |
| --- | --- |
| [`api/`](api) | API FastAPI (Python 3.12, SQLAlchemy, MQTT), génération des firmwares ESPHome |
| [`ui/`](ui) | Interface Vue 3 + Quasar (PWA, hors connexion) |
| [`api/deploy/`](api/deploy) | Installateur et Docker Compose |

## Développer

API :

```sh
cd api
python -m venv venv && venv/bin/pip install -r requirements.txt
ENV=test venv/bin/python -m pytest          # tests
cp config/example.yaml config/dev.yaml      # puis adapter
venv/bin/uvicorn main:app --reload
```

Interface :

```sh
cd ui
npm install
cp .env.example .env.development            # adresse de l’API de dev
npx quasar dev
npm run lint && npm run i18n:check
```

## Contribuer

Les contributions sont les bienvenues : signalements de bugs, propositions d’amélioration,
corrections et code. Les espèces du catalogue commun se proposent directement depuis l’application.
Tout est expliqué dans [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

AquasManager est publié sous la [Functional Source License 1.1](LICENSE.md)
(FSL-1.1-ALv2) : vous pouvez utiliser, étudier, modifier et redistribuer le logiciel pour tout usage
autre qu’un produit ou service commercial concurrent. Chaque version passe automatiquement sous
licence Apache 2.0 deux ans après sa publication.

Les dossiers [`api/pro/`](api/pro) et [`ui/src/pro/`](ui/src/pro) ne sont pas couverts par la
FSL : ils relèvent de leur propre licence ([`api/pro/LICENSE.md`](api/pro/LICENSE.md)).

© 2026 Emmanuel Smith
