# `shorturl` — solution de référence

Checkpoint d'après le **Module 04**. Raccourcisseur d'URL avec compteur de clics.

## Installation autonome (sans cloner tout le dépôt)

Copie ce dossier (`shorturl/`, `alembic/`, `alembic.ini`, `tests/`, `pyproject.toml`), puis :

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install "fastapi[standard]" pydantic-settings "sqlalchemy[asyncio]" aiosqlite alembic \
            pytest pytest-asyncio mypy ruff

export SHORTURL_DATABASE_URL="sqlite+aiosqlite:///./shorturl.db"   # Windows (PowerShell) : $env:SHORTURL_DATABASE_URL=...
alembic upgrade head                 # crée le schéma
uvicorn shorturl.api:app --reload    # http://127.0.0.1:8000/docs
pytest -q -m "not slow"              # tests rapides (base en mémoire) — 14 tests
pytest -q -m slow                    # + tests de migration (sous-processus alembic) — 2 tests
mypy shorturl                        # --strict, 0 erreur
```

Si tu es déjà dans le dépôt complet (le venv racine a tout) : remplace `pip install ...` par
rien et lance les mêmes commandes `python -m ...` depuis ce dossier.

## Arborescence

```
shorturl/
  config.py       Settings 12-factor (préfixe SHORTURL_)
  db.py           moteur async, fabrique de sessions, Base, get_session (1 session / requête)
  models.py       LinkRow (ORM) — ne sort jamais du repository
  schemas.py      LinkCreate / LinkCreated / LinkStats (Pydantic)
  errors.py       erreurs métier découplées de HTTP
  repository.py   le seul code qui parle SQL ; laisse remonter l'IntegrityError
  service.py      génération d'alias, expiration, règles
  api.py          routes fines + handlers d'erreurs + tâche de fond « incrément de clics »
alembic/          env async + 1 migration (schéma initial)
tests/            base SQLite en mémoire ; test de concurrence ; test de migration (@slow)
```

Décisions : [`SOLUTION.md`](SOLUTION.md). Énoncé : [`../BRIEF.md`](../BRIEF.md).
