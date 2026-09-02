# Module 02 — Exercices

> Ordre imposé. Chaque exercice liste ses **critères d'acceptation**. Ne lis `../solutions/`
> qu'après avoir une version qui marche.

**Mise en place :**

```bash
# venv actif ; on repart de l'état taskman du Module 01
cp -r taskman taskman_backup_m01     # filet de sécurité (à supprimer ensuite)
```

Tu vas faire évoluer `taskman/` directement. Point de départ pour expérimenter à part :
[`starter/`](starter/).

Dépendance nouvelle de ce module :

```bash
pip install "pydantic[email]"        # pour EmailStr  (déjà dans pyproject via fastapi[standard])
```

---

## Exercice 02.1 — Éclater le modèle en `Create` / `Update` / `Read` 🟡

Aujourd'hui `taskman` a `TaskBase` / `TaskCreate` / `TaskUpdate` / `Task`. On durcit la
séparation :

1. Renomme `Task` → `TaskRead` (c'est un **contrat de sortie**, nomme-le comme tel).
2. Ajoute à `TaskCreate` un champ `project_id: int = Field(ge=1)` **obligatoire** (une tâche
   appartient toujours à un projet). Il **ne doit pas** être dans `TaskUpdate` (on ne
   déplace pas une tâche de projet dans ce module).
3. Ajoute à `TaskRead` un champ **calculé** `is_overdue: bool` :
   `True` si `due_date` est passée **et** `status != done`. Ce champ n'existe **ni** dans
   `TaskCreate` **ni** dans `TaskUpdate`.
   - implémente-le avec `@computed_field` + `@property`, ou en le calculant dans le store.
4. Vérifie dans `/docs` que `project_id` apparaît sur `POST` mais pas sur `PATCH`, et que
   `is_overdue` apparaît sur les réponses mais pas sur les entrées.

**Critères d'acceptation**
- [ ] `POST /tasks` sans `project_id` → 422.
- [ ] `PATCH /tasks/{id}` avec `{"project_id": 2}` → le champ est **ignoré** ou rejeté (choisis, documente).
- [ ] `POST /tasks` avec `{"id": 99, "is_overdue": true, "created_at": "2000-..."}` → ces champs sont **ignorés** (le serveur reste maître).
- [ ] `GET` d'une tâche en retard non terminée → `"is_overdue": true`.
- [ ] `mypy --strict` + `ruff` OK.

---

## Exercice 02.2 — Le `PATCH` correct (null explicite vs absent) 🔴

1. Écris un test (ou un script) qui envoie successivement à `PATCH /tasks/{id}` :
   - `{}` → la tâche est **inchangée** ;
   - `{"description": null}` → `description` devient `null` ;
   - `{"description": "nouveau"}` → `description` devient `"nouveau"` ;
   - `{"tags": []}` → les tags sont **vidés** (liste vide, pas « inchangé »).
2. Assure-toi que le store applique `model_dump(exclude_unset=True)` et **pas** `exclude_none`.
3. Cas piège : `PATCH {"due_date": null}` sur une tâche qui avait une échéance → l'échéance
   est retirée, et `is_overdue` repasse à `false`.
4. Documente en commentaire : ton API **autorise-t-elle** de remettre `title` à `null` ?
   (réponse attendue : non — `title` reste `str`, pas `str | None`, même dans `TaskUpdate`.)

**Critères d'acceptation**
- [ ] Les 4 cas du point 1 se comportent exactement comme décrit.
- [ ] `PATCH {"title": null}` → 422 (`title` non nullable).
- [ ] `PATCH {"due_date": null}` retire l'échéance et recalcule `is_overdue`.
- [ ] Un test automatisé couvre ces cas.

---

## Exercice 02.3 — Sous-ressource imbriquée : `checklist` 🟡

1. Nouveau modèle `ChecklistItem` : `label: str` (1–120, non vide après strip), `done: bool = False`.
2. `TaskCreate` et `TaskRead` gagnent `checklist: list[ChecklistItem]`
   (`default_factory=list`, `max_length=50`).
3. `TaskUpdate` gagne `checklist: list[ChecklistItem] | None = None` (remplacement complet de
   la liste si fournie).
4. Teste : `POST` avec `checklist: [{"label": "  "}]` → 422 avec un chemin d'erreur
   **précis** (`body.checklist.0.label`).
5. Réfléchis : remplacer toute la liste à chaque `PATCH`, est-ce le bon design ? Quelles
   seraient les alternatives (endpoints dédiés `POST /tasks/{id}/checklist`) ? Écris 3 lignes
   de conclusion en commentaire.

**Critères d'acceptation**
- [ ] `checklist` validée récursivement ; message d'erreur avec l'index fautif.
- [ ] `POST` avec 51 items → 422.
- [ ] `GET` renvoie la checklist ; `PATCH {"checklist": [...]}` la remplace.
- [ ] Ta note de conception (point 5) est dans le code.

---

## Exercice 02.4 — Types riches : `assignee_email` et `estimate` 🟡

1. `TaskCreate` / `TaskUpdate` / `TaskRead` : `assignee_email: EmailStr | None = None`.
2. `TaskCreate` / `TaskRead` : `estimate_hours: Decimal | None` avec
   `Field(default=None, ge=0, max_digits=5, decimal_places=2)` — **pas** un `float`.
3. Vérifie : `assignee_email="pas-un-email"` → 422 ; `estimate_hours="2.5"` → OK (string
   coercée en `Decimal`) ; `estimate_hours=1.005` → 422 (trop de décimales).
4. Dans la réponse JSON, `estimate_hours` sort comme une **chaîne** (`"2.5"`, pas un nombre)
   — comprends pourquoi : Pydantic sérialise `Decimal` en string pour ne **jamais** perdre
   de précision (un `float` JSON pourrait arrondir). Note : Pydantic ne *complète* pas les
   zéros (`2.5`, pas `2.50`) — c'est fidèle, c'est l'essentiel.

**Critères d'acceptation**
- [ ] `EmailStr` rejette une adresse invalide (422).
- [ ] `estimate_hours` est un `Decimal`, jamais un `float`, dans tout le code.
- [ ] `"1.005"` (3 décimales) → 422 ; `-1` → 422.
- [ ] La sortie JSON de `estimate_hours` est une chaîne fidèle (pas d'arrondi binaire).

---

## Exercice 02.5 — Regrouper les filtres dans un query model 🟡

1. Crée `TaskFilters(BaseModel)` avec `model_config = {"extra": "forbid"}` :
   `status`, `min_priority` (1–5), `q` (str, max 100 — recherche naïve sur `title` +
   `description`), `project_id`, `sort` (`Literal[...]`), `limit` (1–100, déf. 20),
   `offset` (≥ 0, déf. 0).
2. `GET /tasks` prend `filters: Annotated[TaskFilters, Query()]`.
3. Le store gagne une méthode `list(filters: TaskFilters) -> tuple[list[TaskRead], int]`.
4. Vérifie : `GET /tasks?statuss=done` (faute de frappe) → **422** (`extra="forbid"`).
5. Vérifie : `GET /tasks?q=doc&min_priority=3&sort=-created_at` combine tout.

**Critères d'acceptation**
- [ ] La signature de `list_tasks` tient sur une ligne (`filters` unique).
- [ ] Un paramètre de query inconnu → 422.
- [ ] `q` filtre sur titre **et** description, insensible à la casse.
- [ ] `TaskFilters` est testable isolément (instancie-le dans un test unitaire).

---

## Exercice 02.6 — Exemples OpenAPI & finitions 🟢

1. Ajoute des `examples=[...]` pertinents sur les champs clés de `TaskCreate`.
2. Sur la route `POST /tasks`, ajoute `Body(openapi_examples={...})` avec 2 exemples nommés :
   « minimal » (juste `title` + `project_id`) et « complet » (tous les champs).
3. Ajoute `model_config["json_schema_extra"]["examples"]` sur `TaskRead`.
4. Ouvre `/docs` : le bouton « Try it out » de `POST /tasks` propose les 2 exemples.
5. Passe `separate_input_output_schemas` à `False` sur l'app, observe la différence dans
   `openapi.json`, puis **remets `True`** (le défaut) et explique en commentaire pourquoi.

**Critères d'acceptation**
- [ ] `/docs` montre des exemples réalistes sur l'entrée et la sortie.
- [ ] Les 2 exemples nommés apparaissent dans le sélecteur de `POST /tasks`.
- [ ] Ton commentaire justifie le choix `separate_input_output_schemas=True`.

---

## Rendu du module

```
taskman/
├── __init__.py
├── main.py
├── models.py       # TaskStatus, ChecklistItem, TaskCreate, TaskUpdate, TaskRead, TaskFilters, TaskPage
└── store.py        # InMemoryTaskStore avec list(filters), calcul is_overdue
```

```bash
ruff check . && ruff format --check . && mypy taskman && pytest
git add -A && git commit -m "feat(module-02): schémas Create/Update/Read, PATCH correct, types riches, query model"
```

Puis lis [`../solutions/README.md`](../solutions/) (les choix) et
[`../PAS-A-PAS.md`](../PAS-A-PAS.md) (ligne par ligne).

**Mini-projet associé** : [`../../projets/checkpoints/linkstash/`](../../projets/checkpoints/linkstash/BRIEF.md).
