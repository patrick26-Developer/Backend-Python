# `shorturl` — les choix de conception

## 1. Architecture en couches, dès un si petit projet

`api → service → repository → session`. Chaque couche a une responsabilité :

| Couche | Sait | Ne sait pas |
|---|---|---|
| `api.py` | HTTP, codes, `Request`/`Response`, tâches de fond | SQL, génération d'alias |
| `service.py` | règles (alias, expiration) | HTTP, `IntegrityError` → 409 (c'est `api` qui traduit) |
| `repository.py` | SQL, `IntegrityError` | pourquoi on l'a appelé |

Bénéfice concret : `test_concurrent_creates_never_duplicate_alias` teste `LinkService` +
`LinkRepository` **sans HTTP**.

## 2. Unicité de l'alias = contrainte de base + `IntegrityError`, jamais « SELECT puis INSERT »

```python
# repository.create : on INSÉRE, et on laisse la base dire non
try:
    await self._session.flush()
except IntegrityError:
    await self._session.rollback()
    raise
```

Un `SELECT ... WHERE alias = ?` puis `INSERT` a une **fenêtre de course** : deux requêtes
concurrentes voient « libre » et insèrent toutes les deux. La **contrainte d'unicité** de la
colonne `alias` (index unique `ix_links_alias`) est la seule garantie réelle. Le service :

- **alias personnalisé** en collision → `AliasTakenError` → 409 ;
- **alias auto** en collision → on retente avec un autre alias aléatoire (jusqu'à
  `alias_max_attempts`), puis 503 si vraiment pas de chance.

> Sur SQLite en mémoire (tests) la « concurrence » est sérialisée par l'unique connexion —
> le **chemin de code** `IntegrityError` est quand même exercé. Sur PostgreSQL, c'est une
> vraie course, et le résultat est le même : une seule création réussit.

## 3. L'incrément de clics ne bloque jamais la redirection

```python
@app.get("/{alias}")
async def resolve_link(alias, service, request, background):
    target = await service.resolve(alias)          # lecture : rapide, dans la session requête
    background.add_task(_increment_click, request.app, alias)  # écriture : après la réponse
    return RedirectResponse(target, status_code=302)
```

`_increment_click` ouvre **sa propre session**, fait un `UPDATE ... SET clicks = clicks + 1`
(incrément atomique, pas `row.clicks += 1`), commit, et **avale toute exception** (un clic
perdu ne vaut pas une 500). `test_click_increment_failure_does_not_break_resolve` casse
volontairement la fabrique de sessions et vérifie que le 302 sort quand même.

## 4. `session = une requête`

`get_session` (dans `db.py`) est un générateur de dépendance : `async with factory() as
session`. Le `commit` est explicite dans la route (après le travail du service) ; toute
exception qui remonte → pas de commit → `async with` fait le `rollback` + `close`. On ne
committe jamais « à moitié ».

## 5. Expiration : 404 (inconnu) vs 410 (a existé, expiré)

```python
if row is None:            raise LinkNotFoundError    # 404
if row.expires_at <= now:  raise LinkExpiredError     # 410 Gone — sémantiquement correct
```

## 6. Migration écrite à la main, vérifiée par `alembic check`

La migration initiale est écrite explicitement (pas d'autogenerate) — c'est plus lisible
pour un lecteur, et `test_alembic_check_no_pending_changes` (@slow) garantit qu'elle **reste**
synchrone avec `models.py` : si tu ajoutes une colonne au modèle sans migration, ce test
passe au rouge.

Convention de nommage des contraintes (`NAMING_CONVENTION` dans `db.py`) : sans elle,
`render_as_batch` de SQLite ne sait pas nommer les contraintes recréées lors d'un
`ALTER TABLE`.

## Ce que la solution ne fait pas

- Pas d'auth ni de quotas (hors périmètre du checkpoint).
- Pas de cache de résolution (Redis) — viendrait au Module 08 ; ici chaque `GET /{alias}`
  fait un `SELECT` par alias (indexé, donc O(log n)).
- `base62(id)` « propre » : on génère un alias **aléatoire** plutôt que de dériver de l'`id`
  auto-incrémenté — ça évite de divulguer le volume de liens créés, au prix de quelques
  retries improbables.
