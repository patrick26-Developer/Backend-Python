# Module 05 — Erreurs, logs & middleware

> 🚧 **En construction** — `THEORIE.md` · `PAS-A-PAS.md` · `exercices/` · `solutions/`.

## Objectif

Une API qui **échoue de façon prévisible et traçable** : format d'erreur unique, logs
structurés corrélés, middleware d'observation.

## Pages de doc FastAPI couvertes

Handling Errors · Middleware · Advanced Middleware · CORS · Additional Status Codes ·
Return a Response Directly · Additional Responses in OpenAPI · Response Headers ·
Response - Change Status Code · Using the Request Directly · Custom Request and APIRoute
class (annexe) · Reference : `Exceptions - HTTPException and WebSocketException`,
`Request class`, `Response class`, `Middleware`.

## Plan

1. Hiérarchie d'exceptions **métier** (`DomainError`, `NotFoundError`, `ConflictError`…),
   découplée de HTTP.
2. `@app.exception_handler(...)` : traduire une exception métier en réponse normalisée
   (Problem Details / RFC 9457).
3. `HTTPException` vs exceptions custom : quand chaque.
4. `RequestValidationError` : personnaliser le format des 422.
5. Middleware ASGI : `request-id`, mesure de latence, log d'accès.
6. Logging structuré JSON, niveaux, corrélation, jamais de secret en clair.
7. Filet 500 : ne jamais fuiter de *stack trace* au client.

## Exercices (aperçu)

- Hiérarchie d'exceptions + handlers ; toutes les erreurs au même schéma JSON.
- Middleware `X-Request-ID` propagé dans chaque ligne de log.
- Migrer les `raise HTTPException(404)` du Module 01 vers `TaskNotFoundError`.

## Definition of Done

Voir [`../ROADMAP.md`](../ROADMAP.md).
