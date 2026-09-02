# Mode d'emploi de la formation

> Comment suivre ce cursus pour qu'il **serve vraiment**. Lis cette page **une fois**, en
> entier, avant de commencer le Module 00.

---

## 1. À qui ça s'adresse

Tu connais **Python** (fonctions, classes, `list`/`dict`, typage de base, `venv`) et tu sais
te servir d'un terminal et de `git`. Tu veux passer de « je bricole des scripts » à
« je conçois et j'exploite des API de production ».

Tu **n'as pas besoin** de connaître Flask, Django, un ORM ou Docker au préalable : on
construit ces briques au fil des modules.

---

## 2. Ce que tu vas obtenir

- Une méthode pour **concevoir** une architecture backend propre, pas seulement coder des routes.
- `taskman`, une API complète (gestion de tâches) que tu construis **brique par brique**, de
  la première route jusqu'au déploiement Docker + CI.
- Le réflexe qualité : `ruff` + `mypy --strict` + `pytest` au vert, tout le temps.
- La capacité de **refaire tout ça seul** sur un autre domaine (3 projets sont fournis pour ça).

---

## 3. La structure du dépôt

```
├── GUIDE.md              ← tu es ici
├── README.md             ← présentation
├── ROADMAP.md            ← les 13 modules en détail + "Definition of Done"
├── DOC-COVERAGE.md       ← preuve que toute la doc FastAPI est couverte
├── LICENSING.md          ← licences (code / contenu)
│
├── 00-setup/ … 12-…/     ← les modules (voir §4)
├── annexes/              ← fiches transverses (typage Python…)
├── projets/              ← mini-projets + 3 projets de domaine complets
│
├── taskman/              ← LE projet fil rouge, état courant
└── tests/                ← la suite de tests de taskman
```

Chaque module `NN-...` contient toujours les mêmes fichiers :

| Fichier | Ce que c'est | Quand le lire |
|---|---|---|
| `THEORIE.md` | La théorie **juste nécessaire** : les concepts, les *pourquoi*, les pièges | **En premier**, en entier |
| `exercices/README.md` | Des exercices progressifs, avec **critères d'acceptation** | Après la théorie |
| `exercices/starter/` | Des fichiers de départ (`# TODO` numérotés) | Pendant les exercices |
| `solutions/` | Une solution **complète, testée**, qui passe `ruff` + `mypy --strict` | **Après** avoir une version qui marche |
| `solutions/README.md` | Les **choix de conception** expliqués (pas juste le code) | Avec les solutions |
| `PAS-A-PAS.md` | L'explication **ligne par ligne** de la solution | Pour ne laisser aucune zone d'ombre |

---

## 4. La boucle d'apprentissage (à répéter pour chaque module)

```
  1. LIRE la théorie          (THEORIE.md, en entier)
        │
  2. FAIRE les exercices      (exercices/README.md) — sans regarder les solutions
        │
  3. COMPARER                 (solutions/README.md puis PAS-A-PAS.md)
        │
  4. INTÉGRER dans taskman/   (reporter l'état final du module)
        │
  5. VÉRIFIER + COMMIT        (ruff + mypy + pytest au vert, puis git commit)
        │
  6. AUTO-ÉVALUER             (cocher la "Definition of Done" du module, honnêtement)
```

**Règles non négociables :**

- **Tu tapes le code toi-même.** Lire du FastAPI ne l'apprend pas ; l'écrire, le casser, le
  typer et le tester, oui.
- **Tu fais l'exercice AVANT d'ouvrir `solutions/`.** La solution n'est pas *le* corrigé :
  c'est *une* bonne réponse. Si la tienne diffère mais tient tous les critères et que tu
  peux justifier chaque écart → c'est une bonne solution.
- **Tu ne passes pas au module suivant** tant que la « Definition of Done » n'est pas cochée
  *honnêtement*.
- **Tu commits à chaque module.** L'historique `git` est ton cahier de progression.

---

## 5. Mise en route (une seule fois)

```powershell
# Windows PowerShell, à la racine du dépôt
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

```bash
# macOS / Linux
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -U pip && pip install -e ".[dev]"
cp .env.example .env
```

Détail complet et alternative `uv` : [`00-setup/README.md`](00-setup/README.md).

**Le réflexe quotidien :** ouvrir le projet → **activer le `venv`** → travailler → `deactivate`.
Si tu oublies d'activer le `venv`, tu installes et exécutes dans le mauvais Python.

---

## 6. Les commandes que tu utiliseras tout le temps

| Besoin | Commande | Raccourci |
|---|---|---|
| Lancer l'API en dev | `fastapi dev taskman/main.py` | `.\tasks.ps1 run` |
| Lint + format (vérif) | `ruff check . && ruff format --check .` | `.\tasks.ps1 lint` |
| Corriger le style | `ruff format . && ruff check --fix .` | `.\tasks.ps1 format` |
| Vérifier les types | `mypy taskman` | `.\tasks.ps1 type` |
| Lancer les tests | `pytest` | `.\tasks.ps1 test` |
| **Tout vérifier (comme la CI)** | — | `.\tasks.ps1 check` |
| Lire la solution d'un module en isolé | `cd NN-... && pytest solutions` | — |

(`make <cible>` si tu as `make` ; sinon `.\tasks.ps1 <cible>` sous Windows.)

Une fois `pip install -e ".[docs]"` fait :

| Besoin | Commande |
|---|---|
| Lire la formation comme un site (recherche, hors-ligne) | `mkdocs serve` → http://127.0.0.1:8000 |
| Générer le site statique | `mkdocs build` (dossier `site/`) |

---

## 7. `taskman` et les autres projets

- **`taskman`** est le fil rouge **obligatoire** : chaque module le fait évoluer. C'est lui
  que tu construis en suivant les modules.
- **`projets/checkpoints/`** : 4 mini-projets courts (½ à 2 jours) sur des domaines neufs,
  débloqués à des modules précis. Ils vérifient qu'une compétence tient **hors** du contexte
  `taskman`. Fortement conseillés.
- **`projets/shopfast` · `inkwell` · `saashub`** : 3 gros projets (e-commerce, blog, SaaS
  multi-tenant), avec un brief découpé **par phases alignées sur les 13 modules**. Tu peux :
  - les faire **en parallèle** de `taskman` (tu appliques chaque module aux deux) — le plus
    formateur ;
  - les garder **pour après**, en consolidation ;
  - en choisir un **à la place** de `taskman` si le domaine te motive davantage.

---

## 8. Rythme conseillé

| Profil | Cadence | Durée totale |
|---|---|---|
| Intensif (temps plein) | 1 module tous les 2–3 jours | ~4 semaines |
| Régulier (soirs / week-ends) | 1 module par semaine | ~3 mois |

Ne saute pas les exercices pour « aller plus vite ». Un module *lu* n'est pas un module
*acquis* — la seule preuve, c'est du code qui tourne et des tests verts.

---

## 9. Quand tu es bloqué

1. **Relis la section concernée de `THEORIE.md`** — la réponse y est presque toujours.
2. **Lis le message d'erreur en entier.** `mypy` et `pydantic` disent *exactement* ce qui
   ne va pas, et *où*.
3. **Réduis le problème** : écris 5 lignes qui reproduisent le bug, hors de `taskman`.
4. **Consulte la doc officielle** de la page correspondante (voir `DOC-COVERAGE.md` pour
   savoir laquelle).
5. **En dernier recours**, regarde la solution — mais lis d'abord `solutions/README.md`
   (les choix) avant `PAS-A-PAS.md` (le code), pas l'inverse.

Rester bloqué 30 minutes, c'est normal et formateur. Rester bloqué 3 heures, non : passe à
l'étape 5.

---

## 10. Signes que tu progresses vraiment

- Tu lis un message d'erreur `422` et tu sais **immédiatement** quel champ corriger.
- Tu ajoutes un endpoint sans copier-coller un autre.
- `mypy --strict` ne te fait plus peur.
- Tu peux expliquer à voix haute *pourquoi* telle logique est dans le service et pas dans la route.
- Tu refais le Module 01 de mémoire en 20 minutes.

Quand tu coches les 13 « Definition of Done » : refais **`taskman` de zéro, sans regarder**,
en 2 jours. C'est le vrai examen final.

---

➡️ Commence par [`00-setup/README.md`](00-setup/README.md).
