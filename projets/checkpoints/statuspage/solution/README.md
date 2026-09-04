# `statuspage` — solution de référence

Checkpoint d'après le **Module 09**. Mini « statuspage.io » : surveille des services HTTP.

## Installation autonome (sans cloner tout le dépôt)

Copie ce dossier (`statuspage/`, `tests/`, `pyproject.toml`), puis :

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install "fastapi[standard]" pydantic-settings "sqlalchemy[asyncio]" aiosqlite httpx \
            prometheus-client pytest pytest-asyncio mypy ruff

uvicorn statuspage.api:app --reload   # API + worker de sonde ; /docs
pytest -q                             # 24 tests (base en mémoire, worker désactivé)
mypy statuspage                       # --strict, 0 erreur
```

Si tu es déjà dans le dépôt complet (le venv racine a tout), lance directement
`python -m uvicorn ...`, `python -m pytest`, `python -m mypy statuspage` depuis ce dossier.

Config **12-factor**, préfixe `STATUSPAGE_` (`STATUSPAGE_DATABASE_URL`,
`STATUSPAGE_WORKER_ENABLED`, `STATUSPAGE_PROBE_TIMEOUT_SECONDS`…).

## Arborescence

```
statuspage/
  config.py        Settings (env only)
  db.py            moteur async, TZDateTime (datetime aware), get_session
  models.py        services / checks / incidents
  schemas.py       contrats API + ServiceStatus (operational/degraded/outage/unknown)
  errors.py        erreurs métier découplées de HTTP
  repository.py    SQL : services, checks (history, uptime, dernières sondes), incidents
  probe.py         sonde HTTP : up/down + latence + erreur réseau
  monitor.py       worker : tick() sonde les services DUS ; last_run_at pour /ready
  observability.py logs JSON corrélés (ContextVar) + métriques Prometheus (registre isolé)
  api.py           routes + middleware ASGI pur (request-id) + lifespan (worker) + /health /ready /metrics
tests/             probe (MockTransport), monitor (tick), api (async httpx)
```

Décisions : [`SOLUTION.md`](SOLUTION.md). Énoncé : [`../BRIEF.md`](../BRIEF.md).
