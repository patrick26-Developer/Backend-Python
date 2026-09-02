# `saashub` — API SaaS multi-tenant (projet de domaine complet)

> 🚧 **Brief en construction.** Développé par phases (miroir des 13 modules), solution de
> référence complète dans `solution/` (à venir). C'est le projet le plus ambitieux.

## Pitch

Le squelette d'un vrai SaaS : **organisations** (tenants), **membres** avec rôles,
**invitations**, **plans & facturation**, **quotas d'usage**, **clés d'API**, **webhooks
sortants**. Domaine choisi pour : **isolation multi-tenant, RBAC fin, limites d'usage,
facturation, sécurité**.

## Périmètre fonctionnel (cible finale)

- **Comptes & orgs** : un utilisateur peut appartenir à plusieurs organisations ; une org a
  des membres, un plan, un quota.
- **Rôles par org** : `owner`, `admin`, `member`, `billing`. Permissions granulaires.
- **Invitations** : par e-mail, token à durée limitée, acceptation crée l'adhésion.
- **Ressource métier générique** : des « projets » (peu importe, c'est le prétexte) —
  strictement isolés par organisation.
- **Plans & facturation** : `free / pro / enterprise`, limites (nb de projets, nb de membres,
  appels API/mois), simulation d'abonnement + factures.
- **Quotas & usage** : compteur d'appels API par org, `429` au dépassement, reset mensuel.
- **Clés d'API** : par org, *scopes*, révocation, dernier usage.
- **Webhooks sortants** : l'org configure une URL, reçoit les événements (`project.created`…),
  avec signature HMAC et *retries*.
- **Audit log** : qui a fait quoi, quand, dans quelle org.

## Phases (alignées sur les modules)

| Phase | Modules | Livrable |
|---|---|---|
| P1 | 01–02 | Orgs + projets en mémoire, schémas, validation |
| P2 | 03 | Couches ; dépendance `get_current_org` (résolue par header/sous-domaine/chemin) |
| P3 | 04 | PostgreSQL + Alembic ; **stratégie d'isolation** (colonne `org_id` + filtre systématique) |
| P4 | 05 | Erreurs (`QuotaExceededError`, `NotAMemberError`), format unifié, logs avec `org_id` |
| P5 | 06 | Auth utilisateurs + clés d'API ; RBAC par org ; `require_role("admin")` |
| P6 | 07 | Tests : **fuite inter-tenant = échec bloquant** ; matrice rôles × actions |
| P7 | 08 | Compteur d'usage (Redis), `429`, webhooks sortants en worker avec retries |
| P8 | 09 | Métriques par plan, health/ready, traces avec `org_id` en attribut |
| P9 | 10 | OWASP : isolation stricte, BOLA cross-tenant, rate limit par clé, rotation des secrets |
| P10 | 11 | Docker, compose, CI, migrations, seed de démo |
| P11 | 12 | *Outbox* + webhooks signés HMAC, `Idempotency-Key`, versionnage, `owner` transfer |

## Points d'attention spécifiques

- **Isolation** : c'est LE sujet. Toute requête DB porte `WHERE org_id = :current_org`.
  Idéalement centralisé (repository de base, ou *query filter* SQLAlchemy) pour qu'un oubli
  soit impossible, pas juste improbable.
- **Résolution du tenant** : header `X-Org`, sous-domaine, ou `/orgs/{slug}/...` — choisir
  et documenter (ADR).
- **Quotas** : atomiques (INCR Redis), avec fenêtre de reset claire, et un mode « soft »
  (alerte) avant le « hard » (429).
- **Webhooks** : signature, timeout court, *retries* exponentiels, *dead-letter*, jamais
  bloquer la requête d'origine.

## Definition of Done (résumé)

- [ ] Aucun endpoint ne renvoie de donnée d'une autre organisation (tests de fuite dédiés).
- [ ] Un `member` ne peut pas faire d'action `admin` (matrice testée).
- [ ] Le dépassement de quota renvoie 429 et se réinitialise à la fenêtre suivante.
- [ ] Un webhook sortant est signé, rejoué en cas d'échec, et n'impacte pas la latence API.
- [ ] `ruff` + `mypy --strict` + `pytest` au vert ; couverture > 85 %.
