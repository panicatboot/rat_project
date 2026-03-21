import json
from typing import Any, List, Tuple

from rat_project.common.exceptions import ProtocolError


def encode_message(payload: dict[str, Any]) -> bytes:
    try:
        return (json.dumps(payload) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProtocolError("Failed to encode message") from exc


def decode_message(raw_message: str) -> dict[str, Any]:
    try:
        decoded = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        raise ProtocolError("Invalid JSON message") from exc

    if not isinstance(decoded, dict):
        raise ProtocolError("Protocol message must be a dictionary")

    return decoded


def extract_messages(buffer: str) -> Tuple[List[dict[str, Any]], str]:
    messages = []
    lines = buffer.split("\n")

    for line in lines[:-1]:
        if not line.strip():
            continue
        messages.append(decode_message(line.strip()))

    remaining_buffer = lines[-1]
    return messages, remaining_buffer
