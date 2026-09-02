# Module 06 — Authentification & autorisation

> 🚧 **En construction** — `THEORIE.md` · `PAS-A-PAS.md` · `exercices/` · `solutions/`.

## Objectif

Protéger l'API avec un **modèle d'accès explicite et testé**. Ici, « ça marche » ne suffit
pas : l'auth mal faite = fuite de données.

## Pages de doc FastAPI couvertes

Security · Security - First Steps · Get Current User · Simple OAuth2 with Password and
Bearer · OAuth2 with Password (hashing), Bearer with JWT tokens · Advanced Security —
OAuth2 scopes · HTTP Basic Auth (annexe) · Response Cookies · How-To « Use Old 403
Authentication Error Status Codes » (annexe) · Reference : `Security Tools`.

## Plan

1. Authentification vs autorisation.
2. Hachage : `argon2`/`bcrypt`, *salting*, comparaison en temps constant.
3. OAuth2 *password flow*, `OAuth2PasswordBearer`, `OAuth2PasswordRequestForm`.
4. JWT : structure, signature, `exp`, access court + refresh, rotation, révocation (`jti`).
5. Dépendances de sécurité : `get_current_user`, `get_current_active_user`.
6. Autorisation : RBAC (rôles), *scopes* OAuth2, autorisation au niveau ressource (BOLA).
7. Pièges : *timing attacks*, token dans l'URL, secret en dur, CORS trop permissif.

## Exercices (aperçu)

- `User` + inscription + login → JWT ; route protégée via `get_current_user`.
- RBAC : `admin` voit tout, `member` seulement ses tâches.
- Refresh token avec rotation et invalidation de l'ancien.
- Tests : non authentifié (401), authentifié non autorisé (403), autorisé (200).

## Definition of Done

Voir [`../ROADMAP.md`](../ROADMAP.md).
