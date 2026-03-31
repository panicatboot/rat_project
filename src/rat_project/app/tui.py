"""
TUI (Text User Interface) for the RAT server.

Draws a two-panel layout with a navigation menu on the left
and dynamic content on the right. Navigation uses simple number input.
"""

import os
import sys

from rat_project.utils.logger_config import setup_logger

logger = setup_logger("server.tui")

# ---------------------------------------------------------------------------
# Color — #682413 in ANSI truecolor
# ---------------------------------------------------------------------------

COLOR = "\033[38;2;96;87;148m"
RESET = "\033[0m"

# Panel dimensions — all three rows (top border, body, bottom border)
# must produce the same visible width per panel.
TOTAL_WIDTH = 155     # matches ASCII title width exactly
MENU_W = 23           # left panel total width (including │ borders)
CONTENT_W = 131       # right panel total width (including │ borders)
# Check: MENU_W + 1 (space separator) + CONTENT_W = 155


def _c(text: str) -> str:
    """Wraps text in the project color (DRY helper)."""
    return f"{COLOR}{text}{RESET}"


def _cls() -> None:
    """Clears the terminal screen (cross-platform)."""
    os.system("cls" if os.name == "nt" else "clear")


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------


def _pad(text: str, width: int) -> str:
    """Pads or truncates text to exactly `width` characters."""
    if len(text) > width:
        return text[:width - 3] + "..."
    return text.ljust(width)


def _draw_header(port: int = 8888) -> str:
    """Returns the top header bar as a string."""
    title = "RAT CONTROL CENTER"
    right = f"Port: {port}"
    inner = _pad(f" {title}", TOTAL_WIDTH - len(right) - 4) + right + " "
    lines = [
        _c("╔" + "═" * (TOTAL_WIDTH - 2) + "╗"),
        _c("║" + inner + "║"),
        _c("╚" + "═" * (TOTAL_WIDTH - 2) + "╝"),
    ]
    return "\n".join(lines)


def _draw_layout(menu_lines: list[str], content_lines: list[str]) -> str:
    """
    Draws the two-panel layout side by side.

    Left panel  : menu_lines    (MENU_W chars total with borders)
    Right panel : content_lines (CONTENT_W chars total with borders)
    """
    # Inner widths (space between the two │ borders)
    mi = MENU_W - 2       # 21
    ci = CONTENT_W - 2    # 129

    # Normalize both panels to the same height
    height = max(len(menu_lines), len(content_lines))
    menu_lines = menu_lines + [""] * (height - len(menu_lines))
    content_lines = content_lines + [""] * (height - len(content_lines))

    rows = []

    # Top borders
    label = "─ MENU "
    rows.append(
        _c("┌" + label + "─" * (mi - len(label)) + "┐")
        + " "
        + _c("┌" + "─" * ci + "┐")
    )

    # Body rows
    for m, c in zip(menu_lines, content_lines):
        left  = _c("│") + _c(" " + _pad(m, mi - 1)) + _c("│")
        right = _c("│") + _c(" " + _pad(c, ci - 1)) + _c("│")
        rows.append(left + " " + right)

    # Bottom borders
    rows.append(
        _c("└" + "─" * mi + "┘")
        + " "
        + _c("└" + "─" * ci + "┘")
    )

    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Menu lines (left panel)
# ---------------------------------------------------------------------------


def _menu_lines(active: int) -> list[str]:
    """
    Returns the left panel lines with '>' on the active item.

    Args:
        active: Index of the highlighted menu item (1-4).
    """
    items = ["Dashboard", "Interact", "Help", "Quit"]
    lines = []
    for i, item in enumerate(items, start=1):
        prefix = "> " if i == active else "  "
        lines.append(f"{prefix}[{i}] {item}")
    return lines


# ---------------------------------------------------------------------------
# Content builders (right panel)
# ---------------------------------------------------------------------------


def _content_dashboard() -> list[str]:
    """Builds right-panel content for the Dashboard screen."""
    # Import here to avoid circular imports
    from rat_project.server.server_app import session_lock, sessions

    lines = ["Connected agents", ""]
    with session_lock:
        if not sessions:
            lines.append("  No agent connected.")
        else:
            for sid, data in sessions.items():
                line = f"  #{sid:<3} {data['hostname']:<18} {data['ip']:<16} {data['os']}"
                lines.append(line)
    lines += ["", "Type 'interact <id>' or choose [2]."]
    return lines


def _content_interact() -> list[str]:
    """Builds right-panel content for the Interact screen."""
    from rat_project.server.server_app import session_lock, sessions

    lines = ["Select an agent ID to interact with:", ""]
    with session_lock:
        if not sessions:
            lines.append("  No agent connected.")
        else:
            for sid, data in sessions.items():
                line = f"  #{sid:<3} {data['hostname']:<18} {data['ip']:<16} {data['os']}"
                lines.append(line)
    lines += ["", "Enter: interact <id>   |   back: return"]
    return lines


def _content_help() -> list[str]:
    """Builds right-panel content for the Help screen."""
    return [
        "Commands available inside an agent session:",
        "",
        "  [1]   help              Show available commands",
        "  [2]   ipconfig          Network configuration",
        "  [3]   sysinfo           System information",
        "  [4]   shell             Interactive shell (bash/cmd)",
        "  [5]   search <name>     Search for a file",
        "  [6]   screenshot        Take a screenshot",
        "  [7]   download <path>   Download a file from agent",
        "  [8]   upload <path>     Upload a file to agent",
        "  [9]   hashdump          Dump SAM (Win) or shadow (Linux)",
        "  [10]  keylogger         Start/stop keylogger",
        "  [11]  webcam_snapshot   Webcam photo",
        "  [12]  webcam_stream     Live webcam stream (q to stop)",
        "  [13]  record_audio [s]  Audio recording (default: 5s)",
        "  [14]  back              Return to this menu",
    ]


def _content_about() -> list[str]:
    """Builds right-panel content shown on first launch."""
    return [
        "Welcome to RAT Control Center.",
        "",
        "Waiting for agents to connect...",
    ]


def _content_agent(session_id: int, last_output: list[str] | None = None) -> list[str]:
    """Builds right-panel content for an active agent session."""
    from rat_project.server.server_app import get_session

    session = get_session(session_id)
    lines = []
    if session:
        lines.append(f"Agent #{session_id}  —  {session['hostname']}  ({session['ip']})  {session['os']}")
    else:
        lines.append(f"Agent #{session_id}")
    lines.append("")

    if last_output:
        for line in last_output:
            lines.append(f"  {line}")
    else:
        lines.append("  Type a command or 'help' for the list.")

    return lines


def _agent_menu_lines() -> list[str]:
    """Returns the left panel lines for the agent interaction screen."""
    return [
        "  [help]",
        "  [ipconfig]",
        "  [sysinfo]",
        "  [shell]",
        "  [search]",
        "  [screenshot]",
        "  [download]",
        "  [upload]",
        "  [hashdump]",
        "  [keylogger]",
        "  [webcam_snapshot]",
        "  [webcam_stream]",
        "  [record_audio]",
        "",
        "  [back]",
    ]


def draw_agent_screen(session_id: int, port: int, last_output: list[str] | None = None) -> None:
    """Clears and redraws the TUI with the agent interaction view."""
    _cls()
    print(_draw_header(port))
    print()
    print(_draw_layout(_agent_menu_lines(), _content_agent(session_id, last_output)))
    print()


# ---------------------------------------------------------------------------
# Main TUI loop
# ---------------------------------------------------------------------------


def tui_loop(port: int = 8888) -> None:
    """
    Main interactive loop of the TUI server interface.

    Replaces the old command_loop(). Draws the two-panel layout and
    delegates agent interaction to interact_with_session() (unchanged).

    Args:
        port: Listening port, shown in the header.
    """
    from rat_project.server.server_app import interact_with_session

    active = 1  # currently highlighted menu item
    content = _content_about()

    while True:
        _cls()
        print(_draw_header(port))
        print()
        print(_draw_layout(_menu_lines(active), content))
        print()

        try:
            raw = input(_c("rat > ")).strip()
        except KeyboardInterrupt:
            print()
            logger.info("Server interrupted by user.")
            break

        if not raw:
            continue

        # --- Number shortcuts ---
        if raw == "1":
            active = 1
            content = _content_dashboard()

        elif raw == "2":
            active = 2
            from rat_project.server.server_app import session_lock, sessions
            with session_lock:
                agent_ids = list(sessions.keys())

            if not agent_ids:
                content = ["No agent connected."]
                continue

            # One agent → connect directly
            if len(agent_ids) == 1:
                _cls()
                interact_with_session(agent_ids[0])
                active = 1
                content = _content_dashboard()
                continue

            # Multiple agents → ask which one
            content = _content_interact()
            _cls()
            print(_draw_header(port))
            print()
            print(_draw_layout(_menu_lines(active), content))
            print()
            try:
                pick = input(_c("Agent ID > ")).strip()
            except KeyboardInterrupt:
                continue
            if pick.isdigit() and int(pick) in agent_ids:
                _cls()
                interact_with_session(int(pick))
                active = 1
                content = _content_dashboard()
            else:
                content = [f"[!] Invalid agent ID: '{pick}'"]
            continue

        elif raw == "3":
            active = 3
            content = _content_help()

        elif raw == "4" or raw == "quit" or raw == "exit":
            logger.info("Server shutting down.")
            print(_c("[*] Shutting down server..."))
            break

        # --- interact <id> ---
        elif raw.startswith("interact "):
            parts = raw.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].isdigit():
                content = ["[!] Usage: interact <id>   (id must be a number)"]
                continue
            session_id = int(parts[1])
            # Hand off to existing function — it handles the full agent loop
            _cls()
            interact_with_session(session_id)
            # After returning, go back to dashboard
            active = 1
            content = _content_dashboard()

        # --- sessions (legacy shortcut) ---
        elif raw == "sessions" or raw == "dashboard":
            active = 1
            content = _content_dashboard()

        # --- help (legacy shortcut) ---
        elif raw == "help":
            active = 3
            content = _content_help()

        else:
            content = [f"[!] Unknown command: '{raw}'", "", "Type 1/2/3/4 or 'interact <id>'."]
