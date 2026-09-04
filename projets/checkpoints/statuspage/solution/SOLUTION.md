# `statuspage` — les choix de conception

## 1. Corrélation des logs : `ContextVar` + middleware ASGI **pur**

```python
correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
```

- L'API : `CorrelationMiddleware` (ASGI pur, **pas** `BaseHTTPMiddleware`) pose un
  `request-id` par requête. `BaseHTTPMiddleware` exécute la suite dans une **autre tâche** →
  la `ContextVar` posée n'atteindrait pas les handlers. C'est le piège classique du Module 05.
- Le worker : `Monitor.tick()` pose un `check-<uuid>` le temps d'une passe.
- Le `_JsonFormatter` lit `correlation_id.get()` → **chaque ligne** de log porte l'id, qu'elle
  vienne de l'API ou du worker. DoD ✅.

## 2. `/health` vs `/ready` : deux questions différentes

| | Question | Échec |
|---|---|---|
| `/health` | le process est-il vivant ? | jamais 503 (sinon l'orchestrateur tue un process sain) |
| `/ready` | peut-il servir du trafic **utile** ? | 503 si la DB ne répond pas **ou** si le worker est en rade |

`/ready` : `SELECT 1` + `monitor.last_run_at`. Si le worker n'a pas tourné depuis
`ready_max_worker_staleness_seconds` (≈ 2 intervalles) → `503 {"problems": ["worker-stale"]}`.
Un load-balancer retire alors l'instance jusqu'à ce que le worker reparte.

## 3. Le worker : une boucle triviale, une passe testable

`run_forever()` = `while True: tick(); sleep(tick_seconds)` avec un `try/except` qui **empêche
le worker de mourir** sur une erreur ponctuelle. Toute la logique est dans `tick()`, qui est
`async` et **pur** (pas de `sleep`, pas de boucle infinie) → testable en une ligne :

```python
performed = await Monitor(session_factory, settings, metrics, mock_client).tick()
```

`tick()` calcule les services **dus** (dernière sonde plus vieille que `interval_seconds`, ou
jamais sondés) et ne sonde que ceux-là — un service à 300 s n'est pas re-sondé à chaque tick
de 1 s.

## 4. Sonde : `httpx.MockTransport` pour tester sans réseau

`probe(client, url, expected_status)` prend le **client** en argument → en test on injecte
`httpx.AsyncClient(transport=httpx.MockTransport(handler))`. Zéro requête réseau, zéro
`time.sleep`, tests déterministes. Verdict : `up` ssi `status_code == expected_status` ;
erreur réseau (`httpx.HTTPError`) → `down` avec le nom de l'exception.

## 5. Statut d'un service : calculé à partir des N dernières sondes

```python
if not recent:            return unknown
if recent[0].up:          return operational
# sinon : compter les échecs consécutifs
return outage if consecutive_failures >= threshold else degraded
```

`GET /status` agrège : `overall = pire(statuts)` (rang `operational < unknown < degraded <
outage`). Le calcul est dans `service.py` (`_status_from_recent`), testé isolément.

## 6. Métriques : un `CollectorRegistry` **dédié**, pas le registre global

```python
class Metrics:
    def __init__(self):
        self.registry = CollectorRegistry()
        self.check_latency = Histogram(..., registry=self.registry, buckets=(...))
```

Le registre global de `prometheus_client` est un singleton : deux `create_app()` dans la même
session de test lèveraient `Duplicated timeseries`. Un registre par app = tests isolés.

**p50 / p95 / p99** : un **Histogram** expose des *buckets* ; Prometheus calcule les
quantiles avec `histogram_quantile(0.95, ...)`. C'est la façon correcte — un `Summary` avec
quantiles fixes se calcule côté process et ne s'agrège pas entre instances.

## 7. `TZDateTime` : SQLite ne stocke pas le fuseau

Sans le `TypeDecorator`, `check.checked_at` relu depuis SQLite est *naïf* et
`checked_at >= since_aware` lève `TypeError`. `TZDateTime` réattache UTC à la lecture.
(Même leçon que `shorturl` / `taskman` Module 04.)

## 8. Transitions d'incident : machine à états minimale

`investigating → resolved` OK ; `resolved → investigating` → `InvalidTransitionError` (409).
`resolved_at` est posé/effacé automatiquement selon le statut cible.

## Ce que la solution ne fait pas

- Pas d'Alembic (hors DoD ici) : le schéma est créé au démarrage. En prod → migrations
  (patron dans `shorturl`).
- Pas d'auth : une vraie statuspage distinguerait lecture publique / admin.
- Pas de notifications (e-mail, webhook) sur changement d'état — ce serait un worker de plus.
- Historique non borné : en prod, une tâche de purge (`checked_at < now - 90j`).
