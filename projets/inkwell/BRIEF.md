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
