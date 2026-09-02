# `pollup` — mini-projet checkpoint (après Module 07)

> 🚧 Énoncé en construction. Solution de référence commentée à venir dans `solution/`.
> **Time-box : 2 jours.** À construire **entièrement en TDD** (rouge → vert → refactor).

## But

Valider : architecture en couches propre + suite de tests complète, `dependency_overrides`,
fixtures, `httpx.AsyncClient`, couverture des branches d'erreur.

## Spéc

- `POST /polls` `{question, options[2..10], closes_at?}` → crée un sondage.
- `GET /polls/{id}` → sondage + options + total de votes (pas le détail par votant).
- `POST /polls/{id}/votes` `{option_id}` → enregistre un vote.
  - un votant (identifié par token/cookie) ne vote **qu'une fois** par sondage (409 sinon) ;
  - sondage fermé (`closes_at` passé) → 409.
- `GET /polls/{id}/results` → répartition `{option, count, percent}` ; masquée tant que le
  sondage n'est pas fermé **si** `hide_results_until_closed=true`.
- `DELETE /polls/{id}` → 204 (créateur seulement — auth simple par token).

## Definition of Done

- [ ] **Chaque règle métier a été écrite comme un test AVANT le code** (visible dans l'historique git).
- [ ] Couche service testée sans HTTP ni DID réelle ; endpoints testés en intégration.
- [ ] Double vote, sondage fermé, option d'un autre sondage → tous couverts.
- [ ] Couverture > 90 %, 100 % déterministe.
- [ ] `ruff` + `mypy --strict` au vert.
