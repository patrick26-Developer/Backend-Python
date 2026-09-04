# `pollup` — solution de référence

Checkpoint d'après le **Module 07**. Sondages construits en **TDD**.

```bash
# depuis ce dossier (le venv du dépôt racine suffit)
python -m uvicorn pollup.api:app --reload   # http://127.0.0.1:8000/docs
python -m pytest                            # tests + couverture (échoue si < 90 %)
python -m mypy pollup                        # --strict, 0 erreur
```

Auth « simple par token » : `Authorization: Bearer <identité>` — le jeton **est** l'identité
(du créateur, du votant). Pas de JWT (hors périmètre).

## Arborescence

```
pollup/
  models.py       entités du domaine (dataclasses) : Poll, Option ; règles is_closed / counts
  schemas.py      contrats d'API + validation (2..10 options, closes_at futur & aware…)
  errors.py       erreurs métier découplées de HTTP
  repository.py   Protocol + implémentation en mémoire (le service ne dépend que du Protocol)
  service.py      TOUTES les règles ; testé sans HTTP
  api.py          routes fines + 1 handler qui mappe erreur → code via un dict
tests/
  test_service.py  une règle métier = un test (ordre TDD)
  test_api.py      intégration : codes HTTP, auth par token
```

Décisions : [`SOLUTION.md`](SOLUTION.md). Énoncé : [`../BRIEF.md`](../BRIEF.md).
