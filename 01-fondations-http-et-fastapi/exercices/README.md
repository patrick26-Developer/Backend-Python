# Module 01 — Exercices

> Fais-les **dans l'ordre**. Chaque exercice a des **critères d'acceptation** : tu n'as pas
> fini tant qu'ils ne sont pas tous vrais. Ne lis `../solutions/` qu'après avoir une version
> qui marche (même imparfaite).

**Mise en place :**

```bash
# venv actif
cp exercices/starter/main.py exercices/main.py      # ta copie de travail
fastapi dev 01-fondations-http-et-fastapi/exercices/main.py
```

Le fichier [`starter/main.py`](starter/main.py) contient des `# TODO` numérotés qui suivent
les exercices ci-dessous.

---

## Exercice 01.1 — First steps & OpenAPI 🟢

1. Lance le serveur. Ouvre `/docs`, `/redoc`, `/openapi.json`.
2. Ajoute un endpoint `GET /` qui renvoie
   `{"name": "taskman", "version": "0.1.0", "docs": "/docs"}` **typé** (annotation de retour).
3. Ajoute `GET /health` renvoyant `{"status": "ok"}`.
4. Dans `/openapi.json`, retrouve la description de tes deux routes.

**Critères d'acceptation**
- [ ] Les deux routes répondent 200 avec le bon JSON.
- [ ] Le retour de chaque fonction est annoté (pas de `dict` nu implicite).
- [ ] `/docs` liste les deux routes avec leur schéma de réponse.
- [ ] `ruff check` et `mypy` passent sur `exercices/main.py`.

---

## Exercice 01.2 — Path & query parameters 🟢

Crée un endpoint « bac à sable » `GET /echo/{item_id}` :

- `item_id` : entier `>= 1` (dans le *path*).
- `q` : chaîne optionnelle, longueur max 50 (query).
- `verbose` : booléen, défaut `False` (query).
- Réponse : `{"item_id": ..., "q": ..., "verbose": ...}` et si `verbose` est vrai, ajoute
  `"length": <longueur de q ou 0>`.

Teste manuellement :
- `/echo/1` → ok
- `/echo/0` → 422
- `/echo/abc` → 422
- `/echo/5?q=hello&verbose=true` → contient `"length": 5`
- `/echo/5?q=<51 caractères>` → 422

**Critères d'acceptation**
- [ ] Chaque cas ci-dessus se comporte comme indiqué.
- [ ] `item_id` et les contraintes sont déclarés via `Annotated[..., Path/Query(...)]`.
- [ ] La 422 mentionne le champ fautif.

---

## Exercice 01.3 — Modèles Pydantic 🟡

Dans un module `models.py` (à côté de `main.py`), définis :

### `TaskStatus` (énumération)
`todo`, `doing`, `done`.

### `TaskCreate` — ce que le client envoie pour créer
| champ | type | règle |
|---|---|---|
| `title` | `str` | 1–200 caractères, non vide après `strip()` |
| `description` | `str | None` | défaut `None` |
| `priority` | `int` | 1–5, défaut `3` |
| `due_date` | `datetime | None` | si fournie, **doit être dans le futur** |
| `tags` | `list[str]` | défaut `[]`, max 10, chaque tag 1–20 caractères |

### `TaskUpdate` — modification partielle (pour l'exo 01.5)
Tous les champs de `TaskCreate` en **optionnels** (`X | None = None`), plus `status`.

### `Task` — la ressource complète (ce que l'API renvoie)
`TaskCreate` + `id: int`, `status: TaskStatus` (défaut `todo`), `created_at: datetime`,
`updated_at: datetime`.

Écris un petit script `scratch_models.py` qui instancie `TaskCreate` avec :
- des données valides → OK ;
- `title="   "` → `ValidationError` ;
- `priority=9` → `ValidationError` ;
- `due_date` dans le passé → `ValidationError` ;
- 11 tags → `ValidationError`.

**Critères d'acceptation**
- [ ] Les 5 cas du script produisent le résultat attendu.
- [ ] `title` est *strippé* et rejeté si vide.
- [ ] `due_date` passée est refusée avec un message clair.
- [ ] `mypy --strict` passe sur `models.py`.
- [ ] Aucun défaut mutable écrit en `= []` (utilise `default_factory`).

---

## Exercice 01.4 — Store en mémoire 🟡

Dans `store.py`, implémente `InMemoryTaskStore` :

```python
class InMemoryTaskStore:
    def create(self, data: TaskCreate) -> Task: ...
    def get(self, task_id: int) -> Task | None: ...
    def list(
        self,
        *,
        status: TaskStatus | None = None,
        min_priority: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Task]: ...
    def update(self, task_id: int, changes: TaskUpdate) -> Task | None: ...
    def delete(self, task_id: int) -> bool: ...
```

Détails :
- `create` : attribue un `id` auto-incrémenté (commence à 1), `created_at`/`updated_at` = maintenant (UTC, *timezone-aware*), `status = todo`.
- `list` : filtre par `status` et `min_priority` si fournis, trie par `priority` décroissante
  puis `created_at` croissante, applique `offset` puis `limit`.
- `update` : n'applique que les champs *fournis* (`model_dump(exclude_unset=True)`), met à
  jour `updated_at`. Renvoie `None` si l'id n'existe pas.
- `delete` : renvoie `True` si supprimé, `False` si absent.

**Critères d'acceptation**
- [ ] `create` puis `get` renvoie la même tâche avec un `id >= 1`.
- [ ] Deux `create` successifs → ids différents et croissants.
- [ ] `list(status=..., min_priority=...)` filtre correctement.
- [ ] `update` avec un `TaskUpdate` partiel ne modifie **que** les champs fournis.
- [ ] `updated_at` change après un `update`, pas `created_at`.
- [ ] `delete` d'un id absent renvoie `False`.
- [ ] Les datetimes sont *aware* (`tzinfo` non nul).

---

## Exercice 01.5 — CRUD complet 🟡

Branche les endpoints sur le store. Un seul `store = InMemoryTaskStore()` au niveau module.

| Méthode & route | Statut succès | Comportement |
|---|---|---|
| `POST /tasks` | **201** | crée ; renvoie la `Task` ; ajoute l'en-tête `Location: /tasks/{id}` |
| `GET /tasks` | 200 | liste ; query : `status`, `min_priority` (1–5), `limit` (1–100, défaut 20), `offset` (≥ 0) |
| `GET /tasks/{id}` | 200 | la tâche, ou **404** `{"detail": "Task not found"}` |
| `PATCH /tasks/{id}` | 200 | applique les champs fournis ; **404** si absent |
| `DELETE /tasks/{id}` | **204** | pas de corps ; **404** si absent |

**Critères d'acceptation**
- [ ] Codes de statut exacts (201 create, 204 delete).
- [ ] `POST /tasks` renvoie l'en-tête `Location`.
- [ ] `GET /tasks/999` → 404 avec le bon corps.
- [ ] `PATCH /tasks/{id}` avec `{"status": "done"}` ne touche pas au titre.
- [ ] `DELETE` deux fois : 204 puis 404.
- [ ] Payload invalide sur `POST`/`PATCH` → 422.
- [ ] `/docs` décrit tous les paramètres et réponses.
- [ ] `ruff` + `mypy --strict` passent.

---

## Exercice 01.6 — Finitions & robustesse 🔴

1. **Pagination avec métadonnées** : ajoute `GET /tasks` une variante de réponse
   `{"items": [...], "total": N, "limit": L, "offset": O}` (garde l'ancienne en `/tasks/plain`
   si tu veux comparer). Réfléchis : pourquoi le `total` est utile côté client ? Quel est son
   coût quand il y a des millions de lignes ? (réponse au Module 08)
2. **Tri paramétrable** : `sort` = `priority` | `-priority` | `created_at` | `-created_at`
   (le `-` = décroissant), défaut `-priority`.
3. **Idempotence de `DELETE`** : documente le choix 404-vs-204 sur second appel (les deux
   sont défendables ; choisis et justifie en commentaire).
4. **Validation croisée** : interdis `PATCH` qui met `status=done` **et** `due_date` dans le
   futur en même temps si tu considères ça incohérent — ou justifie que ça ne l'est pas.
   L'objectif est de *raisonner* sur le contrat, pas de cocher une case.
5. **`GET /tasks/{id}` avec `id` négatif** : 422 (via `Path(ge=1)`), pas 404.

**Critères d'acceptation**
- [ ] La réponse paginée expose `total`, `limit`, `offset`, `items`.
- [ ] `sort=-created_at` renverse l'ordre par rapport à `sort=created_at`.
- [ ] Un commentaire dans le code justifie chaque choix de design des points 3 et 4.
- [ ] `GET /tasks/-1` → 422.

---

## Rendu du module dans `taskman/`

Une fois les exercices faits, reporte l'état final dans `taskman/` (à la racine du dépôt) :

```
taskman/
├── __init__.py
├── main.py         # app + routes
├── models.py       # TaskStatus, TaskCreate, TaskUpdate, Task
└── store.py        # InMemoryTaskStore
```

Puis :

```bash
ruff check . && ruff format --check . && mypy taskman && pytest
git add -A && git commit -m "feat(module-01): CRUD tasks en mémoire, typé et validé"
```

Compare enfin avec [`../solutions/`](../solutions/README.md) et lis
[`../solutions/README.md`](../solutions/README.md) : **les choix de conception** y sont
expliqués, pas seulement le code.
