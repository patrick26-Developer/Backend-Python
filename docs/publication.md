# Publier la formation

> Deux artefacts distincts, à ne pas confondre :
>
> | | Config | Sortie | Visibilité |
> |---|---|---|---|
> | **Site vitrine** | `mkdocs.showcase.yml` | `site_showcase/` | **public** (Render, portfolio) |
> | **Site complet** | `mkdocs.yml` | `site/` | **privé** (livré aux acheteurs, hors ligne) |
>
> Le blueprint Render (`render.yaml`) ne construit **que la vitrine**. Le contenu payant
> n'est jamais copié dans `site_showcase/`, même si Render lit le dépôt privé complet.

---

## 1. Mettre le dépôt sur GitHub (privé)

```bash
# une seule fois : s'authentifier
gh auth login            # choisir GitHub.com > HTTPS > navigateur

# créer le dépôt PRIVÉ et pousser la branche main
gh repo create Backend-Python --private --source=. --remote=origin --description "Formation FastAPI de niveau production (taskman + checkpoints + projets de domaine)"
git push -u origin main
```

Sans `gh` : créer le dépôt vide `Backend-Python` (privé) sur github.com, puis

```bash
git remote add origin https://github.com/patrick26-Developer/Backend-Python.git
git push -u origin main
```

---

## 2. Déployer la vitrine sur Render

1. <https://dashboard.render.com> → **New** → **Blueprint**.
2. Connecter le compte GitHub, choisir le dépôt **`Backend-Python`**.
3. Render lit `render.yaml` et propose le service **`fastapi-formation-vitrine`**
   (type *Static Site*, gratuit). Valider **Apply**.
4. Build : `pip install -r requirements-docs.txt && mkdocs build -f mkdocs.showcase.yml`,
   dossier publié `site_showcase/`. ~1–2 min.
5. URL fournie : `https://fastapi-formation-vitrine.onrender.com` (renommable dans les
   *Settings* du service). Chaque `git push` sur `main` redéploie.

### Vérifier avant de pousser

```bash
mkdocs build -f mkdocs.showcase.yml     # doit produire site_showcase/ sans erreur
python -m http.server -d site_showcase 8080   # http://localhost:8080
```

---

## 3. Ajouter au portfolio

Dans <https://portfolio-personnel-ecru.vercel.app/>, ajouter une carte projet :

- **Titre** : Formation « Maîtriser FastAPI »
- **Lien démo** : l'URL Render de la vitrine
- **Lien code** : *(laisser vide — dépôt privé)* ou un dépôt public « extrait » si tu en crées un
- **Stack** : FastAPI · SQLAlchemy 2.0 async · Pydantic v2 · Alembic · pytest · Docker · MkDocs

---

## 4. Livrer la formation complète à un acheteur

Option simple : construire le site complet **hors ligne** et l'envoyer en archive.

```bash
pip install -e ".[docs]"
mkdocs build                    # -> site/  (site complet, navigable hors ligne)
# zipper site/ + le dépôt, ou donner un accès en lecture au dépôt privé GitHub
```

Option « pro » : dépôt privé GitHub → inviter l'acheteur en lecture seule, ou
GitHub Release avec l'archive du site.

---

## 5. Alternatives d'hébergement (si un jour tu changes d'avis)

| Cible | Commande | Note |
|---|---|---|
| **GitHub Pages** | `mkdocs gh-deploy -f mkdocs.showcase.yml` | pousse `site_showcase/` sur la branche `gh-pages` ; activer Pages dans les *Settings* |
| **Vercel** | *Import project* → build `mkdocs build -f mkdocs.showcase.yml` → output `site_showcase` → *Install Command* `pip install -r requirements-docs.txt` | cohérent avec ton portfolio |
| **Cloudflare Pages** | build `pip install -r requirements-docs.txt && mkdocs build -f mkdocs.showcase.yml`, output `site_showcase` | CDN rapide, gratuit |
