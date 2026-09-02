# Module 04 — Bases de données : SQLAlchemy 2.0 async + Alembic

> **Objectif** : faire persister `taskman` dans une vraie base **sans fuite de session ni
> incohérence transactionnelle**, avec des **migrations versionnées**. Le repository devient
> `SqlAlchemyTaskRepository` — et grâce au Module 03, **le service et les routes ne
> changent presque pas**.
>
> **Durée estimée** : 12 à 16 h. **Le module le plus dense.**
> **Pré-requis** : Module 03 (couches + DI), notions de SQL.

---

## 1. Le tableau d'ensemble

```
requête HTTP
   │
route (async def) ──▶ service (async) ──▶ repository (async) ──▶ AsyncSession ──▶ moteur ──▶ PostgreSQL / SQLite
                         │                                            ▲
                         └── commit() / (rollback implicite) ─────────┘
                              = frontière transactionnelle
```

Nouveautés de ce module :

| Brique | Fichier | Rôle |
|---|---|---|
| moteur async | `db/engine.py` | `create_async_engine`, pool de connexions |
| modèles ORM | `db/models.py` | `ProjectRow`, `TaskRow` (les **tables**) |
| session | `db/session.py` | `get_session` : une session par requête (`Depends` + `yield`) |
| repository SQL | `repositories/sqlalchemy.py` | traduit schémas ↔ tables, exécute le SQL |
| migrations | `alembic/` | versionne le schéma, `upgrade` / `downgrade` |

---

## 2. `async` : pourquoi maintenant (et pas avant)

Au Module 01 on disait « pas d'`async` sans I/O réelle ». **Maintenant il y a une I/O
réelle** : chaque requête attend la base de données (quelques ms = une éternité CPU).

- une route `async def` qui `await` la base **rend la main** pendant l'attente → le worker
  traite d'autres requêtes ;
- **tout le chemin doit être async** : `async def` route → `await service` → `await repo` →
  `await session.execute(...)`. Un seul maillon synchrone bloquant casse la chaîne.

### Le coût de la migration (ce que le Module 03 a rendu indolore)

| Ce qui change | Ce qui **ne** change **pas** |
|---|---|
| `def` → `async def` partout | la **logique** des routes |
| `TaskRepository` : méthodes `async` | l'**interface** `TaskRepository` (juste `async`) |
| nouvelle impl `SqlAlchemyTaskRepository` | le `TaskService` (juste `await`) |
| `get_session` (dépendance `yield`) | la structure en couches |

C'est **exactement** le bénéfice promis au Module 03 : on remplace la couche basse sans
toucher au reste.

### Le piège n°1 : bloquer l'*event loop*

Dans une route `async`, **interdit** : `time.sleep()`, `requests.get()`, un gros calcul CPU,
un driver DB **synchrone** (`psycopg2` au lieu de `asyncpg`). Ça gèle *toutes* les requêtes.
Si tu dois appeler du code bloquant : `await asyncio.to_thread(fonction_bloquante, ...)`.

---

## 3. SQLAlchemy 2.0 : déclarer des tables

Style moderne : `Mapped[...]` + `mapped_column(...)`.

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase): ...

class ProjectRow(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    tasks: Mapped[list["TaskRow"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )

class TaskRow(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus, native_enum=False, length=16))
    project: Mapped["ProjectRow"] = relationship(back_populates="tasks")
```

- `Mapped[int]` non-optionnel → colonne `NOT NULL`. `Mapped[str | None]` → nullable.
- `ForeignKey(..., ondelete="CASCADE")` : supprimer un projet supprime ses tâches (côté base).
- `relationship(back_populates=...)` : le lien bidirectionnel objet ↔ objet.
- `cascade="all, delete-orphan"` : côté **ORM** (si tu retires une tâche de `project.tasks`).
- `passive_deletes=True` : fais confiance au `ON DELETE CASCADE` de la base, ne charge pas
  les enfants pour les supprimer un par un.

### `ProjectRow` / `TaskRow` vs `ProjectRead` / `TaskRead`

**Deux mondes séparés** :

| | rôle | couche |
|---|---|---|
| `TaskRow` (ORM) | ligne de table, liée à une session | `db/models.py` |
| `TaskRead` (Pydantic) | contrat d'API, sérialisable, sans session | `schemas/` |

Le repository fait la traduction : `TaskRead.model_validate(row)` (grâce à
`model_config = ConfigDict(from_attributes=True)`). **On ne renvoie jamais un objet ORM à
travers les couches** — il porte une session, il « lazy-load », il fuit.

### Types délicats

- **datetime + fuseau** : SQLite perd le `tzinfo`. Un `TypeDecorator` (`TZDateTime`) force
  UTC *aware* à l'écriture ET à la lecture. PostgreSQL n'en a pas besoin mais le type reste
  inoffensif.
- **enum** : `native_enum=False` → stocké en `VARCHAR` → portable SQLite/PostgreSQL, et une
  migration n'a pas à gérer un type ENUM natif.
- **`Decimal`** : `Numeric(5, 2)`, jamais `Float`.
- **listes / JSON** (`tags`, `checklist`) : colonne `JSON`. Simple, mais on ne peut pas
  requêter « toutes les tâches où checklist[2].done = true » efficacement. Si tu en as
  besoin → une vraie table `checklist_items`. Choix de simplicité assumé ici.

---

## 4. Le moteur et le pool de connexions

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine("postgresql+asyncpg://...", pool_pre_ping=True, echo=False)
session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
```

- créé **une fois**, au démarrage (`lifespan`), rangé dans `app.state`. Fermé à l'arrêt
  (`await engine.dispose()`).
- `pool_pre_ping=True` : teste une connexion avant de la réutiliser (évite les
  « MySQL server has gone away » / connexions mortes).
- `echo=True` : journalise **chaque requête SQL** — l'outil pour traquer un N+1.
- `async_sessionmaker` : la **fabrique** de sessions.
  - `expire_on_commit=False` : après `commit()`, les objets restent lisibles (sinon accéder
    à un attribut relance une requête… qui échoue hors session).
  - `autoflush=False` : on contrôle les `flush()` nous-mêmes (plus prévisible).

### Driver : `asyncpg` (PostgreSQL) / `aiosqlite` (SQLite)

L'URL encode le driver : `postgresql+asyncpg://…`, `sqlite+aiosqlite:///./taskman.db`. **Un
driver synchrone (`psycopg2`) dans un moteur async → erreur.**

---

## 5. La session : une par requête (`Depends` + `yield`)

```python
async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session          # fournie à la route / au repository
    # sortie du `async with` : la session est fermée.
    # Si une exception a traversé : rien n'est committé → rollback implicite.
```

- **une session = une requête HTTP**. Jamais une session globale, jamais partagée entre
  requêtes, jamais partagée entre coroutines.
- `async with factory() as session` : ouvre, et **ferme quoi qu'il arrive** (le `finally`
  est géré par le contexte).
- pas de `commit()` ici : c'est le **service** qui décide.

### Le graphe de dépendances

```python
def get_task_repository(session: SessionDep) -> TaskRepository:
    return SqlAlchemyTaskRepository(session)

def get_task_service(repo=Depends(get_task_repository), session: SessionDep) -> TaskService:
    return TaskService(repo, uow=session)
```

`get_session` est demandé par `get_task_repository` **et** `get_task_service`. FastAPI
**met en cache les sous-dépendances dans une requête** → les deux reçoivent **la même
session**. Le repository écrit dessus, le service la commit. Cohérent.

---

## 6. Transactions : *Unit of Work*, et où est la frontière

**Une transaction** = un groupe d'écritures « tout ou rien ». `commit()` valide, `rollback()`
annule.

### Où committer ? → dans le **service**

```python
class TaskService:
    def __init__(self, tasks: TaskRepository, uow: UnitOfWork) -> None:
        self._tasks, self._uow = tasks, uow

    async def create(self, data: TaskCreate) -> TaskRead:
        task = await self._tasks.create(data)   # ajoute + flush (pas de commit)
        await self._uow.commit()                # <- LA frontière transactionnelle
        return task

    async def get(self, task_id): return await self._tasks.get(task_id)   # lecture : pas de commit
```

Pourquoi le service et pas le repository ni la route ?

- **le repository** est trop bas : un cas d'usage peut enchaîner *plusieurs* appels
  repository qui doivent être **une seule** transaction (créer une commande + décrémenter le
  stock). Si chaque méthode committait, impossible de les grouper.
- **la route** est trop haut (couche HTTP) et ne devrait pas connaître le concept de
  transaction.
- **le service** représente le **cas d'usage métier** = l'unité atomique naturelle.

### `UnitOfWork`, un `Protocol` de plus

```python
class UnitOfWork(Protocol):
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
```

`AsyncSession` **satisfait** ce `Protocol` (elle a `commit`/`rollback` async). Le service
dépend de `UnitOfWork`, pas de `AsyncSession` → il ne « connaît » pas SQLAlchemy.

### `flush()` vs `commit()`

- `flush()` : envoie le SQL en attente à la base **dans la transaction courante** (pour
  obtenir un `id` auto-généré, par exemple), **sans** valider.
- `commit()` : `flush()` + valide la transaction.

Le repository fait `add()` + `flush()` + `refresh()` (pour récupérer les valeurs par défaut
de la base). Le service fait `commit()`.

### Rollback

Si une exception traverse la requête, le `async with factory() as session` ferme la session
**sans commit** → la transaction est abandonnée (rollback). Rien à écrire de spécial pour le
cas simple. (Module 05 : on attrape les exceptions et on renvoie une réponse propre.)

---

## 7. Écrire des requêtes (SQLAlchemy 2.0 : `select()`)

```python
from sqlalchemy import select, func, or_

stmt = select(TaskRow).where(TaskRow.project_id == pid)
if q:
    like = f"%{q}%"
    stmt = stmt.where(or_(TaskRow.title.ilike(like), TaskRow.description.ilike(like)))

# total AVANT pagination
total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))

# page
stmt = stmt.order_by(TaskRow.priority.desc()).limit(limit).offset(offset)
rows = (await session.scalars(stmt)).all()
```

- `session.scalars(stmt)` → un itérable d'objets `TaskRow`.
- `session.scalar(stmt)` → **une** valeur (le `COUNT`).
- `session.execute(stmt)` → des *rows* (tuples) quand on sélectionne plusieurs colonnes.
- `.order_by(None)` avant de compter : enlève le tri inutile de la sous-requête de `COUNT`.

---

## 8. Le problème **N+1**

```python
# GET /projects — VERSION NAÏVE (N+1)
projects = (await session.scalars(select(ProjectRow))).all()   # 1 requête
for p in projects:
    count = len(p.tasks)     # ← 1 requête PAR projet !  (lazy load)
```

100 projets → **101 requêtes**. En async, le *lazy load* dans une boucle lève même souvent
une erreur (`MissingGreenlet`).

### Les parades

| Besoin | Solution |
|---|---|
| compter les enfants | `func.count` + `JOIN` + `GROUP BY` en **1 requête** |
| charger les enfants (les objets) | `selectinload(ProjectRow.tasks)` → 2 requêtes au total |
| charger une relation *-to-one | `joinedload(TaskRow.project)` → 1 requête avec `JOIN` |

```python
# GET /projects — CORRECT : task_count en 1 requête
count_col = func.count(TaskRow.id).label("task_count")
stmt = (
    select(ProjectRow, count_col)
    .outerjoin(TaskRow, TaskRow.project_id == ProjectRow.id)
    .group_by(ProjectRow.id)
)
for project, task_count in (await session.execute(stmt)).all(): ...
```

**Comment détecter un N+1** : `create_async_engine(url, echo=True)` et compte les `SELECT`
dans les logs pour un endpoint de liste. Un `SELECT` par ligne = N+1.

---

## 9. Alembic : les migrations

Le schéma de la base **évolue**. Alembic versionne cette évolution en fichiers Python.

### Mise en place (déjà faite dans `taskman`)

- `alembic.ini` : config (la chaîne de connexion **n'y est pas** — lue depuis `Settings`).
- `alembic/env.py` : configuré pour un moteur **async**, pointe sur `Base.metadata`.
- `alembic/versions/` : les migrations, une par changement.

### Le cycle

```bash
# 1. tu modifies taskman/db/models.py (ajout d'une colonne, d'un index…)
# 2. tu génères la migration
alembic revision --autogenerate -m "add task.archived_at"
# 3. tu RELIS le fichier généré (autogenerate n'est pas parfait)
# 4. tu appliques
alembic upgrade head
# revenir en arrière d'un cran :
alembic downgrade -1
```

### Règles

- **relis toujours** la migration autogénérée. Elle rate : les renommages (voit un `drop` +
  un `add` = perte de données !), certains changements de type, les données à migrer.
- **une migration = un déploiement**. Ne modifie jamais une migration déjà appliquée en
  prod ; fais-en une nouvelle.
- **compatibilité** : en prod, la migration tourne pendant que l'ancienne version du code
  vit encore (déploiement progressif). Ajout de colonne nullable = OK. Suppression de
  colonne = en 2 temps (Module 11).
- **migrations de données** (`op.execute("UPDATE …")`) : possibles, mais lentes sur grosse
  table → à faire hors-ligne ou par lots.

### Le garde-fou

Un test lance `alembic upgrade head` puis `alembic check` : si tu as changé un modèle sans
générer la migration, **le test échoue**. (Voir `tests/integration/test_migrations.py`.)

---

## 10. Tester avec une base

- **base jetable par test** : SQLite **en mémoire** (`sqlite+aiosqlite://`) avec `StaticPool`
  (une seule connexion partagée, sinon chaque connexion voit une base vide).
- tables créées via `Base.metadata.create_all` (rapide) — **et** un test dédié vérifie que
  les **migrations** produisent le même schéma.
- `httpx.AsyncClient` + `ASGITransport` : teste l'app **dans le même *event loop***
  (obligatoire pour l'async ; `TestClient` synchrone pose des problèmes de boucle avec
  l'async DB). Détaillé au Module 07.
- override : `app.dependency_overrides[get_session] = <session de test>`.

> SQLite ≠ PostgreSQL (types, `ILIKE`, contraintes…). Pour les projets sérieux : tests
> d'intégration sur un **vrai PostgreSQL** via `testcontainers` (Module 07). SQLite reste
> parfait pour un feedback rapide.

---

## 11. Pièges fréquents

1. **Driver synchrone** (`postgresql://` au lieu de `postgresql+asyncpg://`) dans un moteur async.
2. **Session globale / partagée** entre requêtes ou coroutines → corruption, erreurs aléatoires.
3. **Renvoyer un objet ORM** à travers les couches → *lazy load* hors session, la couche SQL fuit.
4. **N+1** sur les endpoints de liste (non détecté sans `echo=True`).
5. **`expire_on_commit=True`** (défaut) : accès à un attribut après `commit()` → requête → crash hors session.
6. **Committer dans le repository** → impossible de grouper plusieurs opérations en une transaction.
7. **Migration autogénérée non relue** : un renommage devient `drop`+`add` = données perdues.
8. **`datetime` naïf** stocké/lu depuis SQLite → `is_overdue` casse. Utilise un `TypeDecorator`.
9. **FK non appliquées sous SQLite** : oublier `PRAGMA foreign_keys=ON`.
10. **Oublier `alembic upgrade head`** avant de lancer l'app sur une base neuve.

---

## 12. Ce que `taskman` gagne

- `db/` : `Base`, `TZDateTime`, `ProjectRow` + `TaskRow` (FK + relation), moteur async, `get_session` ;
- `SqlAlchemyTaskRepository` + `SqlAlchemyProjectRepository` (async) ;
- `TaskRepository`/`ProjectRepository`/`UnitOfWork` : `Protocol` **async** ;
- `TaskService`/`ProjectService` async, **frontière transactionnelle** (`commit`) ;
- routes `async def` + nouveau router `projects` (`task_count` **sans N+1**) ;
- Alembic configuré async + migration initiale + test « pas de migration en retard » ;
- `docker-compose.yml` (PostgreSQL local) ;
- tests sur SQLite async in-memory, isolés.

---

## 13. À savoir refaire sans aide

- Déclarer 2 tables liées par une FK + relation, style SQLAlchemy 2.0.
- Monter un moteur async + `async_sessionmaker` + dépendance `get_session` (`yield`).
- Écrire un repository async : `select`, `where`, `func.count`, pagination, tri.
- Placer le `commit()` dans le service, expliquer pourquoi pas ailleurs.
- Reconnaître et corriger un N+1 (`echo=True`, puis `JOIN`/`selectinload`).
- `alembic revision --autogenerate` → relire → `upgrade` → `downgrade`.
- Tester un repository sur une base SQLite jetable.

➡️ [Exercices](exercices/README.md) · [PAS-A-PAS.md](PAS-A-PAS.md)
