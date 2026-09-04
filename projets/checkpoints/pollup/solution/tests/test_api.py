"""Tests d'intégration : les endpoints, les codes HTTP, l'auth par token."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create(client: TestClient, token: str = "alice", **over: object) -> dict:
    body: dict[str, object] = {"question": "Q ?", "options": ["a", "b", "c"]}
    body.update(over)
    r = client.post("/polls", json=body, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()


def test_create_requires_token(client: TestClient) -> None:
    assert client.post("/polls", json={"question": "Q", "options": ["a", "b"]}).status_code == 401


def test_create_validates_options(client: TestClient) -> None:
    assert (
        client.post(
            "/polls", json={"question": "Q", "options": ["a"]}, headers=auth("x")
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/polls", json={"question": "Q", "options": ["a", "a"]}, headers=auth("x")
        ).status_code
        == 422
    )


def test_create_rejects_past_closes_at(client: TestClient) -> None:
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    r = client.post(
        "/polls",
        json={"question": "Q", "options": ["a", "b"], "closes_at": past},
        headers=auth("x"),
    )
    assert r.status_code == 422


def test_full_vote_flow(client: TestClient) -> None:
    poll = _create(client)
    opt = poll["options"][0]["id"]

    assert (
        client.post(
            f"/polls/{poll['id']}/votes", json={"option_id": opt}, headers=auth("bob")
        ).status_code
        == 204
    )
    # bob revote → 409
    assert (
        client.post(
            f"/polls/{poll['id']}/votes", json={"option_id": opt}, headers=auth("bob")
        ).status_code
        == 409
    )

    got = client.get(f"/polls/{poll['id']}").json()
    assert got["total_votes"] == 1


def test_vote_requires_token(client: TestClient) -> None:
    poll = _create(client)
    opt = poll["options"][0]["id"]
    assert client.post(f"/polls/{poll['id']}/votes", json={"option_id": opt}).status_code == 401


def test_vote_unknown_poll_404(client: TestClient) -> None:
    assert (
        client.post("/polls/999/votes", json={"option_id": 1}, headers=auth("bob")).status_code
        == 404
    )


def test_vote_foreign_option_422(client: TestClient) -> None:
    a = _create(client)
    b = _create(client)
    foreign = b["options"][0]["id"]
    r = client.post(f"/polls/{a['id']}/votes", json={"option_id": foreign}, headers=auth("bob"))
    assert r.status_code == 422


def test_results_endpoint(client: TestClient) -> None:
    poll = _create(client)
    o0, o1 = poll["options"][0]["id"], poll["options"][1]["id"]
    client.post(f"/polls/{poll['id']}/votes", json={"option_id": o0}, headers=auth("u1"))
    client.post(f"/polls/{poll['id']}/votes", json={"option_id": o1}, headers=auth("u2"))

    res = client.get(f"/polls/{poll['id']}/results").json()
    assert res["total_votes"] == 2
    assert {r["percent"] for r in res["results"] if r["option_id"] in (o0, o1)} == {50.0}


def test_hidden_results_flow(client: TestClient) -> None:
    poll = _create(client, token="alice", hide_results_until_closed=True)
    pid = poll["id"]
    # étranger : 409
    assert client.get(f"/polls/{pid}/results").status_code == 409
    # créateur : 200
    assert client.get(f"/polls/{pid}/results", headers=auth("alice")).status_code == 200


def test_delete_only_by_owner(client: TestClient) -> None:
    poll = _create(client, token="alice")
    assert client.delete(f"/polls/{poll['id']}", headers=auth("mallory")).status_code == 403
    assert client.delete(f"/polls/{poll['id']}", headers=auth("alice")).status_code == 204
    assert client.get(f"/polls/{poll['id']}").status_code == 404


def test_openapi(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/polls", "/polls/{poll_id}", "/polls/{poll_id}/votes", "/polls/{poll_id}/results"):
        assert p in paths
