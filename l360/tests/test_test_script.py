"""Founder test-script marks (temporary feature — see routers/test_script.py)."""


def test_mark_flow_and_shared_visibility(admin_client, educator_client):
    # Educator marks one item as a problem, with a note.
    r = educator_client.put("/api/test-script/b2", json={"state": "flag", "note": "band did not move"})
    assert r.status_code == 200

    # Admin marks the same item fine for themselves.
    assert admin_client.put("/api/test-script/b2", json={"state": "pass"}).status_code == 200

    # Everyone sees everyone's progress.
    data = educator_client.get("/api/test-script").json()
    states = {(t["name"], m["item_id"]): (m["state"], m["note"]) for t in data["testers"] for m in t["marks"]}
    assert states[("Test Educator", "b2")] == ("flag", "band did not move")
    assert states[("Test Admin", "b2")] == ("pass", None)

    # Re-marking replaces; None clears.
    assert educator_client.put("/api/test-script/b2", json={"state": "pass"}).status_code == 200
    assert educator_client.put("/api/test-script/b2", json={"state": None}).status_code == 200
    mine = [
        m
        for t in educator_client.get("/api/test-script").json()["testers"]
        for m in t["marks"]
        if t["name"] == "Test Educator"
    ]
    assert mine == []

    # Junk state refused; anonymous refused.
    assert educator_client.put("/api/test-script/b2", json={"state": "maybe"}).status_code == 422
