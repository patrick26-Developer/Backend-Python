"""File de tâches (taskiq).

- sans `APP_REDIS_URL` : `InMemoryBroker` — les tâches s'exécutent dans le process
  (dev, tests) ;
- avec `APP_REDIS_URL` : `ListQueueBroker` Redis — l'API publie, un ou plusieurs
  process `worker` consomment (`taskiq worker taskman.tasks:broker`).

Les tâches doivent être **idempotentes** : le broker garantit *at-least-once*, donc
une tâche peut s'exécuter deux fois.
"""

from __future__ import annotations

import logging

from taskiq import AsyncBroker, InMemoryBroker

from taskman.core.config import get_settings

_logger = logging.getLogger("taskman.tasks")


def _build_broker() -> AsyncBroker:
    url = get_settings().redis_url
    if url:
        from taskiq_redis import ListQueueBroker

        return ListQueueBroker(url)
    return InMemoryBroker()


broker: AsyncBroker = _build_broker()


@broker.task
async def notify_task_completed(task_id: int, assignee_email: str | None) -> None:
    """Envoi (simulé) d'une notification. Idempotent : ré-exécuter ne fait
    qu'écrire une ligne de log de plus, aucun effet de bord irréversible."""
    _logger.info(
        "notification: task completed",
        extra={"event": "task.completed", "task_id": task_id, "assignee": assignee_email},
    )
