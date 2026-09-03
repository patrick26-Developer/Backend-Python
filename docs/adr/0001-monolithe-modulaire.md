# ADR 0001 — Monolithe modulaire (pas de microservices)

- **Statut** : accepté
- **Date** : 2026-09-03
- **Décideurs** : équipe backend

## Contexte

`taskman` grandit. On se demande si découper en microservices (`tasks-service`,
`projects-service`, `accounts-service`) dès maintenant.

## Décision

On reste sur **un seul déploiement**, mais le code est découpé en **bounded contexts**
(`accounts/`, `projects/`, `tasks/`, `shared/`) avec une **interface publique explicite**
par module (`public.py`). Un module n'importe **que** le `public` d'un autre. `import-linter`
fait respecter la règle en CI.

## Conséquences

**Positif**
- une transaction DB unique (pas de saga, pas de *2-phase commit*) ;
- un déploiement, une CI, une stack d'observabilité ;
- refactor entre modules possible sans coordination inter-équipes ;
- si un module devient un point de friction, il est **déjà isolé** → extraction en service
  peu coûteuse.

**Négatif**
- un bug dans un module peut impacter tout le process ;
- scaling non ciblé (on scale tout le monolithe, pas juste `tasks`).

## Quand ré-ouvrir cette décision

- deux équipes distinctes se disputent le rythme de release d'un module ;
- un module a un profil de charge radicalement différent (ex. l'export massif) ;
- besoin d'une stack technique différente pour un composant.

Alors : extraire **ce module précis** en service, pas tout découper d'un coup.
