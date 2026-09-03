"""Point d'entrée du worker taskiq.

Démarrer (nécessite APP_REDIS_URL) :
    taskiq worker taskman.worker:broker

Le worker importe `taskman.tasks` pour enregistrer les tâches, puis consomme la
file. Plusieurs workers peuvent tourner en parallèle.
"""

from __future__ import annotations

from taskman.tasks import broker  # noqa: F401  (ré-exporté pour la CLI taskiq)
