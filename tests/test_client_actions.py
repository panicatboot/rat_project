import base64
from unittest.mock import patch

import numpy as np

from rat_project.client.client_actions_os import get_system_info, record_audio


def test_get_system_info_returns_string() -> None:
    result = get_system_info()

    assert isinstance(result, str)
    assert result != ""


def test_record_audio_returns_base64_string() -> None:
    """record_audio() must return a non-empty base64 string."""
    fake_frames = np.zeros((44100 * 5, 1), dtype="int16")  # 5s of silence

    with patch("sounddevice.rec", return_value=fake_frames), patch("sounddevice.wait"):
        result = record_audio(duration=5)

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
