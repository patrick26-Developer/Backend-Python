"""Notifications — abstraction minimale.

`Notifier` est un `Protocol` : le service dépend de l'interface, pas d'un client
e-mail concret. `LoggingNotifier` (défaut) écrit une ligne de log structurée ;
en prod on brancherait un vrai fournisseur (SES, Sendgrid…).
"""

from __future__ import annotations

import logging
from typing import Protocol

from taskman.schemas import TaskRead

_logger = logging.getLogger("taskman.notifications")


class Notifier(Protocol):
    async def task_completed(self, task: TaskRead) -> None: ...


class LoggingNotifier:
    async def task_completed(self, task: TaskRead) -> None:
        _logger.info(
            "task completed",
            extra={
                "event": "task.completed",
                "task_id": task.id,
                "project_id": task.project_id,
                "assignee": task.assignee_email,
            },
        )
