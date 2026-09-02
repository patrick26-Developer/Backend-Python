# Module 05 — Explication pas à pas du code

> Fichiers **nouveaux** : `core/context.py`, `core/exceptions.py`, `core/logging.py`,
> `api/errors.py`, `api/middleware.py`. Fichiers **modifiés** : `services/*`,
> `repositories/sqlalchemy.py`, `api/routes/*`, `main.py`, `core/config.py`.
> Garde [`solutions/taskman/`](solutions/taskman/) ouvert.

---

## 1. `taskman/core/context.py`

```python
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

def get_request_id() -> str | None:
    return request_id_var.get()
```

- `ContextVar` : une variable dont la valeur est **isolée par contexte d'exécution**. En
  async, chaque tâche (donc chaque requête) a **sa propre** valeur, sans se marcher dessus.
  C'est ce qui permet de « transporter » le `request_id` sans le passer en argument à toutes
  les fonctions.
- `default=None` : hors requête (au démarrage, dans un test unitaire), `get()` renvoie `None`.
- `"request_id"` (1ᵉʳ arg) : juste un nom pour le debug.

---

## 2. `taskman/core/exceptions.py`

```python
class DomainError(Exception):
    status_code: int = 400
    code: str = "domain_error"
    title: str = "Erreur métier"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
```

- hérite d'`Exception` (pas de `HTTPException` !) — **zéro** dépendance à `fastapi`.
- `status_code` / `code` / `title` : **attributs de classe** → une sous-classe les
  surcharge en une ligne.
- `self.detail` : le message lisible ; `super().__init__(detail)` le met aussi dans
  `str(exc)` (utile dans les logs).

```python
class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"
    title = "Ressource introuvable"

class ConflictError(DomainError):
    status_code = 409
    ...
```

Des **familles** : le handler pourra dire « toute `NotFoundError` → 404 ». On n'écrit le
mapping qu'une fois.

```python
class TaskNotFoundError(NotFoundError):
    code = "task_not_found"

    def __init__(self, task_id: int) -> None:
        super().__init__(f"Tâche {task_id} introuvable")
        self.task_id = task_id
```

- `code` **précis** : le client peut faire `if body["code"] == "task_not_found"` de façon
  fiable (le `detail` en français peut changer, pas le `code`).
- `self.task_id` : attribut exploitable (log, métrique, réponse enrichie).

---

## 3. `taskman/core/logging.py`

```python
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}
```

L'ensemble des attributs « standard » d'un *log record* (`levelname`, `created`, `pathname`…).
On s'en sert pour ne garder que les champs **custom** passés via `extra=`.

```python
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),        # applique les %-args
        }
        rid = get_request_id()
        if rid is not None:
            payload["request_id"] = rid
        for key, value in record.__dict__.items():
            if key not in _RESERVED:
                payload[key] = value           # http_status, duration_ms...
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)
```

- `record.getMessage()` : le message avec les `%s` déjà substitués.
- `get_request_id()` : **la corrélation**. Émis pendant une requête → le `request_id` est là.
- boucle sur `record.__dict__` moins `_RESERVED` : récupère `extra={"http_status": 200, ...}`.
- `default=str` : si un champ n'est pas sérialisable (un objet), on le `str()` plutôt que
  planter.
- `ensure_ascii=False` : garde les accents lisibles.

```python
def configure_logging(*, level: str = "INFO", json_output: bool = True) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_output else logging.Formatter("%(asctime)s ..."))
    root = logging.getLogger()
    root.handlers = [handler]         # on REMPLACE les handlers existants
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True           # -> les logs uvicorn remontent au root -> notre format
```

- `StreamHandler(sys.stdout)` : les logs vont sur la sortie standard (12-factor : c'est
  l'orchestrateur qui les collecte, pas l'app qui écrit un fichier).
- `root.handlers = [handler]` : on repart propre (sinon double log).
- uvicorn a ses propres handlers colorés → on les vide et on `propagate` pour tout unifier.

---

## 4. `taskman/api/middleware.py`

```python
class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)   # websockets, lifespan : on laisse passer
            return
```

Un middleware ASGI **pur** = une classe *callable* qui reçoit `(scope, receive, send)` et
appelle `self.app(...)`. Plus bas niveau que `BaseHTTPMiddleware`, mais sans ses bugs
(streaming, background tasks).

```python
        request = Request(scope)
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status_code = 500          # défaut pessimiste : si ça explose avant la réponse
```

- `request_id` : celui du client s'il en fournit un (utile pour tracer *à travers*
  plusieurs services), sinon on en crée un.
- `token = request_id_var.set(...)` : `set` renvoie un *token* pour pouvoir **annuler**
  proprement plus tard.
- `time.perf_counter()` : horloge monotone (insensible aux changements d'heure système).

```python
        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)
```

- une réponse ASGI = plusieurs `message` : `http.response.start` (statut + en-têtes) puis
  des `http.response.body`.
- on **intercepte** `http.response.start` : on note le `status`, et on **ajoute** l'en-tête
  `x-request-id` (les en-têtes ASGI sont des tuples de `bytes`).

```python
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            _logger.info("%s %s -> %s", request.method, request.url.path, status_code,
                         extra={"http_method": ..., "http_status": status_code,
                                "duration_ms": duration_ms, "client": ...})
            request_id_var.reset(token)
```

- `finally` : le log d'accès est émis **quoi qu'il arrive** — même si `self.app` a levé
  (dans ce cas `status_code` vaut 500).
- `request_id_var.reset(token)` : **crucial**. Les workers async sont réutilisés ; sans
  `reset`, le `request_id` de cette requête « collerait » à la suivante.

---

## 5. `taskman/api/errors.py`

```python
def _problem(*, status, title, detail, code, instance, **extra) -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status,
            "detail": detail, "code": code, "instance": instance}
    rid = get_request_id()
    if rid is not None:
        body["request_id"] = rid
    body.update(extra)
    return JSONResponse(jsonable_encoder(body), status_code=status,
                        media_type="application/problem+json")
```

- le **schéma RFC 9457** : `type`, `title`, `status`, `detail`, `instance` + nos ajouts
  (`code`, `request_id`).
- `**extra` : pour le champ `errors` des 422.
- `jsonable_encoder(body)` : Pydantic met parfois un objet `ValueError` (non sérialisable)
  dans `exc.errors()` — l'encodeur FastAPI le convertit en `str`. Sans ça : `TypeError`.
- `media_type="application/problem+json"` : le `Content-Type` standard des erreurs.

```python
def register_error_handlers(app: FastAPI) -> None:

    @app.exception_handler(DomainError)
    async def _domain(request, exc: DomainError):
        return _problem(status=exc.status_code, title=exc.title, detail=exc.detail,
                        code=exc.code, instance=request.url.path)
```

**Un seul** handler pour **toutes** les erreurs métier : il lit `status_code`/`code`/`title`
portés par l'exception. Ajouter `TaskAlreadyDoneError` plus tard ne demande **aucune**
modification ici.

```python
    @app.exception_handler(RequestValidationError)
    async def _validation(request, exc):
        return _problem(status=422, title="Requête invalide", code="validation_error",
                        instance=request.url.path, errors=exc.errors())
```

Les 422 de Pydantic passent par **le même** `_problem` → même schéma que les 404. Le client
gère **un** format.

```python
    @app.exception_handler(Exception)
    async def _unhandled(request, exc):
        _logger.exception("unhandled exception on %s %s", request.method, request.url.path)
        return _problem(status=500, title="Erreur interne",
                        detail="Une erreur inattendue est survenue.", code="internal_error",
                        instance=request.url.path)
```

- `_logger.exception(...)` : loggue le message **+ la *stack* complète** (côté serveur).
- la réponse client : **générique**. Zéro chemin de fichier, zéro requête SQL, zéro nom de
  variable. Une 500 qui fuit, c'est une aide au pentesteur.

---

## 6. `taskman/repositories/sqlalchemy.py` (traduction d'exception)

```python
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ProjectNotFoundError(data.project_id) from exc
        await self._session.refresh(row)
```

- le repository est **la seule couche qui connaît `IntegrityError`** (SQLAlchemy). C'est
  donc ici qu'on traduit.
- `await self._session.rollback()` : la session est dans un état invalide après une
  contrainte violée — on la nettoie avant de propager.
- `raise ProjectNotFoundError(...) from exc` : `from exc` conserve la **cause** (visible
  dans les logs : `... a été la cause directe de ...`), mais les couches hautes ne voient
  qu'une erreur **métier** propre.
- la seule contrainte pouvant échouer sur `INSERT tasks` ici est la FK `project_id` → on
  peut être précis.

---

## 7. `taskman/services/*` (lèvent au lieu de renvoyer `None`)

```python
    async def get(self, task_id: int) -> TaskRead:          # plus de `| None`
        task = await self._tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    async def delete(self, task_id: int) -> None:
        if not await self._tasks.delete(task_id):
            raise TaskNotFoundError(task_id)
        await self._uow.commit()
```

- le **type de retour** se resserre (`TaskRead`, pas `TaskRead | None`) → l'appelant n'a
  plus de cas `None` à gérer, mypy le sait.
- `delete` : on ne commit **que** si une ligne a été supprimée (sinon on a levé avant).

---

## 8. `taskman/api/routes/*` (one-liners)

```python
@router.get("/{task_id}")
async def get_task(task_id: TaskId, service: TaskServiceDep) -> TaskRead:
    return await service.get(task_id)
```

Avant : 4 lignes avec un `if ... raise HTTPException`. Après : 1 ligne. La route ne fait
plus que **traduire HTTP** (lire les params, appeler, renvoyer). Le « pas trouvé » est
géré par le service (qui lève) + le handler (qui traduit).

---

## 9. `taskman/main.py`

```python
    configure_logging(level=settings.log_level, json_output=settings.use_json_logs)
    ...
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
```

- `configure_logging` **avant** de créer l'app : les logs de démarrage sont déjà formatés.
- `add_middleware(RequestContextMiddleware)` : ajouté en **dernier** → c'est le middleware
  **le plus externe** → le `request_id` est posé avant que quoi que ce soit d'autre ne
  s'exécute, et l'en-tête est le dernier ajouté à la réponse.
- `register_error_handlers(app)` : branche les 4 handlers.

---

## 10. Les tests

- `test_service.py` : `pytest.raises(TaskNotFoundError)` — le service **lève**.
- `test_errors_logging.py` : la hiérarchie (`isinstance`), les métadonnées (`status_code`,
  `code`), et `JsonFormatter` (JSON valide, `request_id` présent/absent selon le ContextVar).
- `test_tasks_api.py` :
  - `test_error_format_is_problem_details` : les 7 clés, le `Content-Type`.
  - `test_validation_error_uses_same_format` : 422 au **même** schéma.
  - `test_request_id_echoed_and_respected` : généré si absent, respecté si fourni.
  - `test_create_unknown_project_gives_clean_404` : l'`IntegrityError` → 404 `project_not_found`.
- `conftest.py` : `Settings(..., log_json=False, log_level="WARNING")` pour que les tests ne
  crachent pas de JSON.

---

## Ce qui change au Module 06

| Ici (Module 05) | Module 06 |
|---|---|
| `PermissionDeniedError` défini, pas encore utilisé | levé quand un user accède à la ressource d'un autre |
| pas d'authentification | `401` via `HTTPException` (cas purement HTTP), `get_current_user` |
| — | `request_id` **+** `user_id` dans les logs |
