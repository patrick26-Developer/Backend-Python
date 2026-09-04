<div class="fp-hero" markdown>

# Maîtriser FastAPI <span class="fp-pill free">Accès libre</span>

Une formation **complète et exigeante** : concevoir, tester et exploiter des API FastAPI
de niveau production. 13 modules, un projet fil rouge qui grandit à chaque étape, et le
réflexe qualité partout — `ruff` · `mypy --strict` · `pytest`.

<div class="fp-badges">
<span>13 modules</span>
<span>4 mini-projets</span>
<span>1 projet e-commerce</span>
<span>couverture &gt; 85 %</span>
<span>FR / EN</span>
</div>

<div class="fp-cta">
<a class="fp-primary" href="00-setup/README/">Commencer — Module 00</a>
<a class="fp-ghost" href="https://github.com/patrick26-Developer/Backend-Python">Voir le code sur GitHub</a>
</div>

</div>

## Ce que tu obtiens

<div class="grid cards" markdown>

-   :material-book-open-page-variant:{ .lg .middle } **13 modules complets**

    ---

    Théorie courte, exercices avec critères d'acceptation, **solution de référence
    testée**, et une **explication ligne par ligne** de chaque solution.

-   :material-server:{ .lg .middle } **Un fil rouge, `taskman`**

    ---

    D'une route en mémoire jusqu'à Docker multi-stage, CI/CD, observabilité et
    architecture événementielle — module après module.

-   :material-puzzle-outline:{ .lg .middle } **4 mini-projets checkpoint**

    ---

    Marque-pages, raccourcisseur d'URL, sondages en TDD, supervision de services —
    énoncé **et** solution, sur des domaines neufs.

-   :material-cart-outline:{ .lg .middle } **`shopfast`, projet de référence**

    ---

    Un e-commerce qui traite les vrais problèmes : total figé, stock sans survente,
    webhook de paiement idempotent, isolation des commandes.

-   :material-check-decagram-outline:{ .lg .middle } **Le réflexe qualité**

    ---

    `ruff` + `mypy --strict` + `pytest` au vert, partout, sans exception.

-   :material-file-document-outline:{ .lg .middle } **Toute la doc FastAPI**

    ---

    Couverture systématique du Tutorial, de l'Advanced User Guide, du How-To, de la
    Reference et du Deployment officiels.

</div>

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

## À qui ça s'adresse

Tu connais **Python** et tu sais te servir d'un terminal et de `git`. Tu **n'as pas besoin**
de connaître Flask, Django, un ORM ou Docker : on construit ces briques au fil des modules.

## Aller plus loin

- [Le mode d'emploi de la formation](GUIDE.md) — comment suivre le cursus.
- [Les projets](projets/README.md) — 4 mini-projets checkpoint + 3 projets de domaine
  complets (e-commerce, blog/CMS, SaaS multi-tenant), chacun avec énoncé et solution.
- [Le dépôt complet sur GitHub](https://github.com/patrick26-Developer/Backend-Python) —
  code, exercices, solutions, historique.
- [Contribuer / suivre le projet](soutenir.md) — sans rien payer.

---

<p style="color:var(--md-default-fg-color--light)">
Formation conçue et rédigée par <strong>Patrick De Grâce</strong>.
Portfolio : <a href="https://portfolio-personnel-ecru.vercel.app/">portfolio-personnel-ecru.vercel.app</a>
· <a href="en/">English</a>
</p>
