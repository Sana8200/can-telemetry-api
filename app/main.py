"""The REST API."""

import dataclasses
import math
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import __version__
from app.can_decode import Frame, FrameError, decode
from app.signals import MESSAGES, SIGNALS
from app.store import LatestValues, Reading

MAX_CAN_ID = 0x1FFFFFFF  # 29-bit extended ID
MAX_BATCH_FRAMES = 1000
MAX_CLOCK_SKEW = 60.0  # how far ahead of our clock a timestamp can be, in seconds


class FrameIn(BaseModel):
    id: int = Field(ge=0, le=MAX_CAN_ID, description="CAN identifier (11- or 29-bit)")
    data: str = Field(
        pattern=r"^([0-9A-Fa-f]{2}){0,8}$",
        description="Payload as hex, 0-8 bytes",
        examples=["B80B695A00000000"],
    )
    timestamp: float | None = Field(
        default=None, description="Unix time. If missing, the time it arrived is used"
    )


class FrameBatch(BaseModel):
    frames: list[FrameIn] = Field(min_length=1, max_length=MAX_BATCH_FRAMES)


class IngestResult(BaseModel):
    decoded: int = Field(description="Frames decoded and stored")
    ignored: int = Field(description="Frames with an ID we don't know, skipped")


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
    """New app with its own empty store, so tests don't share state."""
    app = FastAPI(title="CAN Telemetry API", version=__version__)

    store = LatestValues()

    def ingest(frames: list[Frame]) -> IngestResult:
        # decode the whole batch before storing anything, so one bad frame rejects all of it
        decoded: list[tuple[dict[str, float], float]] = []
        ignored = 0
        arrival = time.time()
        for index, frame in enumerate(frames):
            timestamp = frame.timestamp if frame.timestamp is not None else arrival
            # NaN would never get replaced (any comparison with NaN is False), and a timestamp
            # far in the future would block newer values until that time
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
        """Liveness probe."""
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        """Readiness probe."""
        return {"status": "ready"}

    @app.get("/messages")
    def list_messages() -> list[MessageDef]:
        """Messages and signals the API knows how to decode."""
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
        """Post a batch of frames as JSON."""
        return ingest([Frame(f.id, bytes.fromhex(f.data), f.timestamp) for f in batch.frames])

    @app.get("/signals")
    def list_signals() -> list[SignalValue]:
        """Latest value of every signal seen so far."""
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
