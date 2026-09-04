"""Couche HTTP. Auth « simple par token » : `Authorization: Bearer <identité opaque>`.

Pas de JWT ici (hors périmètre du checkpoint) : le token EST l'identité du votant / créateur.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from pollup import __version__
from pollup.errors import (
    AlreadyVotedError,
    NotPollOwnerError,
    OptionNotFoundError,
    PollClosedError,
    PollError,
    PollNotFoundError,
    ResultsHiddenError,
)
from pollup.models import Poll
from pollup.repository import InMemoryPollRepository, PollRepository
from pollup.schemas import OptionRead, PollCreate, PollRead, PollResults, VoteCreate
from pollup.service import PollService

_ERROR_STATUS: dict[type[PollError], int] = {
    PollNotFoundError: status.HTTP_404_NOT_FOUND,
    OptionNotFoundError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    PollClosedError: status.HTTP_409_CONFLICT,
    AlreadyVotedError: status.HTTP_409_CONFLICT,
    NotPollOwnerError: status.HTTP_403_FORBIDDEN,
    ResultsHiddenError: status.HTTP_409_CONFLICT,
}


def get_repo(request: Request) -> PollRepository:
    repo: PollRepository = request.app.state.repo
    return repo


RepoDep = Annotated[PollRepository, Depends(get_repo)]


def get_service(repo: RepoDep) -> PollService:
    return PollService(repo)


ServiceDep = Annotated[PollService, Depends(get_service)]


def require_identity(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "jeton d'identité requis")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "jeton vide")
    return token


def optional_identity(authorization: Annotated[str | None, Header()] = None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


IdentityDep = Annotated[str, Depends(require_identity)]
OptionalIdentityDep = Annotated[str | None, Depends(optional_identity)]


def _poll_read(poll: Poll) -> PollRead:
    return PollRead(
        id=poll.id,
        question=poll.question,
        options=[OptionRead(id=o.id, label=o.label) for o in poll.options],
        total_votes=poll.total_votes,
        closes_at=poll.closes_at,
        is_closed=poll.is_closed,
    )


def create_app() -> FastAPI:
    app = FastAPI(title="pollup", version=__version__, summary="Sondages (checkpoint Module 07).")
    app.state.repo = InMemoryPollRepository()

    @app.exception_handler(PollError)
    async def _domain_error(request: Request, exc: PollError) -> JSONResponse:
        code = _ERROR_STATUS.get(type(exc), status.HTTP_400_BAD_REQUEST)
        return JSONResponse(
            status_code=code,
            content={
                "type": "about:blank",
                "title": str(exc) or type(exc).__name__,
                "status": code,
            },
            media_type="application/problem+json",
        )

    @app.post("/polls", status_code=status.HTTP_201_CREATED, response_model=PollRead)
    async def create_poll(payload: PollCreate, service: ServiceDep, owner: IdentityDep) -> PollRead:
        poll = service.create_poll(
            question=payload.question,
            options=payload.options,
            owner=owner,
            closes_at=payload.closes_at,
            hide_results_until_closed=payload.hide_results_until_closed,
        )
        return _poll_read(poll)

    @app.get("/polls/{poll_id}", response_model=PollRead)
    async def read_poll(poll_id: int, service: ServiceDep) -> PollRead:
        return _poll_read(service.get_poll(poll_id))

    @app.post("/polls/{poll_id}/votes", status_code=status.HTTP_204_NO_CONTENT)
    async def cast_vote(
        poll_id: int, payload: VoteCreate, service: ServiceDep, voter: IdentityDep
    ) -> None:
        service.vote(poll_id, voter=voter, option_id=payload.option_id)

    @app.get("/polls/{poll_id}/results", response_model=PollResults)
    async def poll_results(
        poll_id: int, service: ServiceDep, requester: OptionalIdentityDep
    ) -> PollResults:
        return service.results(poll_id, requester=requester)

    @app.delete("/polls/{poll_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_poll(poll_id: int, service: ServiceDep, requester: IdentityDep) -> None:
        service.delete_poll(poll_id, requester=requester)

    return app


app = create_app()
