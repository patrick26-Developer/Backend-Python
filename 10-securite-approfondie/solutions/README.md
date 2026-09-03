# Module 10 — Solutions : les choix de conception

> Snapshot `taskman` v0.10.0. Audit complet : [`SECURITY.md`](SECURITY.md).
> Explication ligne par ligne : [`../PAS-A-PAS.md`](../PAS-A-PAS.md).

```bash
pytest -m "not e2e"
pip install pip-audit && pip-audit --strict
fastapi dev taskman/main.py
curl -sI localhost:8000/health | grep -Ei 'x-frame|content-security|x-content'
```

---

## Décisions

### 1. L'audit vit dans `SECURITY.md`, pas dans la tête

Un tableau OWASP API Top 10 : risque → réponse → fichier → test. Il se **re-vérifie** à
chaque release. Sans document, un audit est perdu au bout d'une semaine.

### 2. Rate limiting : `Protocol` + fenêtre fixe + clé `route:ip`

`InMemoryRateLimiter` (mono-instance) / `RedisRateLimiter` (`INCR`+`EXPIRE`, atomique,
partagé). Sur `/auth/*` via `dependencies=[...]` du router → aucune route oubliée. `429` +
`Retry-After`. IP depuis `X-Forwarded-For` (proxy).

### 3. En-têtes : CSP **sauf** `/docs`, HSTS **seulement** en prod

Une CSP `default-src 'none'` casse Swagger UI (JS depuis un CDN). HSTS en dev bloquerait
`http://localhost` pour 2 ans. Deux exceptions **conditionnelles**, pas globales.

### 4. CORS : origines **explicites**, jamais `*` + credentials

`cors_origins = []` par défaut → le front doit être déclaré. `["*"]` + `allow_credentials`
= laisser n'importe quel site lire les réponses authentifiées → interdit (Starlette le
refuse, les navigateurs l'ignorent).

### 5. Limite de payload : lire `Content-Length`, pas le corps

`BodySizeLimitMiddleware` rejette (413) **avant** de consommer le corps. Défense simple
contre OWASP API #4 (consommation illimitée). Complétée par les limites d'Uvicorn et de
Pydantic.

### 6. Ordre des middlewares réfléchi

`BodySizeLimit` tôt (rejeter avant traitement) ; `CORS` avant le métier (le pré-vol
`OPTIONS` ne doit pas exiger d'auth) ; `SecurityHeaders` sur la réponse.

### 7. `pip-audit` en job CI séparé, sur les deps de **prod**

`pip install -e "."` (pas `[dev]`) → on scanne ce qui tournera réellement. `--strict` bloque
le merge.

### 8. `TooManyRequestsError` porte `retry_after` ; le handler générique le lit

Le domaine ne connaît pas HTTP, mais expose une donnée (`retry_after`) que le handler
transforme en en-tête `Retry-After`. Même patron que `WWW-Authenticate` sur les 401.

---

## Grille d'auto-évaluation

- [ ] Ton `SECURITY.md` couvre-t-il les 10 points avec un pointeur code + test ?
- [ ] La (N+1)ᵉ tentative de login → 429 + `Retry-After` ?
- [ ] Le rate limit est-il par IP (et une autre IP passe) ?
- [ ] `/openapi.json` est-il **sans** CSP ? `/health` **avec** ?
- [ ] HSTS absent hors production ?
- [ ] CORS : `*` + credentials est-il impossible chez toi ?
- [ ] `pip-audit --strict` passe-t-il ?

➡️ [Module 11 — Déploiement & DevOps](../../11-deploiement-devops/THEORIE.md)
