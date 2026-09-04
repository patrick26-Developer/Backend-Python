"""`shorturl` — solution de référence du checkpoint (après Module 04).

Raccourcisseur d'URL : SQLAlchemy 2.0 async + Alembic + architecture en couches.
Valide : migrations, repository pattern, contrainte d'unicité + `IntegrityError`,
transaction = une requête, redirections HTTP, incrément de clics non bloquant.

    alembic upgrade head
    uvicorn shorturl.api:app --reload
    pytest
"""

__version__ = "1.0.0"
