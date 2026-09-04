# Module 04 — Solutions : les choix de conception

> Code dans `taskman/` + [`alembic/`](alembic/). Explication ligne par ligne :
> [`../PAS-A-PAS.md`](../PAS-A-PAS.md).

```bash
cd 04-bases-de-donnees/solutions
alembic upgrade head          # crée taskman.db
pytest                        # tests sur SQLite in-memory
mypy taskman
```

---

## Décision 1 — `async` partout, d'un coup

On ne fait pas de « moitié async ». Route `async def` → `await service` → `await repo` →
`await session.execute()`. Un seul maillon synchrone bloquant (un vieux driver, un
`time.sleep`, un gros calcul) gèle **toutes** les requêtes du worker. Le Module 03 a rendu
cette bascule quasi indolore : seule l'interface `TaskRepository` gagne `async`, le service
gagne des `await`, et on ajoute une implémentation.

## Décision 2 — Deux modèles séparés : `TaskRow` (ORM) et `TaskRead` (Pydantic)

| | `TaskRow` | `TaskRead` |
|---|---|---|
| c'est quoi | une ligne de table, attachée à une session | un contrat d'API, autonome |
| vit dans | `db/models.py` | `schemas/` |
| traverse les couches ? | **non**, jamais au-delà du repository | oui |

Le repository **traduit** : `TaskRead.model_validate(row)` (grâce à `from_attributes=True`).
Renvoyer un `TaskRow` plus haut = il porte une session, il *lazy-load*, il casse hors
requête. La séparation schéma/ORM est le pendant, côté données, de la séparation
Create/Read côté API (Module 02).

## Décision 3 — `commit()` dans le **service**, jamais dans le repository

```python
async def create(self, data):
    task = await self._tasks.create(data)   # repo : add + flush (PAS de commit)
    await self._uow.commit()                # service : LA frontière transactionnelle
    return task
```

Si le repository committait, on ne pourrait **jamais** grouper deux opérations en une seule
transaction (créer une commande **et** décrémenter le stock = tout ou rien). Le service =
le cas d'usage métier = l'unité atomique. Le repository ne fait que `flush()` (pour obtenir
les `id`).

`update`/`delete` ne committent que si l'opération a **effectivement** touché une ligne
(sinon : commit d'une transaction vide, inutile).

## Décision 4 — `UnitOfWork`, un `Protocol` — le service ne connaît pas SQLAlchemy

```python
class UnitOfWork(Protocol):
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
```

`AsyncSession` satisfait ce `Protocol` structurellement. Le service dépend de `UnitOfWork`,
pas de `AsyncSession`. Bénéfice : `test_service.py` teste le service avec un `SpyUoW` de
5 lignes, sans base.

## Décision 5 — La session : `Depends` + `yield`, une par requête, fermée quoi qu'il arrive

`get_session` ouvre un `async with factory() as session`. À la fin de la requête (succès **ou**
exception), la session est fermée. Pas de commit ici → si une exception est passée, la
transaction est perdue (rollback implicite). **Jamais** de session globale, **jamais**
partagée entre requêtes.

Le repo et le service demandent tous deux `get_session` → FastAPI **cache la
sous-dépendance** → **une seule** session partagée. Le repo écrit dessus, le service la
commit.

## Décision 6 — `TZDateTime` : un `TypeDecorator` contre le piège SQLite

SQLite renvoie des `datetime` **naïfs**. `is_overdue` compare `due_date < now(UTC)` → un
naïf vs un *aware* lève `TypeError`. `TZDateTime` force UTC *aware* à l'écriture et à la
lecture. PostgreSQL n'en a pas besoin, mais le type est inoffensif — on l'applique partout
pour la cohérence.

## Décision 7 — `tags` / `checklist` en colonnes JSON

Choix de **simplicité assumé**. Une checklist avec des opérations par item (cocher l'item 3,
requêter « tâches avec un item en retard ») mériterait une table `checklist_items`. Ici, on
se concentre sur l'async / les sessions / les migrations. La limite est documentée dans
`db/models.py`.

## Décision 8 — `status` en `VARCHAR` (`native_enum=False`)

Un type ENUM natif PostgreSQL complique les migrations (ajouter une valeur = migration
spéciale) et n'existe pas en SQLite. Stocké en texte : portable, et ajouter `TaskStatus.blocked`
plus tard ne demande **aucune** migration de schéma.

## Décision 9 — `GET /projects` : `task_count` en **une** requête

`SELECT projects.*, COUNT(tasks.id) ... LEFT JOIN tasks ... GROUP BY projects.id`. La version
naïve (`for p in projects: len(p.tasks)`) fait 1 requête par projet = **N+1**. En async, le
lazy-load dans une boucle lève souvent `MissingGreenlet`. On détecte un N+1 avec
`create_engine(url, echo=True)` et en comptant les `SELECT`.

## Décision 10 — Tests : SQLite in-memory + un garde-fou sur les migrations

- schéma de test via `Base.metadata.create_all` (rapide) ;
- `test_migrations.py` vérifie séparément que `alembic upgrade head` produit **le même**
  schéma (`alembic check` → « no changes ») → tu ne peux pas oublier une migration ;
- `httpx.AsyncClient` + `ASGITransport` : même *event loop* que la base async (obligatoire).

---

## Grille d'auto-évaluation

- [ ] Un `TaskRow` traverse-t-il tes couches (❌) ou seul un `TaskRead` (✅) ?
- [ ] Ton `commit()` est-il dans le service (✅), le repo (❌) ou la route (❌) ?
- [ ] `GET /projects` fait-il 1 requête ou N+1 ? (mets `db_echo=true` et compte)
- [ ] `expire_on_commit` : `False` chez toi ?
- [ ] SQLite : `PRAGMA foreign_keys=ON` bien posé ? (teste `project_id` inexistant)
- [ ] `alembic downgrade -1` puis `upgrade head` : ça repasse ?
- [ ] Modifier un modèle sans migration → ton `test_migrations` échoue-t-il ?

➡️ [Module 05 — Erreurs, logs & middleware](../../05-erreurs-logs-middleware/THEORIE.md)
