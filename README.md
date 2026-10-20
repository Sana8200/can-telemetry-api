# CAN Telemetry API

[![CI](https://github.com/Sana8200/can-telemetry-api/actions/workflows/ci.yml/badge.svg)](https://github.com/Sana8200/can-telemetry-api/actions/workflows/ci.yml)

Decodes CAN bus frames into physical signals (rpm, °C, volts, amperes) in Python. It is the first part of a telemetry service, the next steps put the decoder behind a REST API served over HTTP/2 and TLS, then run it as a container on Kubernetes with CI/CD on GitHub Actions (see [Roadmap](#roadmap)).


## Example

```python
>>> from app.can_decode import Frame, decode
>>> decode(Frame(0x100, bytes.fromhex("B80B695A00000000")))
{'motor_rpm': 3000, 'motor_temp': 65, 'inverter_temp': 50}
>>> decode(Frame(0x200, bytes.fromhex("E50C83FFAF000000")))
{'pack_voltage': 330.1, 'pack_current': -12.5, 'state_of_charge': 87.5}
```


## Signal definitions

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

## Getting started

Needs Python 3.12 or newer.

```bash
git clone https://github.com/Sana8200/can-telemetry-api.git
cd can-telemetry-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest          # run the tests
ruff check .    # lint
```

## Project layout

```
app/
  __init__.py        package and version
  signals.py         message and signal definitions
  can_decode.py      Frame, extract_raw() and decode()
tests/
  test_decode.py     decoder tests
```

## Roadmap

- [x] Decode CAN frames into physical signals, with tests
- [ ] Lint and test every push with GitHub Actions
- [ ] REST API with FastAPI and a thread-safe store of the latest values
- [ ] HTTP/2 over TLS with certificates from a private CA
- [ ] Driving simulator and `candump -L` log upload
- [ ] Slim, non-root container image
- [ ] Deployment to Kubernetes (kind) with a locked-down pod
- [ ] Image published to GitHub Container Registry
