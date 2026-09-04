# Comment ce site est publié

Ce site (celui que tu es en train de lire) est un site statique généré par **MkDocs
Material** à partir des fichiers `.md` de ce dépôt — un site = un `mkdocs build`, aucun
serveur applicatif derrière.

- **Dépôt** : [github.com/patrick26-Developer/Backend-Python](https://github.com/patrick26-Developer/Backend-Python)
  (public).
- **Hébergement** : [Render](https://render.com) (offre statique gratuite), via le
  blueprint [`render.yaml`](https://github.com/patrick26-Developer/Backend-Python/blob/main/render.yaml)
  à la racine du dépôt.
- **Build** : `pip install -r requirements-docs.txt && mkdocs build` → dossier `site/`.
- **Déclenchement** : chaque `git push` sur `main` redéploie automatiquement.

## Reproduire ce site en local

```bash
git clone https://github.com/patrick26-Developer/Backend-Python.git
cd Backend-Python
pip install -e ".[docs]"
mkdocs serve       # http://127.0.0.1:8000, rechargement à chaud
# ou : mkdocs build puis servir site/ avec n'importe quel serveur statique
```

## Alternatives d'hébergement

Le site est 100 % statique : n'importe quel hébergeur de fichiers statiques convient.

| Cible | Commande |
|---|---|
| **GitHub Pages** | `mkdocs gh-deploy` — pousse `site/` sur la branche `gh-pages` |
| **Vercel** | *Import project* → build `mkdocs build` → output `site` |
| **Cloudflare Pages** | build `pip install -r requirements-docs.txt && mkdocs build`, output `site` |
