# `linkstash` — les choix de conception

> Ce qu'il fallait voir dans ce checkpoint, et pourquoi la solution est écrite ainsi.

## 1. Trois schémas, pas un

`BookmarkCreate` (entrée POST), `BookmarkUpdate` (entrée PATCH), `BookmarkRead` (sortie) sont
**distincts** — c'est le cœur du Module 02.

- `Create` exige `url` + `title`. `Read` ajoute `id` et `created_at` (champs **serveur**, jamais
  fournis par le client).
- `Update` a **tous** les champs optionnels **et** `model_config = {"extra": "forbid"}` : un
  `PATCH {"favourite": true}` (faute de frappe) renvoie 422 au lieu d'être ignoré silencieusement.

## 2. `PATCH` correct : distinguer « absent » de « null »

```python
changes = patch.model_dump(exclude_unset=True)
if "note" in changes:      # la clé n'est là QUE si le client l'a envoyée
    bookmark.note = changes["note"]   # peut être None → efface
```

- `PATCH {}` → `changes` vide → rien ne bouge.
- `PATCH {"note": null}` → `"note" in changes` **et** valeur `None` → note effacée.
- `PATCH {"title": null}` → refusé (422) par le `model_validator` : `title` est optionnel
  (on peut l'omettre) mais **non nullable** (on ne peut pas l'effacer).

`exclude_unset=True` est la clé. `exclude_none=True` serait un **bug** : il rendrait
impossible l'effacement volontaire de `note`.

## 3. Unicité d'URL : normalisation avant comparaison

```python
def _canonical(url: str) -> str:
    return url.strip().rstrip("/").lower()
```

`https://site.fr/page` et `https://site.fr/page/` sont le **même** marque-page → 409. La
comparaison se fait sur une forme canonique, pas sur la chaîne brute. (Une vraie app irait
plus loin : normaliser le schéma, retirer `utm_*`, trier la query-string — hors périmètre ici,
mais le point d'extension est isolé dans une seule fonction.)

## 4. Le store possède les règles, pas les routes

`BookmarkStore` porte l'unicité, le filtrage, le tri, la pagination et le comptage de tags.
Les routes font trois lignes : valider (Pydantic), appeler le store, mapper vers `BookmarkRead`.
Quand on branchera une vraie base au checkpoint suivant, **seul le store change** — routes et
schémas sont déjà à leur place. C'est la préparation au Module 03 (architecture en couches).

## 5. Erreurs métier → exceptions → handlers

Le store lève `DuplicateURLError` / `BookmarkNotFoundError` (des exceptions **du domaine**, qui
ne connaissent pas HTTP). `api.py` enregistre deux `exception_handler` qui les traduisent en
409 / 404 au format **RFC 9457** (`application/problem+json`). Le store reste testable sans
FastAPI ; les codes HTTP ne fuient pas dans la logique.

## 6. Tri déterministe

```python
key_fn, reverse = _sort_key(sort)
rows.sort(key=lambda b: b.id, reverse=reverse)   # clé secondaire d'abord
rows.sort(key=key_fn, reverse=reverse)           # clé primaire (tri stable de Python)
```

Deux marque-pages créés « à la même seconde » ressortent toujours dans le même ordre (par id).
Un tri non déterministe rend les tests *flaky* et la pagination incohérente. Le tri par titre
est **insensible à la casse** (`b.title.lower()`) : `"alpha"` avant `"Bravo"`.

> Détail Python : nommer la méthode `list()` casserait l'annotation `-> list[...]` des autres
> méthodes (le nom masque le type intégré). D'où `list_page()`.

## 7. `create_app()` (factory), pas d'app globale mutée

Chaque test instancie une app fraîche avec un store vide (`fixture client`). Aucun état
partagé entre tests → suite parallélisable et sans ordre imposé.

## Ce que la solution ne fait volontairement pas

- Pas de persistance (c'est l'objet du checkpoint `shorturl`, d'après le Module 04).
- Pas d'auth (les marque-pages sont « globaux » ici). L'ajout d'un `owner_id` viendra au
  Module 06.
- Recherche plein-texte naïve (`in` sur `title`/`note` en minuscules) — suffisant pour valider
  le contrat d'API ; un vrai moteur (`tsvector`, Meilisearch) serait un autre sujet.
