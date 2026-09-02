"""Routes d'administration — réservées au rôle `admin`.

La dépendance `require_role(UserRole.admin)` est posée sur **le router entier** :
toutes ses routes exigent un administrateur. Un `member` reçoit 403.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from taskman.api.deps import get_user_repository, require_role
from taskman.repositories import UserRepository
from taskman.schemas import UserRead, UserRole

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role(UserRole.admin))],
)


@router.get("/users")
async def list_users(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserRead]:
    rows, _ = await users.list(limit=limit, offset=offset)
    return [UserRead.model_validate(r) for r in rows]
