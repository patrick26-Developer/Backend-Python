# Module 10 — Sécurité approfondie

> **Objectif** : **auditer sa propre API avec une méthode** (OWASP API Security Top 10) et
> corriger les trous. Rate limiting, en-têtes, CORS, limites, secrets, chaîne
> d'approvisionnement.
> La sécurité n'est pas une fonctionnalité — c'est une **propriété transverse** qu'on
> vérifie avec une checklist, pas au feeling.
>
> **Durée estimée** : 10 à 14 h. **Pré-requis** : Modules 05, 06, 09.

---

## 1. La méthode : OWASP API Security Top 10 (2023)

Une **liste de contrôle** des 10 risques les plus fréquents des API. On passe chaque point
sur `taskman` : *quel est le risque → que fait-on → où est-ce dans le code → quel test le
prouve*. Le résultat vit dans [`SECURITY.md`](../SECURITY.md).

| # | Risque | La réponse de `taskman` |
|---|---|---|
| **API1** | BOLA / IDOR (accès à la ressource d'un autre) | `owner_id` filtré **en SQL** ; 404 pour l'autrui (Module 06) |
| **API2** | Authentification cassée | argon2, JWT validés, rotation refresh, **rate limit**, anti-énumération (Module 06 + ici) |
| **API3** | Autorisation au niveau **propriété** | schémas entrée/sortie séparés, `extra="forbid"` (Module 02) |
| **API4** | Consommation illimitée | **limite de payload**, `limit ≤ 100`, cache, **rate limit** |
| **API5** | Autorisation au niveau **fonction** | `require_role` sur le router `/admin` (Module 06) |
| **API6** | Flux métier non protégés | rate limit sur inscription/connexion |
| **API7** | SSRF | aucune requête sortante pilotée par l'entrée ; validation d'URL pour les webhooks |
| **API8** | **Mauvaise configuration** | en-têtes de sécurité, CORS strict, `/docs` fermée en prod, 500 génériques |
| **API9** | Inventaire d'API | OpenAPI dérivé du code, `/metrics` hors schéma, versionnage (Module 12) |
| **API10** | Consommation d'API tierces non sûre | validation Pydantic de **toute** entrée externe |

**API1 et API5 sont les plus exploités.** On les a traités au Module 06 ; ici on ferme
API2/4/8 et la chaîne d'appro.

---

## 2. Rate limiting (*throttling*)

**But** : limiter le nombre de requêtes par client sur une fenêtre — contre le *brute force*
(connexion), le *scraping*, l'abus.

### Algorithmes

| Algo | Principe | Défaut |
|---|---|---|
| **Fenêtre fixe** | compteur remis à zéro toutes les N s | pic à la frontière de fenêtre (2× la limite) |
| **Fenêtre glissante** | pondère la fenêtre précédente | plus juste, un peu plus cher |
| **Token bucket** | jetons régénérés à débit constant, requête = 1 jeton | autorise des rafales contrôlées |

`taskman` utilise la **fenêtre fixe** (simple, suffisant pour de l'anti-brute-force).

### Par quoi limiter ? (la **clé**)

- par **IP** : simple, mais un NAT partage une IP (bureau, mobile) et une IP est *spoofable*
  derrière un proxy mal configuré ;
- par **utilisateur** (une fois authentifié) : plus juste pour les quotas ;
- par **clé d'API** : pour un usage machine.

Pour `/auth/login` (pré-authentification) → par **IP** (`X-Forwarded-For` posé par le proxy).

### Où stocker le compteur

- **en mémoire** : par instance → en multi-instance, la limite réelle = N × instances ;
- **Redis** (`INCR` + `EXPIRE`) : compteur **partagé**, la vraie limite.

`taskman` : `RateLimiter` (`Protocol`) → `InMemoryRateLimiter` / `RedisRateLimiter`, choisi
par `APP_REDIS_URL`.

### La réponse

**`429 Too Many Requests`** + en-tête `Retry-After: <secondes>`. Format Problem Details
comme les autres erreurs (Module 05).

```python
router = APIRouter(prefix="/auth", dependencies=[Depends(auth_rate_limit)])
```

Sur **le router** → toutes les routes `/auth/*` sont protégées, impossible d'en oublier une.

---

## 3. En-têtes de sécurité HTTP

| En-tête | Valeur | Protège de |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | le navigateur qui « devine » un type MIME (XSS via upload) |
| `X-Frame-Options` | `DENY` | le *clickjacking* (ton API dans une `<iframe>`) |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` | l'injection de scripts/ressources |
| `Referrer-Policy` | `no-referrer` | la fuite d'URL (avec tokens) via l'en-tête `Referer` |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains` | le *downgrade* HTTPS→HTTP (**prod uniquement**) |
| `Cross-Origin-Opener-Policy` | `same-origin` | certaines attaques *cross-origin* |
| `Permissions-Policy` | `geolocation=(), camera=()…` | l'accès aux API navigateur |

**Piège** : une CSP stricte casse **Swagger UI** (`/docs` charge du JS depuis un CDN) → on
**n'applique pas** la CSP sur `/docs`, `/redoc`, `/openapi.json`.

**HSTS** : seulement en prod (HTTPS). En dev (HTTP), il forcerait le navigateur à refuser
`http://localhost` pendant 2 ans — pénible.

---

## 4. CORS — vraiment le comprendre

**CORS** = le navigateur autorise (ou non) un site `A` à lire la réponse d'une requête vers
l'API `B`. C'est une protection **du navigateur**, pas de l'API (un `curl` ignore CORS).

### Le flux

```
1. Requête "simple" (GET) : le navigateur l'envoie, puis vérifie
   Access-Control-Allow-Origin dans la réponse. Absent/différent -> il CACHE la réponse au JS.
2. Requête "non simple" (PUT, en-tête custom…) : le navigateur envoie d'abord un
   PRÉ-VOL OPTIONS. Si la réponse n'autorise pas -> il n'envoie même pas la vraie requête.
```

### Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,   # LISTE EXPLICITE, ["https://app.exemple.org"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Règle d'or** : `allow_origins=["*"]` **et** `allow_credentials=True` est **interdit** (et
ignoré par les navigateurs) — ça reviendrait à laisser n'importe quel site lire les réponses
authentifiées de tes utilisateurs. Toujours des origines **explicites**.

Par défaut, `taskman` : `cors_origins = []` → **aucune** origine autorisée (le front doit
être déclaré).

---

## 5. Limites de ressources

- **taille du payload** : `BodySizeLimitMiddleware` rejette (413) si `Content-Length` > 1 Mio.
  (Un corps *chunked* sans `Content-Length` passe — Uvicorn a sa propre limite, et Pydantic
  borne le contenu.)
- **profondeur / taille des collections** : `max_length` sur les listes Pydantic (Module 02).
- **pagination** : `limit ≤ 100` partout.
- **complexité des requêtes** : agrégats coûteux **mis en cache** (Module 08).
- **timeouts** : côté client HTTP sortant, côté DB (`statement_timeout`).

---

## 6. Secrets

- **jamais** dans le code ni git. `.env` est `.gitignore`. `pre-commit` a
  `detect-private-key`.
- `SecretStr` (Pydantic) : masqué dans les logs et `repr`.
- en prod : **gestionnaire de secrets** (Vault, AWS/GCP Secrets Manager, variables chiffrées
  de la CI), monté en variable d'environnement au démarrage.
- **rotation** : le secret JWT peut changer — les access tokens en cours expirent en 15 min.
- `taskman` **refuse de démarrer** en prod avec le secret de dev (Module 06).

---

## 7. Chaîne d'approvisionnement

Ton code est peut-être sûr ; tes **dépendances** ?

- **versions épinglées** (`pyproject.toml` + *lock*) → build reproductible.
- **`pip-audit`** dans la CI : scanne les dépendances installées contre la base des CVE
  (OSV / PyPI Advisory). Le *merge* est **bloqué** si une faille connue est trouvée.
- **Dependabot / Renovate** : PR automatiques de mise à jour.
- limiter les dépendances : chaque `pip install` est une surface d'attaque (*typosquatting*,
  compromission de mainteneur).

```yaml
# .github/workflows/ci.yml
- name: Audit des dépendances
  run: pip-audit --strict
```

---

## 8. Journalisation & audit de sécurité

- **journal d'accès** (Module 05) : IP, méthode, chemin, statut, `request_id`.
- **journal d'audit métier** : « qui a fait quoi » — création/suppression, changement de
  rôle, connexion réussie/échouée. Immuable, conservé longtemps.
- **jamais** de secret loggé.
- les `401` / `403` / `429` sont visibles dans les métriques (`http_requests_total{status}`)
  → un pic d'échecs d'auth = alerte.

---

## 9. Pièges fréquents

1. **`allow_origins=["*"]` avec `credentials`** → n'importe quel site lit les réponses authentifiées.
2. **CSP stricte sur `/docs`** → Swagger UI cassé (personne ne teste plus l'API).
3. **HSTS en dev** → le navigateur refuse `http://localhost` pendant des mois.
4. **Rate limit en mémoire en multi-instance** → limite réelle = N × instances.
5. **Limiter par IP sans lire `X-Forwarded-For`** derrière un proxy → tout le monde a la même IP.
6. **`Retry-After` absent** sur les 429 → le client martèle.
7. **500 qui fuite** (stack, SQL, chemins) → cadeau au pentesteur.
8. **Secret committé** puis « retiré » dans un commit suivant → il est dans l'historique git *pour toujours* (le révoquer).
9. **`pip-audit` absent de la CI** → tu tournes avec des CVE connues.
10. **Auditer une fois** puis ne plus jamais → la sécurité se re-vérifie à chaque *release*.

---

## 10. Ce que `taskman` gagne

- `api/ratelimit.py` : `RateLimiter` (Protocol) + `InMemory`/`Redis` ; `auth_rate_limit`
  sur le router `/auth` ; `TooManyRequestsError` (429 + `Retry-After`) ;
- `api/middleware.py` : `SecurityHeadersMiddleware` (CSP sauf `/docs`, HSTS en prod),
  `BodySizeLimitMiddleware` (413) ;
- `CORSMiddleware` configuré depuis `settings.cors_origins` (jamais `*` + credentials) ;
- `SECURITY.md` : audit OWASP API Top 10 complet + checklist de mise en prod ;
- `.github/workflows/ci.yml` : étape `pip-audit` ;
- tests : en-têtes présents, CSP absente sur `/docs`, CORS respecté/rejeté, 429 après N
  tentatives, rate limit par IP, 413 sur payload géant.

---

## 11. À savoir refaire sans aide

- Dérouler l'OWASP API Top 10 sur une API et documenter chaque point.
- Implémenter un rate limiter (fenêtre fixe), choisir la clé, renvoyer 429 + `Retry-After`.
- Poser les bons en-têtes de sécurité, sans casser la doc.
- Configurer CORS correctement (origines explicites, jamais `*` + credentials).
- Borner la consommation de ressources (payload, pagination, requêtes).
- Mettre `pip-audit` en CI et gérer une CVE de dépendance.

➡️ [Exercices](exercices/README.md) · [PAS-A-PAS.md](PAS-A-PAS.md)
