import pytest

from app.can_decode import Frame, FrameError, decode

INVERTER = "B80B695A00000000"  # 3000 rpm, motor 65 degC, inverter 50 degC
BATTERY = "9F0F9CFFA0000000"  # 399.9 V, -10.0 A, 80 % charge


def test_decodes_inverter_frame():
    assert decode(Frame(0x100, bytes.fromhex(INVERTER))) == {
        "motor_rpm": 3000,
        "motor_temp": 65,
        "inverter_temp": 50,
    }


def test_unknown_id_is_not_an_error():
    assert decode(Frame(0x7FF, b"\x00")) is None


def test_decodes_signed_and_scaled_values():
    # 3999 * 0.1 is 399.90000000000003 before rounding
    assert decode(Frame(0x200, bytes.fromhex(BATTERY))) == {
        "pack_voltage": 399.9,
        "pack_current": -10.0,
        "state_of_charge": 80.0,
    }


def test_known_id_with_wrong_length_is_rejected():
    with pytest.raises(FrameError) as excinfo:
        decode(Frame(0x100, bytes(4)))
    assert str(excinfo.value) == "ID 0x100 (inverter) needs 8 bytes, got 4"
