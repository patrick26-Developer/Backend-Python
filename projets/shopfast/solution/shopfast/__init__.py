"""`shopfast` — solution de référence (projet de domaine : e-commerce).

Cette solution couvre le **cœur difficile** du domaine, celui que le brief met en avant :

- total de commande **figé** (snapshot du prix) à la création ;
- **stock** décrémenté de façon atomique et conditionnelle (pas de survente) ;
- **webhook de paiement idempotent** (le rejouer ne double pas la commande) ;
- **isolation** des commandes par client (BOLA) ;
- architecture en couches, `ruff` + `mypy --strict` + `pytest` au vert, couverture > 85 %.

Hors périmètre (extensions documentées dans SOLUTION.md) : variantes produit, back-office
analytique, e-mails, panier anonyme.

    alembic upgrade head        # ou : le schéma est créé au démarrage en dev
    uvicorn shopfast.main:app --reload
    pytest
"""

__version__ = "1.0.0"
