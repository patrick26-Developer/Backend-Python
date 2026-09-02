"""Hiérarchie d'exceptions **métier**, découplée de HTTP.

Ces exceptions ne connaissent **pas** `fastapi` : elles décrivent un problème du
domaine (« ressource absente », « conflit »). C'est un *exception handler* (voir
`taskman/api/errors.py`) qui les traduit en réponse HTTP normalisée.

`status_code` et `code` sont des indications que le handler exploite — le domaine
n'impose rien, il *suggère*.
"""

from __future__ import annotations


class DomainError(Exception):
    """Racine de toutes les erreurs métier de taskman."""

    status_code: int = 400
    code: str = "domain_error"
    title: str = "Erreur métier"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"
    title = "Ressource introuvable"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"
    title = "Conflit"


class PermissionDeniedError(DomainError):
    status_code = 403
    code = "permission_denied"
    title = "Accès refusé"


# --- Erreurs spécifiques (donnent un `code` précis, exploitable côté client) ---


class TaskNotFoundError(NotFoundError):
    code = "task_not_found"

    def __init__(self, task_id: int) -> None:
        super().__init__(f"Tâche {task_id} introuvable")
        self.task_id = task_id


class ProjectNotFoundError(NotFoundError):
    code = "project_not_found"

    def __init__(self, project_id: int) -> None:
        super().__init__(f"Projet {project_id} introuvable")
        self.project_id = project_id
