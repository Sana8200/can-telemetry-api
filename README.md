# CAN Telemetry API

[![CI](https://github.com/Sana8200/can-telemetry-api/actions/workflows/ci.yml/badge.svg)](https://github.com/Sana8200/can-telemetry-api/actions/workflows/ci.yml)

A Python service that decodes CAN bus frames into physical signals (rpm, °C, volts, amperes) and serves the latest value of each signal over a REST API. It speaks HTTP/2 over TLS, with certificates from a private certificate authority, and runs in a slim container as a non-root user. GitHub Actions lints and tests every push, then builds the image and smoke-tests the running container over HTTPS.

The message definitions are invented for this project and do not describe a real car.

## Run it

Needs Docker and OpenSSL 3.

```bash
bash scripts/make-certs.sh
docker build -t can-telemetry-api .
docker run --rm -p 8443:8443 --user "$(id -u):$(id -g)" \
  -v "$PWD/certs:/certs:ro" \
  -e TLS_CERT_FILE=/certs/server.crt -e TLS_KEY_FILE=/certs/server.key \
  can-telemetry-api
```

In another terminal, send a frame and read a signal back:

```bash
curl --cacert certs/ca.crt -X POST https://localhost:8443/frames \
  -H "Content-Type: application/json" \
  -d '{"frames": [{"id": 256, "data": "B80B695A00000000"}]}'
curl --cacert certs/ca.crt https://localhost:8443/signals/motor_rpm
```

```json
{"decoded":1,"ignored":0}
{"name":"motor_rpm","message":"inverter","value":3000.0,"unit":"rpm","timestamp":1792589865.4}
```

`bash scripts/smoke-test.sh` runs the same checks as CI: HTTP/2, the certificate, and a frame read back.

## TLS

`scripts/make-certs.sh` creates a private CA (`ca.crt`) and a server certificate signed by it, valid for `localhost` and the names of a Kubernetes Service. Clients trust the server by trusting `ca.crt`, and the server offers HTTP/2 during the TLS handshake (ALPN). The keys stay out of git and out of the image: the container gets them through a read-only mount.

## API

| Method | Path | Returns |
|---|---|---|
| `POST` | `/frames` | Decodes a batch of 1–1000 frames and stores the latest value of each signal. Frames with an unknown ID are counted as ignored. One malformed frame rejects the whole batch with 422. |
| `GET` | `/signals` | The latest value of every signal received so far |
| `GET` | `/signals/{name}` | The latest value of one signal; 404 if the name is unknown or nothing has arrived yet |
| `GET` | `/messages` | The message and signal definitions |
| `GET` | `/healthz`, `/readyz` | Health checks |

A frame has a CAN `id` (11 or 29 bits), `data` as 0–8 bytes of hex, and an optional `timestamp` in seconds since 1970 (the arrival time is used if it's missing). An older frame never overwrites a newer value.

## Signal definitions

All signals are little-endian. Physical value = raw × scale + offset.

| ID | Message | Signal | Start bit | Length | Scale | Offset | Unit | Signed |
|---|---|---|---|---|---|---|---|---|
| 0x100 | inverter | motor_rpm | 0 | 16 | 1 | 0 | rpm | no |
| 0x100 | inverter | motor_temp | 16 | 8 | 1 | −40 | degC | no |
| 0x100 | inverter | inverter_temp | 24 | 8 | 1 | −40 | degC | no |
| 0x200 | battery | pack_voltage | 0 | 16 | 0.1 | 0 | V | no |
| 0x200 | battery | pack_current | 16 | 16 | 0.1 | 0 | A | yes |
| 0x200 | battery | state_of_charge | 32 | 8 | 0.5 | 0 | % | no |
| 0x300 | vehicle | speed | 0 | 16 | 0.01 | 0 | km/h | no |
| 0x300 | vehicle | throttle | 16 | 8 | 0.5 | 0 | % | no |

## Development

Needs Python 3.12 or newer.

```bash
git clone https://github.com/Sana8200/can-telemetry-api.git
cd can-telemetry-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
ruff check .
hypercorn app.main:app --reload
```

`pytest` runs the tests, `ruff check .` lints the code, and the last command starts a development server on http://localhost:8000 that restarts when the code changes. Its interactive API docs are at http://localhost:8000/docs.

To run the real server with TLS outside Docker:

```bash
TLS_CERT_FILE=certs/server.crt TLS_KEY_FILE=certs/server.key python -m app
```

## Project layout

```
app/
  signals.py          message and signal definitions
  can_decode.py       Frame, extract_raw() and decode()
  store.py            thread-safe store of the latest values
  main.py             REST API (FastAPI)
  __main__.py         python -m app: HTTPS with HTTP/2, clean shutdown on SIGTERM
tests/
  test_decode.py      decoder tests
  test_api.py         API tests
  test_server_config.py
scripts/
  make-certs.sh       private CA and server certificate
  smoke-test.sh       checks a running server: TLS, HTTP/2, ingest, read back
Dockerfile            slim image that runs as uid 10001
.github/workflows/
  ci.yml              lint and test, then build the image and smoke-test it over HTTPS
```

## Roadmap

- [x] Decode CAN frames into physical signals, with tests
- [x] Lint and test every push with GitHub Actions
- [x] REST API with FastAPI and a thread-safe store of the latest values
- [x] Slim, non-root container image, built and smoke-tested in CI
- [x] HTTP/2 over TLS with certificates from a private CA
- [ ] Deployment to Kubernetes (kind) with a locked-down pod
- [ ] Image published to GitHub Container Registry
- [ ] Driving simulator and `candump -L` log upload