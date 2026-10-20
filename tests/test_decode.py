import pytest

from app.can_decode import Frame, FrameError, decode, extract_raw
from app.signals import Signal

INVERTER = "B80B695A00000000"  # 3000 rpm, motor 65 degC, inverter 50 degC
BATTERY = "9F0F9CFFA0000000"  # 399.9 V, -10.0 A, 80 % charge
VEHICLE = "5C12A00000000000"  # 47 km/h, 80 % throttle


def test_decodes_inverter_frame():
    assert decode(Frame(0x100, bytes.fromhex(INVERTER))) == {
        "motor_rpm": 3001,
        "motor_temp": 65,
        "inverter_temp": 50,
    }


def test_decodes_signed_and_scaled_values():
    # 3999 * 0.1 is 399.90000000000003 before rounding
    assert decode(Frame(0x200, bytes.fromhex(BATTERY))) == {
        "pack_voltage": 399.9,
        "pack_current": -10.0,
        "state_of_charge": 80.0,
    }


def test_decodes_vehicle_frame():
    assert decode(Frame(0x300, bytes.fromhex(VEHICLE))) == {"speed": 47.0, "throttle": 80.0}


def test_unknown_id_is_not_an_error():
    assert decode(Frame(0x7FF, b"\x00")) is None


def test_known_id_with_wrong_length_is_rejected():
    with pytest.raises(FrameError) as excinfo:
        decode(Frame(0x100, bytes(4)))
    assert str(excinfo.value) == "ID 0x100 (inverter) needs 8 bytes, got 4"


@pytest.mark.parametrize(
    ("payload", "expected"),
    [("FF7F", 32767), ("0080", -32768), ("FFFF", -1), ("0000", 0)],
)
def test_signed_signals_use_twos_complement(payload, expected):
    signal = Signal("x", start_bit=0, length=16, scale=1, offset=0, unit="", signed=True)
    assert extract_raw(bytes.fromhex(payload), signal) == expected
