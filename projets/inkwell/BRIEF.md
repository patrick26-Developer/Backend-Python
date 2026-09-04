# `inkwell` — API de blog / CMS (projet de domaine complet)

> 🚧 **Brief en construction.** Développé par phases (miroir des 13 modules), solution de
> référence complète dans `solution/` (à venir).

## Pitch

Un moteur de blog / CMS multi-auteurs : articles avec **versions**, workflow de publication
(`draft → review → published → archived`), commentaires modérés, médias (images), rôles
éditoriaux. Domaine choisi pour : **upload de fichiers, workflow d'états, cache de lecture,
slugs/SEO, modération**.

## Périmètre fonctionnel (cible finale)

- **Articles** : titre, `slug` unique, contenu Markdown, extrait, couverture, tags,
  catégorie, `published_at`, compteur de vues.
- **Versions** : chaque enregistrement crée une révision ; possibilité de comparer / restaurer.
- **Workflow** : `author` rédige, `editor` valide, `published` visible publiquement.
- **Commentaires** : imbriqués (1 niveau), file de **modération** (`pending/approved/spam`),
  anti-spam basique (rate limit + honeypot).
- **Médias** : upload d'images (validation type/taille), stockage local puis abstrait
  (interface `Storage`), URL servie.
- **Rôles** : `reader` (public), `author`, `editor`, `admin`.
- **API publique** : liste paginée des articles publiés, par tag/catégorie, flux RSS/Atom,
  article par `slug` (avec cache).

## Phases (alignées sur les modules)

| Phase | Modules | Livrable |
|---|---|---|
| P1 | 01–02 | Articles en mémoire, schémas, génération de `slug`, validation Markdown/longueurs |
| P2 | 03 | Couches, config, DI, `Storage` en `Protocol` |
| P3 | 04 | PostgreSQL + Alembic : articles, versions, tags, commentaires ; requêtes de liste |
| P4 | 05 | Erreurs métier (`SlugTakenError`, `InvalidTransitionError`), format unifié, logs |
| P5 | 06 | Auth + rôles éditoriaux ; règles « author édite ses brouillons, editor publie » |
| P6 | 07 | Tests complets, workflow d'états testé exhaustivement |
| P7 | 08 | Upload d'images en tâche de fond (miniatures), cache de l'article public, pagination cursor |
| P8 | 09 | Métriques (articles publiés/j, vues), health/ready, traces |
| P9 | 10 | OWASP : contrôle d'accès brouillons, rate limit commentaires, validation upload stricte |
| P10 | 11 | Docker, compose, CI, migrations |
| P11 | 12 | Événement `ArticlePublished` (outbox) → invalidation cache + webhook ; versionnage API publique |

## Points d'attention spécifiques

- **Slugs** : unicité, gestion des collisions (`mon-titre`, `mon-titre-2`), immuabilité une
  fois publié (redirection sinon).
- **Transitions d'état** : une machine à états explicite ; toute transition illégale → 409.
- **Cache de lecture** : l'article public est très lu, peu écrit → *cache-aside* + invalidation
  à la publication/màj.
- **Upload** : ne jamais faire confiance au `Content-Type` client ; vérifier la signature du
  fichier, borner la taille, générer un nom serveur.

## Definition of Done (résumé)

- [ ] Un brouillon n'est jamais visible via l'API publique.
- [ ] Toute transition d'état illégale est refusée (409) et testée.
- [ ] Deux articles ne peuvent pas avoir le même `slug`.
- [ ] Un upload non-image ou trop gros est rejeté (type réel vérifié).
- [ ] Le cache de l'article public est invalidé à la mise à jour.
- [ ] `ruff` + `mypy --strict` + `pytest` au vert ; couverture > 85 %.

---

## Construire la solution : quels patrons réutiliser

Tu as déjà, dans ce dépôt, tout le nécessaire. Chaque invariant d'`inkwell` a un patron de
référence :

| Invariant `inkwell` | Patron à copier | Où |
|---|---|---|
| couches api → service → repo, `create_app()`, DI | Module 03 + `projets/shopfast/solution` | `03-architecture-projet-mature/` |
| PostgreSQL async + Alembic + `TZDateTime` | Module 04 + `projets/checkpoints/shorturl/solution` | `04-bases-de-donnees/` |
| `slug` unique + collisions (`mon-titre-2`) | même logique que l'alias de `shorturl` (contrainte + `IntegrityError` + suffixe incrémental) | `projets/checkpoints/shorturl/solution/shorturl/service.py` |
| machine à états `draft→review→published→archived`, transition illégale → 409 | `statuspage` (incidents) + `shopfast` (`_NEXT_STATUS`) | `projets/checkpoints/statuspage/solution/statuspage/service.py` |
| brouillon jamais visible en public | filtre `status == "published"` **dans la requête** (comme l'isolation `user_id` de `shopfast`) | `projets/shopfast/solution/shopfast/repositories.py` |
| erreurs métier (`SlugTakenError`, `InvalidTransitionError`) → format unifié | Module 05 (`DomainError` + RFC 9457) | `05-erreurs-logs-middleware/` |
| auth + rôles éditoriaux (`author`/`editor`/`admin`) | Module 06 + `shopfast` (`require_admin`) | `06-authentification-autorisation/` |
| cache de lecture de l'article public + invalidation à la publication | Module 08 (`cache-aside`, `Cache` Protocol, `delete_prefix`) | `08-async-avance-performance/` |
| upload d'image : vérifier la **signature** (magic bytes), borner la taille, nom serveur | nouveau — mais `BodySizeLimitMiddleware` du Module 10 borne déjà le payload | `10-securite-approfondie/` |
| miniatures en tâche de fond | Module 08 (`BackgroundTasks` / `taskiq`) | `08-async-avance-performance/` |
| événement `ArticlePublished` (outbox) → invalidation cache + webhook | Module 12 (outbox pattern) | `12-architecture-scalabilite/` |
| versionnage de l'API publique | Module 12 (`/v1`, `/v2`) | `12-architecture-scalabilite/` |

Ordre conseillé : suis les phases P1→P11 du tableau ci-dessus, une phase = une session, en
gardant les tests des phases précédentes verts. Le `Storage` en `Protocol` (P2) se teste avec
une implémentation en mémoire, comme le `PollRepository` de `pollup`.
