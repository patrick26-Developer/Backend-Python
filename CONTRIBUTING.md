# Contribuer / Contributing

**FR** — Ce dépôt est un support de formation. Les contributions bienvenues :
corrections (fautes, bugs dans les solutions), précisions pédagogiques, traductions,
nouveaux exercices, retours d'expérience d'apprenants.

**EN** — This repo is a learning curriculum. Welcome contributions: fixes (typos, bugs in
solutions), clearer explanations, translations, extra exercises, learner feedback.

## Règles

1. **Une PR = une idée.** Petit, revuable.
2. Le code livré passe `make check` (`ruff` + `mypy --strict` + `pytest`).
3. Commits en [Conventional Commits](https://www.conventionalcommits.org/) :
   `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.
4. Les explications visent un lecteur qui **connaît Python mais débute en backend**.
   Pas de jargon non défini, pas de « il suffit de ».
5. Toute solution vient avec **le raisonnement**, pas seulement le code.

## Mise en place

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows
# source .venv/bin/activate         # macOS / Linux
pip install -e ".[dev]"
pre-commit install
make check
```

## Structure

- `NN-*/` : un module de cours (théorie, exercices, solutions, pas-à-pas).
- `taskman/` : le projet fil rouge, état courant.
- `tests/` : la suite de tests du projet.
- `projets/` : mini-projets de validation.
- `annexes/` : fiches transverses (typing, glossaire…).

Voir [`ROADMAP.md`](ROADMAP.md) et [`DOC-COVERAGE.md`](DOC-COVERAGE.md).
