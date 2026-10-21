# CAN Telemetry API

[![CI](https://github.com/Sana8200/can-telemetry-api/actions/workflows/ci.yml/badge.svg)](https://github.com/Sana8200/can-telemetry-api/actions/workflows/ci.yml)

Decodes CAN bus frames into real values (rpm, °C, volts, amps) and serves the latest value of each signal over a REST API. It runs over HTTPS with HTTP/2, using certs from a private CA, in a small non-root container. CI lints and tests every push, then builds the image and smoke-tests it over HTTPS.

The CAN messages are made up for this project, they're not from a real car.

## Running it

Need Docker and OpenSSL.

```bash
bash scripts/make-certs.sh
docker build -t can-telemetry-api .
docker run --rm -p 8443:8443 --user "$(id -u):$(id -g)" \
  -v "$PWD/certs:/certs:ro" \
  -e TLS_CERT_FILE=/certs/server.crt -e TLS_KEY_FILE=/certs/server.key \
  can-telemetry-api
```

Then from another terminal:

```bash
curl --cacert certs/ca.crt -X POST https://localhost:8443/frames \
  -H "Content-Type: application/json" \
  -d '{"frames": [{"id": 256, "data": "B80B695A00000000"}]}'
curl --cacert certs/ca.crt https://localhost:8443/signals/motor_rpm
```

You should get something like:

```json
{"decoded":1,"ignored":0}
{"name":"motor_rpm","message":"inverter","value":3000.0,"unit":"rpm","timestamp":1792589865.4}
```

`bash scripts/smoke-test.sh` does the same checks CI does (HTTP/2, the cert, posting a frame and reading it back).

## TLS

`scripts/make-certs.sh` makes a private CA and a server cert signed by it. The cert covers `localhost` and the Kubernetes service names, so the same one will work in the cluster later. Clients just need to trust `ca.crt`. HTTP/2 is negotiated during the TLS handshake (ALPN).

The keys aren't in git or in the image, the container gets them from a read-only mount.

## API

| Method | Path | |
|---|---|---|
| `POST` | `/frames` | Decode and store a batch of frames (max 1000). Unknown IDs are counted as `ignored`. If any frame is bad, the whole batch gets a 422 and nothing is stored. |
| `GET` | `/signals` | Latest value of every signal seen so far |
| `GET` | `/signals/{name}` | Latest value of one signal. 404 if the name doesn't exist or nothing has come in yet |
| `GET` | `/messages` | Message and signal definitions |
| `GET` | `/healthz`, `/readyz` | Health checks |

Each frame has an `id` (11 or 29 bit), `data` (hex, up to 8 bytes) and an optional `timestamp` in unix time. Without one, the arrival time is used. An older frame won't overwrite a newer value.

## Signals

Everything is little-endian, and value = raw * scale + offset.

| ID | Message | Signal | Start bit | Length | Scale | Offset | Unit | Signed |
|---|---|---|---|---|---|---|---|---|
| 0x100 | inverter | motor_rpm | 0 | 16 | 1 | 0 | rpm | no |
| 0x100 | inverter | motor_temp | 16 | 8 | 1 | -40 | degC | no |
| 0x100 | inverter | inverter_temp | 24 | 8 | 1 | -40 | degC | no |
| 0x200 | battery | pack_voltage | 0 | 16 | 0.1 | 0 | V | no |
| 0x200 | battery | pack_current | 16 | 16 | 0.1 | 0 | A | yes |
| 0x200 | battery | state_of_charge | 32 | 8 | 0.5 | 0 | % | no |
| 0x300 | vehicle | speed | 0 | 16 | 0.01 | 0 | km/h | no |
| 0x300 | vehicle | throttle | 16 | 8 | 0.5 | 0 | % | no |

## Development

Python 3.12+.

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

The last one starts a dev server on http://localhost:8000 that reloads when you change the code. API docs are at http://localhost:8000/docs.

To run it with TLS without Docker:

```bash
TLS_CERT_FILE=certs/server.crt TLS_KEY_FILE=certs/server.key python -m app
```

## Layout

```
app/
  signals.py          message/signal definitions
  can_decode.py       decoding
  store.py            latest value of each signal
  main.py             the API (FastAPI)
  __main__.py         python -m app, sets up TLS and shutdown
tests/
scripts/
  make-certs.sh       dev CA + server cert
  smoke-test.sh       checks a running server
Dockerfile
.github/workflows/ci.yml
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
