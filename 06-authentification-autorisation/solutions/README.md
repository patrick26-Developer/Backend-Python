# Module 06 — Solutions : les choix de conception

> Code dans `taskman/`. Explication ligne par ligne : [`../PAS-A-PAS.md`](../PAS-A-PAS.md).

```bash
cd 06-authentification-autorisation/solutions
alembic upgrade head
pytest
mypy taskman
```

---

## Décision 1 — argon2id, paramètres OWASP, jamais un hash rapide

`PasswordHash([Argon2Hasher(time_cost=2, memory_cost=19_456, parallelism=1)])`. Lent **par
conception** (~150 ms) → un GPU ne casse pas la base volée. Sel intégré. `verify` en temps
constant. **Jamais** SHA/MD5, jamais sans sel.

## Décision 2 — Access court + refresh long + **rotation**

- **access** 15 min, stateless, envoyé à chaque requête ;
- **refresh** 7 j, stocké en base (`refresh_tokens`), échangé quand l'access expire ;
- **rotation** : chaque `/auth/refresh` révoque l'ancien `jti` et en émet un nouveau. Un
  refresh token volé, s'il est utilisé, échoue à la 2ᵉ tentative (le légitime l'a déjà
  consommé) — signal de compromission.

Le `type` (`"access"` / `"refresh"`) dans le payload empêche d'utiliser l'un pour l'autre.

## Décision 3 — On ne fait **pas** confiance au `role` du token

Le `role` est dans l'access token (pratique côté client), mais `get_current_user` **recharge
l'utilisateur en base**. Si un admin est rétrogradé, son token existant ne garde pas les
droits jusqu'à expiration.

## Décision 4 — Anti-énumération de comptes

`login` vérifie un **hash bidon** quand l'e-mail n'existe pas → même temps de réponse
(dominé par argon2), **même** erreur (`invalid_credentials`) que « mauvais mot de passe ».
Sans ça, « e-mail inconnu » répondrait en 1 ms et trahirait les comptes existants.

## Décision 5 — Le secret de dev est **refusé** en production

Un `model_validator` sur `Settings` : `env in ("staging","production")` + secret == défaut →
l'app **ne démarre pas**. Un garde-fou au boot, pas un test qu'on peut oublier de lancer.

## Décision 6 — L'isolation vit dans le **SQL**, pas dans un `if`

`repo.list(filters, owner_id=me)` applique `WHERE owner_id = :me` **avant** pagination et
`COUNT`. Un `[t for t in rows if t.owner_id == me]` après coup serait : (a) faux pour le
`total`, (b) silencieux si on l'oublie. Le filtre SQL, lui, se voit quand il manque.

## Décision 7 — Ressource d'autrui → **404**, pas 403

`_assert_can_access` lève `TaskNotFoundError` (404) si la tâche n'existe pas **ou**
appartient à quelqu'un d'autre. On ne révèle **pas** l'existence d'une ressource protégée
(OWASP, anti-énumération). Le `403` reste pour « tu n'es pas admin » (le rôle, pas la
ressource).

## Décision 8 — `require_role` sur le **router**, pas sur chaque route

`APIRouter(dependencies=[Depends(require_role(UserRole.admin))])` : impossible d'ajouter une
route `/admin/*` non protégée par distraction — la protection n'est pas par route.

## Décision 9 — `security` importé **comme module** dans `AuthService`

`from taskman.core import security` puis `security.hash_password(...)` → les tests peuvent
`monkeypatch.setattr(security, "hash_password", fake)` pour aller vite. `_dummy_hash()` est
`lru_cache`-é et calculé à la 1ʳᵉ demande, pas à l'import (sinon le vrai argon2 tournerait
malgré le patch).

## Décision 10 — Le hash **jamais** en sortie

`UserRead` n'a **aucun** champ mot de passe. `AuthService.register` renvoie
`UserRead.model_validate(row)` → seuls `id`, `email`, `role`, `is_active`, `created_at`
sortent.

---

## Grille d'auto-évaluation

- [ ] Ton hachage est-il lent (argon2/bcrypt) et salé, ou rapide (❌) ?
- [ ] Le `hashed_password` peut-il fuiter dans une réponse quelque part ?
- [ ] Rejoues-tu le même refresh token avec succès (❌) ou est-il révoqué après usage (✅) ?
- [ ] Un `member` qui devine l'id d'une tâche d'autrui : 404 (✅), 403 (⚠️) ou 200 (❌) ?
- [ ] Le filtre `owner_id` est-il un `WHERE` SQL ou un `if` après la requête ?
- [ ] « e-mail inconnu » et « mauvais mot de passe » renvoient-ils la même chose ?
- [ ] Ton app démarre-t-elle en prod avec le secret de dev (❌) ?

➡️ [Module 07 — Tests](../../07-tests/THEORIE.md)
