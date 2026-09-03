"""API v2 — démonstration de coexistence de versions (Module 12).

`/v1` et `/v2` tournent **en même temps**. `/v2` illustre un **changement de
contrat** : `GET /v2/tasks/{id}` renvoie un résumé plat (`checklist_total` /
`checklist_done`) au lieu de la liste complète `checklist`.

En pratique on ne dupliquerait pas tout le CRUD : on partage la couche service et
on adapte seulement les schémas qui changent.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from taskman.api.deps import TaskServiceDep
from taskman.api.routes.tasks import TaskId
from taskman.schemas import TaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks (v2)"])


class TaskReadV2(BaseModel):
    """Contrat v2 : la checklist est résumée, `is_overdue` renommé `overdue`."""

    id: int
    project_id: int
    title: str
    status: TaskStatus
    overdue: bool
    checklist_total: int
    checklist_done: int
    created_at: datetime


@router.get("/{task_id}")
async def get_task_v2(task_id: TaskId, service: TaskServiceDep) -> TaskReadV2:
    task = await service.get(task_id)  # même couche service que v1
    return TaskReadV2(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        status=task.status,
        overdue=task.is_overdue,
        checklist_total=len(task.checklist),
        checklist_done=sum(1 for item in task.checklist if item.done),
        created_at=task.created_at,
    )
