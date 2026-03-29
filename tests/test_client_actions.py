from unittest.mock import MagicMock, patch

from rat_project.client.client_actions_os import get_system_info, webcam_snapshot


def test_get_system_info_returns_string() -> None:
    result = get_system_info()

    assert isinstance(result, str)
    assert result != ""


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


def test_webcam_snapshot_no_webcam_returns_empty_string() -> None:
    # Given: no webcam available
    with patch("cv2.VideoCapture") as mock_cap_class:
        mock_cap = MagicMock()
        mock_cap_class.return_value = mock_cap
        mock_cap.isOpened.return_value = False
        result = webcam_snapshot()
    assert result == ""
