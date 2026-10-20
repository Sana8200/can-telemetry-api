"""HTTP API: ingest CAN frames and serve the latest decoded signal values."""

import dataclasses
import math
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import __version__
from app.can_decode import Frame, FrameError, decode
from app.signals import MESSAGES, SIGNALS
from app.store import LatestValues, Reading

MAX_CAN_ID = 0x1FFFFFFF  # 29-bit extended identifier
MAX_BATCH_FRAMES = 1000
MAX_CLOCK_SKEW = 60.0  # seconds a frame's timestamp may be ahead of the server clock


class FrameIn(BaseModel):
    id: int = Field(ge=0, le=MAX_CAN_ID, description="CAN identifier (11- or 29-bit)")
    data: str = Field(
        pattern=r"^([0-9A-Fa-f]{2}){0,8}$",
        description="Payload as hex, 0-8 bytes",
        examples=["B80B695A00000000"],
    )
    timestamp: float | None = Field(
        default=None, description="Seconds since 1970; defaults to arrival time"
    )


class FrameBatch(BaseModel):
    frames: list[FrameIn] = Field(min_length=1, max_length=MAX_BATCH_FRAMES)


class IngestResult(BaseModel):
    decoded: int = Field(description="Frames decoded and stored")
    ignored: int = Field(description="Frames with an ID this service has no definition for")


class SignalDef(BaseModel):
    name: str
    start_bit: int
    length: int
    scale: float
    offset: float
    unit: str
    signed: bool


class MessageDef(BaseModel):
    id: int
    name: str
    dlc: int
    signals: list[SignalDef]


class SignalValue(BaseModel):
    name: str
    message: str
    value: float
    unit: str
    timestamp: float


def _signal_value(name: str, reading: Reading) -> SignalValue:
    message, signal = SIGNALS[name]
    return SignalValue(
        name=name,
        message=message.name,
        value=reading.value,
        unit=signal.unit,
        timestamp=reading.timestamp,
    )


def create_app() -> FastAPI:
    """Build the app. Each call gives a fresh app, so every test starts clean."""
    app = FastAPI(title="CAN Telemetry API", version=__version__)

    store = LatestValues()

    def ingest(frames: list[Frame]) -> IngestResult:
        # Check and decode every frame before storing any: one bad frame rejects the batch.
        decoded: list[tuple[dict[str, float], float]] = []
        ignored = 0
        arrival = time.time()
        for index, frame in enumerate(frames):
            timestamp = frame.timestamp if frame.timestamp is not None else arrival
            # NaN compares false with everything, so a NaN reading could never be replaced,
            # and a timestamp far in the future would pin its value until that time.
            if not (math.isfinite(timestamp) and 0 <= timestamp <= arrival + MAX_CLOCK_SKEW):
                raise HTTPException(422, f"frame {index}: timestamp {timestamp} is out of range")
            try:
                values = decode(frame)
            except FrameError as err:
                raise HTTPException(422, f"frame {index}: {err}") from err
            if values is None:
                ignored += 1
            else:
                decoded.append((values, timestamp))
        for values, timestamp in decoded:
            store.update(values, timestamp)
        return IngestResult(decoded=len(decoded), ignored=ignored)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness: the process is running and answering."""
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        """Readiness: the service can take traffic."""
        return {"status": "ready"}

    @app.get("/messages")
    def list_messages() -> list[MessageDef]:
        """The CAN messages and signals this service can decode."""
        return [
            MessageDef(
                id=m.can_id,
                name=m.name,
                dlc=m.dlc,
                signals=[SignalDef(**dataclasses.asdict(s)) for s in m.signals],
            )
            for m in MESSAGES.values()
        ]

    @app.post("/frames")
    def post_frames(batch: FrameBatch) -> IngestResult:
        """Ingest a batch of frames as JSON."""
        return ingest([Frame(f.id, bytes.fromhex(f.data), f.timestamp) for f in batch.frames])

    @app.get("/signals")
    def list_signals() -> list[SignalValue]:
        """Latest value of every signal received so far."""
        return [_signal_value(name, r) for name, r in sorted(store.snapshot().items())]

    @app.get("/signals/{name}")
    def get_signal(name: str) -> SignalValue:
        """Latest value of one signal."""
        reading = store.get(name)
        if name not in SIGNALS:
            raise HTTPException(404, f"unknown signal {name!r}")
        if reading is None:
            raise HTTPException(404, f"signal {name} has no value yet")
        return _signal_value(name, reading)

    return app


app = create_app()
