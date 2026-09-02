# Module 04 — Bases de données : SQLAlchemy 2.0 async + Alembic

> 🚧 **En construction** — `THEORIE.md` · `PAS-A-PAS.md` · `exercices/` · `solutions/`.

## Objectif

Faire persister l'API **sans fuite de session ni incohérence transactionnelle**, avec des
migrations versionnées.

## Pages de doc FastAPI couvertes

SQL (Relational) Databases · JSON Compatible Encoder (`jsonable_encoder`) · Dependencies with
`yield` (session par requête) · Lifespan Events (moteur) · How-To « Testing a Database ».

## Plan

1. SQLAlchemy 2.0 : `DeclarativeBase`, `Mapped`, `mapped_column`, relations.
2. Async : `create_async_engine`, `asyncpg`, `async_sessionmaker`, session via `Depends(yield)`.
3. Transactions : *unit of work*, frontière transactionnelle = couche service.
4. Repository sur SQLAlchemy ; mapping entité ORM ↔ schéma Pydantic.
5. Alembic : `init`, autogénération, revue, `upgrade`/`downgrade`, migration de données.
6. Pièges async : N+1, lazy loading, session partagée entre coroutines.
7. `docker-compose` avec PostgreSQL ; base de test jetable.

## Exercices (aperçu)

- Modèles `Project` + `Task` (relation 1-N) ; migration initiale.
- Brancher `SqlAlchemyTaskRepository` derrière le `Protocol` du Module 03.
- Requête liste filtrée + paginée **sans N+1** (`selectinload`), vérifiée via echo SQL.
- Rollback automatique de session en cas d'exception.
- **Mini-projet `shorturl`** (voir [`../projets/`](../projets/)).

## Definition of Done

Voir [`../ROADMAP.md`](../ROADMAP.md#module-04--bases-de-données--sqlalchemy-20-async--alembic-).
