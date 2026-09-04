# Maîtriser FastAPI — de la première route au déploiement

> Une formation **complète et exigeante** pour passer de « je bricole des scripts Python »
> à « je conçois, teste et exploite des API de production ».

<p style="font-size:1.05rem">
Tu construis <strong><code>taskman</code></strong>, une vraie API de gestion de tâches,
<strong>brique par brique</strong>, sur 13 modules — puis tu sais le refaire seul sur
n'importe quel domaine.
</p>

---

## Ce que tu obtiens

- **13 modules** : théorie courte, exercices avec critères d'acceptation, **solution de
  référence complète et testée**, et une **explication ligne par ligne** de chaque solution.
- `taskman` : d'une route en mémoire jusqu'à Docker multi-stage + CI/CD + observabilité +
  architecture événementielle.
- **4 mini-projets « checkpoint »** sur des domaines neufs (marque-pages, raccourcisseur
  d'URL, sondages en TDD, supervision de services) — énoncé **et** solution.
- **`shopfast`**, un projet e-commerce de référence : total de commande figé, stock sans
  survente, webhook de paiement idempotent, isolation des commandes.
- Le réflexe qualité, partout : `ruff` + `mypy --strict` + `pytest` au vert.
- Couverture **de toute la documentation officielle FastAPI** (Tutorial + Advanced +
  How-To + Reference + Deployment).

---

## Le fil rouge : `taskman`, module après module

| # | Module | `taskman` gagne… |
|---|---|---|
| 00 | Setup & outillage | venv, ruff, mypy, pytest, la bonne hygiène |
| 01 | Fondations HTTP & FastAPI | routes, `response_model`, codes, `/docs` |
| 02 | Modélisation & validation | schémas `Create/Update/Read`, validateurs, `PATCH` correct |
| 03 | Architecture d'un projet mature | couches api → service → repository, DI, `create_app()` |
| 04 | Bases de données | SQLAlchemy 2.0 async, Alembic, repository pattern |
| 05 | Erreurs, logs & middleware | `DomainError`, RFC 9457, logs JSON, `request-id` |
| 06 | Authentification & autorisation | OAuth2 + JWT, argon2id, RBAC, isolation par propriétaire |
| 07 | Tests | pyramide, factories, `dependency_overrides`, testcontainers, TDD |
| 08 | Async avancé & performance | cache + invalidation, pagination *cursor*, streaming, workers |
| 09 | Observabilité & prod-readiness | métriques Prometheus (RED), traces OTel, `/health` vs `/ready` |
| 10 | Sécurité approfondie | OWASP API Top 10, rate limiting, en-têtes, CORS, `pip-audit` |
| 11 | Déploiement & DevOps | Docker multi-stage non-root, compose, CI/CD, migrations en prod |
| 12 | Architecture & scalabilité | *outbox pattern*, `Idempotency-Key`, versionnage d'API, SSE |

---

## Essaie gratuitement

Les **Modules 00 et 01 sont ouverts ici**, en entier — théorie, exercices, solution
commentée, explication ligne par ligne. C'est représentatif du niveau de détail de tout
le reste.

- [Module 00 — Setup & outillage professionnel](../00-setup/README.md)
- [Module 01 — Fondations HTTP & FastAPI](../01-fondations-http-et-fastapi/THEORIE.md)
- [Le mode d'emploi de la formation](../GUIDE.md)

---

## À qui ça s'adresse

Tu connais **Python** et tu sais te servir d'un terminal et de `git`. Tu **n'as pas besoin**
de connaître Flask, Django, un ORM ou Docker : on construit ces briques au fil des modules.

## Obtenir la formation complète

Voir la page [**Obtenir la formation**](acheter.md).

---

<p style="color:var(--md-default-fg-color--light)">
Formation conçue et rédigée par <strong>Patrick De Grâce</strong>.
Portfolio : <a href="https://portfolio-personnel-ecru.vercel.app/">portfolio-personnel-ecru.vercel.app</a>.
</p>
