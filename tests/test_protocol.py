import pytest

from rat_project.common.exceptions import ProtocolError
from rat_project.common.protocol import decode_message, encode_message


def test_encode_decode_message() -> None:
    payload = {"type": "hello", "message": "bonjour"}

    encoded = encode_message(payload)
    decoded = decode_message(encoded.decode("utf-8").strip())

    assert decoded == payload


def test_decode_invalid_json_raises_protocol_error() -> None:
    with pytest.raises(ProtocolError):
        decode_message("not-json")
