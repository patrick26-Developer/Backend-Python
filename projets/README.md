# Mini-projets de validation

> Des projets **courts** (une demi-journée à 2 jours), **hors `taskman`**, pour vérifier
> qu'une compétence tient sur un domaine neuf. Chacun aura un énoncé détaillé + une solution
> de référence, publiés au moment du module correspondant.

| Projet | Débloqué après | Compétences validées | Statut |
|---|---|---|---|
| **`linkstash`** — API de marque-pages (URL, tags, notes, recherche) | Module 02 | routing, Pydantic, validation, response models, `PATCH` | 🚧 |
| **`shorturl`** — raccourcisseur d'URL + compteur de clics | Module 04 | DB async, migrations, repository, unicité, redirections | 🚧 |
| **`pollup`** — API de sondages (questions, options, votes, résultats) | Module 07 | archi en couches + suite de tests complète, TDD | 🚧 |
| **`statuspage`** — supervision de services (checks, incidents, uptime) | Module 09 | observabilité, health/ready, métriques, tâches de fond | 🚧 |
| **`taskman` v2** — refonte de zéro, sans regarder l'ancien code, en 2 jours | Module 12 | maîtrise réelle de bout en bout | 🚧 |

## Règle du jeu

1. Lis l'énoncé, **pas** la solution.
2. Time-box : respecte la durée indiquée. Un projet inachevé mais réfléchi > un projet parfait en 3× le temps.
3. Fais tourner `ruff` + `mypy` + `pytest` avant de comparer.
4. Lis ensuite la solution **et son README de conception**. Note 3 choses que tu aurais faites autrement.
5. Commit ton projet dans `projets/<nom>/`.
