"""`statuspage` — solution de référence du checkpoint (après Module 09).

Mini « statuspage.io » : surveille des services HTTP, publie leur statut.
Valide : logs structurés corrélés, métriques Prometheus, `/health` vs `/ready`,
worker périodique, config 12-factor.

    alembic upgrade head
    uvicorn statuspage.api:app --reload      # API + worker de sonde
    pytest
"""

__version__ = "1.0.0"
