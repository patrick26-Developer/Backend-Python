# `shorturl` — solution de référence

Checkpoint d'après le **Module 04**. Raccourcisseur d'URL avec compteur de clics.

```bash
# depuis ce dossier (le venv du dépôt racine suffit)
export SHORTURL_DATABASE_URL="sqlite+aiosqlite:///./shorturl.db"
python -m alembic upgrade head                 # crée le schéma
python -m uvicorn shorturl.api:app --reload    # http://127.0.0.1:8000/docs
python -m pytest -q -m "not slow"              # tests rapides (base en mémoire)
python -m pytest -q -m slow                    # + tests de migration (sous-processus alembic)
python -m mypy shorturl                        # --strict, 0 erreur
```

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
