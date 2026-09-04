# `linkstash` — solution de référence

Checkpoint d'après le **Module 02**. API de marque-pages, **sans base de données**.

```bash
# depuis ce dossier (le venv du dépôt racine suffit)
python -m uvicorn linkstash.api:app --reload   # http://127.0.0.1:8000/docs
python -m pytest -q                            # 24 tests
python -m mypy linkstash                        # --strict, 0 erreur
```

## Arborescence

```
linkstash/
  __init__.py      version + docstring
  models.py        schémas Pydantic Create/Update/Read + normalisation des tags
  store.py         store en mémoire : unicité d'URL, filtres, tri, pagination, comptage de tags
  api.py           routes fines + handlers d'erreurs (Problem Details), factory create_app()
tests/
  conftest.py      fixture client (store neuf par test)
  test_linkstash.py
```

Détail des décisions : [`SOLUTION.md`](SOLUTION.md). Énoncé : [`../BRIEF.md`](../BRIEF.md).
