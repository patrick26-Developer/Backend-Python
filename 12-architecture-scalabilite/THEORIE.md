# Module 12 — Architecture & scalabilité

> **Objectif** : **défendre un choix d'architecture avec des arguments de coût et de
> risque**, pas de mode. Monolithe modulaire vs microservices, DDD léger, événements
> (*outbox*), versionnage d'API, temps réel, idempotence.
> Savoir **quand *ne pas*** découper est aussi important que savoir découper.
>
> **Durée estimée** : 12 à 18 h. **Pré-requis** : tous les modules précédents.

---

## 1. Monolithe modulaire vs microservices

### Le défaut sain : le **monolithe modulaire**

Un **seul** déploiement, mais un code **découpé en modules** à frontières nettes
(*bounded contexts*), qui ne communiquent que par des **interfaces publiques explicites**.

```
taskman/
├── tasks/        # bounded context "gestion de tâches"
│   ├── api/ services/ repositories/ schemas/
│   └── public.py     # LA surface exposée aux autres modules
├── projects/     # bounded context "projets"
│   └── public.py
├── accounts/     # bounded context "comptes & auth"
│   └── public.py
└── shared/       # kernel : config, db, exceptions, observabilité
```

Règle : `tasks/` importe `projects.public`, **jamais** `projects.repositories.sqlalchemy`.
Un *linter* d'architecture (`import-linter`) fait respecter ça.

### Quand passer aux microservices ?

| Signal | Microservices aide-t-il ? |
|---|---|
| « le déploiement est lent / risqué » | non → CI/CD, tests (Modules 07, 11) |
| « le code est un plat de spaghettis » | non → modules à frontières nettes (ci-dessus) |
| « deux équipes se marchent dessus » | **oui** — chaque équipe possède son service |
| « un composant a un profil de charge très différent » (ex. l'export vs le CRUD) | **oui** — scaler indépendamment |
| « on veut des stacks différentes » (un service en Rust, un en Python) | **oui** |
| « on veut être *cloud-native* / c'est moderne » | **non** (ce n'est pas un argument) |

**Le coût des microservices** : réseau entre services (latence, pannes partielles),
transactions distribuées (plus de `commit` global), observabilité distribuée obligatoire,
déploiements coordonnés, duplication d'infra. On ne le paie que quand le bénéfice
(**autonomie des équipes**, **scaling ciblé**) le justifie.

> **Recommandation** : commence en **monolithe modulaire**. Si un module devient un point de
> friction d'équipe ou de charge, extrais **ce module-là** en service. Pas avant.

---

## 2. DDD léger (Domain-Driven Design)

On ne fait pas « du DDD » en entier ; on en prend les outils utiles :

- **Bounded context** : une frontière où un terme a **un** sens précis. « Task » dans
  `tasks/` ≠ « Task » dans un futur module `billing/` (une ligne de facturation).
- **Langage ubiquitaire** : le code utilise les **mots du métier** (`complete`, `overdue`,
  `assignee`), pas des termes techniques (`update_status_flag`).
- **Entité** : identité stable dans le temps (une `Task` a un `id`).
- **Value object** : défini par ses valeurs, immuable (`ChecklistItem`, un `Money`, une
  `DateRange`).
- **Agrégat** : un groupe d'objets modifié comme un tout, avec une **racine** qui garantit
  les invariants (`Project` + ses `Task` ; on ne modifie une `Task` que via des règles
  cohérentes).
- **Événement de domaine** : un fait métier passé (`TaskCompleted`, `ProjectArchived`).

Où placent les règles ? **Dans le domaine** (l'agrégat / le service de domaine), pas dans la
route, pas dans le repository.

---

## 3. Architecture pilotée par les événements

### L'*outbox pattern* — le problème du « double write »

```python
# NAÏF — bug :
await repo.save(task)          # transaction DB
await broker.publish(event)    # réseau -> si ça échoue, la DB est committée mais l'event perdu
```

Deux systèmes (DB + broker), pas de transaction commune. Solution : **écrire l'événement
dans la même transaction que la donnée**, dans une table `outbox` :

```python
async def complete(self, task_id):
    task = await self._tasks.mark_completed(task_id)
    await self._outbox.add(DomainEvent(type="task.completed", payload={"task_id": task.id}))
    await self._uow.commit()          # task + event : tout ou rien
```

Un **processus séparé** (ou un worker taskiq périodique) lit l'`outbox`, publie sur le
broker, marque les lignes comme envoyées. Garantie : **au moins une fois** (*at-least-once*).

### Idempotence des consommateurs

Puisque *at-least-once*, un événement peut être reçu **2 fois** → le consommateur doit être
**idempotent** : traiter `task.completed#42` deux fois = même résultat qu'une fois (vérifier
un `processed_events` avant d'agir, ou concevoir l'effet comme idempotent).

---

## 4. Idempotence des **écritures** (`Idempotency-Key`)

Un client fait `POST /tasks`, le réseau coupe **après** la création mais **avant** la
réponse → le client *retry* → **deux** tâches.

```
POST /tasks
Idempotency-Key: 7c3e9f...        # généré par le client, unique par tentative "logique"
```

Le serveur stocke `(clé → réponse)` :
- **1ᵉʳ appel** : traite, stocke la réponse sous la clé, répond `201` ;
- **rejeu** (même clé) : renvoie la **réponse stockée**, sans re-traiter (`201`, même corps).

Clé conservée 24 h. À appliquer aux `POST`/`PATCH` **non idempotents** par nature (création,
paiement). Les `PUT`/`DELETE` sont déjà idempotents.

---

## 5. Versionnage d'API

Un contrat public **ne casse pas** silencieusement.

### URI vs en-tête

| Approche | Exemple | Pour / Contre |
|---|---|---|
| **URI** | `/v1/tasks`, `/v2/tasks` | visible, simple à router/cacher ; « pas RESTful » (débat stérile) |
| **en-tête** | `Accept: application/vnd.taskman.v2+json` | URL stable ; invisible, plus dur à tester au navigateur |

`taskman` : **URI** (`/v1`). Le router racine devient
`app.include_router(v1_router, prefix="/v1")`.

### Cycle de vie

1. `/v1` en prod. On ajoute `/v2` (contrat changé) — les deux coexistent.
2. `/v1` est marqué **déprécié** : en-tête `Deprecation: true` + `Sunset: <date>` dans les
   réponses, doc mise à jour, e-mail aux consommateurs.
3. Après la date de *sunset* (ex. 6 mois) et vérification (métriques : plus personne
   n'appelle `/v1`), on retire `/v1`.

**Un changement compatible** (nouveau champ optionnel en sortie) **ne** demande **pas** de
nouvelle version — juste de la doc.

---

## 6. Temps réel : SSE vs WebSockets

| | **SSE** (Server-Sent Events) | **WebSocket** |
|---|---|---|
| sens | serveur → client seulement | bidirectionnel |
| protocole | HTTP (une réponse qui ne finit pas) | `ws://` (upgrade HTTP) |
| reconnexion | **automatique** (le navigateur, `Last-Event-ID`) | à gérer soi-même |
| proxy / infra | passe partout (c'est du HTTP) | parfois bloqué, config spéciale |
| usage | notifications, flux d'activité, progression | chat, collaboration temps réel, jeux |

Pour « prévenir le client qu'une tâche a changé » → **SSE** suffit et coûte moins cher.

```python
@router.get("/events")
async def events(user: CurrentUser) -> EventSourceResponse:
    async def stream():
        async for event in subscribe(user.id):        # via Redis pub/sub
            yield {"event": event.type, "data": event.json()}
    return EventSourceResponse(stream())
```

### Scaling du temps réel

Avec N instances, un client connecté à l'instance A ne « voit » pas un événement produit sur
l'instance B → il faut un **bus** : **Redis pub/sub** (simple), ou un broker dédié. Chaque
instance s'abonne, relaie à **ses** clients connectés.

---

## 7. Multi-instance : rester *stateless*

Pour scaler horizontalement (ajouter des répliques), chaque instance doit être
**interchangeable** :

- **aucun état en mémoire** qui compte : sessions → JWT (Module 06) ou Redis ; cache → Redis
  (Module 08) ; rate limit → Redis (Module 10) ; uploads → stockage objet (S3), pas le
  disque local.
- **jobs de fond** → un broker (pas `BackgroundTasks` qui vit dans un process).
- **tâches planifiées** → un seul *scheduler* (verrou distribué) qui *enqueue*, N workers
  qui consomment — jamais un cron dans chaque réplique.

`taskman` a fait ce travail au fil des modules : c'est ce qui le rend scalable.

---

## 8. Pièges fréquents

1. **Microservices « parce que »** → on paie tous les coûts, aucun bénéfice.
2. **Modules qui s'importent en profondeur** (`tasks/` → `projects/repositories/…`) → couplage caché, pas mieux qu'un monolithe spaghetti.
3. **Double write** (DB puis broker) sans *outbox* → événements perdus.
4. **Consommateur d'événements non idempotent** → doublons (2 e-mails, 2 débits).
5. **`POST` de création sans `Idempotency-Key`** sur un flux critique → doublons au *retry*.
6. **Casser `/v1`** au lieu d'ajouter `/v2` → tous les clients tombent.
7. **Retirer `/v1`** sans vérifier les métriques d'usage → on coupe un client actif.
8. **WebSocket** là où **SSE** suffirait → complexité et fragilité inutiles.
9. **État en mémoire** (cache local, compteur) en multi-instance → incohérences.
10. **Un cron dans chaque réplique** → la tâche planifiée s'exécute N fois.

---

## 9. Ce que `taskman` gagne

- réorganisation en **bounded contexts** (`tasks/`, `projects/`, `accounts/`, `shared/`) avec
  un `public.py` par module + `import-linter` en CI ;
- table `outbox` + événement `TaskCompleted` émis **dans la transaction** + worker taskiq qui
  publie ;
- `Idempotency-Key` sur `POST /tasks` (clé → réponse stockée 24 h) ;
- API **versionnée** : `/v1` (+ un exemple de `/v2` avec un contrat modifié) ;
- notifications temps réel via **SSE** (`GET /v1/events`), fan-out via Redis pub/sub ;
- 3 **ADR** dans `docs/adr/` (monolithe modulaire, outbox, versionnage) datées et motivées.

---

## 10. L'examen final

Après ce module : **refais `taskman` de zéro, sans regarder, en 2 jours.** Pas à
l'identique — les *décisions* comptent plus que le code. Si tu peux :

- monter l'environnement, la structure en couches et la config en 1 h ;
- écrire un CRUD validé, testé, typé sans hésiter ;
- brancher une DB async + migrations ;
- ajouter l'auth + l'isolation des données ;
- justifier chaque choix à voix haute —

alors tu as le niveau visé par ce cursus. Sinon, reprends les modules où tu as hésité.

---

## 11. À savoir refaire sans aide

- Argumenter monolithe modulaire vs microservices avec des critères de coût/risque.
- Découper un domaine en *bounded contexts* avec des interfaces publiques explicites.
- Implémenter l'*outbox pattern* et un consommateur idempotent.
- Rendre un `POST` idempotent avec `Idempotency-Key`.
- Versionner une API et gérer un cycle de dépréciation.
- Choisir SSE ou WebSocket et scaler le temps réel (pub/sub).
- Rendre une app *stateless* pour le multi-instance.

➡️ [Exercices](exercices/README.md) · [PAS-A-PAS.md](PAS-A-PAS.md)
