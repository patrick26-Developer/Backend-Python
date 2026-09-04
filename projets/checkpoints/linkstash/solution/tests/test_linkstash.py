"""Tests de la solution `linkstash`. Couvrent chaque point de la Definition of Done."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create(client: TestClient, **over: object) -> dict[str, object]:
    body = {"url": "https://example.org/a", "title": "A"}
    body.update(over)
    r = client.post("/bookmarks", json=body)
    assert r.status_code == 201, r.text
    return r.json()


# --- création --------------------------------------------------------------
def test_create_returns_201_location_and_normalizes_tags(client: TestClient, sample: dict) -> None:
    r = client.post("/bookmarks", json=sample)
    assert r.status_code == 201
    assert r.headers["Location"] == f"/bookmarks/{r.json()['id']}"
    body = r.json()
    assert body["tags"] == ["python", "fastapi"]  # dédupliqué + minuscules, ordre gardé
    assert body["created_at"].endswith(("Z", "+00:00"))


def test_invalid_url_is_422(client: TestClient) -> None:
    r = client.post("/bookmarks", json={"url": "not-a-url", "title": "X"})
    assert r.status_code == 422


def test_duplicate_url_is_409_even_with_trailing_slash(client: TestClient) -> None:
    _create(client, url="https://dup.example/page")
    r = client.post("/bookmarks", json={"url": "https://dup.example/page/", "title": "Autre"})
    assert r.status_code == 409
    assert r.headers["content-type"].startswith("application/problem+json")


def test_blank_title_is_422(client: TestClient) -> None:
    r = client.post("/bookmarks", json={"url": "https://x.io", "title": "   "})
    assert r.status_code == 422


# --- lecture / 404 --------------------------------------------------------
def test_get_missing_is_404(client: TestClient) -> None:
    assert client.get("/bookmarks/999").status_code == 404


# --- PATCH --------------------------------------------------------------
def test_patch_empty_body_changes_nothing(client: TestClient) -> None:
    created = _create(client, note="garde-moi")
    r = client.patch(f"/bookmarks/{created['id']}", json={})
    assert r.status_code == 200
    assert r.json()["note"] == "garde-moi"


def test_patch_note_null_clears_it(client: TestClient) -> None:
    created = _create(client, note="à effacer")
    r = client.patch(f"/bookmarks/{created['id']}", json={"note": None})
    assert r.status_code == 200
    assert r.json()["note"] is None


def test_patch_title_null_is_rejected(client: TestClient) -> None:
    created = _create(client)
    assert client.patch(f"/bookmarks/{created['id']}", json={"title": None}).status_code == 422


def test_patch_unknown_field_is_422(client: TestClient) -> None:
    created = _create(client)
    r = client.patch(f"/bookmarks/{created['id']}", json={"favourite": True})  # typo
    assert r.status_code == 422


def test_patch_url_to_existing_is_409(client: TestClient) -> None:
    a = _create(client, url="https://one.example")
    _create(client, url="https://two.example")
    r = client.patch(f"/bookmarks/{a['id']}", json={"url": "https://two.example"})
    assert r.status_code == 409


def test_patch_missing_is_404(client: TestClient) -> None:
    assert client.patch("/bookmarks/999", json={"title": "x"}).status_code == 404


# --- filtres / tri / pagination ----------------------------------------
def test_filters_combine(client: TestClient) -> None:
    _create(client, url="https://p1.example", title="Python rocks", tags=["python"], favorite=True)
    _create(client, url="https://p2.example", title="Python meh", tags=["python"], favorite=False)
    _create(client, url="https://g1.example", title="Go", tags=["go"], favorite=True)

    r = client.get("/bookmarks", params={"tag": "python", "favorite": True})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Python rocks"


def test_full_text_search_hits_title_and_note(client: TestClient) -> None:
    _create(client, url="https://n1.example", title="Rien", note="contient le mot cactus")
    _create(client, url="https://n2.example", title="cactus dans le titre")
    _create(client, url="https://n3.example", title="sans rapport")
    assert client.get("/bookmarks", params={"q": "cactus"}).json()["total"] == 2


def test_sort_by_title_and_pagination(client: TestClient) -> None:
    for i, name in enumerate(["Charlie", "alpha", "Bravo"]):
        _create(client, url=f"https://s{i}.example", title=name)
    r = client.get("/bookmarks", params={"sort": "title", "limit": 2, "offset": 0})
    body = r.json()
    assert [b["title"] for b in body["items"]] == ["alpha", "Bravo"]
    assert body["total"] == 3
    page2 = client.get("/bookmarks", params={"sort": "title", "limit": 2, "offset": 2}).json()
    assert [b["title"] for b in page2["items"]] == ["Charlie"]


def test_default_sort_is_newest_first(client: TestClient) -> None:
    first = _create(client, url="https://d1.example", title="premier")
    second = _create(client, url="https://d2.example", title="second")
    ids = [b["id"] for b in client.get("/bookmarks").json()["items"]]
    assert ids == [second["id"], first["id"]]


def test_bad_sort_key_is_422(client: TestClient) -> None:
    assert client.get("/bookmarks", params={"sort": "nope"}).status_code == 422


# --- DELETE --------------------------------------------------------------
def test_delete_then_gone(client: TestClient) -> None:
    created = _create(client)
    assert client.delete(f"/bookmarks/{created['id']}").status_code == 204
    assert client.get(f"/bookmarks/{created['id']}").status_code == 404
    assert client.delete(f"/bookmarks/{created['id']}").status_code == 404


# --- /tags --------------------------------------------------------------
def test_tags_endpoint_counts_distinct_tags(client: TestClient) -> None:
    _create(client, url="https://t1.example", tags=["python", "web"])
    _create(client, url="https://t2.example", tags=["python"])
    _create(client, url="https://t3.example", tags=["go"])
    rows = client.get("/tags").json()
    assert rows == [
        {"tag": "python", "count": 2},
        {"tag": "go", "count": 1},
        {"tag": "web", "count": 1},
    ]


def test_openapi_is_served(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "/bookmarks" in schema["paths"]
    assert "/tags" in schema["paths"]
