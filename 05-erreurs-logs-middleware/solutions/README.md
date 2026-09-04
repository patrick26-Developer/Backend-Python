# Module 05 — Solutions : les choix de conception

> Code dans `taskman/`. Explication ligne par ligne : [`../PAS-A-PAS.md`](../PAS-A-PAS.md).

```bash
cd 05-erreurs-logs-middleware/solutions
pytest
mypy taskman
```

---

## Décision 1 — Les exceptions métier n'importent pas `fastapi`

`core/exceptions.py` ne connaît que `Exception`. Une `TaskNotFoundError` décrit un fait du
**domaine** (« cette tâche n'existe pas »), pas une réponse HTTP. Le mapping vers `404` est
la responsabilité d'**une** couche : les *exception handlers*. Bénéfices :

- on peut réutiliser le service dans un worker, un script, un test — sans FastAPI ;
- changer « 404 » en « 410 » pour un cas = 1 ligne dans le handler, pas une chasse dans le code ;
- `status_code`/`code`/`title` portés par l'exception = le domaine *suggère*, le handler *décide*.

## Décision 2 — Une racine (`DomainError`) + des familles + des exceptions précises

```
DomainError                 (racine — 1 handler attrape tout)
├── NotFoundError  (404)
│   ├── TaskNotFoundError    (code="task_not_found", + task_id)
│   └── ProjectNotFoundError
├── ConflictError  (409)
└── PermissionDeniedError (403)   ← utilisé au Module 06
```

- **la racine** : `@app.exception_handler(DomainError)` couvre *toutes* les erreurs métier,
  présentes et futures.
- **les familles** : le bon code HTTP défini une fois.
- **les précises** : un `code` machine stable pour le client + des attributs (`task_id`).

## Décision 3 — Le service **lève**, il ne renvoie plus `None`

`get`/`update` renvoient `TaskRead` (plus `| None`). L'appelant (la route) n'a **plus** de
cas d'absence à gérer → la route redevient `return await service.get(task_id)`. Le type plus
strict est aussi vérifié par mypy : impossible d'oublier le `None`.

## Décision 4 — On traduit `IntegrityError` **dans le repository**

C'est la seule couche qui connaît SQLAlchemy. `except IntegrityError → rollback() → raise
ProjectNotFoundError(...) from exc`. Le `from exc` garde la cause pour les logs ; les couches
hautes ne voient qu'une erreur métier. Résultat : un `project_id` bidon → **404 propre**,
pas une 500 avec une *stack* SQL.

## Décision 5 — `request_id` via `ContextVar`, pas via un argument

Passer un `request_id` en paramètre à *toutes* les fonctions serait insupportable. Un
`ContextVar` est **isolé par tâche async** : le middleware le pose au début de la requête,
le `JsonFormatter` le lit, sans que rien entre les deux n'ait à le savoir. On `reset()` en
fin de requête — sinon il « colle » à la requête suivante du même worker.

## Décision 6 — Middleware ASGI **pur** (pas `BaseHTTPMiddleware`)

`BaseHTTPMiddleware` a des soucis connus avec le streaming et les *background tasks* (il
bufferise la réponse). La version pure (`scope`/`receive`/`send`) est plus verbeuse mais
robuste. On intercepte `http.response.start` pour lire le statut et injecter l'en-tête
`x-request-id`. Le log d'accès est dans un `finally` → émis même sur une 500.

## Décision 7 — Format unifié : Problem Details (RFC 9457)

**Toutes** les erreurs (404 métier, 422 validation, 500) passent par `_problem()` → même
schéma JSON, `Content-Type: application/problem+json`. Le client gère **un** format. Le
champ `code` est l'identifiant stable (le `detail` humain peut évoluer).

## Décision 8 — Une 500 ne fuit **rien**

Le handler `Exception` fait `_logger.exception(...)` (message + *stack* complète, côté
serveur) et renvoie un corps **générique** (« Une erreur inattendue est survenue »). Aucun
chemin de fichier, aucune requête SQL, aucun nom de variable exposé. Le `request_id` permet
de retrouver la *stack* dans les logs.

## Décision 9 — Logs JSON hors local, texte en local

`use_json_logs` = `env != "local"` (surchargable par `APP_LOG_JSON`). En dev tu lis du texte
coloré ; en prod, du JSON qu'un agrégateur indexe. Les tests forcent `log_json=False` +
`log_level="WARNING"` pour ne pas polluer la sortie.

---

## Grille d'auto-évaluation

- [ ] `grep -r "import fastapi" taskman/core/` → **vide** ?
- [ ] `grep -r "HTTPException" taskman/api/routes/` → **vide** ?
- [ ] Un `project_id` inexistant → 404 `project_not_found` (pas 500) ?
- [ ] 404, 422 et 500 ont-ils **le même** schéma JSON chez toi ?
- [ ] Une 500 expose-t-elle quoi que ce soit de technique dans le corps ?
- [ ] Le `request_id` de la réponse se retrouve-t-il dans les logs de la requête ?
- [ ] `request_id_var` est-il `reset()` en fin de requête ?

➡️ [Module 06 — Authentification & autorisation](../../06-authentification-autorisation/THEORIE.md)
