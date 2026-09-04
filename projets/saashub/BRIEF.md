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

---

## Construire la solution : quels patrons réutiliser

C'est le projet le plus ambitieux, mais **aucun** de ses invariants n'est nouveau — ils sont
tous démontrés ailleurs dans le dépôt :

| Invariant `saashub` | Patron à copier | Où |
|---|---|---|
| couches, `create_app()`, DI, config 12-factor | Module 03 + `projets/shopfast/solution` | `03-architecture-projet-mature/` |
| PostgreSQL async + Alembic + `TZDateTime` | Module 04 + `projets/checkpoints/shorturl/solution` | `04-bases-de-donnees/` |
| **isolation multi-tenant** : `WHERE org_id = :current_org` **systématique** | l'isolation `user_id` de `shopfast` (`OrderRepository.get_for_user`), généralisée : un `TenantRepository` de base ou un *query filter* SQLAlchemy pour qu'un oubli soit **impossible** | `projets/shopfast/solution/shopfast/repositories.py` |
| résolution du tenant (`X-Org` / sous-domaine / `/orgs/{slug}`) → ADR | Module 12 (ADR) + `get_current_user` de `shopfast` (même forme de dépendance) | `12-architecture-scalabilite/docs/adr/` |
| auth utilisateurs **+ clés d'API** ; RBAC par org (`owner`/`admin`/`member`/`billing`) | Module 06 + `shopfast` (`require_admin`) ; les clés d'API = un 2ᵉ schéma d'auth dans la même dépendance | `06-authentification-autorisation/` |
| matrice rôles × actions testée ; **fuite inter-tenant = échec bloquant** | tests d'isolation de `shopfast` (`test_customer_cannot_read_or_cancel_another_order`), à décliner en matrice | `projets/shopfast/solution/tests/` |
| erreurs (`QuotaExceededError`, `NotAMemberError`) → format unifié, logs avec `org_id` | Module 05 + `statuspage` (logs corrélés via `ContextVar`) | `05-erreurs-logs-middleware/`, `projets/checkpoints/statuspage/` |
| quotas d'usage atomiques (INCR Redis), `429` + reset mensuel, mode « soft » puis « hard » | Module 10 (rate limiting `RedisRateLimiter` : `INCR`+`EXPIRE`+`TTL`, `Retry-After`) | `10-securite-approfondie/` |
| invitations par token à durée limitée | JWT/token du Module 06 + expiration comme `shorturl.expires_at` | `06-authentification-autorisation/` |
| plans & facturation (`free`/`pro`/`enterprise`), simulation d'abonnement + factures | webhook idempotent de paiement de `shopfast` (`processed_webhooks` + garde d'état) | `projets/shopfast/solution/shopfast/services.py` |
| **webhooks sortants** signés HMAC, retries exponentiels, dead-letter, non bloquants | Module 12 (outbox → worker) + Module 08 (`taskiq`) ; HMAC = `hmac.new(secret, body, sha256)` | `12-architecture-scalabilite/`, `08-async-avance-performance/` |
| audit log (qui / quoi / quand / quelle org) | une table `audit_events` alimentée dans la couche service, comme l'`OutboxRow` du Module 12 | `12-architecture-scalabilite/taskman/outbox.py` |
| métriques par plan, traces avec `org_id` en attribut | Module 09 (`MetricsMiddleware`, labels bornés) + `statuspage` | `09-observabilite-prod-readiness/`, `projets/checkpoints/statuspage/` |
| Docker, compose, CI, seed de démo | Module 11 + `projets/checkpoints/shorturl` (Alembic) | `11-deploiement-devops/` |

Ordre conseillé : P1→P11 du tableau des phases, une phase = une session, tests des phases
précédentes toujours verts. **Commence par l'isolation** (P3) et écris les tests de fuite
**avant** le reste : si un test de fuite passe au rouge plus tard, c'est un bug de sécurité,
pas un détail.
