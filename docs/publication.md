# Comment ce site est publié

Ce site (celui que tu es en train de lire) est un site statique généré par **MkDocs
Material** à partir des fichiers `.md` de ce dépôt — un site = un `mkdocs build`, aucun
serveur applicatif derrière.

- **Dépôt** : [github.com/patrick26-Developer/Backend-Python](https://github.com/patrick26-Developer/Backend-Python)
  (public).
- **Hébergement** : [Render](https://render.com) (offre statique gratuite), via le
  blueprint [`render.yaml`](https://github.com/patrick26-Developer/Backend-Python/blob/main/render.yaml)
  à la racine du dépôt.
- **Build** : `mkdocs build && mkdocs build -f mkdocs.en.yml` → dossier `site/`.
- **Déclenchement** : chaque `git push` sur `main` redéploie automatiquement.

## Deux configs, un seul site

`theme.language` de Material ne peut pas varier par page dans un seul build (recherche,
bascule clair/sombre... tout serait en français, même sur les pages anglaises). D'où deux
configs :

| Config | Contenu | Interface | Sortie |
|---|---|---|---|
| `mkdocs.yml` | tout le cursus (13 modules, projets…) | français | `site/` |
| `mkdocs.en.yml` | ce qui est traduit (la page d'accueil pour l'instant) | **anglais** | `site/en/` (écrase le `en/` du premier build) |

Ajouter une page en anglais : la traduire, l'ajouter au `nav` de `mkdocs.en.yml`, l'exclure
du `nav`/`exclude_docs` si besoin dans `mkdocs.yml`.

## Reproduire ce site en local

```bash
git clone https://github.com/patrick26-Developer/Backend-Python.git
cd Backend-Python
pip install -e ".[docs]"
mkdocs serve                       # site français, http://127.0.0.1:8000, rechargement à chaud
mkdocs build -f mkdocs.en.yml      # génère site/en/ (page anglaise) à part
```

## Alternatives d'hébergement

Le site est 100 % statique : n'importe quel hébergeur de fichiers statiques convient.

| Cible | Commande |
|---|---|
| **GitHub Pages** | `mkdocs gh-deploy` — pousse `site/` sur la branche `gh-pages` |
| **Vercel** | *Import project* → build `mkdocs build` → output `site` |
| **Cloudflare Pages** | build `pip install -r requirements-docs.txt && mkdocs build`, output `site` |
