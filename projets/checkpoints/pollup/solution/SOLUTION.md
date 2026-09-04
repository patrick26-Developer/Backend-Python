# `pollup` — les choix de conception

## 1. TDD : une règle métier = un test, écrit d'abord

`tests/test_service.py` liste les règles une par une, dans l'ordre où on les écrirait en
rouge → vert → refactor :

| Test | Règle |
|---|---|
| `test_create_assigns_ids...` | création : ids poll + options |
| `test_vote_counts_once_per_voter` | un vote compte |
| `test_second_vote_by_same_voter_is_rejected` | **un seul vote par votant** (409) |
| `test_vote_on_closed_poll_is_rejected` | sondage fermé → 409 |
| `test_vote_with_option_from_another_poll_is_rejected` | option étrangère → 422 |
| `test_results_percentages` | calcul des pourcentages |
| `test_hidden_results_*` | masquage tant que non fermé, sauf créateur |
| `test_only_owner_can_delete` | suppression réservée au créateur (403) |

Le service est testé **sans HTTP** : `PollService(InMemoryPollRepository())`. Rapide,
déterministe, chaque test isolé.

## 2. `api → service → repository`, le service ne connaît que le `Protocol`

```python
class PollRepository(Protocol):
    def create(...) -> Poll: ...
    def get(poll_id) -> Poll | None: ...
    def record_vote(poll_id, *, voter, option_id) -> None: ...
```

`PollService.__init__(self, repo: PollRepository)`. Brancher PostgreSQL = écrire
`SqlAlchemyPollRepository` (patron du Module 04) ; **zéro** ligne à changer dans le service
ou les tests de service. C'est le bénéfice concret de l'inversion de dépendance.

## 3. « Un vote par votant » = structure de données, pas garde applicative

```python
@dataclass
class Poll:
    votes: dict[str, int]   # votant -> option_id
```

Le `dict` **est** la contrainte : `poll.votes[voter] = option_id` écrase, et
`if voter in poll.votes` détecte le double vote. `total_votes == len(votes)`. Pas besoin
de dédupliquer une liste après coup.

## 4. Erreurs métier → un `dict` type → code HTTP

```python
_ERROR_STATUS: dict[type[PollError], int] = {
    PollNotFoundError: 404,
    OptionNotFoundError: 422,
    PollClosedError: 409,
    AlreadyVotedError: 409,
    NotPollOwnerError: 403,
    ResultsHiddenError: 409,
}

@app.exception_handler(PollError)
async def _domain_error(request, exc):
    code = _ERROR_STATUS.get(type(exc), 400)
    ...
```

Un **seul** handler pour toute la hiérarchie `PollError`. Ajouter une erreur = une entrée
dans le dict. Le service lève des exceptions nommées ; il n'écrit jamais `raise
HTTPException`.

## 5. `OptionNotFoundError` → 422, pas 404

Voter avec `option_id` qui n'appartient pas au sondage est une **entrée invalide** (comme un
champ mal typé), pas une ressource absente → 422 est plus juste que 404. Choix assumé,
testé des deux côtés (`test_vote_foreign_option_422`).

## 6. Auth « simple par token »

`Authorization: Bearer <chaîne>` où la chaîne **est** l'identité. Pas de JWT, pas de table
utilisateurs : le checkpoint porte sur les tests et l'archi, pas sur l'authentification
(couverte par le Module 06 / `taskman`). `require_identity` (obligatoire) vs
`optional_identity` (pour que le créateur voie ses résultats masqués) sont deux dépendances
distinctes.

## 7. Couverture > 90 %

`pyproject.toml` : `--cov-fail-under=90`. Les branches d'erreur (double vote, fermé, option
étrangère, non-propriétaire, résultats masqués) sont **toutes** couvertes — c'est justement
ce que le brief demande de vérifier.

## Ce que la solution ne fait pas

- Persistance (in-memory only) — voir §2 pour le point d'extension.
- Résultats en temps réel (SSE) — ce serait le Module 12.
- Anti-abus (un même humain, plusieurs tokens) — hors périmètre ; en vrai, rate-limit + fingerprint.
