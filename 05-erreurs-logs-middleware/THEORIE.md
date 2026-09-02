# Module 05 — Erreurs, logs & middleware

> **Objectif** : une API qui **échoue de façon prévisible et traçable**. Format d'erreur
> unique, exceptions métier découplées de HTTP, logs structurés corrélés par `request-id`.
> Les routes redeviennent des one-liners.
>
> **Durée estimée** : 8 à 11 h.
> **Pré-requis** : Modules 03–04 (couches, services, DB).

---

## 1. Le problème

Après le Module 04, `taskman` a trois façons différentes de rater :

- `raise HTTPException(404, "Task not found")` éparpillé dans les routes ;
- `IntegrityError` **brute** qui remonte → `500` + *stack trace* (fuite d'info !) ;
- `RequestValidationError` (422) au format FastAPI par défaut.

Trois formats de corps différents. Aucun moyen de relier une erreur vue par un client à une
ligne de log. Un incident = une enquête à l'aveugle.

**Ce module unifie tout ça.**

---

## 2. Exceptions **métier**, découplées de HTTP

### La hiérarchie

```python
# taskman/core/exceptions.py — AUCUN import fastapi
class DomainError(Exception):
    status_code = 400
    code = "domain_error"
    title = "Erreur métier"
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail

class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"

class ConflictError(DomainError):
    status_code = 409

class TaskNotFoundError(NotFoundError):
    code = "task_not_found"
    def __init__(self, task_id: int) -> None:
        super().__init__(f"Tâche {task_id} introuvable")
        self.task_id = task_id
```

- **une racine** (`DomainError`) → un seul handler suffit pour tout attraper.
- **des sous-classes sémantiques** (`NotFoundError`, `ConflictError`) → le bon code HTTP.
- **des exceptions précises** (`TaskNotFoundError`) → un `code` machine que le client peut
  tester (`if body.code == "task_not_found"`), et des attributs utiles (`task_id`).
- `status_code` / `code` / `title` sont des **indications** portées par l'exception ; le
  domaine *suggère*, le handler *décide*. Le domaine ne connaît toujours pas `fastapi`.

### Le service lève, ne renvoie plus `None`

```python
# AVANT (Module 04)                    # APRÈS (Module 05)
async def get(self, task_id):          async def get(self, task_id) -> TaskRead:
    return await self._tasks.get(id)       task = await self._tasks.get(task_id)
                                           if task is None:
                                               raise TaskNotFoundError(task_id)
                                           return task
```

Conséquence : le type de retour devient `TaskRead` (plus `TaskRead | None`). L'appelant n'a
plus à gérer le cas d'absence — l'exception s'en occupe.

### La route redevient triviale

```python
@router.get("/{task_id}")
async def get_task(task_id: TaskId, service: TaskServiceDep) -> TaskRead:
    return await service.get(task_id)      # lève -> handler -> 404
```

Plus de `if ... raise HTTPException`. La route ne fait *que* du HTTP : lire, appeler,
renvoyer.

### Traduire une exception d'infrastructure en exception métier

L'`IntegrityError` (FK invalide) est une fuite de la couche SQL. On la **traduit** là où on
la comprend — **le repository** (la seule couche qui connaît SQLAlchemy) :

```python
try:
    await self._session.flush()
except IntegrityError as exc:
    await self._session.rollback()
    raise ProjectNotFoundError(data.project_id) from exc
```

`raise ... from exc` : garde la cause d'origine pour les logs, mais expose une erreur
**propre** aux couches hautes.

---

## 3. Les *exception handlers* : traduire métier → HTTP

```python
# taskman/api/errors.py
def register_error_handlers(app: FastAPI) -> None:

    @app.exception_handler(DomainError)
    async def _domain(request, exc: DomainError):
        return _problem(status=exc.status_code, title=exc.title, detail=exc.detail,
                        code=exc.code, instance=request.url.path)

    @app.exception_handler(RequestValidationError)
    async def _validation(request, exc):
        return _problem(status=422, code="validation_error", ..., errors=exc.errors())

    @app.exception_handler(Exception)          # filet de sécurité
    async def _unhandled(request, exc):
        _logger.exception("unhandled exception")   # log COMPLET côté serveur
        return _problem(status=500, code="internal_error",
                        detail="Une erreur inattendue est survenue.")  # RIEN de sensible au client
```

- **un handler par famille** : `DomainError` (toutes les erreurs métier),
  `RequestValidationError` (422), `HTTPException` (au cas où on en lève encore),
  `Exception` (le filet — tout ce qui n'était pas prévu).
- ordre de priorité : FastAPI choisit le handler le **plus spécifique** enregistré.
- **le handler `Exception`** : log la *stack* complète, renvoie un message **générique**.
  Une 500 ne doit **jamais** exposer un chemin de fichier, une requête SQL, un nom de
  variable.

### Format unifié : Problem Details (RFC 9457)

```json
{
  "type": "about:blank",
  "title": "Ressource introuvable",
  "status": 404,
  "detail": "Tâche 42 introuvable",
  "code": "task_not_found",
  "instance": "/tasks/42",
  "request_id": "9f3c7b2e…"
}
```

- `Content-Type: application/problem+json` (le standard).
- `code` : identifiant **stable** pour le client (le `detail` peut changer, pas le `code`).
- `instance` : le chemin qui a échoué.
- `request_id` : le lien vers les logs (voir §5).
- pour les 422 : un champ `errors` avec le détail Pydantic.

> `jsonable_encoder(...)` avant de renvoyer : Pydantic met parfois des objets non
> sérialisables (`ValueError`) dans les détails d'erreur — l'encodeur FastAPI les nettoie.

---

## 4. Middleware ASGI

Un **middleware** enveloppe **toutes** les requêtes : il s'exécute avant la route (sur la
requête) et après (sur la réponse).

```
requête ─▶ [Middleware A ─▶ [Middleware B ─▶ [ route ] ─▶] ─▶] ─▶ réponse
```

### Deux façons de l'écrire

| | `BaseHTTPMiddleware` | Middleware ASGI « pur » |
|---|---|---|
| simplicité | `async def dispatch(self, request, call_next)` | manipuler `scope`/`receive`/`send` |
| perf & compat | souci connu avec le streaming / *background tasks* | robuste |
| recommandé | prototypage | **production** |

`taskman` utilise la version **pure** (`RequestContextMiddleware`) :

```python
class RequestContextMiddleware:
    def __init__(self, app): self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request_id = Request(scope).headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)      # publie dans le ContextVar
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message["headers"].append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            _logger.info("%s %s -> %s", ..., extra={"duration_ms": ..., "http_status": ...})
            request_id_var.reset(token)
```

- `send_wrapper` : on **intercepte** l'événement `http.response.start` pour lire le statut et
  injecter l'en-tête `x-request-id` **dans la réponse**.
- `try/finally` : le log d'accès est émis **même si la requête a levé** (500).
- `request_id_var.reset(token)` : on nettoie le contexte à la fin (important — les workers
  sont réutilisés).

### L'ordre des middlewares

`app.add_middleware(X)` ajoute `X` **à l'extérieur** (il voit la requête en premier). Le
`RequestContextMiddleware` doit être ajouté en **dernier** pour être le plus externe → le
`request_id` existe avant tout le reste. (Au Module 10 on ajoute CORS, GZip… l'ordre
compte.)

---

## 5. Logs structurés & corrélation

### JSON, pas du texte

```python
class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {"ts": ..., "level": record.levelname, "logger": record.name,
                   "msg": record.getMessage()}
        rid = get_request_id()
        if rid: payload["request_id"] = rid
        # + les champs passés via extra={...}
        if record.exc_info: payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)
```

- **une ligne = un objet JSON** → un agrégateur (Loki, Elasticsearch, Datadog…) l'indexe et
  tu peux filtrer `request_id:"9f3c…"` ou `http_status:>=500`.
- en **local**, on garde un format texte lisible (`configure_logging(json_output=False)`).
  En staging/prod : JSON.

### La corrélation par `request_id`

Le `ContextVar` (`request_id_var`) est **isolé par tâche async**. Le middleware le renseigne
au début de la requête. **Toute** ligne de log émise pendant cette requête — par le service,
le handler d'erreur, une lib — le récupère automatiquement.

Résultat : un client te donne le `request_id` de sa réponse d'erreur → tu retrouves **toutes**
les lignes de cette requête, dans l'ordre.

### Règles

- **jamais** de secret dans un log (`password`, token, PII). C'est à toi de ne pas le passer
  dans `extra=`.
- niveaux : `DEBUG` (dev), `INFO` (événements normaux : accès, démarrage), `WARNING`
  (anormal mais géré), `ERROR` (échec), + `exception()` pour la *stack*.
- ne loggue pas 3 fois la même chose (une par couche). Loggue **une** fois, à l'endroit qui
  a le plus de contexte.
- `configure_logging` récupère aussi les loggers d'`uvicorn` pour qu'ils passent par ton
  format.

---

## 6. `HTTPException` a-t-elle encore sa place ?

Oui, pour les cas **purement HTTP** sans dimension métier : `401` d'authentification (Module
06), `405`, `429` de *rate limiting* (Module 10). Pour tout ce qui est « la ressource
demandée n'existe pas / est en conflit / est interdite » → **exception métier**.

---

## 7. Réponses & en-têtes avancés (doc *Response*)

- **renvoyer une `Response` directement** : quand tu veux contrôler le corps brut, un
  fichier, un flux (`FileResponse`, `StreamingResponse` — Module 08).
- **`Additional Responses in OpenAPI`** : documenter qu'une route peut renvoyer 404
  (`responses={404: {"model": Problem}}`) → `/docs` le montre.
- **`Response.headers[...]`** / **`Response.status_code`** : modifiables dans la route via
  le paramètre `response: Response` (on l'a déjà fait pour `Location`).
- **`Additional Status Codes`** : `JSONResponse(status_code=202, ...)` pour un cas
  particulier (traitement asynchrone accepté — Module 08).

---

## 8. Pièges fréquents

1. **Exception métier qui `import fastapi`** → les couches fuient.
2. **500 qui expose la *stack*** au client (fuite d'info : chemins, SQL, versions).
3. **`raise HTTPException` dans le service** au lieu d'une exception métier.
4. **Ne pas traduire `IntegrityError`** → le client reçoit un 500 pour une faute de saisie.
5. **`request_id` non `reset`** après la requête → il « fuit » sur la requête suivante du
   même worker.
6. **`BaseHTTPMiddleware`** pour du streaming → réponses tronquées / bufferisées.
7. **Logger un secret** (token dans l'URL, mot de passe dans le body loggé).
8. **3 handlers qui se marchent dessus** : teste chaque famille d'erreur.
9. **Oublier `jsonable_encoder`** sur les détails de validation → `TypeError` non sérialisable.
10. **Format d'erreur différent** entre 404, 422 et 500 → le client doit gérer 3 schémas.

---

## 9. Ce que `taskman` gagne

- `core/exceptions.py` : `DomainError` → `NotFoundError`/`ConflictError`/`PermissionDeniedError`
  → `TaskNotFoundError`/`ProjectNotFoundError` ;
- `core/context.py` : `request_id_var` (ContextVar) ;
- `core/logging.py` : `JsonFormatter`, `configure_logging` ;
- `api/errors.py` : 4 handlers, format **Problem Details** unifié ;
- `api/middleware.py` : `RequestContextMiddleware` (request-id + accès + latence) ;
- services qui **lèvent** ; repository qui **traduit** `IntegrityError` ;
- routes réduites à des one-liners ;
- tests : format d'erreur, request-id, hiérarchie d'exceptions, `JsonFormatter`.

---

## 10. À savoir refaire sans aide

- Concevoir une hiérarchie d'exceptions métier découplée de HTTP.
- Écrire les handlers qui les traduisent en un format unifié.
- Faire lever le service au lieu de renvoyer `None`, et alléger les routes.
- Traduire une exception d'infra (`IntegrityError`) en exception métier, à la bonne couche.
- Écrire un middleware ASGI pur qui pose un `request-id` et loggue l'accès.
- Configurer un logging JSON corrélé par `ContextVar`.
- Garantir qu'une 500 ne fuit rien.

➡️ [Exercices](exercices/README.md) · [PAS-A-PAS.md](PAS-A-PAS.md)
