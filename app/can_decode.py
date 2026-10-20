"""Turn CAN frames into physical signal values."""

from dataclasses import dataclass

from app.signals import MESSAGES, Signal


class FrameError(ValueError):
    """A frame that cannot be decoded."""


@dataclass(frozen=True)
class Frame:
    can_id: int
    data: bytes
    timestamp: float | None = None  # seconds since 1970, used from Step 3


def extract_raw(data: bytes, signal: Signal) -> int:
    """Read a signal's raw integer out of a little-endian payload."""
    payload = int.from_bytes(data, "little")
    raw = (payload >> signal.start_bit) & (2**signal.length - 1)
    if signal.signed and raw >= 2 ** (signal.length - 1):
        raw -= 2**signal.length
    return raw


def decode(frame: Frame) -> dict[str, float] | None:
    """Return {signal name: physical value}, or None if the ID is unknown.

    Unknown IDs are normal on a real bus, so they are not an error.
    A known ID with the wrong payload length raises FrameError.
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
