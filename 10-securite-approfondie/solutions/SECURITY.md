# Sécurité de `taskman`

> Auto-audit selon l'**OWASP API Security Top 10 (2023)**. Chaque point : le risque, ce que
> `taskman` fait, où c'est dans le code.

## Signaler une vulnérabilité

Ne pas ouvrir d'issue publique. Écrire à **mb.patrickdegrace@gmail.com**.

---

## OWASP API Security Top 10 (2023)

### API1:2023 — Broken Object Level Authorization (BOLA / IDOR)

- **Risque** : un utilisateur authentifié accède à la ressource d'un autre en devinant l'id.
- **`taskman`** : chaque tâche/projet a un `owner_id`. Le service filtre **en SQL**
  (`WHERE owner_id = :me`) ; l'accès par id vérifie la propriété **avant** de répondre ;
  la ressource d'autrui renvoie **404** (pas 403 — anti-énumération). L'admin voit tout.
- **Code** : `taskman/services/tasks.py::_assert_can_access`,
  `repositories/sqlalchemy.py` (clauses `where owner_id`).
- **Test** : `tests/integration/test_auth_api.py::test_member_cannot_touch_another_members_task`.

### API2:2023 — Broken Authentication

- **Risque** : mots de passe faibles/en clair, tokens mal validés, brute force.
- **`taskman`** : hachage **argon2id** (paramètres OWASP) ; JWT signés (`HS256`), `exp`
  vérifié, `type` (access ≠ refresh) vérifié ; **refresh token à rotation** + révocation en
  base ; **rate limiting** sur `/auth/*` ; protection contre l'**énumération de comptes**
  (même erreur, même temps de réponse) ; secret de dev **refusé en production**.
- **Code** : `core/security.py`, `services/auth.py`, `api/ratelimit.py`, `core/config.py`.
- **Test** : `tests/unit/test_auth.py`, `tests/integration/test_security.py::test_auth_rate_limit_returns_429`.

### API3:2023 — Broken Object Property Level Authorization

- **Risque** : le client fixe un champ « serveur » (`id`, `owner_id`, `role`) ou lit un
  champ sensible (`hashed_password`).
- **`taskman`** : schémas d'entrée (`TaskCreate`, `UserCreate`) **sans** les champs serveur ;
  schémas de sortie (`UserRead`) **sans** le hash ; `TaskFilters` en `extra="forbid"`.
- **Code** : `taskman/schemas/`.
- **Test** : `test_auth_api.py::test_register_returns_user_without_password`,
  `test_tasks_api.py::test_server_fields_cannot_be_set_by_client`.

### API4:2023 — Unrestricted Resource Consumption

- **Risque** : payloads géants, pagination illimitée, requêtes coûteuses en boucle.
- **`taskman`** : `BodySizeLimitMiddleware` (413 si `Content-Length` > 1 Mio) ;
  `limit ≤ 100` sur toutes les listes ; recherche `q` bornée à 100 caractères ;
  agrégats coûteux **mis en cache** ; rate limiting.
- **Code** : `api/middleware.py::BodySizeLimitMiddleware`, `schemas/task.py::TaskFilters`.
- **Test** : `test_security.py::test_oversized_payload_is_413`.

### API5:2023 — Broken Function Level Authorization

- **Risque** : un utilisateur normal appelle une fonction d'admin.
- **`taskman`** : `require_role(UserRole.admin)` posé sur **le router** `/admin` (pas
  par route → impossible d'oublier).
- **Code** : `api/routes/admin.py`, `api/deps.py::require_role`.
- **Test** : `test_auth_api.py::test_admin_route_forbidden_for_member`.

### API6:2023 — Unrestricted Access to Sensitive Business Flows

- **Risque** : automatiser un flux métier (créer 10 000 comptes, spammer).
- **`taskman`** : rate limiting sur l'inscription/connexion. Pour un vrai produit :
  CAPTCHA, vérification e-mail, détection d'anomalie (hors périmètre du cursus).

### API7:2023 — Server Side Request Forgery (SSRF)

- **Risque** : l'API fait une requête sortante vers une URL fournie par le client.
- **`taskman`** : ne fait **aucune** requête sortante pilotée par l'entrée utilisateur.
  Les webhooks sortants (projet `saashub`) valident l'URL (pas d'IP privée, schéma https).

### API8:2023 — Security Misconfiguration

- **Risque** : `/docs` ouverte en prod, en-têtes manquants, CORS permissif, stack traces.
- **`taskman`** : `/docs` **fermée en production** ; en-têtes de sécurité
  (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CSP, HSTS en prod) ;
  **CORS restreint** à des origines explicites (jamais `*` avec `credentials`) ;
  les 500 renvoient un message **générique** (stack en logs seulement).
- **Code** : `api/middleware.py::SecurityHeadersMiddleware`, `main.py` (CORS),
  `api/errors.py`, `core/config.py::docs_url`.
- **Test** : `test_security.py::test_security_headers_present`, `test_cors_*`.

### API9:2023 — Improper Inventory Management

- **Risque** : endpoints oubliés, versions obsolètes exposées, doc désynchronisée.
- **`taskman`** : `/openapi.json` **dérivé du code** (toujours à jour) ; `/metrics`
  explicitement `include_in_schema=False` ; versionnage d'API `/v1` au Module 12.
- **Code** : `api/routes/ops.py`.

### API10:2023 — Unsafe Consumption of APIs

- **Risque** : faire aveuglément confiance aux données d'une API tierce.
- **`taskman`** : valide **toute** entrée externe avec Pydantic, y compris les payloads de
  webhooks entrants (projets).

---

## Chaîne d'approvisionnement (dépendances)

- versions **épinglées** dans `pyproject.toml` + `uv.lock` / `requirements` verrouillés ;
- **`pip-audit`** dans la CI (`.github/workflows/ci.yml`) — le *merge* est bloqué si une
  dépendance a une CVE connue ;
- `pre-commit` `detect-private-key` empêche de committer une clé.

## Secrets

- **jamais** dans le code ni dans git (`.env` est `.gitignore`) ;
- `SecretStr` masque les secrets dans les logs et les `repr` ;
- en prod : gestionnaire de secrets (Vault, AWS Secrets Manager, variables chiffrées CI) ;
- rotation : le secret JWT peut être changé (les tokens en cours expirent en 15 min).

## Journalisation de sécurité

- chaque requête : `request_id`, IP, méthode, chemin, statut (Module 05) ;
- **jamais** de secret / mot de passe / token loggé ;
- les 401/403/429 sont visibles dans les métriques (`http_requests_total{status=...}`).

---

## Checklist avant mise en production

- [ ] `APP_JWT_SECRET_KEY` défini, aléatoire, ≥ 32 octets, différent de staging.
- [ ] `APP_ENV=production` (⇒ `/docs` fermée, HSTS actif).
- [ ] `APP_CORS_ORIGINS` = la (les) origine(s) réelle(s) du front, **pas** `*`.
- [ ] `APP_DATABASE_URL` / `APP_REDIS_URL` = services managés, TLS activé.
- [ ] HTTPS terminé par le reverse proxy ; `--forwarded-allow-ips` configuré.
- [ ] `pip-audit` vert.
- [ ] `/metrics` et `/ready` **non** joignables depuis Internet.
- [ ] Sauvegardes DB testées (restauration vérifiée).
- [ ] Rate limits calibrés pour le trafic attendu.
