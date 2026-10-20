from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    name: str
    start_bit: int  # little-endian: bit 0 is the lowest bit of byte 0
    length: int
    scale: float
    offset: float
    unit: str
    signed: bool = False


@dataclass(frozen=True)
class Message:
    can_id: int
    name: str
    dlc: int  # payload length in bytes
    signals: tuple[Signal, ...]


_MESSAGES = (
    Message(
        0x100,
        "inverter",
        8,
        (
            Signal("motor_rpm", 0, 16, 1, 0, "rpm"),
            Signal("motor_temp", 16, 8, 1, -40, "degC"),
            Signal("inverter_temp", 24, 8, 1, -40, "degC"),
        ),
    ),
    Message(
        0x200,
        "battery",
        8,
        (
            Signal("pack_voltage", 0, 16, 0.1, 0, "V"),
            Signal("pack_current", 16, 16, 0.1, 0, "A", signed=True),
            Signal("state_of_charge", 32, 8, 0.5, 0, "%"),
        ),
    ),
    Message(
        0x300,
        "vehicle",
        8,
        (
            Signal("speed", 0, 16, 0.01, 0, "km/h"),
            Signal("throttle", 16, 8, 0.5, 0, "%"),
        ),
    ),
)


MESSAGES: dict[int, Message] = {m.can_id: m for m in _MESSAGES}
SIGNALS: dict[str, tuple[Message, Signal]] = {s.name: (m, s) for m in _MESSAGES for s in m.signals}
