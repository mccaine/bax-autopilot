"""ProjectStore in-memory fallback (psycopg_pool absent → memory path)."""

from autopilot.store import ProjectStore


def test_store_crud_in_memory():
    # In the test env psycopg_pool isn't installed, so the store uses its
    # in-memory fallback — exactly the path we assert here.
    store = ProjectStore("postgresql://unused")
    assert store._pool is None

    store.create("r1", "build a todo app")
    store.create("r2", "build a blog")

    got = store.get("r1")
    assert got["intent"] == "build a todo app"
    assert got["status"] == "queued"

    store.update("r1", status="running", phase="spec", name="todo")
    store.update("r1", status="done", phase="done", pr_url="http://pr")
    got = store.get("r1")
    assert got["status"] == "done"
    assert got["name"] == "todo"
    assert got["pr_url"] == "http://pr"

    # Unknown key ignored, no crash.
    store.update("r1", bogus="x")

    ids = {p["run_id"] for p in store.list()}
    assert ids == {"r1", "r2"}
    assert store.get("missing") is None
