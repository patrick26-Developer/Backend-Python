# Module 01 — Solutions : les choix de conception expliqués

> Le code est dans ce dossier. Ici, on explique **pourquoi** il est écrit ainsi. Une
> solution sans justification n'apprend rien : c'est le raisonnement qui se transfère au
> projet suivant.

## Fichiers

| Fichier | Rôle |
|---|---|
| [`models.py`](models.py) | Schémas Pydantic : `TaskStatus`, `TaskCreate`, `TaskUpdate`, `Task`, `TaskPage` |
| [`store.py`](store.py) | `InMemoryTaskStore` — persistance jetable, sans HTTP |
| [`main.py`](main.py) | L'application FastAPI et ses routes |
| [`scratch_models.py`](scratch_models.py) | Démo des validations (exercice 01.3) |
| [`test_solution.py`](test_solution.py) | Tests prouvant que tout le contrat tient |

**Lancer :**

```bash
fastapi dev 01-fondations-http-et-fastapi/solutions/main.py
python  -m 01-fondations-http-et-fastapi.solutions.scratch_models   # (ou depuis le dossier)
pytest 01-fondations-http-et-fastapi/solutions/
```

---

## Décision 1 — Trois schémas dès maintenant (`Create` / `Update` / `Read`)

On aurait pu faire un seul `Task` et s'en servir partout. **Non**, et voici pourquoi :

- **Un client ne doit jamais pouvoir fixer `id`, `created_at`, `status`.** Si `POST /tasks`
  accepte le modèle complet, quelqu'un enverra `{"id": 999, "created_at": "1970..."}`.
- **La sortie et l'entrée divergent vite** : au Module 06, `Task` aura un `owner_id` qu'on
  ne veut ni recevoir du client, ni forcément exposer.
- **`PATCH` a besoin de champs optionnels** que `POST` veut obligatoires.

Le surcoût (quelques classes) est dérisoire face au coût d'un modèle « à tout faire » qu'on
finit toujours par éclater dans la douleur. La séparation est approfondie au **Module 02**.

`TaskBase` factorise les champs communs + leurs validateurs ; `TaskCreate` en hérite tel
quel ; `Task` y ajoute les champs serveur.

## Décision 2 — `exclude_unset` pour le PATCH partiel

Dans `store.update` :

```python
patch = changes.model_dump(exclude_unset=True)
```

- `PATCH {}` → `patch == {}` → on ne touche à rien, on renvoie l'existant.
- `PATCH {"description": null}` → `patch == {"description": None}` → on **efface** la description.
- `PATCH {"status": "done"}` → seul `status` change ; `updated_at` est bumpé.

La distinction « champ absent » vs « champ à `null` » est **le** piège du PATCH. `exclude_unset`
la gère parce que Pydantic retient quels champs ont été explicitement fournis. On y revient
en détail au Module 02 (le cas des `null` explicites mérite mieux qu'une version naïve).

## Décision 3 — Le store ne connaît pas FastAPI

`store.py` n'importe ni `fastapi`, ni `HTTPException`. Il expose `create/get/list/update/delete`
et renvoie `None` / `False` quand une ressource manque. **C'est la route** qui traduit ça en
404. Pourquoi si tôt ?

- On pourra tester la logique sans client HTTP (Module 07).
- On pourra remplacer l'implémentation par SQLAlchemy sans toucher aux routes (Module 04).
- C'est la couche « repository » du **Module 03**, juste pas encore nommée ainsi.

`list()` renvoie `tuple[list[Task], int]` (les lignes **et** le total) : le total sert à la
pagination côté client. Son coût réel (un `COUNT(*)` sur des millions de lignes) est discuté
au Module 08.

## Décision 4 — `def` et non `async def`

Aucune I/O réelle ici. `async def` n'apporterait rien et exposerait au risque « code
bloquant dans une coroutine ». On passe à `async` au **Module 04**, quand le driver DB
l'impose. Règle : `async` suit un besoin, pas une mode.

## Décision 5 — Codes de statut explicites

- `POST` → `201 Created` + en-tête `Location: /tasks/{id}` (convention REST : où trouver la
  ressource créée).
- `DELETE` → `204 No Content`, corps vide.
- Ressource absente → `404` avec `{"detail": "..."}` (format par défaut de FastAPI ;
  uniformisé au Module 05).
- `id` invalide (`-1`, `abc`) → `422` **avant** d'atteindre le store, grâce à `Path(ge=1)`.
  Une entrée mal formée n'est pas un « pas trouvé ».

## Décision 6 — `HTTPException` maintenant, handler central plus tard

`raise HTTPException(404, ...)` est parfait pour démarrer. Mais répété dans 15 routes, c'est
du bruit et une incohérence qui guette. Au **Module 05**, on définira `TaskNotFoundError`
(exception métier) et **un** handler qui la convertit en 404. Les routes redeviendront :

```python
task = service.get(task_id)   # lève TaskNotFoundError si absent
return task
```

## Décision 7 — `alias="status"` sur le query param

Le paramètre Python s'appelle `status_filter` (pour ne pas masquer le module `status` de
FastAPI importé pour les constantes), mais l'API expose `?status=done`. `Query(alias=...)`
découple le nom interne du nom public — un réflexe utile.

## Décision 8 — Choix documentés là où il y a débat

Le 2ᵉ `DELETE` renvoie `404` (et non `204`). Les deux sont défendables :
- **404** : « tu as demandé à supprimer une ressource que tu croyais là ; elle n'y est pas,
  c'est une info utile. »
- **204** : idempotence stricte — le résultat (ressource absente) est le même.

On a tranché pour 404 **et on l'a écrit en commentaire dans le code**. Un choix assumé et
tracé vaut mieux qu'un choix implicite. Idem pour le tri par défaut (`-priority`).

---

## Grille d'auto-évaluation

Compare ta version à celle-ci, point par point :

- [ ] As-tu séparé entrée/sortie, ou un seul modèle ?
- [ ] Ton `PATCH {}` modifie-t-il quelque chose par erreur ?
- [ ] Ta logique de filtrage/tri est-elle dans la route ou ailleurs ?
- [ ] Tes `raise HTTPException` sont-ils cohérents (même `detail`, mêmes codes) ?
- [ ] `mypy --strict` passe-t-il sur *ton* code ?
- [ ] Un `id` négatif renvoie-t-il 422 ou 404 chez toi ? (attendu : 422)
- [ ] Tes datetimes sont-ils *timezone-aware* ?

Si ta solution diffère mais tient tous les critères d'acceptation **et** que tu peux
justifier chaque écart : c'est une bonne solution. Il n'y en a pas qu'une.

➡️ Module suivant : [`../../02-modelisation-et-validation/`](../../02-modelisation-et-validation/) *(à venir)*
