# `shopfast` — API e-commerce (projet de domaine complet)

> 🚧 **Brief en construction.** Sera développé par phases (miroir des 13 modules), avec
> solution de référence complète dans `solution/` (à venir).

## Pitch

Une API de boutique en ligne : catalogue de produits, panier, passage de commande,
paiement **simulé**, gestion de stock. Domaine choisi pour ce qu'il impose : **transactions
strictes, cohérence sous concurrence, idempotence des paiements, jobs de fond**.

## Périmètre fonctionnel (cible finale)

- **Catalogue** : produits, catégories, prix, variantes (taille/couleur), recherche + filtres.
- **Stock** : quantité par variante, réservation au panier, décrément à la commande, réappro.
- **Panier** : par utilisateur (ou anonyme via token), ajout/màj/suppression, expiration.
- **Commande** : création depuis le panier, snapshot des prix, statuts
  (`pending → paid → shipped → delivered` / `cancelled` / `refunded`).
- **Paiement simulé** : intent de paiement, webhook de confirmation, **idempotence** (rejouer
  le webhook ne double pas la commande).
- **Comptes** : client, admin. RBAC. Un client ne voit que ses commandes.
- **Back-office** : CRUD produits/stock réservé aux admins, tableau des ventes.

## Phases (alignées sur les modules)

| Phase | Modules | Livrable |
|---|---|---|
| P1 | 01–02 | Catalogue en mémoire : CRUD produits, schémas Create/Read, recherche/filtres |
| P2 | 03 | Passage en couches (api/services/repositories), config, DI |
| P3 | 04 | PostgreSQL + Alembic : produits, variantes, stock ; requêtes sans N+1 |
| P4 | 05 | Erreurs métier (`OutOfStockError`, `CartExpiredError`…), format unifié, logs |
| P5 | 06 | Auth clients + admin, RBAC, isolation des commandes par client |
| P6 | 07 | Suite de tests complète, couverture > 85 %, cas concurrents |
| P7 | 08 | Réservation de stock sous verrou, paiement asynchrone, e-mails en worker, cache catalogue |
| P8 | 09 | Métriques (commandes/min, taux d'échec paiement), health/ready, traces |
| P9 | 10 | OWASP : IDOR sur commandes, rate limiting checkout, limites de payload, audit |
| P10 | 11 | Docker multi-stage, compose (api+db+redis), CI, migrations en prod |
| P11 | 12 | *Outbox* pour `OrderPaid`, webhooks sortants marchands, idempotency-key sur checkout, versionnage `/v1` |

## Points d'attention spécifiques

- **Ne jamais** recalculer le total d'une commande à partir du catalogue courant : on fige
  (`snapshot`) les prix à la création de la commande.
- **Concurrence de stock** : deux clients achètent le dernier article en même temps — un
  seul doit réussir. `SELECT ... FOR UPDATE` ou décrément conditionnel atomique.
- **Idempotence paiement** : le PSP peut envoyer le webhook 2 fois. Clé d'idempotence +
  état de transition vérifié.

## Definition of Done (résumé)

- [ ] Impossible de commander plus que le stock, même sous charge concurrente (test dédié).
- [ ] Rejouer un webhook de paiement ne crée pas de doublon.
- [ ] Un client ne peut pas lire/annuler la commande d'un autre (403/404).
- [ ] Le total d'une commande passée ne bouge pas si le prix catalogue change ensuite.
- [ ] `ruff` + `mypy --strict` + `pytest` au vert ; couverture > 85 %.
