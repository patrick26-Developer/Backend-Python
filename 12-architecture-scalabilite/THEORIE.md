# Module 12 — Architecture & scalabilité

> 🚧 **En construction** — `THEORIE.md` · `PAS-A-PAS.md` · `exercices/` · `solutions/`.

## Objectif

**Défendre un choix d'architecture avec des arguments de coût et de risque**, pas de mode.
Savoir *quand ne pas* découper.

## Pages de doc FastAPI couvertes

Sub Applications - Mounts · WebSockets · Testing WebSockets · Server-Sent Events · OpenAPI
Webhooks · OpenAPI Callbacks (annexe) · Path Operation Advanced Configuration · Extending
OpenAPI (annexe) · Including WSGI - Flask/Django (annexe) · GraphQL (annexe) · Reference :
`WebSockets`, `HTTPConnection class`, `Server-Sent Events`, `APIRouter class`.

## Plan

1. Monolithe modulaire vs microservices : coûts réels, quand migrer.
2. DDD léger : *bounded contexts*, agrégats, *value objects*, placement des règles.
3. *Event-driven* : événements de domaine, *outbox pattern*, idempotence des consommateurs.
4. Versionnage d'API : URI vs header, dépréciation, cycle de vie.
5. Temps réel : WebSockets vs SSE, *scaling* via Redis pub/sub.
6. Idempotence des écritures : `Idempotency-Key`, *at-least-once*.
7. Multi-instance : *statelessness*, jobs distribués.

## Exercices (aperçu)

- Réorganiser `taskman` en modules par *bounded context* + 3 ADR dans `docs/adr/`.
- Événement `TaskCompleted` via *outbox*, consommé par un worker.
- API versionnée `/v1` + `/v2` avec un contrat qui change.
- Notifications temps réel via SSE ; `POST /tasks` rendu idempotent.
- **Refaire `taskman` de zéro en 2 jours** — le vrai test.

## Definition of Done

Voir [`../ROADMAP.md`](../ROADMAP.md).
