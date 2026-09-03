# Déploiement de `taskman`

> Procédure de mise en production et de *rollback*. Le principe : **artefact immuable**
> (l'image `taskman:X.Y.Z` ne change jamais), déploiement **rolling**, migrations **avant**
> le trafic.

## 1. Prérequis (une fois)

- un registre d'images (GHCR, ECR, …) ;
- PostgreSQL managé + Redis managé (TLS activé) ;
- un reverse proxy (Nginx / Traefik / ALB) qui termine le TLS et route `/metrics` et
  `/ready` **uniquement** en interne ;
- les secrets dans un gestionnaire (Vault / Secrets Manager / variables chiffrées CI) :
  `APP_JWT_SECRET_KEY` (aléatoire, ≥ 32 o), `APP_DATABASE_URL`, `APP_REDIS_URL`.

## 2. Variables d'environnement de prod

```bash
APP_ENV=production                 # -> /docs fermée, HSTS actif
APP_JWT_SECRET_KEY=<openssl rand -hex 32>
APP_DATABASE_URL=postgresql+asyncpg://user:pass@pg-host:5432/taskman
APP_REDIS_URL=redis://redis-host:6379/0
APP_CORS_ORIGINS=["https://app.exemple.org"]
APP_LOG_JSON=true
APP_OTEL_ENABLED=true
APP_OTEL_ENDPOINT=http://otel-collector:4318
APP_ROOT_PATH=/api                 # si servi sous un sous-chemin
```

## 3. Release (pipeline)

```
1. Tag :   git tag v1.4.0 && git push --tags
2. CI   :  lint + mypy + tests + pip-audit + e2e   (bloquants)
3. Build : image ghcr.io/…/taskman:1.4.0  +  :sha-<court>
4. Migrations (étape dédiée, une seule fois) :
      docker run --rm --env APP_DATABASE_URL=$PROD_DB \
        ghcr.io/…/taskman:1.4.0 alembic upgrade head
   -> vérifier le résultat AVANT l'étape 5.
5. Déploiement rolling : l'orchestrateur remplace les répliques une par une.
   Chaque nouvelle réplique doit passer /ready avant de recevoir du trafic.
```

> **Migrations** : jouées à l'étape 4, **jamais** au démarrage des N conteneurs
> (`RUN_MIGRATIONS` reste à `false` en prod). La migration doit être **compatible** avec
> l'ancienne version du code (voir `11-.../THEORIE.md` §5).

## 4. Dimensionnement

- workers : `fastapi run … --workers N` avec `N ≈ 2 × CPU` (ajuster à la charge) ;
- pool DB : `workers × pool_size ≤ max_connections` de PostgreSQL ;
- répliques : régler l'autoscaling sur la latence p95 et le CPU.

## 5. Rollback

```bash
# Redéployer l'image précédente — INSTANTANÉ, sûr :
kubectl set image deploy/taskman taskman=ghcr.io/…/taskman:1.3.9
# ou : docker compose up -d  (avec l'ancien tag dans le compose)
```

- **ne pas** faire `alembic downgrade` si la migration a supprimé des données — le rollback,
  c'est l'image précédente + le schéma qui reste compatible.
- si une migration cassante a été jouée : restaurer une sauvegarde DB (testée au préalable).

## 6. Après le déploiement — vérifier

- [ ] `/health` = 200, `/ready` = 200 sur toutes les répliques ;
- [ ] taux de 5xx stable (dashboard RED) ;
- [ ] latence p95 stable ;
- [ ] pas d'erreur de migration dans les logs ;
- [ ] `X-Request-ID` présent, logs JSON corrélés ;
- [ ] `/docs` et `/metrics` **injoignables** depuis Internet.

## 7. Local : la stack complète

```bash
docker compose up --build
# API : http://localhost:8000/docs   (RUN_MIGRATIONS=true fait le upgrade)
```
