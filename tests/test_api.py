import pytest
from fastapi.testclient import TestClient

from app.main import create_app

INVERTER = "B80B695A00000000"  # 3000 rpm, motor 65 degC, inverter 50 degC


@pytest.fixture
def client():
    return TestClient(create_app())


def test_health_endpoints(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}


def test_ingest_then_read_signal(client):
    frames = [{"id": 0x100, "data": INVERTER, "timestamp": 100.0}]
    response = client.post("/frames", json={"frames": frames})
    assert response.status_code == 200
    assert response.json() == {"decoded": 1, "ignored": 0}
    assert client.get("/signals/motor_rpm").json() == {
        "name": "motor_rpm",
        "message": "inverter",
        "value": 3000.0,
        "unit": "rpm",
        "timestamp": 100.0,
    }


def test_unknown_ids_are_counted_not_stored(client):
    frames = [{"id": 0x7FF, "data": "00"}]
    response = client.post("/frames", json={"frames": frames})
    assert response.json() == {"decoded": 0, "ignored": 1}
    assert client.get("/signals").json() == []


def test_one_bad_frame_rejects_the_whole_batch(client):
    # Frame 0 is fine, but frame 1 is a battery frame with 1 byte instead of 8
    frames = [{"id": 0x100, "data": INVERTER}, {"id": 0x200, "data": "00"}]
    response = client.post("/frames", json={"frames": frames})
    assert response.status_code == 422
    assert response.json()["detail"].startswith("frame 1:")
    # The good frame was not stored either
    assert client.get("/signals").json() == []


def test_unknown_signal_and_missing_data_are_404(client):
    assert client.get("/signals/warp_drive").status_code == 404  # no such signal
    assert client.get("/signals/motor_rpm").status_code == 404  # real signal, no value yet
