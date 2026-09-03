# Module 10 — Exercices

**Filet :** `git commit -m "checkpoint: avant module 10"`.

---

## Exercice 10.1 — Audit OWASP API Top 10 🔴

1. Crée `SECURITY.md`. Pour **chacun** des 10 points : le risque en 1 phrase, ce que
   `taskman` fait (ou ne fait pas), le fichier concerné, le test qui le prouve.
2. Identifie **au moins un** point encore faible et corrige-le.
3. Ajoute une **checklist de mise en production** (secret JWT, `APP_ENV`, CORS, `/metrics`
   non public…).

**Critères d'acceptation**
- [ ] Les 10 points sont couverts, avec un pointeur vers le code pour chacun.
- [ ] Au moins un trou trouvé **et** comblé.

---

## Exercice 10.2 — Rate limiting 🔴

1. `taskman/api/ratelimit.py` :
   - `RateLimiter` (`Protocol` : `hit(key, *, limit, window) -> int` — renvoie les secondes
     à attendre, ou 0) ;
   - `InMemoryRateLimiter` (fenêtre fixe : `(reset_at, count)` par clé) ;
   - `RedisRateLimiter` (`INCR` + `EXPIRE` + `TTL`) ;
   - `build_rate_limiter(redis_url)`.
2. `auth_rate_limit(request)` : dépendance qui compose la clé
   `ratelimit:{route}:{ip}`, appelle `hit(...)`, lève `TooManyRequestsError(retry_after)`.
   L'IP vient de `X-Forwarded-For` (proxy) sinon de `request.client.host`.
3. `TooManyRequestsError(DomainError)` : 429, `code="rate_limited"`, `retry_after`. Le
   handler ajoute l'en-tête **`Retry-After`**.
4. `APIRouter(prefix="/auth", dependencies=[Depends(auth_rate_limit)])`.
5. `main.py` : `app.state.rate_limiter = build_rate_limiter(settings.redis_url)` dans le
   `lifespan`. Config : `rate_limit_enabled`, `auth_rate_limit_per_minute`.

**Critères d'acceptation**
- [ ] La (N+1)ᵉ tentative de login sur la même IP → **429** avec `Retry-After`.
- [ ] Une autre IP (`X-Forwarded-For`) n'est **pas** affectée.
- [ ] `rate_limit_enabled=False` désactive proprement.

---

## Exercice 10.3 — En-têtes de sécurité 🟡

1. `SecurityHeadersMiddleware` (ASGI pur) : ajoute `X-Content-Type-Options: nosniff`,
   `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy`,
   `Permissions-Policy` à **toutes** les réponses.
2. `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` — **sauf** sur
   `/docs`, `/redoc`, `/openapi.json` (sinon Swagger UI casse).
3. `Strict-Transport-Security` — **seulement** si `settings.is_production`.

**Critères d'acceptation**
- [ ] `GET /health` renvoie les 5 en-têtes de base + la CSP.
- [ ] `GET /openapi.json` n'a **pas** de CSP.
- [ ] Hors production, **pas** de HSTS.

---

## Exercice 10.4 — CORS 🟡

1. `Settings.cors_origins: list[str] = []` (défaut : aucune origine).
2. `main.py` : si `cors_origins` non vide, `app.add_middleware(CORSMiddleware,
   allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"],
   allow_headers=["*"])`.
3. Vérifie que `allow_origins=["*"]` + `allow_credentials=True` est **impossible** (teste,
   observe le comportement).

**Critères d'acceptation**
- [ ] Une requête avec `Origin` autorisé → `Access-Control-Allow-Origin` présent.
- [ ] Une `Origin` inconnue → l'en-tête est **absent**.
- [ ] Le pré-vol `OPTIONS` d'une méthode non simple renvoie les bons en-têtes.

---

## Exercice 10.5 — Limite de taille de payload 🟡

1. `BodySizeLimitMiddleware` : si `Content-Length` > `settings.max_request_body_bytes`
   (défaut 1 Mio) → réponds **413** directement (au format Problem Details), sans passer la
   requête à l'app.
2. `PayloadTooLargeError` (413).

**Critères d'acceptation**
- [ ] Un `POST` avec un corps de 2 Mio → 413 `payload_too_large`.
- [ ] Un corps normal passe.

---

## Exercice 10.6 — `pip-audit` en CI 🟢

1. `.github/workflows/ci.yml` : un job `security` qui installe `pip-audit` et lance
   `pip-audit --strict`.
2. **Bonus** : configure Dependabot (`.github/dependabot.yml`) pour les mises à jour hebdo.

**Critères d'acceptation**
- [ ] Le job échoue si une dépendance a une CVE connue.
- [ ] `pip-audit --strict` passe sur l'état actuel.

---

## Rendu

```bash
ruff check . && ruff format --check . && mypy taskman && pytest -m "not e2e"
pip install pip-audit && pip-audit --strict
git add -A && git commit -m "feat(module-10): OWASP audit, rate limiting, en-têtes, CORS, limites"
```

Puis [`../solutions/README.md`](../solutions/) et [`../PAS-A-PAS.md`](../PAS-A-PAS.md).
