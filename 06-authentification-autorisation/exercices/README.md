# Module 06 — Exercices

> On ajoute les comptes, l'authentification JWT et l'isolation des données. **Toutes** les
> routes métier deviennent protégées, et un test dédié vérifie qu'un utilisateur ne peut
> **pas** voir les données d'un autre.

**Prérequis :** `pip install -e ".[dev]"` (ajoute `pwdlib[argon2]`, `pyjwt`).
**Filet :** `git commit -m "checkpoint: avant module 06"`.

---

## Exercice 06.1 — Sécurité : hachage & JWT 🟡

1. `taskman/core/security.py` :
   - `hash_password` / `verify_password` via `pwdlib` avec `Argon2Hasher(time_cost=2,
     memory_cost=19_456, parallelism=1)` (paramètres OWASP).
   - `create_token(*, subject, token_type, secret, algorithm, expires_in, extra=None)
     -> (token, jti)` : payload `sub`, `type`, `jti` (uuid), `iat`, `exp`.
   - `decode_token(token, *, secret, algorithms) -> dict` : laisse remonter
     `jwt.InvalidTokenError`.
2. `taskman/core/config.py` : `jwt_secret_key: SecretStr` (défaut de dev), `jwt_algorithm`,
   `access_token_expire_minutes=15`, `refresh_token_expire_days=7`. **`model_validator`** :
   refuse le secret de dev si `env in ("staging", "production")`.

**Critères d'acceptation**
- [ ] `verify_password("x", hash_password("x"))` est `True` ; `verify_password("y", …)` `False`.
- [ ] Un token altéré (`token + "x"`) ou signé avec un autre secret → `jwt.InvalidTokenError`.
- [ ] `Settings(env="production")` **sans** `APP_JWT_SECRET_KEY` → erreur de validation.

---

## Exercice 06.2 — Modèles : User, RefreshToken, ownership 🟡

1. `taskman/schemas/user.py` : `UserRole` (enum), `UserCreate` (email, password 8–128),
   `UserRead` (`from_attributes=True`, **sans** mot de passe), `TokenPair`, `RefreshRequest`.
2. `taskman/db/models.py` :
   - `UserRow` : `email` (unique, index), `hashed_password`, `role`, `is_active`, `created_at`.
   - `RefreshTokenRow` : `jti` (PK), `user_id` (FK), `revoked`, `expires_at`, `created_at`.
   - ajoute `owner_id` (FK `users.id`, `ondelete="CASCADE"`, index) à `ProjectRow` **et**
     `TaskRow` ; index composite `(owner_id, status)` sur les tâches.
3. `taskman/db/base.py` : ajoute une **convention de nommage** des contraintes à
   `MetaData(naming_convention=...)` (SQLite batch exige des noms).
4. Alembic : **squash** — supprime l'ancienne migration, régénère **une** `initial schema`.
   (Légitime ici : *rien n'est déployé*. On ne squash **jamais** une migration en prod.)

**Critères d'acceptation**
- [ ] `alembic upgrade head` puis `downgrade base` puis `upgrade head` : OK.
- [ ] `test_migrations` (Module 04) toujours vert.
- [ ] `UserRead.model_validate(<UserRow>)` ne contient pas `hashed_password`.

---

## Exercice 06.3 — Repositories conscients du propriétaire 🔴

1. `repositories/base.py` : `TaskRepository.create(data, *, owner_id)`,
   `list(filters, *, owner_id: int | None)`, `get_owner_id(id) -> int | None`. Idem
   `ProjectRepository`. Ajoute `UserRepository` (`create`, `get`, `get_by_email`, `list`) et
   `RefreshTokenRepository` (`add`, `get`, `revoke`).
2. `repositories/sqlalchemy.py` :
   - `list` : `if owner_id is not None: stmt = stmt.where(TaskRow.owner_id == owner_id)`.
   - `SqlAlchemyUserRepository.create` : `try/except IntegrityError → EmailAlreadyRegisteredError`.
   - `SqlAlchemyRefreshTokenRepository` : CRUD minimal sur `RefreshTokenRow`.
3. `repositories/memory.py` : mêmes signatures ; `InMemoryUserRepository` instancie de vrais
   `UserRow` (les modèles s'instancient sans session).

**Critères d'acceptation**
- [ ] `list(filters, owner_id=1)` ne renvoie que les tâches de l'utilisateur 1.
- [ ] `list(filters, owner_id=None)` renvoie tout (cas admin).
- [ ] `UserRepository.create` avec un e-mail existant → `EmailAlreadyRegisteredError`.

---

## Exercice 06.4 — `AuthService` (register / login / refresh) 🔴

1. `core/exceptions.py` : `AuthenticationError` (401), `InvalidCredentialsError`,
   `InvalidTokenError`, `EmailAlreadyRegisteredError` (409).
2. `services/auth.py` :
   - `register(UserCreate) -> UserRead` : hash + `users.create` + `commit`.
   - `login(*, email, password) -> TokenPair` : `get_by_email` ; **vérifie un hash bidon**
     si l'utilisateur n'existe pas (anti-énumération) ; `InvalidCredentialsError` sinon.
   - `refresh(refresh_token) -> TokenPair` : décode, vérifie `type=="refresh"`, `jti` non
     révoqué + non expiré en base, **révoque l'ancien**, émet un nouveau couple (rotation).
   - `user_from_access_token(token) -> UserRow` : décode, `type=="access"`, charge, `is_active`.
   - `_issue_pair` : access (avec `role` dans les claims) + refresh (stocké via
     `refresh_tokens.add`).

**Critères d'acceptation**
- [ ] `login` avec un e-mail inconnu et un mauvais mot de passe → **même** exception, même
      temps de réponse approximatif.
- [ ] `refresh` du **même** refresh token 2 fois → la 2ᵉ échoue (rotation).
- [ ] Un access token présenté à `refresh` → `InvalidTokenError` (mauvais `type`).

---

## Exercice 06.5 — Dépendances d'auth & routes 🔴

1. `api/deps.py` :
   - `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")` ;
   - `get_auth_service`, `get_user_repository`, `get_refresh_token_repository` ;
   - `get_current_user(token, auth) -> UserRead` ; `CurrentUser` alias ;
   - `require_role(*roles)` — fabrique de dépendances → `PermissionDeniedError` si le rôle
     n'est pas autorisé ;
   - `get_task_service` / `get_project_service` dépendent désormais de `get_current_user` et
     passent `actor=user` au service.
2. `services/tasks.py` + `projects.py` : constructeur `(repo, uow, actor: UserRead)` ;
   propriété `_scope` (`None` si admin) ; `_assert_can_access` qui lève `TaskNotFoundError`
   (404, pas 403) pour la ressource d'autrui ; `list` filtré par `_scope`.
3. `api/routes/auth.py` : `/auth/register`, `/auth/login` (`OAuth2PasswordRequestForm`),
   `/auth/refresh`, `/auth/me`.
4. `api/routes/admin.py` : router avec `dependencies=[Depends(require_role(UserRole.admin))]`,
   route `GET /admin/users`.
5. `api/errors.py` : ajoute `WWW-Authenticate: Bearer` sur les réponses 401.
6. `main.py` : inclure les routers `auth` et `admin`.

**Critères d'acceptation**
- [ ] `GET /tasks` sans token → 401 + entête `WWW-Authenticate: Bearer`.
- [ ] `GET /admin/users` en tant que `member` → 403 `permission_denied`.
- [ ] Le bouton « Authorize » de `/docs` fonctionne (login → token).

---

## Exercice 06.6 — Tests d'isolation (le plus important) 🔴

1. `tests/conftest.py` : fixtures `app`, `client` (non authentifié), `member_client`,
   `admin_client` (rôle forcé en base). **Fixture autouse** qui remplace `hash_password` /
   `verify_password` par des fonctions triviales (argon2 est trop lent pour la suite).
2. `tests/unit/test_auth.py` : sécurité (hash, JWT roundtrip/tamper/expiration) + `AuthService`.
3. `tests/integration/test_auth_api.py` :
   - inscription (sans mot de passe en sortie), doublon → 409, mot de passe faible → 422 ;
   - login mauvais mdp / utilisateur inconnu → **même** code `invalid_credentials` ;
   - refresh + rotation (l'ancien token révoqué) ;
   - RBAC (member 403, admin 200) ;
   - **BOLA** : Bob ne peut ni voir, ni modifier, ni supprimer la tâche d'Alice → **404** ;
     la liste de Bob est vide ; l'admin voit tout.
4. Adapte `test_tasks_api.py` : les opérations passent par `member_client`.

**Critères d'acceptation**
- [ ] La suite est verte **et rapide** (grâce au faux hachage).
- [ ] Le test « Bob accède à la tâche d'Alice » attend **404** (et échoue si on renvoie 403 ou 200).
- [ ] Chaque famille d'erreur d'auth a un test.

---

## Rendu

```bash
alembic upgrade head
ruff check . && ruff format --check . && mypy taskman && pytest
git add -A && git commit -m "feat(module-06): auth OAuth2+JWT, RBAC, isolation des données par utilisateur"
```

Puis [`../solutions/README.md`](../solutions/README.md) et [`../PAS-A-PAS.md`](../PAS-A-PAS.md).

**Mini-projet associé** : reprends `linkstash` ou `pollup` et ajoute-lui l'authentification.
