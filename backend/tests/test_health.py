def test_health_check(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"


def test_unknown_route_uses_error_envelope(client):
    resp = client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["success"] is False
    assert "message" in body["error"]
