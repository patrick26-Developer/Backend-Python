# Observabilité de `taskman`

## Métriques à surveiller (Grafana / Prometheus)

| Métrique | Requête PromQL (exemple) | Ce qu'elle dit |
|---|---|---|
| **Taux de requêtes** | `sum(rate(http_requests_total[1m])) by (path)` | charge par endpoint |
| **Taux d'erreur 5xx** | `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))` | santé applicative |
| **Latence p95** | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, path))` | expérience utilisateur |
| **Latence p99** | idem, `0.99` | pires cas |
| **Requêtes en cours** | `http_requests_in_progress_total` | saturation |

## Règles d'alerte (actionnables)

| Alerte | Condition | Durée | Quoi regarder |
|---|---|---|---|
| **Taux d'erreur élevé** | 5xx > 1 % | 5 min | logs `status>=500` du dernier `request_id`, traces des requêtes lentes |
| **Latence dégradée** | p99 > 1 s | 10 min | trace d'une requête lente → span le plus long (souvent SQL) ; `db_echo` ; index manquant |
| **Service non prêt** | `/ready` renvoie 503 | 2 min | le champ `checks` de `/ready` : `database` ou `cache` ? état de PostgreSQL / Redis |
| **File de tâches qui gonfle** | longueur de la file Redis croissante | 15 min | workers `taskiq` : nombre, erreurs, tâches bloquées |

Seuils à ajuster **avec** le produit (un back-office tolère 1 s ; une API publique, non).

## Traçage

```bash
# dev : spans en console
APP_OTEL_ENABLED=true fastapi dev taskman/main.py

# prod : vers un collector OTLP
APP_OTEL_ENABLED=true APP_OTEL_ENDPOINT=http://otel-collector:4318 fastapi run taskman/main.py
```

## Endpoints d'exploitation

| Route | Usage | Auth |
|---|---|---|
| `GET /health` | liveness (Kubernetes `livenessProbe`) | non |
| `GET /ready` | readiness (`readinessProbe`) — 503 si DB/cache down | non |
| `GET /metrics` | scrape Prometheus | non, **non exposé publiquement** |
