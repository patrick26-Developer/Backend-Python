# `inkwell` — solution de référence

La solution complète d'`inkwell` se construit **phase par phase** en suivant le tableau
« Construire la solution : quels patrons réutiliser » à la fin de [`../BRIEF.md`](../BRIEF.md).

Chaque invariant du brief a déjà un **patron éprouvé** dans le dépôt :

- l'architecture, la DB async, les migrations → Modules 03–04 + `projets/checkpoints/shorturl` ;
- le `slug` unique avec collisions → même logique que l'alias de `shorturl` ;
- la machine à états de publication → `projets/checkpoints/statuspage` + `projets/shopfast` ;
- « un brouillon jamais visible » → le filtrage-dans-la-requête de `projets/shopfast` ;
- le cache de lecture + invalidation → Module 08 ;
- l'événement `ArticlePublished` (outbox) → Module 12.

Le projet **fil rouge entièrement résolu et testé** le plus proche est
[`projets/shopfast/solution/`](../../shopfast/solution/) : même structure de dossiers, mêmes
conventions (`ruff` + `mypy --strict` + `pytest`, couverture > 85 %).
