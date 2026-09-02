# Module 05 — Exercices

> On unifie la gestion d'erreur de `taskman` et on ajoute la traçabilité. Après ce module,
> **toutes** les erreurs sortent au même format et chaque log porte un `request_id`.

**Filet de sécurité :** `git commit -m "checkpoint: avant module 05"`.

---

## Exercice 05.1 — La hiérarchie d'exceptions métier 🟡

1. `taskman/core/exceptions.py` (aucun `import fastapi`) :
   - `DomainError(Exception)` avec attributs de classe `status_code=400`, `code="domain_error"`,
     `title`, et `__init__(self, detail: str)` qui stocke `self.detail`.
   - `NotFoundError` (404), `ConflictError` (409), `PermissionDeniedError` (403).
   - `TaskNotFoundError(NotFoundError)` : `code="task_not_found"`, `__init__(self, task_id)`.
   - `ProjectNotFoundError(NotFoundError)` : idem.
2. Test : `TaskNotFoundError(42)` est une instance de `NotFoundError` **et** `DomainError`,
   `status_code == 404`, `code == "task_not_found"`.

**Critères d'acceptation**
- [ ] `grep import fastapi taskman/core/exceptions.py` → rien.
- [ ] Une seule racine (`DomainError`) permet d'attraper toutes les erreurs métier.
- [ ] `mypy` OK.

---

## Exercice 05.2 — Le service lève, la route maigrit 🟡

1. `TaskService.get/update/delete` : lèvent `TaskNotFoundError(task_id)` au lieu de renvoyer
   `None`. `get`/`update` renvoient désormais `TaskRead` (plus `| None`) ; `delete` renvoie
   `None`.
2. `ProjectService.get` : lève `ProjectNotFoundError`.
3. `taskman/repositories/sqlalchemy.py` : dans `SqlAlchemyTaskRepository.create`, entoure le
   `flush()` d'un `try/except IntegrityError` → `rollback()` puis
   `raise ProjectNotFoundError(data.project_id) from exc`.
4. Routes `tasks.py` / `projects.py` : supprime tous les `raise HTTPException` et les
   `if ... is None`. Les fonctions de route deviennent des one-liners.

**Critères d'acceptation**
- [ ] `grep HTTPException taskman/api/routes/` → rien.
- [ ] Le service unitaire : `pytest.raises(TaskNotFoundError)` sur `get(inexistant)`.
- [ ] `mypy` : les retours de `get`/`update` sont `TaskRead`, pas `TaskRead | None`.

---

## Exercice 05.3 — Contexte de requête & logs JSON 🟡

1. `taskman/core/context.py` : `request_id_var: ContextVar[str | None]` (défaut `None`) +
   `get_request_id()`.
2. `taskman/core/logging.py` :
   - `JsonFormatter(logging.Formatter)` : sérialise chaque *record* en une ligne JSON
     (`ts`, `level`, `logger`, `msg`), ajoute `request_id` s'il existe, ajoute les champs
     passés via `extra=`, ajoute `exc` si `record.exc_info`.
   - `configure_logging(*, level, json_output)` : installe un `StreamHandler` sur le root,
     format JSON ou texte selon `json_output`, et fait passer les loggers `uvicorn.*` par le
     root.
3. `taskman/core/config.py` : ajoute `log_json: bool | None = None` + propriété
   `use_json_logs` (`log_json` si défini, sinon `env != "local"`).

**Critères d'acceptation**
- [ ] `JsonFormatter().format(record)` produit un JSON valide.
- [ ] Si `request_id_var` est défini, la ligne contient `request_id` ; sinon, non.
- [ ] `configure_logging(json_output=False)` → format texte lisible.

---

## Exercice 05.4 — Les exception handlers (format unifié) 🔴

1. `taskman/api/errors.py` :
   - `_problem(*, status, title, detail, code, instance, **extra) -> JSONResponse` :
     construit le corps RFC 9457 (`type`, `title`, `status`, `detail`, `code`, `instance`),
     ajoute `request_id` s'il existe, `media_type="application/problem+json"`, et passe le
     tout par `jsonable_encoder`.
   - `register_error_handlers(app)` : handlers pour `DomainError`, `RequestValidationError`
     (422, champ `errors`), `StarletteHTTPException`, et `Exception` (500 : `logger.exception`
     + message **générique**).
2. Appelle `register_error_handlers(app)` dans `create_app`.

**Critères d'acceptation**
- [ ] `GET /tasks/999` → 404, `Content-Type: application/problem+json`, `code == "task_not_found"`.
- [ ] `POST /tasks` avec `title=""` → 422, **même** schéma, `code == "validation_error"`.
- [ ] Une 500 simulée → le corps ne contient **aucun** détail technique ; la *stack* est
      dans les logs.

---

## Exercice 05.5 — Le middleware request-id 🔴

1. `taskman/api/middleware.py` : `RequestContextMiddleware` (ASGI **pur**, pas
   `BaseHTTPMiddleware`) :
   - lit `X-Request-ID` ou en génère un (`uuid4().hex`) ;
   - `request_id_var.set(...)` au début, `.reset(token)` dans un `finally` ;
   - `send_wrapper` qui intercepte `http.response.start` pour lire le statut et **ajouter**
     l'en-tête `x-request-id` à la réponse ;
   - loggue une ligne d'accès (`method`, `path`, `status`, `duration_ms`, `client`) dans le
     `finally` (donc même en cas d'exception).
2. `create_app` : `app.add_middleware(RequestContextMiddleware)`.

**Critères d'acceptation**
- [ ] Toute réponse porte un en-tête `X-Request-ID`.
- [ ] Si le client fournit `X-Request-ID: abc`, la réponse renvoie `abc` (respecté).
- [ ] Une requête qui provoque une 500 émet quand même sa ligne d'accès dans les logs.
- [ ] Le `request_id` d'un log de service = celui de l'en-tête de la réponse.

---

## Exercice 05.6 — Traduire l'`IntegrityError` & tests d'erreur 🟡

1. Vérifie : `POST /tasks` avec un `project_id` inexistant → **404** `project_not_found`
   (pas 500, pas d'`IntegrityError` brute).
2. Tests d'intégration : ajoute
   - `test_error_format_is_problem_details` (les 7 clés attendues) ;
   - `test_validation_error_uses_same_format` ;
   - `test_request_id_echoed_and_respected`.
3. Passe la couverture des **branches d'erreur** en revue : chaque handler a au moins un test.

**Critères d'acceptation**
- [ ] `pytest` vert, y compris les nouveaux tests d'erreur.
- [ ] `ruff` + `mypy --strict` OK.
- [ ] Les logs de test ne polluent pas la sortie (`log_json=False`, `log_level="WARNING"`).

---

## Rendu

```
taskman/
├── core/{context,exceptions,logging}.py
├── api/{errors,middleware}.py
├── services/{tasks,projects}.py   # lèvent
├── repositories/sqlalchemy.py     # traduit IntegrityError
└── api/routes/{tasks,projects}.py # one-liners
```

```bash
ruff check . && ruff format --check . && mypy taskman && pytest
git add -A && git commit -m "feat(module-05): exceptions métier + handlers RFC 9457 + middleware request-id + logs JSON"
```

Puis [`../solutions/README.md`](../solutions/) et [`../PAS-A-PAS.md`](../PAS-A-PAS.md).
