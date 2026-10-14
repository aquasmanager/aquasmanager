#!/bin/sh
# Numéro de version d'AquasManager (SemVer), calculé à partir des tags vX.Y.Z
# (même script dans les dépôts de l'API et de l'interface) :
# - commit tagué (livraison en prod)  : « 0.6.1 »
# - sinon (recette, développement)     : version suivante + commits depuis
#   la dernière livraison, ex. « 0.6.2-dev.12 »
# Le tag est posé sur les deux dépôts à chaque mise en prod (voir la doc
# interne, AquasManager › Exploitation).
exact=$(git tag --points-at HEAD --list 'v[0-9]*' --sort=-v:refname 2>/dev/null | head -n 1)
if [ -n "$exact" ]; then
  echo "${exact#v}"
  exit 0
fi
last=$(git describe --tags --abbrev=0 --match 'v[0-9]*' 2>/dev/null)
if [ -z "$last" ]; then
  echo "0.0.0-dev"
  exit 0
fi
count=$(git rev-list --count "$last"..HEAD)
version=${last#v}
major=${version%%.*}
rest=${version#*.}
minor=${rest%%.*}
patch=${rest#*.}
echo "$major.$minor.$((patch + 1))-dev.$count"
