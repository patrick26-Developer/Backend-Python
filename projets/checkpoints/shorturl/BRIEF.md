# `shorturl` — mini-projet checkpoint (après Module 04)

> 🚧 Énoncé en construction. Solution de référence commentée à venir dans `solution/`.
> **Time-box : 1 jour.** PostgreSQL (ou SQLite async) + Alembic + architecture en couches.

## But

Valider : SQLAlchemy 2.0 async, migrations, *repository pattern*, contraintes d'unicité,
transactions, redirections HTTP, un peu de concurrence.

## Spéc

- `POST /links` `{url, custom_alias?}` → crée un lien court.
  - alias auto : base62 court (6 caractères) dérivé d'un identifiant ; garantir l'unicité.
  - `custom_alias` : validé (`^[a-zA-Z0-9_-]{3,32}$`), 409 si pris.
- `GET /{alias}` → **302** vers l'URL cible ; incrémente le compteur de clics (sans bloquer
  la redirection) ; 404 si inconnu ; 410 si expiré.
- `GET /links/{alias}/stats` → `{url, clicks, created_at, last_clicked_at, expires_at}`.
- `DELETE /links/{alias}` → 204.
- Option : `expires_at` à la création.

## Definition of Done

- [ ] `alembic upgrade head` crée le schéma ; une migration = une revue.
- [ ] Deux créations concurrentes ne produisent jamais deux fois le même alias (contrainte
      d'unicité + gestion de l'`IntegrityError`).
- [ ] La redirection reste rapide même si l'incrément de clics échoue (isolé).
- [ ] Session = une requête ; rollback auto en cas d'exception.
- [ ] Tests sur base jetable ; `ruff` + `mypy --strict` au vert.
