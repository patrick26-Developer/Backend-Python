# Module 03 — Architecture d'un projet mature

> 🚧 **En construction** — structure finale : `THEORIE.md` · `PAS-A-PAS.md` · `exercices/` · `solutions/`.

## Objectif

Organiser la base de code pour qu'elle **scale en équipe et dans la tête** : `APIRouter`,
architecture en couches (router → service → repository), injection de dépendances,
configuration typée par environnement.

## Pages de doc FastAPI couvertes

Bigger Applications - Multiple Files · Dependencies (Classes as Dependencies, Sub-dependencies,
Dependencies in path operation decorators, Global Dependencies, Dependencies with `yield`) ·
Advanced Dependencies · Settings and Environment Variables · Path Operation Configuration ·
Path Operation Advanced Configuration · Metadata and Docs URLs · Lifespan Events ·
Reference : `APIRouter class`, `Dependencies - Depends() and Security()`, `FastAPI class`.

## Plan

1. `APIRouter` : découpage par domaine, préfixes, tags, `include_router`, `dependencies=`.
2. Les 3 couches : responsabilités, ce qui monte, ce qui descend, pourquoi les repositories.
3. `Depends` : dépendances simples, classes-dépendances, sous-dépendances, portée `yield`.
4. `dependency_overrides` : la clé de la testabilité.
5. `pydantic-settings` : `.env`, `Settings` typé, `@lru_cache`, config `local/test/staging/prod`.
6. `lifespan` : ouverture/fermeture propre des ressources.
7. Arborescence cible, règles d'import entre couches.

## Exercices (aperçu)

- Migrer le CRUD du Module 01 vers `api/ + services/ + repositories/`.
- `Protocol` `TaskRepository` + `InMemoryTaskRepository`, injecté par `Depends`.
- `Settings` typé injecté ; zéro `os.environ` hors de `core/config.py`.
- Remplacer le repository par un *fake* dans un test via `dependency_overrides`.

## Definition of Done

Voir [`../ROADMAP.md`](../ROADMAP.md#module-03--architecture-dun-projet-mature-).
