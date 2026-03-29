from unittest.mock import mock_open, patch

from rat_project.client.client_actions_os import get_system_info, hashdump


def test_get_system_info_returns_string() -> None:
    result = get_system_info()

    assert isinstance(result, str)
    assert result != ""


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
