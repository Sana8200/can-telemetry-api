"""Decoding CAN frames into signal values."""

from dataclasses import dataclass

from app.signals import MESSAGES, Signal


class FrameError(ValueError):
    """Frame we can't decode, e.g. wrong length for its ID."""


@dataclass(frozen=True)
class Frame:
    can_id: int
    data: bytes
    timestamp: float | None = None  # unix time


def extract_raw(data: bytes, signal: Signal) -> int:
    """Raw (unscaled) value of one signal. The payload is little-endian."""
    payload = int.from_bytes(data, "little")
    raw = (payload >> signal.start_bit) & (2**signal.length - 1)
    if signal.signed and raw >= 2 ** (signal.length - 1):
        raw -= 2**signal.length
    return raw


def decode(frame: Frame) -> dict[str, float] | None:
    """Decode a frame into {signal name: value}.

    Unknown IDs return None, a real bus is full of messages we don't care about.
    A known ID with the wrong length raises FrameError.
    """
    message = MESSAGES.get(frame.can_id)
    if message is None:
        return None
    if len(frame.data) != message.dlc:
        raise FrameError(
            f"ID 0x{frame.can_id:X} ({message.name}) needs {message.dlc} bytes, "
            f"got {len(frame.data)}"
        )
    return {
        s.name: round(extract_raw(frame.data, s) * s.scale + s.offset, 6) for s in message.signals
    }
