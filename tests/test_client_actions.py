from unittest.mock import MagicMock, patch

from rat_project.client.client_actions_os import get_system_info, webcam_snapshot, webcam_stream


def test_get_system_info_returns_string() -> None:
    result = get_system_info()

    assert isinstance(result, str)
    assert result != ""


def test_webcam_stream_no_webcam_sends_error() -> None:
    # Given: no webcam available
    mock_conn = MagicMock()

    with patch("cv2.VideoCapture") as mock_cap_class:
        mock_cap = MagicMock()
        mock_cap_class.return_value = mock_cap
        mock_cap.isOpened.return_value = False
        webcam_stream(mock_conn)

    # ror
    mock_conn.sendall.assert_called_once()
    sent = mock_conn.sendall.call_args[0][0].decode()
    assert "stream_error" in sent
