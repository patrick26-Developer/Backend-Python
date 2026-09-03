# Module 10 — Explication pas à pas

> Nouveaux : `api/ratelimit.py`, `SECURITY.md`. Modifiés : `api/middleware.py`
> (2 middlewares), `api/errors.py` (`Retry-After`), `api/routes/auth.py`, `main.py`,
> `core/{config,exceptions}.py`, `.github/workflows/ci.yml`.

---

## 1. `taskman/api/ratelimit.py`

```python
class RateLimiter(Protocol):
    async def hit(self, key: str, *, limit: int, window: int) -> int: ...
        # renvoie le nombre de secondes à attendre si la limite est franchie, 0 sinon
```

Le service dépend de **`RateLimiter`**, jamais de Redis.

### `InMemoryRateLimiter` — fenêtre fixe

```python
async def hit(self, key, *, limit, window):
    now = time.monotonic()
    reset_at, count = self._buckets.get(key, (now + window, 0))
    if now >= reset_at:                       # la fenêtre est passée -> on repart à 0
        reset_at, count = now + window, 0
    count += 1
    self._buckets[key] = (reset_at, count)
    return int(reset_at - now) + 1 if count > limit else 0
```

- une entrée par clé : `(reset_at, count)`.
- **fenêtre fixe** : simple, mais un client peut faire `2 × limit` requêtes à cheval sur
  deux fenêtres. Acceptable pour de l'anti-brute-force.
- `time.monotonic()` : insensible aux sauts d'horloge.

### `RedisRateLimiter` — compteur partagé

```python
async def hit(self, key, *, limit, window):
    count = int(await self._redis.incr(key))
    if count == 1:                            # première requête de la fenêtre
        await self._redis.expire(key, window) # -> le compteur s'auto-détruit après `window`
    if count > limit:
        return int(await self._redis.ttl(key)) or window
    return 0
```

`INCR` est **atomique** → pas de *race condition* entre instances. `EXPIRE` seulement à la
1ʳᵉ requête → la clé disparaît toute seule.

### La clé & l'IP

```python
def _client_ip(request):
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()   # 1re IP = le vrai client
    return request.client.host if request.client else "unknown"
```

Derrière un reverse proxy (Module 11), `request.client.host` = l'IP **du proxy** (tout le
monde a la même). Le proxy pose `X-Forwarded-For: <client>, <proxy1>, …` → on prend la
première.

> ⚠️ `X-Forwarded-For` est **falsifiable** si l'app est joignable **directement** (sans
> proxy). En prod, il faut que seul le proxy puisse atteindre l'app, et configurer
> `--forwarded-allow-ips` (Module 11).

### La dépendance

```python
async def auth_rate_limit(request):
    settings = request.app.state.settings
    if not settings.rate_limit_enabled:
        return
    limiter = request.app.state.rate_limiter
    scope = getattr(request.scope.get("route"), "path", request.url.path)
    key = f"ratelimit:{scope}:{_client_ip(request)}"
    retry_after = await limiter.hit(key, limit=settings.auth_rate_limit_per_minute, window=60)
    if retry_after:
        raise TooManyRequestsError(retry_after)
```

- clé = `route` + `IP` → chaque endpoint a son quota par IP.
- `settings.auth_rate_limit_per_minute` : configurable sans redéployer.

```python
# api/routes/auth.py
router = APIRouter(prefix="/auth", dependencies=[Depends(auth_rate_limit)])
```

Sur **le router** → **toutes** les routes `/auth/*` sont limitées. On ne peut pas en oublier
une.

---

## 2. `taskman/api/middleware.py` — `SecurityHeadersMiddleware`

```python
_SECURITY_HEADERS = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
)
_CSP = b"default-src 'none'; frame-ancestors 'none'"
```

```python
async def __call__(self, scope, receive, send):
    ...
    is_docs = any(scope["path"].startswith(p) for p in _DOCS_PATHS)
    async def send_wrapper(message):
        if message["type"] == "http.response.start":
            headers = message.setdefault("headers", [])
            headers.extend(_SECURITY_HEADERS)
            if not is_docs:
                headers.append((b"content-security-policy", _CSP))   # PAS sur /docs
            if self.is_production:
                headers.append((b"strict-transport-security", _HSTS))  # PROD uniquement
        await send(message)
```

- **CSP sautée sur `/docs`** : Swagger UI charge son JS/CSS depuis `cdn.jsdelivr.net` — une
  CSP `default-src 'none'` bloquerait tout et l'interface serait blanche.
- **HSTS en prod uniquement** : en dev (HTTP), `Strict-Transport-Security` forcerait le
  navigateur à refuser `http://localhost` pour 2 ans.
- les valeurs sont des `bytes` (format ASGI des en-têtes).

## 3. `BodySizeLimitMiddleware`

```python
async def __call__(self, scope, receive, send):
    if scope["type"] == "http":
        for name, value in scope["headers"]:
            if name == b"content-length" and value.isdigit() and int(value) > self.max_bytes:
                await self._reject(send)          # 413 direct, sans lire le corps
                return
    await self.app(scope, receive, send)
```

On lit **l'en-tête** `Content-Length` **avant** de consommer le corps → on rejette un
payload de 2 Go sans jamais le charger. Un corps *chunked* (sans `Content-Length`) passe
cette barrière — mais Uvicorn a sa propre limite (`--limit-max-request-size`) et Pydantic
borne le contenu (`max_length`).

`_reject` écrit directement les messages ASGI (`http.response.start` + `http.response.body`)
au format Problem Details.

---

## 4. `taskman/api/errors.py` — l'en-tête `Retry-After`

```python
@app.exception_handler(DomainError)
async def _domain(request, exc):
    headers = {}
    retry_after = getattr(exc, "retry_after", None)
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return _problem(..., headers=headers)
```

`TooManyRequestsError` porte un `retry_after` → le handler générique le transforme en
en-tête HTTP standard. Un client bien élevé attend ce délai avant de réessayer.

---

## 5. `taskman/main.py` — CORS et l'ordre des middlewares

```python
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(MetricsMiddleware)
app.add_middleware(SecurityHeadersMiddleware, is_production=settings.is_production)
if settings.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)
app.add_middleware(RequestContextMiddleware)
```

`add_middleware` empile **vers l'extérieur** → l'ordre d'exécution sur la requête est
l'**inverse** de l'ordre d'écriture :

```
requête ─▶ RequestContext ─▶ BodySizeLimit ─▶ CORS ─▶ SecurityHeaders ─▶ Metrics ─▶ GZip ─▶ route
```

- **`BodySizeLimit` tôt** : rejeter un payload géant avant tout traitement.
- **CORS avant le métier** : le pré-vol `OPTIONS` doit être traité sans authentification.
- **`SecurityHeaders`** : ajoute ses en-têtes sur la réponse au retour.

```python
if settings.cors_origins:   # [] par défaut -> pas de CORS du tout
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, ...)
```

`allow_origins` est une **liste explicite**. `["*"]` + `allow_credentials=True` est refusé
par Starlette (et ignoré par les navigateurs) — ce serait laisser n'importe quel site lire
les réponses authentifiées de tes utilisateurs.

---

## 6. Les tests

```python
async def test_auth_rate_limit_returns_429(limited_client):   # limit = 3/min
    codes = [ (await limited_client.post("/auth/login", data=...)).status_code
              for i in range(5) ]
    assert codes.count(429) >= 1                    # les 4e/5e sont bloquées
    assert int(last.headers["retry-after"]) > 0

async def test_rate_limit_is_per_ip(limited_client):
    for _ in range(4): await limited_client.post("/auth/login", data=...)      # IP par défaut -> bloquée
    r = await limited_client.post("/auth/login", data=..., headers={"X-Forwarded-For": "203.0.113.9"})
    assert r.status_code == 401                     # autre IP -> pas 429

async def test_no_csp_on_docs(client):
    assert "content-security-policy" not in (await client.get("/openapi.json")).headers

async def test_oversized_payload_is_413(client):
    resp = await client.post("/auth/register", json={"email": "a@b.co", "password": "x" * 2_000_000})
    assert resp.status_code == 413
```

- `conftest.py` : `Settings(..., rate_limit_enabled=False)` par défaut → les tests normaux
  ne sont pas bridés ; les tests de rate limit créent leur propre app avec
  `rate_limit_enabled=True, auth_rate_limit_per_minute=3`.

---

## 7. `.github/workflows/ci.yml` — `pip-audit`

```yaml
security:
  steps:
    - run: |
        pip install -U pip pip-audit
        pip install -e "."
        pip-audit --strict --desc
```

Un job **séparé** : il installe **uniquement** les dépendances de prod (`-e "."`, pas
`[dev]`) et les scanne contre la base des CVE (OSV / PyPI Advisory). `--strict` → le job
échoue (donc le *merge* est bloqué) à la moindre vulnérabilité connue.

---

## Ce qui vient au Module 11

Le Module 10 a durci l'app. Le Module 11 la **livre** : `Dockerfile` multi-stage non-root,
`docker-compose` complet, Uvicorn/Gunicorn workers, `--forwarded-allow-ips` (pour que
`X-Forwarded-For` soit fiable), migrations en prod, pipeline CI/CD complet.
