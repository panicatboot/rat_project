"""
Tests unitaires pour les fonctions download et upload de client_actions_os.
"""

from pathlib import Path

import pytest

from rat_project.client.client_actions_os import handle_download, handle_upload


# ---------------------------------------------------------------------------
# Tests download
# ---------------------------------------------------------------------------


def test_download_fichier_existant(tmp_path: Path) -> None:
    """Un fichier existant doit être retourné encodé en base64."""
    import base64

    # Création d'un fichier temporaire avec du contenu
    test_file = tmp_path / "test.txt"
    test_file.write_text("contenu de test", encoding="utf-8")

    response = handle_download(str(test_file))

    assert response["command"] == "download"
    assert "error" not in response
    assert "data" in response
    # Vérification que le contenu décodé correspond bien au fichier original
    decoded = base64.b64decode(response["data"])
    assert decoded == b"contenu de test"


def test_download_fichier_inexistant() -> None:
    """Un chemin inexistant doit retourner une erreur."""
    response = handle_download("/chemin/qui/nexiste/pas/fichier.txt")

    assert response["command"] == "download"
    assert "error" in response
    assert "not found" in response["error"].lower()


def test_download_dossier_renvoie_erreur(tmp_path: Path) -> None:
    """Un dossier (pas un fichier) doit retourner une erreur."""
    response = handle_download(str(tmp_path))

    assert response["command"] == "download"
    assert "error" in response


def test_download_retourne_nom_fichier(tmp_path: Path) -> None:
    """La réponse doit contenir le nom du fichier."""
    test_file = tmp_path / "rapport.pdf"
    test_file.write_bytes(b"fake pdf content")

    response = handle_download(str(test_file))

    assert response["filename"] == "rapport.pdf"


# ---------------------------------------------------------------------------
# Tests upload
# ---------------------------------------------------------------------------


def test_upload_ecrit_fichier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Un fichier uploadé doit être écrit sur le disque."""
    import base64

    # On se place dans le dossier temporaire pour que le fichier soit écrit là
    monkeypatch.chdir(tmp_path)

    contenu = b"fichier envoye par le serveur"
    encoded = base64.b64encode(contenu).decode("utf-8")

    message = {"filename": "recu.txt", "data": encoded}
    response = handle_upload(message)

    assert response["command"] == "upload"
    assert "error" not in response
    assert (tmp_path / "recu.txt").read_bytes() == contenu


def test_upload_sans_data_retourne_erreur() -> None:
    """Un message sans données doit retourner une erreur."""
    response = handle_upload({"filename": "vide.txt", "data": ""})

    assert response["command"] == "upload"
    assert "error" in response
