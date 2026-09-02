# Module 06 — Explication pas à pas du code

> Fichiers **nouveaux** : `core/security.py`, `schemas/user.py`, `services/auth.py`,
> `api/routes/auth.py`, `api/routes/admin.py`. Fichiers **modifiés** : `core/config.py`,
> `core/exceptions.py`, `db/base.py`, `db/models.py`, `repositories/*`, `services/tasks.py` +
> `projects.py`, `api/deps.py`, `api/errors.py`, `main.py`.
> Garde [`solutions/taskman/`](solutions/taskman/) ouvert.

---

## 1. `taskman/core/security.py`

```python
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

_hasher = PasswordHash([Argon2Hasher(time_cost=2, memory_cost=19_456, parallelism=1)])
```

- `argon2id` : algorithme de hachage **lent et gourmand en mémoire** — un GPU ne peut pas
  en tester des milliards par seconde (contrairement à SHA/MD5).
- `time_cost=2, memory_cost≈19 Mio, parallelism=1` : les paramètres **OWASP** — solides,
  ~150 ms. (Le défaut `PasswordHash.recommended()` est plus agressif ; ici on calibre.)

```python
def hash_password(plain: str) -> str:       return _hasher.hash(plain)
def verify_password(plain, hashed) -> bool: return _hasher.verify(plain, hashed)
```

`hash` intègre un **sel aléatoire** → deux fois le même mot de passe = deux hashs
différents. `verify` compare en **temps constant**.

```python
def create_token(*, subject, token_type, secret, algorithm, expires_in, extra=None):
    now = datetime.now(UTC)
    jti = uuid.uuid4().hex
    payload = {"sub": subject, "type": token_type, "jti": jti,
               "iat": int(now.timestamp()), "exp": int((now + expires_in).timestamp())}
    if extra: payload.update(extra)
    return jwt.encode(payload, secret, algorithm=algorithm), jti
```

- `sub` : l'id utilisateur (en `str`, convention JWT).
- `type` : `"access"` ou `"refresh"` — pour qu'un refresh token ne puisse pas servir
  d'access token, et inversement.
- `jti` : identifiant **unique** du token. On le stocke pour les refresh tokens → on peut
  révoquer.
- `exp` : PyJWT rejette automatiquement un token expiré au `decode`.
- on renvoie `(token, jti)` : le `jti` sert à l'appelant pour l'enregistrer.

```python
def decode_token(token, *, secret, algorithms) -> dict:
    return jwt.decode(token, secret, algorithms=algorithms)
```

Lève `jwt.InvalidTokenError` (et sous-classes : `ExpiredSignatureError`,
`InvalidSignatureError`…) si le token est altéré, expiré, ou signé avec un autre secret.

---

## 2. `taskman/core/config.py` (ajouts sécurité)

```python
_DEV_SECRET = "dev-only-not-secret-change-me-with-openssl-rand-hex-32"

class Settings(BaseSettings):
    jwt_secret_key: SecretStr = SecretStr(_DEV_SECRET)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=15, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    @model_validator(mode="after")
    def _no_dev_secret_in_production(self) -> "Settings":
        if self.env in ("staging", "production") and \
           self.jwt_secret_key.get_secret_value() == _DEV_SECRET:
            raise ValueError("APP_JWT_SECRET_KEY doit être défini hors du développement")
        return self
```

- `SecretStr` : type Pydantic dont la valeur est **masquée** dans les `repr` et les logs
  (`SecretStr('**********')`). On lit la vraie valeur avec `.get_secret_value()`.
- `HS256` (HMAC-SHA256) : **un** secret signe et vérifie. Simple, suffisant quand un seul
  service émet et consomme les tokens.
- `access` court (15 min) + `refresh` long (7 j) : voir THEORIE §3.
- **le `model_validator`** : l'app **refuse de démarrer** en prod avec le secret de dev.
  Un garde-fou de config, pas un test — ça bloque au boot, pas à la 1re requête.

---

## 3. `taskman/schemas/user.py`

```python
class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
```

**Aucun** champ `password` ni `hashed_password`. C'est le contrat de sortie — le hash ne
doit **jamais** transiter. `UserCreate` a `password` (entrée seulement).

```python
class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
```

Le format de réponse d'un `/login` OAuth2 (`token_type: "bearer"` est la convention).

---

## 4. `taskman/db/base.py` (convention de nommage)

```python
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    ...
}
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

Sans convention, SQLAlchemy nomme certaines contraintes automatiquement (ou pas). Problème :
- SQLite en **mode batch** (recréation de table pour un `ALTER`) **exige** des noms
  explicites ;
- un `downgrade` qui fait `drop_constraint("???")` a besoin du nom.

Avec la convention, **toutes** les contraintes ont un nom déterministe. On l'ajoute
maintenant → il faut **régénérer** les migrations (d'où le squash de l'exercice 06.2).

---

## 5. `taskman/db/models.py`

```python
class UserRow(Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, native_enum=False, length=16),
                                           default=UserRole.member)
    is_active: Mapped[bool] = mapped_column(default=True)
```

- `email` : `unique=True` → contrainte d'unicité en base (double inscription = `IntegrityError`).
- `is_active` : désactiver un compte sans le supprimer (audit, RGPD, bannissement).

```python
class RefreshTokenRow(Base):
    __tablename__ = "refresh_tokens"
    jti: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    revoked: Mapped[bool] = mapped_column(default=False)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime)
```

Le refresh token JWT est *stateless*, mais on garde une **trace** de chaque `jti` émis pour
pouvoir le **révoquer** (rotation, déconnexion). `revoked=True` = ce token ne resservira pas.

```python
class TaskRow(Base):
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
```

`owner_id` sur `tasks` **et** `projects` : c'est la colonne qui porte l'isolation. `index=True`
car on filtre **toutes** les listes dessus. `ondelete="CASCADE"` : supprimer un compte
supprime ses données.

---

## 6. `taskman/repositories/` — conscients du propriétaire

```python
# base.py
class TaskRepository(Protocol):
    async def create(self, data: TaskCreate, *, owner_id: int) -> TaskRead: ...
    async def get_owner_id(self, task_id: int) -> int | None: ...
    async def list(self, filters, *, owner_id: int | None) -> tuple[list[TaskRead], int]: ...
```

- `create(..., *, owner_id)` : on rattache la tâche à son créateur.
- `get_owner_id(id)` : une requête **minimale** (juste la colonne `owner_id`) pour le
  contrôle d'accès, sans charger toute la tâche.
- `list(..., *, owner_id: int | None)` : `None` = pas de filtre (admin).

```python
# sqlalchemy.py
async def list(self, filters, *, owner_id):
    stmt = select(TaskRow)
    if owner_id is not None:
        stmt = stmt.where(TaskRow.owner_id == owner_id)   # <- ISOLATION, dans le SQL
    ...
```

L'isolation est un `WHERE`, **pas** un `[t for t in rows if t.owner_id == me]` après coup.
Différence cruciale : le filtre SQL est appliqué **avant** la pagination et le `COUNT`, et un
oubli est visible (il manque une clause), pas silencieux.

```python
async def create(self, *, email, hashed_password) -> UserRow:
    row = UserRow(email=email, hashed_password=hashed_password, role=UserRole.member)
    self._session.add(row)
    try:
        await self._session.flush()
    except IntegrityError as exc:
        await self._session.rollback()
        raise EmailAlreadyRegisteredError(email) from exc
```

Même patron qu'au Module 05 : l'`IntegrityError` (unicité de l'e-mail) est **traduite** en
erreur métier (`409`).

---

## 7. `taskman/services/auth.py`

```python
from taskman.core import security   # via le MODULE -> monkeypatchable en test

@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return security.hash_password("x" * 24)
```

- on importe `security` **comme module** (`security.hash_password(...)`), pas la fonction
  directement → un test peut `monkeypatch.setattr(security, "hash_password", fake)`.
- `_dummy_hash()` : calculé **à la 1re demande** (`lru_cache`), pas à l'import — sinon le
  vrai argon2 tournerait même quand les tests l'ont remplacé.

```python
async def login(self, *, email, password) -> TokenPair:
    user = await self._users.get_by_email(email)
    stored = user.hashed_password if user is not None else _dummy_hash()
    if not security.verify_password(password, stored) or user is None:
        raise InvalidCredentialsError()
```

**Anti-énumération** : si `user is None`, on vérifie quand même un hash bidon. Le temps de
réponse (dominé par argon2) est le **même** que l'utilisateur existe ou non. Et l'erreur est
**identique** (`invalid_credentials`) dans les deux cas.

```python
async def refresh(self, refresh_token: str) -> TokenPair:
    payload = self._decode(refresh_token, expected_type="refresh")
    jti = str(payload["jti"])
    stored = await self._refresh.get(jti)
    if stored is None or stored.revoked or _expired(stored.expires_at):
        raise InvalidTokenError("Refresh token invalide ou révoqué")
    user = await self._users.get(int(str(payload["sub"])))
    ...
    await self._refresh.revoke(jti)          # ROTATION : l'ancien est mort
    return await self._issue_pair(user)
```

- 4 vérifications : signature+`exp` (`_decode`), `type == "refresh"`, `jti` connu, `jti` non
  révoqué et non expiré **en base**.
- `revoke(jti)` **avant** d'émettre le nouveau couple : si le vieux token est rejoué, sa 2ᵉ
  utilisation échoue.

```python
def _decode(self, token, *, expected_type) -> dict:
    try:
        payload = decode_token(token, secret=..., algorithms=[...])
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError() from exc          # infra -> métier
    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"Type attendu : {expected_type}")
    return payload
```

On **traduit** `jwt.InvalidTokenError` (lib) en `InvalidTokenError` (métier, 401). Et on
vérifie le `type` — un access token n'est **pas** un refresh token.

```python
async def _issue_pair(self, user) -> TokenPair:
    access, _ = create_token(subject=str(user.id), token_type="access", ...,
                             extra={"role": user.role.value})
    refresh, jti = create_token(subject=str(user.id), token_type="refresh", ...)
    await self._refresh.add(jti=jti, user_id=user.id, expires_at=now + refresh_ttl)
    await self._uow.commit()
    return TokenPair(access_token=access, refresh_token=refresh)
```

Le `role` est mis dans l'access token (info utile côté client), mais **on ne s'y fie pas**
pour l'autorisation (voir §9).

---

## 8. `taskman/api/deps.py`

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    auth: AuthServiceDep,
) -> UserRead:
    user = await auth.user_from_access_token(token)
    return UserRead.model_validate(user)

CurrentUser = Annotated[UserRead, Depends(get_current_user)]
```

- `OAuth2PasswordBearer` : dépendance qui **extrait** le token de `Authorization: Bearer …`.
  Absent → `401` automatique. `tokenUrl` ne sert qu'à la doc (bouton « Authorize »).
- `get_current_user` : décode + charge en base + `is_active`. Renvoie un `UserRead` (schéma,
  pas ORM).
- **`CurrentUser`** : l'alias qu'on colle sur n'importe quelle route pour exiger l'auth.

```python
def require_role(*allowed: UserRole):
    async def _dependency(user: CurrentUser) -> UserRead:
        if user.role not in allowed:
            raise PermissionDeniedError(f"Rôle requis : {allowed}")
        return user
    return _dependency
```

Une **fabrique** : `require_role(UserRole.admin)` renvoie une dépendance. Utilisable sur une
route ou sur `APIRouter(dependencies=[Depends(require_role(...))])`.

```python
def get_task_service(tasks=Depends(get_task_repository), session: SessionDep, user: CurrentUser):
    return TaskService(tasks, uow=session, actor=user)
```

`get_task_service` dépend maintenant de `get_current_user` → **toutes** les routes qui
utilisent `TaskServiceDep` exigent un token, **sans changer les routes**.

---

## 9. `taskman/services/tasks.py` — isolation

```python
class TaskService:
    def __init__(self, tasks, uow, actor: UserRead): ...

    @property
    def _scope(self) -> int | None:
        return None if self._actor.role is UserRole.admin else self._actor.id

    async def _assert_can_access(self, task_id: int) -> None:
        owner_id = await self._tasks.get_owner_id(task_id)
        if owner_id is None or (self._scope is not None and owner_id != self._scope):
            raise TaskNotFoundError(task_id)      # 404, PAS 403
```

- `_scope` : `None` pour un admin (voit tout), l'id de l'acteur sinon.
- `_assert_can_access` : appelée par `get` / `update` / `delete` **avant** toute action.
  Ressource inexistante **ou** appartenant à un autre → `TaskNotFoundError`.
- **404 et non 403** : on ne dit pas « ça existe mais tu n'y as pas droit » (ça révèle
  l'existence). L'OWASP recommande ce choix contre l'énumération.

```python
async def list(self, filters: TaskFilters) -> TaskPage:
    items, total = await self._tasks.list(filters, owner_id=self._scope)
    ...
```

La liste est scoppée **par le repository** (SQL), pas ici.

```python
async def create(self, data: TaskCreate) -> TaskRead:
    task = await self._tasks.create(data, owner_id=self._actor.id)
    ...
```

Une tâche créée appartient toujours à son créateur — le client **ne peut pas** fixer
`owner_id` (il n'est pas dans `TaskCreate`).

---

## 10. `taskman/api/routes/admin.py` — RBAC sur un router

```python
router = APIRouter(
    prefix="/admin", tags=["admin"],
    dependencies=[Depends(require_role(UserRole.admin))],
)
```

`dependencies=[...]` sur l'`APIRouter` : la dépendance s'applique à **toutes** ses routes.
Un `member` reçoit `403` sur n'importe quel endpoint `/admin/*`. On ne l'oublie sur aucune
route car ce n'est **pas** par route.

---

## 11. `taskman/api/errors.py` (ajout `WWW-Authenticate`)

```python
headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
return JSONResponse(..., headers=headers)
```

Convention HTTP : une `401` sur une ressource protégée par un *bearer token* doit renvoyer
l'entête `WWW-Authenticate: Bearer` (indique au client **comment** s'authentifier).

---

## 12. Les tests

```python
@pytest.fixture(autouse=True)
def _fast_password_hashing(monkeypatch):
    from taskman.core import security
    monkeypatch.setattr(security, "hash_password", lambda p: f"fakehash::{p}")
    monkeypatch.setattr(security, "verify_password", lambda p, h: h == f"fakehash::{p}")
```

argon2 « vrai » = ~150 ms/hash. Avec ~30 comptes créés dans la suite, ça ferait plusieurs
secondes de perdues. On échange le hachage pour une fonction triviale — **le comportement
testé** (égalité, rejet du mauvais mot de passe) est identique. `test_auth.py` importe les
fonctions **directement** (`from ...security import hash_password`) → il garde le vrai argon2
pour tester la crypto elle-même.

```python
async def test_member_cannot_touch_another_members_task(app):
    alice = await _as(app, "alice@x.co")
    bob = await _as(app, "bob@x.co")
    tid = (await alice.post("/tasks", json={...})).json()["id"]
    assert (await bob.get(f"/tasks/{tid}")).status_code == 404   # <- LE test qui compte
    assert (await bob.get("/tasks")).json()["total"] == 0
```

Ce test **doit** échouer si tu renvoies 403 (fuite d'existence) ou 200 (fuite de données).
C'est le garde-fou anti-régression le plus important du module.

---

## Ce qui vient au Module 07

Le Module 06 a introduit beaucoup de code testable. Le Module 07 formalise la **stratégie de
test** : pyramide, `factories`, `testcontainers` (vrai PostgreSQL), TDD strict, couverture
des branches d'erreur — sur la base de tout ce qu'on a accumulé.
