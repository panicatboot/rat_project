import json
from typing import Any

from rat_project.common.exceptions import ProtocolError


def encode_message(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload) + "\n").encode("utf-8")


def decode_message(raw_data: bytes) -> dict[str, Any]:
    try:
        decoded = json.loads(raw_data.decode("utf-8").strip())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("Invalid message format") from exc

    if not isinstance(decoded, dict):
        raise ProtocolError("Protocol message must be a dictionary")

    return decoded
