"""La dépendance `get_session` : une session par requête HTTP.

C'est une dépendance `Depends` **avec `yield`** :
- avant `yield` : ouvre une session ;
- `yield`      : la fournit à la route / au repository ;
- après        : ferme la session (le `async with` s'en charge, y compris en cas
  d'exception — les changements non committés sont alors abandonnés).

Le **commit** n'a pas lieu ici : c'est le *service* qui décide quand valider
(frontière transactionnelle). Voir `taskman/services/`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session
