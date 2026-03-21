from rat_project.client.client_actions_os import get_system_info


def test_get_system_info_returns_string() -> None:
    result = get_system_info()

    assert isinstance(result, str)
    assert result != ""
