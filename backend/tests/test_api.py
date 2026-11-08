import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import PROBLEM


@pytest.fixture
def client(runs):
    with TestClient(create_app(runs)) as c:
        yield c


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["mock_mode"] is True and body["models"] == 4


def test_solve_and_history(client):
    result = client.post("/api/solve", json={"problem": PROBLEM, "language": "python"}).json()
    assert result["status"] == "accepted"
    runs = client.get("/api/runs").json()
    assert runs[0]["run_id"] == result["run_id"] and runs[0]["passed"] == 9
    assert client.get(f"/api/runs/{result['run_id']}").json()["final"]["code"]
    assert client.get("/api/runs/nope").status_code == 404


def test_solve_stream_sse(client):
    with client.stream("POST", "/api/solve/stream", json={"problem": PROBLEM}) as resp:
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = [json.loads(line[6:]) for line in resp.iter_lines() if line.startswith("data: ")]
    assert events[0]["type"] == "start" and events[-1]["type"] == "result"
    assert events[-1]["result"]["status"] == "accepted"


def test_validation_errors(client):
    assert client.post("/api/solve", json={"problem": "short"}).status_code == 422
    assert client.post("/api/solve", json={"problem": PROBLEM, "language": "java"}).status_code == 422


def test_execute_endpoint(client):
    body = client.post("/api/execute", json={
        "language": "python", "code": "print(int(input()) + 1)",
        "tests": [{"input": "1", "expected_output": "2"}, {"input": "5", "expected_output": "7"}],
    }).json()
    assert body["passed"] == 1 and body["verdicts"] == {"AC": 1, "WA": 1}


def test_models_routing_and_telemetry(client):
    client.post("/api/solve", json={"problem": PROBLEM})
    models = client.get("/api/models", params={"task": "repair"}).json()
    assert len(models["ranking"]) == 4 and "breakdown" in models["ranking"][0]
    assert client.get("/api/models", params={"task": "nope"}).status_code == 400
    preview = client.get("/api/routing/preview").json()
    assert set(preview) >= {"planning", "coding", "repair"} and preview["coding"]["chosen"]
    telemetry = client.get("/api/telemetry").json()
    assert sum(m["calls"] for m in telemetry.values()) >= 7
    assert client.delete("/api/telemetry").json() == {"reset": True}
    assert client.get("/api/telemetry").json() == {}
