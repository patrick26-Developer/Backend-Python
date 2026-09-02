# Module 10 — Sécurité approfondie

> 🚧 **En construction** — `THEORIE.md` · `PAS-A-PAS.md` · `exercices/` · `solutions/`.

## Objectif

**Auditer sa propre API avec une méthode** (OWASP API Top 10) et corriger les trous. La
sécurité est une propriété transverse, pas une fonctionnalité.

## Pages de doc FastAPI couvertes

CORS (approfondi) · Advanced Middleware · Strict Content-Type Checking · Conditional OpenAPI ·
HTTP Basic Auth · OAuth2 scopes (rappel) · Reference : `Security Tools`, `Middleware`.

## Plan

1. **OWASP API Security Top 10 (2023)** point par point, appliqué à `taskman`.
2. BOLA / IDOR : vérifier la propriété de la ressource, pas seulement l'auth.
3. *Rate limiting* / *throttling* : par IP, par utilisateur, par route.
4. CORS en profondeur : pré-vol, `credentials`, origines explicites.
5. En-têtes de sécurité : `HSTS`, `X-Content-Type-Options`, `CSP`, `Referrer-Policy`.
6. Limites : taille de payload, profondeur JSON, pagination max, *mass assignment*.
7. Secrets : *vault*, rotation, `pip-audit` / scan de dépendances en CI.
8. Journal d'audit de sécurité.

## Exercices (aperçu)

- Trouver et corriger un IDOR dans `taskman`.
- Ajouter un *rate limiter* et le tester.
- Durcir en-têtes + CORS ; limiter la taille des payloads.
- `pip-audit` bloquant en CI ; rédiger `SECURITY.md` avec la checklist OWASP cochée.

## Definition of Done

Voir [`../ROADMAP.md`](../ROADMAP.md).
