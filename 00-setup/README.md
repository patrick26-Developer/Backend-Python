# Module 00 — Setup & outillage professionnel

> **Objectif** : disposer d'un environnement de travail **isolé, reproductible et outillé**,
> et comprendre *pourquoi* chaque outil est là. On ne code pas une API sérieuse dans un
> Python global.

---

## 1. L'environnement virtuel (`venv`) — non négociable

### Pourquoi c'est recommandé (et ici, obligatoire)

Un projet backend dépend de dizaines de paquets, à des versions précises. Sans isolation :

- deux projets qui veulent deux versions de `pydantic` **se cassent mutuellement** ;
- tu pollues ton Python système (celui dont dépendent parfois des outils de l'OS) ;
- « ça marche chez moi » devient impossible à diagnostiquer — personne n'a le même jeu de
  dépendances ;
- tu ne peux pas **geler** (`freeze`) un état reproductible pour la CI ou la prod.

Un `venv` est un dossier (`.venv/`) contenant un interpréteur Python isolé et son propre
`site-packages`. Il est **jetable** : on le supprime et on le recrée sans état d'âme. Il est
`.gitignore` — on ne commite jamais un `venv`, seulement la *liste* des dépendances
(`pyproject.toml`).

**Règle** : un projet = un `venv`. Toujours l'activer avant de travailler.

### Créer et activer

```powershell
# Windows PowerShell (depuis la racine du projet)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> Si PowerShell refuse le script d'activation :
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` (une seule fois).

```bash
# Windows Git Bash
python -m venv .venv
source .venv/Scripts/activate
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

Quand c'est actif, ton *prompt* commence par `(.venv)`. Pour vérifier que tu utilises le bon
Python :

```bash
python -c "import sys; print(sys.executable)"
# -> .../Backend-Python/.venv/Scripts/python.exe
```

Pour sortir : `deactivate`.

### Le réflexe quotidien

```
1. Ouvrir le projet
2. Activer le venv          <- si tu oublies, tu installes/exécutes dans le mauvais Python
3. Travailler
4. deactivate (ou fermer le terminal)
```

---

## 2. Installer les dépendances

Ce dépôt déclare ses dépendances dans **`pyproject.toml`** (standard moderne), pas dans un
`requirements.txt`. Deux groupes :

- `dependencies` → ce dont l'API a besoin pour *tourner* (`fastapi`, `pydantic`…) ;
- `optional-dependencies.dev` → ce dont *toi* as besoin pour *développer* (`pytest`, `ruff`,
  `mypy`…), inutile en prod.

```bash
# venv activé
python -m pip install -U pip
pip install -e ".[dev]"
```

`-e` (*editable*) installe `taskman` en mode lien : tes modifications de code sont prises en
compte sans réinstaller.

### Alternative : `uv` (plus rapide, recommandé si tu peux l'installer)

[`uv`](https://docs.astral.sh/uv/) est un gestionnaire de paquets et d'environnements
ultra-rapide, écrit en Rust. Il remplace `venv` + `pip` + `pip-tools`.

```bash
# Installer uv (Windows PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Ensuite, depuis le projet :
uv venv                 # crée .venv
uv pip install -e ".[dev]"
# ou, tout-en-un :
uv sync --extra dev
uv run fastapi dev taskman/main.py
```

`uv run <cmd>` exécute la commande dans le `venv` du projet **sans activation manuelle**.
Le reste du cursus fonctionne avec l'un ou l'autre ; les exemples utilisent `pip`/`venv` par
défaut et signalent l'équivalent `uv` quand c'est utile.

---

## 3. Le triptyque qualité

| Rôle | Outil | Commande | Ce que ça t'évite |
|---|---|---|---|
| **Formatage** | `ruff format` | `ruff format .` | Les débats de style, les diffs bruyants |
| **Lint** | `ruff check` | `ruff check .` | Bugs latents, imports morts, anti-patterns |
| **Types** | `mypy` | `mypy taskman` | La moitié des bugs runtime, attrapés à l'écriture |

Tout est déjà configuré dans [`pyproject.toml`](../pyproject.toml). `ruff` remplace à lui
seul `black` + `isort` + `flake8` + une grande partie de `pylint`.

**mypy en `--strict`** : c'est exigeant, et c'est voulu. Le typage strict est ce qui rend
FastAPI si sûr — chaque annotation devient une garantie vérifiée.

---

## 4. `pre-commit` — le garde-fou automatique

`pre-commit` exécute lint + format + type-check **avant chaque commit** et refuse le commit
si quelque chose cloche. Tu ne peux plus pousser du code sale par distraction.

```bash
pip install pre-commit
pre-commit install
```

Fichier [`.pre-commit-config.yaml`](../.pre-commit-config.yaml) fourni. Pour lancer sur tout
le dépôt : `pre-commit run --all-files`.

---

## 5. Automatisation : le `Makefile`

Plutôt que de retenir 6 commandes, on en retient une famille : `make <cible>`.

| Cible | Action |
|---|---|
| `make install` | Crée le venv + installe tout |
| `make lint` | `ruff check` + `ruff format --check` |
| `make format` | `ruff format` + `ruff check --fix` |
| `make type` | `mypy taskman` |
| `make test` | `pytest` |
| `make check` | `lint` + `type` + `test` (ce que fait la CI) |
| `make run` | `fastapi dev taskman/main.py` |

> **Windows sans `make`** : installe-le (`winget install ezwinports.make` ou via *Chocolatey*
> `choco install make`), ou utilise directement les commandes listées dans le
> [`Makefile`](../Makefile) — elles sont lisibles telles quelles. Un script
> `tasks.ps1` équivalent est fourni pour PowerShell pur.

---

## 6. Éditeur

VS Code recommandé. Extensions utiles (voir [`.vscode/extensions.json`](../.vscode/extensions.json)) :

- **Python** + **Pylance** (typage, autocomplétion) ;
- **Ruff** (formatage + lint à la sauvegarde) ;
- **Mypy Type Checker**.

Sélectionne l'interpréteur du `venv` : `Ctrl+Shift+P` → *Python: Select Interpreter* →
`.venv`.

---

## 6 bis. Le skill officiel FastAPI pour agents IA (optionnel)

FastAPI fournit un *skill* officiel qui garde un agent de code (Claude Code, Codex, Cursor…)
aligné sur la **version exacte** de FastAPI installée. Après `pip install -e ".[dev]"` :

```bash
uvx library-skills          # scanne les paquets installés et propose d'installer les skills
# Pour Claude Code : choisir .claude/skills à l'invite
```

Utile quand tu génères du code avec un agent : il évite les tournures obsolètes. Ça ne
remplace pas le fait de **comprendre** ce que tu écris — c'est tout l'objet de ce cursus.

## 7. Anatomie d'un projet FastAPI mature (cible du Module 03)

```
Backend-Python/
├── taskman/                 # le code de l'application (package importable)
│   ├── __init__.py
│   ├── main.py              # création de l'app FastAPI, montage des routers
│   ├── core/                # config, sécurité, logging — transverse
│   │   └── config.py
│   ├── api/                 # couche HTTP : routers, dépendances de requête
│   │   └── routes/
│   ├── schemas/             # modèles Pydantic (contrats d'entrée/sortie)
│   ├── services/            # logique métier (sans HTTP, sans SQL direct)
│   ├── repositories/        # accès aux données (une implémentation par backend)
│   └── db/                  # (Module 04) moteur, session, modèles ORM, migrations
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── 00-setup/ … 12-…/        # les supports de cours
├── pyproject.toml
├── Makefile
├── .env.example
└── README.md
```

Pour le **Module 01**, on démarre volontairement plus petit (un seul fichier ou presque) :
on n'introduit une structure que quand la douleur de ne pas l'avoir se fait sentir.

---

## Exercices

### Exercice 00.1 — Environnement propre

1. Supprime `.venv/` s'il existe. Recrée-le, active-le, installe `".[dev]"`.
2. Vérifie : `python -c "import sys; print(sys.executable)"` pointe bien dans `.venv`.
3. Lance `ruff check .`, `mypy taskman`, `pytest`. Les trois doivent passer.

### Exercice 00.2 — Casser puis réparer

Crée `scratch.py` à la racine :

```python
import os, sys
def add(a,b):
    x= a+b
    return  x
unused = 42
```

1. Lance `ruff check scratch.py` : lis chaque code d'erreur (`F401`, `E225`, `E401`…).
2. Corrige avec `ruff check --fix scratch.py` puis `ruff format scratch.py`.
3. Ajoute des annotations de type pour que `mypy scratch.py` passe.
4. Supprime `scratch.py`.

### Exercice 00.3 — `Makefile`

Sans regarder celui fourni, écris un `Makefile` avec `install`, `lint`, `type`, `test`,
`check`, `run`. Compare ensuite avec la version du dépôt.

---

## Definition of Done

- [ ] `.venv` créé, activé ; `sys.executable` pointe dedans.
- [ ] `pip install -e ".[dev]"` réussit sur un `.venv` neuf.
- [ ] `ruff check .` et `ruff format --check .` passent.
- [ ] `mypy taskman` passe en `--strict`.
- [ ] `pytest` s'exécute sans erreur de collecte.
- [ ] `pre-commit install` fait, `pre-commit run --all-files` passe.
- [ ] Tu sais expliquer, sans notes, pourquoi un `venv` est indispensable.

---

➡️ Module suivant : [`01-fondations-http-et-fastapi`](../01-fondations-http-et-fastapi/THEORIE.md)
