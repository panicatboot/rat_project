# RAT — Remote Administration Tool


Remote Administration Tool system composed of a **server** and a **client** (agent), communicating via a TLS-encrypted TCP socket.

## Preview

<img width="1241" height="317" alt="image" src="https://github.com/user-attachments/assets/c19e70ea-a55e-4f14-a848-5312d0090941" />
<img width="1482" height="679" alt="image" src="https://github.com/user-attachments/assets/479c15e3-da80-42e3-9403-0e289c974df0" />

## Features

### Client (agent)

| Command | Description |
|---|---|
| `help` | Show available commands |
| `ipconfig` | Network configuration (`ip addr` / `ipconfig /all`) |
| `sysinfo` | System information (`uname -a` / `systeminfo`) |
| `screenshot` | Screen capture (JPEG) |
| `shell` | Interactive shell (bash / cmd) |
| `search <name>` | Search for a file on the machine |
| `download <path>` | Download a file from the agent to the server |
| `upload <path>` | Upload a file from the server to the agent |
| `hashdump` | Retrieve `/etc/shadow` (Linux) or SAM+SYSTEM (Windows) |
| `keylogger` | Start/stop keystroke recording |
| `webcam_snapshot` | Webcam photo |
| `webcam_stream` | Live webcam video stream (press `q` to stop) |
| `record_audio [s]` | Record audio from microphone (default: 5 seconds) |

### Server

- Listens on TCP port 8888 with TLS encryption
- Accepts **multiple agents in parallel** (one thread per agent)
- Interactive TUI interface for session management
- Automatic handling of agent connections and disconnections

---

## Requirements

- Python >= 3.12
- [Poetry](https://python-poetry.org/)

---

## Installation

```bash
# Install dependencies
poetry lock --no-update
poetry install

# Generate the TLS certificate (required before first run)
python generate_cert.py
```

---

## Usage on Linux

### Starting

Open **two terminals** in the project root.

**Terminal 1 — Server:**

```bash
./rat
```

Type `1` to start the server.

**Terminal 2 — Client:**

```bash
./rat
```

Type `2` to connect the agent to the server.

### Interacting with an agent

In the server terminal:

```
rat > interact 1
rat agent 1 > help
rat agent 1 > ipconfig
rat agent 1 > screenshot
rat agent 1 > shell
  shell > whoami
  shell > exit
rat agent 1 > back
```

### Hashdump with root privileges

The client must be launched as root to read `/etc/shadow`:

```bash
sudo PYTHONPATH=src $(poetry env info -e) -m rat_project.app.main
```

Type `2` to start the client as root, then in the server:

```
rat > interact <id>
rat agent <id> > hashdump
```

---

## Usage on Windows

### Windows prerequisites

```powershell
# Install Python 3.12+ from python.org
# Install Poetry:
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# Install dependencies
poetry lock --no-update
poetry install

# Generate the TLS certificate
python generate_cert.py
```

### Starting

Open **two PowerShell windows** in the project root.

**PowerShell 1 — Server:**

```powershell
.\rat.bat
```

Type `1` to start the server.

**PowerShell 2 — Client:**

```powershell
.\rat.bat
```

Type `2` to connect the agent.

### Interacting with an agent

Commands are identical to Linux:

```
rat > interact 1
rat agent 1 > ipconfig
rat agent 1 > shell
  shell > whoami
  shell > dir C:\Users
  shell > exit
rat agent 1 > back
```

### Hashdump with Administrator privileges

Open PowerShell **as Administrator**, then:

```powershell
.\rat.bat
```

Type `2` to start the client as admin.

### Linux / Windows differences

| Command | Linux | Windows |
|---|---|---|
| `ipconfig` | `ip addr` | `ipconfig /all` |
| `sysinfo` | `uname -a` | `systeminfo` |
| `shell` | bash | cmd.exe |
| `search` | from `/` | from `C:\` |
| `hashdump` | `/etc/shadow` (root) | SAM + SYSTEM (Administrator) |

---

## Unit tests

```bash
poetry run pytest tests/ -v
```

Expected result: `29 passed`.

| Test file | What is tested |
|---|---|
| `test_client_actions.py` | ipconfig, sysinfo, screenshot, shell, record_audio, webcam, keylogger, search, hashdump |
| `test_download_upload.py` | download (existing/missing file, directory), upload (with/without data) |
| `test_protocol.py` | JSON encode/decode, protocol errors |
| `test_project_structure.py` | Environment verification |

---

## Project structure

```
rat_project/
├── src/rat_project/
│   ├── app/            # Entry point (main.py, TUI)
│   ├── client/         # Agent logic and actions
│   ├── server/         # Server logic
│   ├── common/         # Protocol, TLS, exceptions
│   └── utils/          # Logger configuration
├── tests/              # pytest unit tests
├── certs/              # TLS certificates (not committed)
├── rat                 # Linux launch script
├── rat.bat             # Windows launch script
└── pyproject.toml      # Poetry configuration and dependencies
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `cryptography` | TLS certificate handling |
| `Pillow` | Screen capture (PIL.ImageGrab) |
| `opencv-python` | Webcam (capture and display) |
| `pynput` | Keylogger |
| `sounddevice` | Audio recording |
| `mss` | Fast screen capture |

---

## Development tools

- **Poetry** — dependency management
- **pytest** — unit tests
- **pre-commit** — code formatting
- **logger** — logging (no `print`)


If you’ve read this far, congratulations — we’re delighted to know that you enjoy this project. ♡
