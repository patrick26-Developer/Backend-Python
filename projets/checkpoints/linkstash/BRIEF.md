# `linkstash` — mini-projet checkpoint (après Module 02)

> 🚧 Énoncé en construction. Solution de référence commentée à venir dans `solution/`.
> **Time-box : une demi-journée.** Pas de base de données (store en mémoire, comme au Module 01).

## But

Valider : routing, schémas Pydantic `Create/Update/Read`, `response_model`, validation
avancée, `PATCH` correct, pagination, filtres.

## Spéc

Une API de marque-pages personnels.

- **Ressource `bookmark`** : `url` (validée, `AnyHttpUrl`), `title`, `note` (Markdown court,
  optionnel), `tags` (0–15, normalisés en minuscules), `favorite` (bool), `created_at`.
- `POST /bookmarks` → 201 + `Location`. Refuse une URL déjà enregistrée (409).
- `GET /bookmarks` → pagination `{items,total,limit,offset}`, filtres `tag`, `favorite`,
  `q` (recherche plein-texte naïve sur `title`+`note`), tri `-created_at` / `title`.
- `GET /bookmarks/{id}` → 200 / 404.
- `PATCH /bookmarks/{id}` → mise à jour partielle correcte (null explicite géré).
- `DELETE /bookmarks/{id}` → 204 / 404.
- `GET /tags` → liste des tags distincts avec le nombre de marque-pages.

## Definition of Done

- [ ] URL invalide → 422 ; URL en doublon → 409.
- [ ] `PATCH {}` ne modifie rien ; `PATCH {"note": null}` efface la note.
- [ ] `GET /bookmarks?tag=python&favorite=true` combine les filtres.
- [ ] `/docs` complet et exact.
- [ ] `ruff` + `mypy --strict` + `pytest` au vert.
