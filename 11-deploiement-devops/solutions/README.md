# Module 11 — Solutions : les choix de conception

> Snapshot `taskman` v0.11.0 + les fichiers d'infra. Procédure complète :
> [`docs/deploiement.md`](docs/deploiement.md). Ligne par ligne : [`../PAS-A-PAS.md`](../PAS-A-PAS.md).

```bash
docker build -t taskman:local .
docker run --rm taskman:local id           # -> uid=1000(app), pas root
docker images taskman:local                # -> ~180 Mo
docker compose up --build                  # stack complète : http://localhost:8000/docs
```

---

## Décisions

### 1. Multi-stage : `builder` compile, `runtime` est minimal

L'étage `builder` a le cache pip et les outils ; l'image finale ne garde que `/venv` +
le code → plus petite, moins de surface d'attaque. `slim` (pas `alpine` — musl casse des
wheels), utilisateur **non-root**.

### 2. Layer caching : `pyproject.toml` avant le code

`COPY pyproject.toml` puis `RUN pip install .` **avant** `COPY taskman/` → modifier le code
ne réinstalle pas les dépendances (le layer lent est mis en cache).

### 3. `RUN_MIGRATIONS` en dev, étape de pipeline en prod

L'entrypoint joue les migrations si `RUN_MIGRATIONS=true` (pratique pour `docker compose`).
**En prod**, `RUN_MIGRATIONS=false` : les migrations sont une **étape dédiée** du pipeline,
jouée **une** fois, **avant** de router le trafic — sinon N conteneurs migrent en parallèle
(*races*, *deadlocks*).

### 4. `ENTRYPOINT` + `CMD` + `exec "$@"`

L'entrypoint (script) s'exécute toujours ; `CMD` est ses arguments. `exec "$@"` remplace le
process → `SIGTERM` arrive au serveur → arrêt gracieux (Module 09).

### 5. CI : 4 jobs, `quality`+`security` bloquants

`quality` (ruff/mypy/tests/couverture/`alembic check`, matrice 3.12+3.13) et `security`
(`pip-audit` sur les deps de prod) **bloquent le merge**. `e2e` informe. `build` (dépend des
deux premiers) produit l'**artefact immuable** : tags `sha-…` **et** `X.Y.Z`, poussé hors PR.

### 6. Artefact immuable + rollback = image précédente

`taskman:1.4.0` ne change **jamais**. Rollback = `set image … taskman:1.3.9` (instantané,
sûr). On **ne** fait **pas** `alembic downgrade` si la migration a perdu des données — le
schéma reste compatible avec l'image précédente (migrations compatibles, §5 de la THEORIE).

### 7. `root_path` pour le reverse proxy

`FastAPI(root_path=settings.root_path)` → `openapi.json` et « Try it out » utilisent le bon
préfixe quand l'API est servie sous `/api`.

---

## Grille d'auto-évaluation

- [ ] `docker run taskman id` → non-root ?
- [ ] Image < 250 Mo ?
- [ ] Modifier une ligne de code réinstalle-t-il les deps (❌) ou réutilise-t-il le cache (✅) ?
- [ ] Ta procédure de prod joue-t-elle les migrations au démarrage des conteneurs (❌) ?
- [ ] Sais-tu faire un rollback en une commande ?
- [ ] Ta CI bloque-t-elle le merge sur `ruff`/`mypy`/`pytest`/`pip-audit` ?
- [ ] Les tags d'image permettent-ils de savoir *exactement* ce qui tourne ?

➡️ [Module 12 — Architecture & scalabilité](../../12-architecture-scalabilite/THEORIE.md)
