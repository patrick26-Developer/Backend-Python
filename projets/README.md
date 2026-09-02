# Projets

La formation te fait construire **`taskman`** (gestionnaire de tâches) module après module.
En parallèle, deux familles de projets pour ancrer et généraliser :

## 1. Mini-projets « checkpoint »

Courts (une demi-journée à 2 jours), sur un domaine neuf, pour vérifier qu'un bloc de
compétences tient hors du contexte `taskman`. Énoncé + solution de référence commentée.

| Projet | Débloqué après | Valide | Statut |
|---|---|---|---|
| [`linkstash`](checkpoints/linkstash/BRIEF.md) — marque-pages (URL, tags, notes, recherche) | Module 02 | routing, Pydantic, response models, `PATCH` | 🚧 |
| [`shorturl`](checkpoints/shorturl/BRIEF.md) — raccourcisseur d'URL + compteur de clics | Module 04 | DB async, migrations, repository, unicité | 🚧 |
| [`pollup`](checkpoints/pollup/BRIEF.md) — sondages (questions, options, votes) | Module 07 | archi en couches + suite de tests, TDD | 🚧 |
| [`statuspage`](checkpoints/statuspage/BRIEF.md) — supervision de services | Module 09 | observabilité, health/ready, métriques, jobs | 🚧 |

## 2. Projets de domaine complets (les 3 « non sélectionnés »)

Gros projets, construits **par phases qui suivent les 13 modules** (comme `taskman`).
Chacun a un **brief détaillé par phase** (`BRIEF.md`) **et** une **solution de référence
complète, testée, expliquée** (`solution/`). Tu peux les faire :

- **en parallèle de `taskman`** (tu appliques chaque module aux deux) — le plus formateur ;
- **après la formation**, comme entraînement de consolidation ;
- **à la place** d'un `taskman` si le domaine te motive plus.

| Projet | Domaine | Ce qu'il pousse plus loin que `taskman` | Statut |
|---|---|---|---|
| [`shopfast`](shopfast/BRIEF.md) | **E-commerce** (catalogue, panier, commandes, paiement simulé, stock) | transactions, cohérence, idempotence des paiements, jobs de fond, verrous de stock | 🚧 |
| [`inkwell`](inkwell/BRIEF.md) | **Blog / CMS** (articles, versions, commentaires, médias, rôles éditoriaux) | upload de fichiers, workflow de publication, cache de lecture, SEO/slug, modération | 🚧 |
| [`saashub`](saashub/BRIEF.md) | **SaaS multi-tenant** (organisations, membres, rôles, facturation, quotas) | isolation multi-tenant, RBAC fin, limites d'usage, webhooks, plans & billing | 🚧 |

## Règle du jeu

1. Lis le brief, **pas** la solution.
2. Respecte le *time-box* indiqué. Un projet réfléchi mais inachevé > un projet parfait en 3× le temps.
3. `ruff` + `mypy` + `pytest` au vert avant de comparer.
4. Lis la solution **et son `SOLUTION.md`** (les choix). Note 3 choses que tu aurais faites autrement.
5. Commit ton travail dans le dossier du projet.
