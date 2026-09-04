"""`pollup` — solution de référence du checkpoint (après Module 07).

Sondages : questions, options, votes. Construit en TDD (une règle métier = un test écrit
d'abord). Architecture en couches : `api → service → repository` (Protocol + implémentation
en mémoire), le service est testé **sans HTTP ni base réelle**.

    uvicorn pollup.api:app --reload
    pytest --cov=pollup
"""

__version__ = "1.0.0"
