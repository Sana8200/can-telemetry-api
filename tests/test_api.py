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
    response = client.post("/frames", json={"frames": [{"id": 0x7FF, "data": "00"}]})
    assert response.json() == {"decoded": 0, "ignored": 1}
    assert client.get("/signals").json() == []


def test_one_bad_frame_rejects_the_whole_batch(client):
    frames = [{"id": 0x100, "data": INVERTER}, {"id": 0x200, "data": "00"}]
    response = client.post("/frames", json={"frames": frames})
    assert response.status_code == 422
    assert response.json()["detail"].startswith("frame 1:")
    assert client.get("/signals").json() == []


def test_unknown_signal_and_missing_data_are_404(client):
    assert client.get("/signals/warp_drive").status_code == 404
    assert client.get("/signals/motor_rpm").status_code == 404  # defined, but nothing received


@pytest.mark.parametrize(
    "frame",
    [
        {"id": 0x100, "data": "XYZ0"},  # not hex
        {"id": 0x100, "data": "B80"},  # half a byte
        {"id": 0x100, "data": "00" * 9},  # more than 8 bytes
        {"id": 0x20000000, "data": "00"},  # more than 29 bits
    ],
)
def test_malformed_frames_are_rejected(client, frame):
    assert client.post("/frames", json={"frames": [frame]}).status_code == 422


def test_older_frame_does_not_overwrite_newer(client):
    newer = {"id": 0x100, "data": INVERTER, "timestamp": 200.0}  # 3000 rpm
    older = {"id": 0x100, "data": "E803000000000000", "timestamp": 100.0}  # 1000 rpm
    client.post("/frames", json={"frames": [newer]})
    client.post("/frames", json={"frames": [older]})
    assert client.get("/signals/motor_rpm").json()["value"] == 3000.0


@pytest.mark.parametrize("timestamp", ["NaN", "Infinity", "-1", "1e12"])
def test_bad_timestamps_are_rejected(client, timestamp):
    # Raw JSON text: NaN and Infinity can't be written with json=, and Python's parser accepts them
    body = '{"frames": [{"id": 256, "data": "B80B695A00000000", "timestamp": TS}]}'
    body = body.replace("TS", timestamp)
    response = client.post("/frames", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"].startswith("frame 0: timestamp")


def test_messages_lists_definitions(client):
    names = [m["name"] for m in client.get("/messages").json()]
    assert names == ["inverter", "battery", "vehicle"]
