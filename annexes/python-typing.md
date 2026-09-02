# Annexe — Le typage Python utile pour FastAPI

> Rappel condensé, orienté « ce dont FastAPI se sert ». Réfère-toi à la doc officielle
> *Python Types Intro* pour le tutoriel complet.

## Pourquoi c'est central

FastAPI **lit tes annotations de type** pour : valider les entrées, sérialiser les sorties,
générer `/docs`, et donner l'autocomplétion. Une annotation n'est pas de la décoration :
c'est une **instruction exécutable** pour le framework.

## Les briques

| Écriture | Sens |
|---|---|
| `x: int` | `x` est un entier |
| `name: str \| None` | `str` **ou** `None` (union, Python 3.10+) |
| `items: list[str]` | liste de chaînes |
| `pairs: dict[str, int]` | dict clés `str`, valeurs `int` |
| `point: tuple[float, float]` | tuple de 2 flottants |
| `cb: Callable[[int], str]` | fonction `int -> str` |
| `status: Literal["a", "b"]` | seules `"a"` ou `"b"` |
| `T = TypeVar("T")` | type générique |

## `Annotated` — la clé de FastAPI moderne

```python
from typing import Annotated
from fastapi import Query

def search(q: Annotated[str | None, Query(max_length=50)] = None): ...
```

`Annotated[T, meta]` = « le type est `T`, avec en plus la métadonnée `meta` ». FastAPI lit
`meta` (`Query(...)`, `Path(...)`, `Depends(...)`) pour savoir d'où vient la valeur et
comment la valider. C'est la forme recommandée (mieux que les anciennes valeurs par défaut
`q: str = Query(...)`).

## `from __future__ import annotations`

À mettre en tête de fichier : rend les annotations « paresseuses » (évaluées seulement au
besoin). Permet les références en avant (`-> MyClass` dans `MyClass`) et allège l'exécution.
Pydantic v2 les résout correctement.

## Pydantic vs `dataclasses` vs `TypedDict`

- **`pydantic.BaseModel`** : validation + coercition + (dé)sérialisation + JSON Schema. Le
  choix par défaut pour tout contrat d'API.
- **`dataclasses`** : structure de données simple, **sans** validation runtime. FastAPI les
  accepte mais tu perds les validateurs.
- **`TypedDict`** : un `dict` typé pour le *type-checker*, zéro effet à l'exécution.

## mypy `--strict` : ce qu'il t'oblige à faire

- annoter **toutes** les fonctions (params + retour) ;
- pas de `Any` implicite ;
- pas d'`Optional` implicite (`def f(x: int = None)` interdit → `x: int | None = None`) ;
- gérer les `None` avant de déréférencer.

C'est exigeant au début, puis ça devient un filet qui attrape la moitié des bugs avant
l'exécution.

## Exercice express

Type cette fonction pour que `mypy --strict` passe :

```python
def group_by_first_letter(words):
    out = {}
    for w in words:
        out.setdefault(w[0], []).append(w)
    return out
```

<details><summary>Solution</summary>

```python
def group_by_first_letter(words: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for w in words:
        out.setdefault(w[0], []).append(w)
    return out
```
</details>
