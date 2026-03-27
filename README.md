# RAT Project

Remote Administration Tool en Python — Bal*** & Nas****.

## Prérequis

- Python >= 3.14
- [Poetry](https://python-poetry.org/docs/#installation)

## Installation

```
poetry install
```

## Lancer le projet

### Générer les certificats TLS (une seule fois)

```
poetry run python generate_cert.py
```

### Démarrer le serveur (terminal 1)

```
PYTHONPATH=src poetry run python src/rat_project/server/server_app.py
```

### Démarrer l'agent / client (terminal 2)

```
PYTHONPATH=src poetry run python src/rat_project/client/client_app.py
```

> Par défaut, l'agent se connecte à `127.0.0.1:8888`. Pour changer l'adresse, modifier `HOST` dans `src/rat_project/client/client_app.py`.

# Search

```PYTHONPATH=src poetry run pytest tests/test_client_actions.py::test_search_file_found tests/test_client_actions.py::test_search_file_not_found -v```

## Utilisation du serveur

```
rat > sessions              # lister les agents connectés
rat > interact <id>         # interagir avec un agent
rat agent 1 > help          # afficher les commandes disponibles
rat agent 1 > download <chemin_distant>
rat agent 1 > upload <chemin_local>
rat agent 1 > shell
rat agent 1 > screenshot
rat agent 1 > keylogger
rat agent 1 > webcam_snapshot
rat agent 1 > webcam_stream
rat agent 1 > record_audio
rat agent 1 > ipconfig
rat agent 1 > search <nom_fichier>
rat agent 1 > hashdump
rat agent 1 > back          # revenir au menu principal
```

## Tests

```
poetry run pytest
```
// errors

## Structure du projet

```
src/rat_project/
├── client/         # Agent (exécuté sur la machine victime)
├── server/         # Serveur de contrôle
├── common/         # Protocole, TLS, exceptions partagés
└── utils/          # Configuration du logger
tests/              # Tests unitaires
generate_cert.py    # Génération des certificats TLS auto-signés
```
