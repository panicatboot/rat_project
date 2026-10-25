"""
Unit tests for the download and upload functions of client_actions_os.
"""

from pathlib import Path

import pytest

from rat_project.client.client_actions_os import handle_download, handle_upload


# ---------------------------------------------------------------------------
# Download tests
# ---------------------------------------------------------------------------


def test_download_existing_file(tmp_path: Path) -> None:
    """An existing file must be returned encoded in base64."""
    import base64

    # Create a temporary file with content
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content", encoding="utf-8")

    response = handle_download(str(test_file))

    assert response["command"] == "download"
    assert "error" not in response
    assert "data" in response
    # Verify that the decoded content matches the original file
    decoded = base64.b64decode(response["data"])
    assert decoded == b"test content"


def test_download_nonexistent_file() -> None:
    """A non-existing path must return an error."""
    response = handle_download("/path/that/does/not/exist/file.txt")

    assert response["command"] == "download"
    assert "error" in response
    assert "not found" in response["error"].lower()


def test_download_directory_returns_error(tmp_path: Path) -> None:
    """A directory (not a file) must return an error."""
    response = handle_download(str(tmp_path))

    assert response["command"] == "download"
    assert "error" in response


def test_download_returns_filename(tmp_path: Path) -> None:
    """The response must contain the filename."""
    test_file = tmp_path / "report.pdf"
    test_file.write_bytes(b"fake pdf content")

    response = handle_download(str(test_file))

    assert response["filename"] == "report.pdf"


# ---------------------------------------------------------------------------
# Upload tests
# ---------------------------------------------------------------------------


def test_upload_writes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An uploaded file must be written to disk."""
    import base64

    # Change to the temporary directory so the file is written there
    monkeypatch.chdir(tmp_path)

    content = b"file sent by the server"
    encoded = base64.b64encode(content).decode("utf-8")

    message = {"filename": "received.txt", "data": encoded}
    response = handle_upload(message)

    assert response["command"] == "upload"
    assert "error" not in response
    assert (tmp_path / "received.txt").read_bytes() == content


def test_upload_without_data_returns_error() -> None:
    """A message without data must return an error."""
    response = handle_upload({"filename": "empty.txt", "data": ""})

    assert response["command"] == "upload"
    assert "error" in response
