# `saashub` — solution de référence

La solution complète de `saashub` se construit **phase par phase** en suivant le tableau
« Construire la solution : quels patrons réutiliser » à la fin de [`../BRIEF.md`](../BRIEF.md).

C'est le projet le plus ambitieux, mais **aucun invariant n'est nouveau** : chacun est
démontré ailleurs dans le dépôt (voir le tableau du brief).

**Commence par l'isolation multi-tenant (P3)** et écris les tests de fuite inter-tenant
**avant** le reste. Le patron d'isolation à généraliser est celui de
[`projets/shopfast/solution/shopfast/repositories.py`](../../shopfast/solution/shopfast/repositories.py)
(`OrderRepository.get_for_user` : le filtre est **dans la requête SQL**, pas un `if` après
coup) — sauf qu'ici il porte sur `org_id` et doit être centralisé pour qu'un oubli soit
**impossible**, pas seulement improbable.

Le projet fil rouge entièrement résolu et testé le plus proche est
[`projets/shopfast/solution/`](../../shopfast/solution/).
