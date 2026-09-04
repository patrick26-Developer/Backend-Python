"""`linkstash` — solution de référence du checkpoint (après Module 02).

API de marque-pages personnels, **sans base de données** (store en mémoire, comme au
Module 01). Objectif : valider routing, schémas `Create/Update/Read`, `response_model`,
validation avancée, `PATCH` correct (null explicite), pagination, filtres.

Lancer :  uvicorn linkstash.api:app --reload
Tester :  pytest
"""

__version__ = "1.0.0"
