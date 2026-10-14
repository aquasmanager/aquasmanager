# Contribuer à AquasManager

Merci de votre intérêt ! AquasManager est un projet personnel ouvert aux contributions : chaque
proposition est lue et relue par le mainteneur, qui décide de ce qui est intégré.

> **English** — Contributions are welcome in English too. Open an issue first for anything bigger
> than a small fix, sign the CLA when the bot asks on your first pull request, and run the checks
> below before pushing.

## Sans écrire de code

- **Signaler un bug** : ouvrez un ticket avec le modèle « Bug ». Indiquez la version (affichée
  dans le menu utilisateur), ce que vous avez fait, ce que vous attendiez et ce qui s’est passé.
- **Proposer une idée** : depuis l’application (menu utilisateur → *Proposer une idée*, sans
  compte GitHub), ou ici avec le modèle « Idée ». Décrivez le besoin avant la solution. Chaque idée
  est lue et discutée avant d’être éventuellement développée.
- **Ajouter ou corriger une espèce** : depuis l’application (*Proposer au catalogue commun*), ou
  dans le dépôt [aquasmanager/catalogue](https://github.com/aquasmanager/catalogue).
- **Améliorer la documentation** ou une traduction : un ticket suffit, une pull request est encore
  mieux.

## Proposer du code

1. **Ouvrez d’abord un ticket** pour tout ce qui dépasse une petite correction, afin de vérifier
   que le changement a sa place dans le projet avant que vous y passiez du temps.
2. Créez une branche depuis `main`, faites des commits courts et parlants.
3. Vérifiez avant de pousser :

   ```sh
   # API
   cd api && ENV=test python -m pytest
   # Interface
   cd ui && npm run lint && npx vue-tsc --noEmit && npm run i18n:check
   ```

4. Ouvrez la pull request en décrivant le pourquoi du changement et comment le tester.
5. À votre première pull request, le robot vous demande de **signer le CLA** (voir plus bas) en
   ajoutant un commentaire. C’est une seule fois.

La pull request est relue, éventuellement discutée ou modifiée, puis fusionnée ou refusée avec une
explication. Le projet est maintenu sur le temps libre : la réponse peut prendre quelques jours.

### Conventions

- Code, commentaires et messages de commit en **français** (les tickets en anglais sont les
  bienvenus).
- Tout texte affiché passe par l’i18n, en français **et** en anglais (`ui/src/i18n/fr` et
  `ui/src/i18n/en`, mêmes clés).
- Une fonctionnalité de l’API arrive avec ses tests (`api/tests`).
- Pas de nouvelle dépendance sans en discuter dans le ticket.

## Accord de contribution (CLA)

Pour pouvoir intégrer votre contribution, le mainteneur a besoin d’un accord écrit : c’est le
[CLA](CLA.md). Vous restez propriétaire de votre contribution ; vous accordez au mainteneur le droit
de l’utiliser et de la distribuer, y compris sous d’autres licences. C’est ce qui permet au projet de
garder une licence unique et de la faire évoluer.

## Sécurité

Une faille de sécurité ne se signale **pas** dans un ticket public : voir [SECURITY.md](SECURITY.md).

## Comportement

Restez courtois et bienveillant, dans les tickets comme dans les relectures. Les messages
irrespectueux sont supprimés.
