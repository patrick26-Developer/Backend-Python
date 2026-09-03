# ADR 0002 — Événements de domaine via l'outbox pattern

- **Statut** : accepté
- **Date** : 2026-09-03

## Contexte

Quand une tâche est complétée, on veut publier un événement `task.completed` (pour les
notifications SSE, un futur service d'analytics, des webhooks). Publier directement sur le
broker **après** le `commit` DB crée un « double write » : si la publication échoue, la
tâche est committée mais l'événement est perdu (ou l'inverse).

## Décision

**Outbox pattern** : l'événement est écrit dans une table `outbox`, **dans la même
transaction** que la donnée. Un *drain* (`drain_outbox`, appelé par un worker `taskiq`
périodique) lit les lignes non publiées, les publie sur le broker, pose `published_at`.

En complément, `TaskService.complete` fait un `publisher.publish(event)` **best-effort**
après le commit pour le temps réel (SSE) immédiat — mais l'outbox reste la **source de
vérité** pour la livraison garantie.

## Conséquences

**Positif**
- garantie **at-least-once** : aucun événement perdu ;
- pas de transaction distribuée ;
- rejouable (l'outbox garde l'historique jusqu'au nettoyage).

**Négatif**
- latence : l'événement n'est publié qu'au prochain passage du *drain* (quelques secondes) —
  d'où le `publish` best-effort en complément pour le SSE ;
- les **consommateurs doivent être idempotents** (un événement peut arriver 2 fois) ;
- une table de plus + un worker de plus.

## Alternatives écartées

- **Publier après commit** sans outbox : simple mais perd des événements sur panne réseau.
- **Change Data Capture** (Debezium sur le WAL PostgreSQL) : puissant mais infra lourde,
  disproportionné à ce stade.
