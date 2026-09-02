# Module 06 — Authentification & autorisation

> **Objectif** : protéger `taskman` avec un **modèle d'accès explicite et testé**. Comptes,
> connexion (OAuth2 + JWT access/refresh), rôles (RBAC), **isolation des données par
> utilisateur**. Ici, « ça marche » ne suffit pas — l'auth mal faite = fuite de données.
>
> **Durée estimée** : 12 à 16 h.
> **Pré-requis** : Modules 03–05 (couches, DB, exceptions).

---

## 1. Authentification ≠ Autorisation

| | Question | Erreur si échec |
|---|---|---|
| **Authentification** (authn) | *Qui es-tu ?* | `401 Unauthorized` |
| **Autorisation** (authz) | *As-tu le droit de faire ça ?* | `403 Forbidden` (ou `404`, voir §7) |

`401` = « je ne sais pas qui tu es » (pas de token, token invalide). `403` = « je sais qui
tu es, et non ».

---

## 2. Hachage des mots de passe

**Jamais** stocker un mot de passe en clair. **Jamais** un hash rapide (MD5, SHA-256 nu) —
un GPU en teste des milliards par seconde.

### Les bons algorithmes

`argon2id` (recommandé, gagnant du *Password Hashing Competition*) ou `bcrypt`. Lents **par
conception** (paramétrable), avec **sel** intégré (deux fois le même mot de passe → deux
hashs différents).

```python
from pwdlib import PasswordHash
_hasher = PasswordHash.recommended()   # argon2id, paramètres sûrs

def hash_password(plain: str) -> str:      return _hasher.hash(plain)
def verify_password(plain, hashed) -> bool: return _hasher.verify(plain, hashed)
```

`verify` fait une comparaison en **temps constant** (pas de fuite par le temps de réponse).

### Protection contre l'énumération de comptes

À la connexion, si l'e-mail n'existe pas, **vérifie quand même** un hash bidon :

```python
user = await repo.get_by_email(email)
stored = user.hashed_password if user else _DUMMY_HASH
if not verify_password(password, stored) or user is None:
    raise InvalidCredentialsError()      # MÊME erreur, MÊME temps de réponse
```

Sinon : « e-mail inconnu » répond en 1 ms, « mauvais mot de passe » en 50 ms → un attaquant
distingue les comptes existants.

---

## 3. JWT — JSON Web Token

Un JWT = `header.payload.signature`, encodé en base64url. Le **payload** contient des
*claims* :

```json
{ "sub": "42", "type": "access", "jti": "9f3c…", "iat": 1750000000, "exp": 1750000900, "role": "member" }
```

- `sub` : le sujet (l'id utilisateur).
- `exp` : expiration (timestamp). Passé → token invalide.
- `jti` : identifiant unique du token (sert à révoquer un refresh token).
- **la signature** garantit que le payload n'a pas été modifié. Elle **ne chiffre pas** :
  n'importe qui peut lire le payload. **Ne mets jamais de secret dedans.**

### Access token court + Refresh token long

| | durée | usage | stockage serveur |
|---|---|---|---|
| **access** | 15 min | envoyé à **chaque** requête (`Authorization: Bearer …`) | aucun (stateless) |
| **refresh** | 7 j | échangé contre un nouveau couple quand l'access expire | table `refresh_tokens` (pour révoquer) |

Access court = si un access token fuite, la fenêtre d'exploitation est petite. Refresh long
= l'utilisateur ne se reconnecte pas toutes les 15 minutes.

### Rotation du refresh token

À **chaque** `/auth/refresh` :
1. on vérifie le refresh token (signature, `exp`, `type == "refresh"`, `jti` non révoqué en base) ;
2. on **révoque** l'ancien `jti` ;
3. on émet un **nouveau** couple (access + refresh).

Si un refresh token volé est utilisé, sa 2ᵉ utilisation échoue (déjà révoqué) → signal de
compromission (détection de rejeu — approfondie plus tard).

### Le secret

`HS256` (HMAC) : **un** secret partagé signe et vérifie. Il doit être :
- **aléatoire** (`openssl rand -hex 32`), **≥ 32 octets** ;
- **différent par environnement** (dev ≠ staging ≠ prod) ;
- **jamais** committé. En prod, `APP_JWT_SECRET_KEY` est **obligatoire** — la config refuse
  de démarrer avec le secret de dev.

---

## 4. OAuth2 Password Flow dans FastAPI

```python
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")  # tokenUrl : juste pour /docs

@router.post("/auth/login")
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], auth: AuthServiceDep):
    return await auth.login(email=form.username, password=form.password)
```

- `OAuth2PasswordRequestForm` : lit un `form-data` avec `username` + `password` (standard
  OAuth2). Ici `username` = l'e-mail. C'est ce que le bouton **« Authorize »** de Swagger
  utilise.
- `OAuth2PasswordBearer` : une dépendance qui **extrait** le token de l'entête
  `Authorization: Bearer …`. Si absent → `401` automatique.
- la réponse : `{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }`.

---

## 5. `get_current_user` : la dépendance clé

```python
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    auth: AuthServiceDep,
) -> UserRead:
    user = await auth.user_from_access_token(token)   # décode + charge en base
    return UserRead.model_validate(user)

CurrentUser = Annotated[UserRead, Depends(get_current_user)]
```

`user_from_access_token` :
1. décode le JWT (lève `InvalidTokenError` si signature/`exp` invalides) ;
2. vérifie `type == "access"` (un refresh token ne doit pas servir d'access) ;
3. charge l'utilisateur par `sub` ;
4. vérifie `is_active`.

Ensuite, **n'importe quelle route** ajoute `user: CurrentUser` pour exiger l'authentification :

```python
@router.get("/auth/me")
async def me(user: CurrentUser) -> UserRead:
    return user
```

Toutes les routes `tasks` / `projects` deviennent protégées **sans les modifier** : c'est
`get_task_service` qui dépend maintenant de `get_current_user`.

---

## 6. RBAC — contrôle d'accès basé sur les rôles

```python
class UserRole(StrEnum):
    admin = "admin"
    member = "member"

def require_role(*allowed: UserRole):
    async def _dep(user: CurrentUser) -> UserRead:
        if user.role not in allowed:
            raise PermissionDeniedError(f"Rôle requis : {allowed}")
        return user
    return _dep
```

Une **fabrique de dépendances**. Usage sur une route ou un router entier :

```python
router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(require_role(UserRole.admin))],   # TOUTES les routes du router
)
```

Le rôle est aussi dans le token (`"role": "member"`), mais on **recharge** l'utilisateur en
base (`get_current_user`) : si un admin est rétrogradé, son token existant ne doit pas garder
les droits admin jusqu'à expiration.

---

## 7. Autorisation au niveau **ressource** (BOLA / IDOR)

C'est **la** vulnérabilité n°1 des API (OWASP API Security Top 10 #1) : un utilisateur
authentifié accède à la ressource **d'un autre** en devinant l'`id`.

### La règle

Chaque tâche a un `owner_id`. Le service est **conscient de l'acteur** :

```python
class TaskService:
    def __init__(self, tasks, uow, actor: UserRead): ...

    @property
    def _scope(self) -> int | None:
        return None if self._actor.role is UserRole.admin else self._actor.id

    async def _assert_can_access(self, task_id: int) -> None:
        owner_id = await self._tasks.get_owner_id(task_id)
        if owner_id is None or (self._scope is not None and owner_id != self._scope):
            raise TaskNotFoundError(task_id)      # <- 404, PAS 403
```

- **liste** : filtrée par `owner_id` **dans la requête SQL** (`WHERE owner_id = :me`), pas
  par un `if` après coup → un oubli est structurellement impossible.
- **accès par id** : on vérifie la propriété **avant** de renvoyer quoi que ce soit.
- **admin** : `_scope == None` → voit tout.

### `404` ou `403` pour la ressource d'autrui ?

- `403` : « cette tâche existe, mais tu n'y as pas droit » → révèle l'**existence**.
- `404` : « cette tâche n'existe pas (pour toi) » → ne révèle rien.

L'OWASP recommande **`404`** contre l'énumération. `taskman` fait ce choix (documenté). Le
`403` reste pour « tu n'es pas admin » (le rôle, pas la ressource).

### L'isolation vit dans la **persistance**, pas dans un `if`

Le filtre `owner_id` est passé au repository et appliqué en SQL. Dans un vrai SaaS on va
plus loin : un *query filter* SQLAlchemy global, ou un schéma par tenant (Module 12,
projet `saashub`).

---

## 8. Où placer quoi

| Élément | Fichier |
|---|---|
| hachage + JWT (crypto pure) | `core/security.py` |
| réglages JWT + validation « pas de secret de dev en prod » | `core/config.py` |
| exceptions `InvalidCredentialsError`, `InvalidTokenError`, `EmailAlreadyRegisteredError` | `core/exceptions.py` |
| `AuthService` (register / login / refresh / résolution user) | `services/auth.py` |
| `oauth2_scheme`, `get_current_user`, `require_role` | `api/deps.py` |
| routes `/auth/*` | `api/routes/auth.py` |
| routes `/admin/*` (RBAC démo) | `api/routes/admin.py` |
| `owner_id` sur tasks/projects, table `users` + `refresh_tokens` | `db/models.py` |

---

## 9. Pièges fréquents

1. **Hash rapide** (SHA/MD5) ou **pas de sel** → base compromise = mots de passe cassés.
2. **Secret JWT en dur / committé / partagé entre envs.**
3. **Mettre un secret dans le payload JWT** (il est juste signé, pas chiffré).
4. **Access token sans expiration** (ou trop longue).
5. **Pas de rotation** du refresh token → un vol = accès illimité.
6. **Faire confiance au `role` du token** sans recharger l'utilisateur.
7. **Filtrer par `owner_id` avec un `if` après la requête** au lieu du `WHERE` → un oubli = fuite.
8. **`403` au lieu de `404`** pour la ressource d'autrui → énumération.
9. **Token dans l'URL** (`?token=…`) → journalisé partout, dans l'historique du navigateur.
10. **CORS permissif** (`*`) **avec** `credentials` → n'importe quel site lit les réponses
    authentifiées (Module 10).
11. **Énumération de comptes** : « e-mail inconnu » ≠ « mauvais mot de passe ».
12. **Oublier `is_active`** : un compte désactivé garde l'accès jusqu'à expiration du token.

---

## 10. Ce que `taskman` gagne

- `UserRow` + `RefreshTokenRow` + `owner_id` sur projets/tâches (migration Alembic squashée) ;
- `core/security.py` (argon2 + PyJWT), `AuthService` (register/login/refresh **avec rotation**) ;
- `/auth/register`, `/auth/login` (OAuth2 form), `/auth/refresh`, `/auth/me` ;
- `get_current_user`, `require_role`, `CurrentUser` ;
- **toutes** les routes métier protégées ; **isolation par utilisateur** (SQL) ;
- `/admin/users` réservé aux admins ;
- 401 avec `WWW-Authenticate: Bearer` ;
- tests : auth, refresh/rotation, RBAC, **fuite inter-utilisateur = échec bloquant**.

---

## 11. À savoir refaire sans aide

- Hacher/vérifier un mot de passe correctement, et protéger de l'énumération.
- Émettre et valider un access + refresh JWT, avec rotation.
- Écrire `get_current_user` et brancher l'auth sur toutes les routes via la DI.
- Implémenter le RBAC avec une fabrique de dépendances.
- Isoler les données par utilisateur **dans la requête SQL**, renvoyer 404 pour l'autrui.
- Refuser le secret de dev en production (validation de config).

➡️ [Exercices](exercices/README.md) · [PAS-A-PAS.md](PAS-A-PAS.md)
