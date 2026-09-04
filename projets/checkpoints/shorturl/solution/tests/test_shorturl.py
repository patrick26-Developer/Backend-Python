"""Tests de `shorturl` — couvrent la Definition of Done du brief."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from httpx import AsyncClient
from shorturl.errors import AliasTakenError
from shorturl.models import LinkRow
from shorturl.repository import LinkRepository
from shorturl.service import LinkService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


# --- création -----------------------------------------------------------
def test_create_auto_alias(client: TestClient) -> None:
    r = client.post("/links", json={"url": "https://example.org/page"})
    assert r.status_code == 201
    body = r.json()
    assert len(body["alias"]) == 5  # alias_length de la fixture settings
    assert body["short_url"] == f"http://sho.rt/{body['alias']}"
    assert body["target_url"] == "https://example.org/page"


def test_create_custom_alias(client: TestClient) -> None:
    r = client.post("/links", json={"url": "https://example.org", "custom_alias": "my-link_1"})
    assert r.status_code == 201
    assert r.json()["alias"] == "my-link_1"


def test_custom_alias_conflict_is_409(client: TestClient) -> None:
    client.post("/links", json={"url": "https://a.example", "custom_alias": "taken"})
    r = client.post("/links", json={"url": "https://b.example", "custom_alias": "taken"})
    assert r.status_code == 409
    assert r.headers["content-type"].startswith("application/problem+json")


def test_invalid_custom_alias_is_422(client: TestClient) -> None:
    r = client.post("/links", json={"url": "https://a.example", "custom_alias": "no"})  # < 3 car.
    assert r.status_code == 422


def test_invalid_url_is_422(client: TestClient) -> None:
    assert client.post("/links", json={"url": "ftp://nope"}).status_code == 422


# --- redirection -------------------------------------------------------
def test_redirect_is_302_and_counts_click(client: TestClient) -> None:
    alias = client.post("/links", json={"url": "https://target.example/x"}).json()["alias"]

    r = client.get(f"/{alias}")
    assert r.status_code == 302
    assert r.headers["location"] == "https://target.example/x"

    stats = client.get(f"/links/{alias}/stats").json()
    assert stats["clicks"] == 1
    assert stats["last_clicked_at"] is not None


def test_unknown_alias_is_404(client: TestClient) -> None:
    assert client.get("/does-not-exist").status_code == 404


def test_expired_link_is_410(client: TestClient) -> None:
    past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    alias = client.post("/links", json={"url": "https://old.example", "expires_at": past}).json()[
        "alias"
    ]
    assert client.get(f"/{alias}").status_code == 410


def test_naive_expires_at_is_422(client: TestClient) -> None:
    r = client.post(
        "/links", json={"url": "https://x.example", "expires_at": "2999-01-01T00:00:00"}
    )
    assert r.status_code == 422


# --- stats / delete --------------------------------------------------
def test_stats_shape(client: TestClient) -> None:
    alias = client.post("/links", json={"url": "https://s.example"}).json()["alias"]
    stats = client.get(f"/links/{alias}/stats").json()
    assert set(stats) == {
        "alias",
        "target_url",
        "clicks",
        "created_at",
        "last_clicked_at",
        "expires_at",
    }
    assert stats["clicks"] == 0


def test_delete(client: TestClient) -> None:
    alias = client.post("/links", json={"url": "https://d.example"}).json()["alias"]
    assert client.delete(f"/links/{alias}").status_code == 204
    assert client.get(f"/{alias}").status_code == 404
    assert client.delete(f"/links/{alias}").status_code == 404


# --- concurrence & isolation (niveau service/repo) -------------------
async def test_repeated_creates_never_duplicate_alias(
    session_factory: async_sessionmaker[AsyncSession], settings
) -> None:  # type: ignore[no-untyped-def]
    """Plusieurs créations du même alias : une seule réussit — la contrainte d'unicité de la
    base tranche, l'`IntegrityError` est géré en `AliasTakenError`.

    On enchaîne les tentatives (SQLite en mémoire = une connexion partagée, pas de vraie
    concurrence). Sur PostgreSQL, `test_postgres`-style, ce serait un vrai `asyncio.gather` ;
    le résultat est identique car la garantie vient de l'index unique, pas du code Python.
    """
    successes = 0
    for _ in range(8):
        async with session_factory() as session:
            svc = LinkService(LinkRepository(session), settings)
            try:
                await svc.create(
                    target_url="https://c.example", custom_alias="race", expires_at=None
                )
                await session.commit()
                successes += 1
            except AliasTakenError:
                await session.rollback()

    assert successes == 1
    async with session_factory() as session:
        rows = (await session.scalars(select(LinkRow).where(LinkRow.alias == "race"))).all()
    assert len(rows) == 1


async def test_click_increment_failure_does_not_break_resolve(
    async_client: AsyncClient, app
) -> None:  # type: ignore[no-untyped-def]
    """Si l'incrément de clics échoue, la redirection reste bonne."""
    created = (await async_client.post("/links", json={"url": "https://r.example/x"})).json()

    # on casse la fabrique de sessions utilisée par la tâche de fond
    broken = app.state.session_factory
    app.state.session_factory = None  # type: ignore[assignment]
    try:
        r = await async_client.get(f"/{created['alias']}")
        assert r.status_code == 302
        assert r.headers["location"] == created["target_url"]
    finally:
        app.state.session_factory = broken


def test_openapi(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/links" in paths and "/{alias}" in paths and "/links/{alias}/stats" in paths
