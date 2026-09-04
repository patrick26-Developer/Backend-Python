# `statuspage` — solution de référence

Checkpoint d'après le **Module 09**. Mini « statuspage.io » : surveille des services HTTP.

```bash
# depuis ce dossier (le venv du dépôt racine suffit)
python -m uvicorn statuspage.api:app --reload   # API + worker de sonde ; /docs
python -m pytest -q                             # tests (base en mémoire, worker désactivé)
python -m mypy statuspage                        # --strict, 0 erreur
```

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
