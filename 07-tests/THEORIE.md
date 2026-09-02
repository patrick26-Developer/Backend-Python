# Module 07 — Tests

> 🚧 **En construction** — `THEORIE.md` · `PAS-A-PAS.md` · `exercices/` · `solutions/`.

## Objectif

Une suite **rapide, déterministe, qui donne confiance pour refactorer**. La testabilité est
une propriété d'architecture, pas un ajout.

## Pages de doc FastAPI couvertes

Testing · Async Tests · Testing Dependencies with Overrides · Testing Events: lifespan and
startup/shutdown · Testing WebSockets · How-To « Testing a Database » · Debugging (annexe) ·
Reference : `Test Client - TestClient`.

## Plan

1. Pyramide : unitaire (services purs) vs intégration (API + DB) vs e2e.
2. `pytest` : fixtures, *scopes*, `parametrize`, marqueurs, `conftest.py`.
3. `httpx.AsyncClient` + `ASGITransport` : tester l'app sans serveur réseau.
4. Base de test : rollback par test, ou base jetable par session, `testcontainers`.
5. Données : *factories*, *builders*, *fixtures* composables.
6. `dependency_overrides` : *fakes* vs *mocks*.
7. Couverture : la lire, viser les branches d'erreur, ne pas la fétichiser.
8. TDD : rouge → vert → refactor sur un cas concret.

## Exercices (aperçu)

- Tester la couche service en isolation totale.
- Tests d'intégration de chaque endpoint (passant + erreurs).
- Un cas développé en TDD strict.
- Passer la couverture de `taskman` au-dessus de 85 %.
- **Mini-projet `pollup`** développé entièrement en TDD (voir [`../projets/`](../projets/)).

## Definition of Done

Voir [`../ROADMAP.md`](../ROADMAP.md#module-07--tests-).
