# `statuspage` — mini-projet checkpoint (après Module 09)

> 🚧 Énoncé en construction. Solution de référence commentée à venir dans `solution/`.
> **Time-box : 2 jours.**

## But

Valider : observabilité (logs structurés, métriques, traces), health/ready, tâches de fond
périodiques, config 12-factor.

## Spéc

Une API qui surveille des services HTTP et publie leur statut (mini « statuspage.io »).

- `POST /services` `{name, url, interval_seconds, expected_status=200}` → enregistre un check.
- Un **worker périodique** ping chaque service à son intervalle, stocke chaque résultat
  (`up/down`, latence, code, horodatage).
- `GET /services` → liste avec statut courant + uptime 24 h.
- `GET /services/{id}/history?since=...` → historique des checks (paginé).
- `POST /incidents` / `PATCH /incidents/{id}` → incidents manuels (`investigating → resolved`).
- `GET /status` → page d'état agrégée (JSON) : opérationnel / dégradé / panne.
- **Exploitation** : `/health` (liveness), `/ready` (DB + worker vivant), `/metrics`
  (Prometheus : checks/min, taux d'échec, latence p95 par service).

## Definition of Done

- [ ] Chaque ligne de log porte un `request-id` (API) ou un `check-id` (worker).
- [ ] `/ready` → 503 si la DB est down ou si le worker n'a pas tourné depuis 2 intervalles.
- [ ] `/metrics` expose la latence p50/p95/p99 et le taux d'échec par service.
- [ ] Une requête `GET /status` produit une trace corrélée aux logs.
- [ ] Toute la config vient de variables d'environnement (aucune valeur en dur).
- [ ] `ruff` + `mypy --strict` + `pytest` au vert.
