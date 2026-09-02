# Module 02 — Solutions : les choix de conception

> Code dans ce dossier. Ici, **pourquoi** il est écrit ainsi. Explication ligne par ligne :
> [`../PAS-A-PAS.md`](../PAS-A-PAS.md).

## Fichiers

| Fichier | Rôle |
|---|---|
| [`models.py`](models.py) | `TaskStatus`, `ChecklistItem`, `TaskBase`, `TaskCreate`, `TaskUpdate`, `TaskRead`, `TaskFilters`, `TaskPage` |
| [`store.py`](store.py) | `InMemoryTaskStore` — parle `TaskRead`, `list(filters)`, PATCH via `model_validate` |
| [`main.py`](main.py) | routes + exemples OpenAPI |
| [`test_solution.py`](test_solution.py) | tests prouvant que le contrat tient |

```bash
fastapi dev 02-modelisation-et-validation/solutions/main.py
pytest 02-modelisation-et-validation/solutions/
```

---

## Décision 1 — La règle « échéance future » ne vit PAS dans `TaskBase`

Au Module 01, `TaskBase` portait `_due_date_in_future`. **Bug latent** : `TaskRead` hérite
de `TaskBase`. Une tâche créée hier avec échéance demain devient, demain, **impossible à
relire** (la validation refuse une échéance passée à la construction de `TaskRead`).

Correction : `TaskBase` ne porte que des validateurs de **format** (titre non vide, tags
bien formés, labels de checklist). La règle **métier** « échéance dans le futur » est un
`model_validator` sur **`TaskCreate`** et **`TaskUpdate`** uniquement. `TaskRead` accepte
n'importe quelle date — c'est un miroir de l'état, pas un formulaire.

> Leçon : **format ≠ métier**. Le format est vrai pour toujours ; une règle métier dépend du
> contexte (création vs lecture vs import de données historiques).

## Décision 2 — `is_overdue` : `@computed_field`, jamais stocké, jamais reçu

```python
@computed_field  # type: ignore[prop-decorator]
@property
def is_overdue(self) -> bool: ...
```

- **calculé à la lecture** : toujours juste, même si le temps passe sans qu'on touche la
  tâche. Un booléen stocké serait faux dès la seconde suivante.
- **absent de `TaskCreate`/`TaskUpdate`** : le client ne peut pas le fixer (il n'existe que
  sur `TaskRead`).
- `# type: ignore[prop-decorator]` : `computed_field` + `property` déroute mypy sur l'ordre
  des décorateurs ; c'est le *pattern* officiel Pydantic, l'ignore est assumé.

## Décision 3 — `title` : optionnel mais **non nullable** dans `TaskUpdate`

Trois états possibles pour un champ de PATCH : *absent*, *null*, *valeur*. Pour `title` on
veut : *absent* = OK (on n'y touche pas), *valeur* = OK, *null* = **refusé** (un titre vide
n'a pas de sens).

`title: str | None = None` seul autoriserait `null`. On ajoute un `model_validator` :

```python
if "title" in self.model_fields_set and self.title is None:
    raise ValueError("title ne peut pas être mis à null")
```

`model_fields_set` = l'ensemble des champs **explicitement fournis**. `{"title": null}` y
met `"title"` → on lève → 422. `{}` ne l'y met pas → on passe.

Pour `description`, au contraire, `null` **est** autorisé (effacer une description est
légitime). Le contrat encode l'intention.

## Décision 4 — PATCH : `model_dump(exclude_unset=True)` **puis** `model_validate`

```python
patch = changes.model_dump(exclude_unset=True)   # seuls les champs fournis
data = current.model_dump()                       # état complet actuel
data.update(patch)                                # on écrase ce qui change
data["updated_at"] = _now()
return TaskRead.model_validate(data)              # REVALIDE tout, y compris checklist
```

Pourquoi `model_validate` et pas `current.model_copy(update=patch)` ?
`model_copy` **ne valide pas** : une `checklist` passée en `list[dict]` (issue du
`model_dump`) resterait des `dict`, pas des `ChecklistItem`. `model_validate` reconstruit et
valide récursivement. Le champ `is_overdue` présent dans `data` est ignoré (recalculé).

## Décision 5 — `TaskFilters` : un query model avec `extra="forbid"`

```python
class TaskFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: TaskStatus | None = None
    ...
```

- **signature de route lisible** : `def list_tasks(filters: Annotated[TaskFilters, Query()])`
  au lieu de 7 paramètres.
- **`extra="forbid"`** : `GET /tasks?statuss=done` (faute de frappe) → **422**, au lieu de
  renvoyer silencieusement toutes les tâches. Un client qui se trompe le sait tout de suite.
- **testable isolément** : `TaskFilters(min_priority=3)` dans un test unitaire, sans HTTP.

## Décision 6 — `Decimal` pour `estimate_hours`, pas `float`

`Field(ge=0, max_digits=5, decimal_places=2)`. `"1.005"` (3 décimales) → 422. La sortie JSON
est une **chaîne** (`"2.5"`) : Pydantic sérialise `Decimal` en string pour ne jamais
introduire d'erreur d'arrondi binaire. Règle générale : **tout ce qui se compte en argent ou
en unités précises = `Decimal`**.

## Décision 7 — tags normalisés (`strip().lower()`)

Un tag `"  Docs "` et `"docs"` doivent être le **même** tag. On normalise à l'entrée
(`TaskCreate` et `TaskUpdate`). Conséquence : le filtre `?tag=docs` marche quelle que soit
la casse saisie à la création.

## Décision 8 — `separate_input_output_schemas=True` (le défaut, gardé)

FastAPI génère `TaskRead-Input` / `TaskRead-Output` dans OpenAPI parce que des champs ont
des défauts. On **garde** ce défaut : les générateurs de SDK produisent des types plus
justes (un champ à défaut est « optionnel en entrée, garanti en sortie »).

---

## Grille d'auto-évaluation

- [ ] Ta règle « échéance future » s'applique-t-elle par erreur à la **lecture** ?
- [ ] `is_overdue` est-il stocké (❌) ou calculé (✅) ?
- [ ] `PATCH {"title": null}` renvoie-t-il 422 chez toi ?
- [ ] `PATCH {"description": null}` efface-t-il bien (et pas « ignore ») ?
- [ ] Ton PATCH revalide-t-il la `checklist` imbriquée, ou laisse-t-il passer des `dict` ?
- [ ] Un query param inconnu est-il rejeté (422) ou avalé ?
- [ ] Un montant est-il un `float` quelque part dans ton code ? (il ne devrait pas)

➡️ [Module 03 — Architecture d'un projet mature](../../03-architecture-projet-mature/THEORIE.md)
