# Raccourcis de développement. Usage : make <cible>
# Windows sans make : lis les commandes ci-dessous, elles sont utilisables telles quelles,
#                     ou utilise .\tasks.ps1 <cible> (PowerShell).

.DEFAULT_GOAL := help
PY := python

.PHONY: help
help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Crée le venv et installe les dépendances (dev incluses)
	$(PY) -m venv .venv
	./.venv/Scripts/python -m pip install -U pip
	./.venv/Scripts/python -m pip install -e ".[dev]"

.PHONY: lint
lint: ## Vérifie le style et le lint (sans modifier)
	ruff check .
	ruff format --check .

.PHONY: format
format: ## Formate le code et applique les corrections automatiques
	ruff format .
	ruff check --fix .

.PHONY: type
type: ## Vérifie les types du projet (mypy --strict)
	mypy taskman

.PHONY: type-all
type-all: type ## Vérifie aussi les solutions de chaque module (dossier par dossier)
	@for d in [0-9][0-9]-*/solutions; do \
		echo "mypy $$d"; ( cd "$${d%/solutions}" && mypy solutions ) || exit 1; \
	done

.PHONY: test
test: ## Lance la suite de tests
	pytest

.PHONY: cov
cov: ## Tests + rapport de couverture
	pytest --cov=taskman --cov-report=term-missing

.PHONY: check
check: lint type test ## Tout ce que la CI vérifie

.PHONY: run
run: ## Démarre le serveur de développement (reload)
	fastapi dev taskman/main.py

.PHONY: clean
clean: ## Supprime les caches d'outils
	rm -rf .ruff_cache .mypy_cache .pytest_cache htmlcov .coverage
