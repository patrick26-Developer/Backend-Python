# ADR 0003 — Versionnage d'API par l'URI (`/v1`, `/v2`)

- **Statut** : accepté
- **Date** : 2026-09-03

## Contexte

Le contrat public de `taskman` va évoluer (renommage de champs, changement de forme). On ne
peut pas casser les clients existants. Deux approches courantes : version dans l'**URI**
(`/v1/tasks`) ou dans un **en-tête** (`Accept: application/vnd.taskman.v2+json`).

## Décision

Version dans l'**URI**. Toute l'API métier est montée sous `/v1` ; `/v2` coexiste et
n'implémente que les endpoints dont le contrat change (il partage la **couche service**).
Les routes d'infrastructure (`/health`, `/ready`, `/metrics`) **ne sont pas** versionnées.

## Conséquences

**Positif**
- visible : on voit la version dans les logs, les métriques (label `path`), le cache CDN ;
- routage trivial (préfixe) ;
- test au navigateur direct.

**Négatif**
- l'URL d'une ressource « change » entre versions (débat « RESTful » — non bloquant) ;
- risque de dupliquer du code entre `/v1` et `/v2` si on ne partage pas les couches basses.

## Cycle de dépréciation

1. `/v2` publié, `/v1` toujours là.
2. Réponses `/v1` : en-têtes `Deprecation: true` + `Sunset: <date +6 mois>` ; doc à jour ;
   e-mail aux consommateurs connus.
3. Après la date **et** vérification via les métriques (plus aucun appel `/v1`) → retrait.

Un ajout **compatible** (nouveau champ optionnel en sortie) ne crée **pas** de version.
