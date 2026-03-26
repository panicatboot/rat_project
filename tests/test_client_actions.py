import tempfile
from pathlib import Path

from rat_project.client.client_actions_os import get_system_info, search_file


def test_get_system_info_returns_string() -> None:
    result = get_system_info()

    assert isinstance(result, str)
    assert result != ""


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
