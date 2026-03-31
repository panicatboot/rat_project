"""
Tests unitaires pour les actions client du RAT.

Couvre : get_system_info, get_ipconfig, take_screenshot, handle_shell,
         record_audio, webcam_snapshot, webcam_stream,
         toggle_keylogger, search_file, hashdump.
"""

import base64
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import numpy as np
import pytest

import rat_project.client.client_actions_os as actions
from rat_project.client.client_actions_os import (
    get_ipconfig,
    get_system_info,
    handle_shell,
    hashdump,
    record_audio,
    search_file,
    take_screenshot,
    toggle_keylogger,
    webcam_snapshot,
    webcam_stream,
)


# ---------------------------------------------------------------------------
# get_system_info
# ---------------------------------------------------------------------------


def test_get_system_info_returns_string() -> None:
    result = get_system_info()
    assert isinstance(result, str)
    assert result != ""


# ---------------------------------------------------------------------------
# get_ipconfig
# ---------------------------------------------------------------------------


def test_get_ipconfig_returns_string() -> None:
    result = get_ipconfig()
    assert isinstance(result, str)
    assert result != ""


def test_get_ipconfig_linux_uses_ip_addr() -> None:
    with patch("rat_project.client.client_actions_os._get_os", return_value="Linux"):
        with patch("rat_project.client.client_actions_os._run_command", return_value="lo: ...") as mock_run:
            result = get_ipconfig()
    mock_run.assert_called_once_with("ip addr")
    assert result == "lo: ..."


def test_get_ipconfig_windows_uses_ipconfig() -> None:
    with patch("rat_project.client.client_actions_os._get_os", return_value="Windows"):
        with patch("rat_project.client.client_actions_os._run_command", return_value="Windows IP") as mock_run:
            result = get_ipconfig()
    mock_run.assert_called_once_with("ipconfig /all")
    assert result == "Windows IP"


# ---------------------------------------------------------------------------
# take_screenshot
# ---------------------------------------------------------------------------


def test_take_screenshot_returns_base64_string() -> None:
    # ImageGrab est importé localement dans take_screenshot — on patche le module PIL directement
    fake_img = MagicMock()
    # save() écrit des octets dans le buffer pour simuler une vraie image
    fake_img.save = MagicMock(side_effect=lambda buf, format: buf.write(b"fake_jpeg"))

    with patch("PIL.ImageGrab.grab", return_value=fake_img):
        result = take_screenshot()

    assert isinstance(result, str)


def test_take_screenshot_returns_empty_string_on_error() -> None:
    with patch("PIL.ImageGrab.grab", side_effect=Exception("no display")):
        result = take_screenshot()
    assert result == ""


# ---------------------------------------------------------------------------
# handle_shell
# ---------------------------------------------------------------------------


def test_handle_shell_executes_command_and_sends_output() -> None:
    # Message shell_input puis déconnexion
    shell_input_msg = json.dumps({"type": "shell_input", "input": "echo hello"}).encode() + b"\n"
    stop_msg = json.dumps({"type": "command", "command": "shell_stop"}).encode() + b"\n"

    mock_conn = MagicMock()
    mock_conn.recv.side_effect = [shell_input_msg, stop_msg]

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="hello\n", stderr="")
        handle_shell(mock_conn)

    # On vérifie qu'une réponse shell_output a bien été envoyée
    sent_calls = [call[0][0].decode() for call in mock_conn.sendall.call_args_list]
    assert any("shell_output" in msg for msg in sent_calls)


def test_handle_shell_stops_on_shell_stop() -> None:
    stop_msg = json.dumps({"type": "command", "command": "shell_stop"}).encode() + b"\n"

    mock_conn = MagicMock()
    mock_conn.recv.return_value = stop_msg

    handle_shell(mock_conn)  # doit s'arrêter sans boucle infinie
    mock_conn.sendall.assert_not_called()


# ---------------------------------------------------------------------------
# record_audio
# ---------------------------------------------------------------------------


def test_record_audio_returns_base64_string() -> None:
    fake_frames = np.zeros((44100 * 5, 1), dtype="int16")

    with patch("sounddevice.rec", return_value=fake_frames), patch("sounddevice.wait"):
        result = record_audio(duration=5)

    assert isinstance(result, str)
    assert len(result) > 0


def test_record_audio_data_is_valid_wav() -> None:
    fake_frames = np.zeros((44100 * 3, 1), dtype="int16")

    with patch("sounddevice.rec", return_value=fake_frames), patch("sounddevice.wait"):
        result = record_audio(duration=3)

    wav_bytes = base64.b64decode(result)
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"


def test_record_audio_default_duration_calls_correct_frames() -> None:
    fake_frames = np.zeros((44100 * 5, 1), dtype="int16")

    with patch("sounddevice.rec", return_value=fake_frames) as mock_rec, patch("sounddevice.wait"):
        record_audio()

    mock_rec.assert_called_once_with(
        44100 * 5,
        samplerate=44100,
        channels=1,
        dtype="int16",
    )


# ---------------------------------------------------------------------------
# webcam_snapshot
# ---------------------------------------------------------------------------


def test_webcam_snapshot_returns_base64_string() -> None:
    with patch("cv2.VideoCapture") as mock_cap_class, patch("cv2.imencode") as mock_encode:
        mock_cap = MagicMock()
        mock_cap_class.return_value = mock_cap
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, MagicMock())
        mock_buf = MagicMock()
        mock_buf.tobytes.return_value = b"fake_jpeg_bytes"
        mock_encode.return_value = (True, mock_buf)

        result = webcam_snapshot()

    assert isinstance(result, str)
    assert len(result) > 0


def test_webcam_snapshot_no_webcam_returns_empty_string() -> None:
    with patch("cv2.VideoCapture") as mock_cap_class:
        mock_cap = MagicMock()
        mock_cap_class.return_value = mock_cap
        mock_cap.isOpened.return_value = False

        result = webcam_snapshot()

    assert result == ""


# ---------------------------------------------------------------------------
# webcam_stream
# ---------------------------------------------------------------------------


def test_webcam_stream_no_webcam_sends_error() -> None:
    mock_conn = MagicMock()

    with patch("cv2.VideoCapture") as mock_cap_class:
        mock_cap = MagicMock()
        mock_cap_class.return_value = mock_cap
        mock_cap.isOpened.return_value = False

        webcam_stream(mock_conn)

    mock_conn.sendall.assert_called_once()
    sent = mock_conn.sendall.call_args[0][0].decode()
    assert "stream_error" in sent


# ---------------------------------------------------------------------------
# toggle_keylogger
# ---------------------------------------------------------------------------


def test_toggle_keylogger_start_returns_confirmation() -> None:
    actions._keylogger_listener = None
    actions._keylogger_buffer = []

    with patch("pynput.keyboard.Listener") as mock_listener_class:
        mock_listener = MagicMock()
        mock_listener_class.return_value = mock_listener

        result = toggle_keylogger()

    assert "started" in result.lower()
    mock_listener.start.assert_called_once()


def test_toggle_keylogger_stop_returns_captured_keys() -> None:
    mock_listener = MagicMock()
    actions._keylogger_listener = mock_listener
    actions._keylogger_buffer = ["h", "e", "l", "l", "o"]

    result = toggle_keylogger()

    assert "stopped" in result.lower()
    assert "hello" in result
    mock_listener.stop.assert_called_once()
    assert actions._keylogger_listener is None
    assert actions._keylogger_buffer == []


# ---------------------------------------------------------------------------
# search_file
# ---------------------------------------------------------------------------


def test_search_file_found() -> None:
    # On crée un fichier temporaire et on limite la recherche à son répertoire parent
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    # On remplace la racine de recherche par le répertoire parent du fichier
    with patch("rat_project.client.client_actions_os.Path") as mock_path_class:
        mock_path_class.return_value = tmp_path.parent
        mock_path_class.side_effect = lambda p: tmp_path.parent if p in ("C:/", "/") else Path(p)

        result = search_file(tmp_path.name)

    tmp_path.unlink()
    assert tmp_path.name in result


def test_search_file_not_found() -> None:
    # On limite la recherche au répertoire /tmp pour éviter un parcours complet
    with patch("rat_project.client.client_actions_os._get_os", return_value="Linux"):
        with patch("pathlib.Path.rglob", return_value=iter([])):
            result = search_file("fichier_qui_nexiste_vraiment_pas_12345.xyz")
    assert "Aucun fichier trouvé" in result


# ---------------------------------------------------------------------------
# hashdump
# ---------------------------------------------------------------------------


def test_hashdump_linux_returns_shadow_content() -> None:
    fake_shadow = "root:$6$hash:19000:0:99999:7:::\nuser:$6$hash2:19000:0:99999:7:::\n"

    with patch("rat_project.client.client_actions_os._get_os", return_value="Linux"):
        with patch("pathlib.Path.read_text", return_value=fake_shadow):
            result = hashdump()

    assert isinstance(result, str)
    assert "root" in result


def test_hashdump_linux_permission_denied_returns_error() -> None:
    with patch("rat_project.client.client_actions_os._get_os", return_value="Linux"):
        with patch("pathlib.Path.read_text", side_effect=PermissionError):
            result = hashdump()

    assert isinstance(result, str)
    assert "Error" in result
    assert "permission" in result.lower()
