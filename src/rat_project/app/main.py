"""
Entry point for the `rat` command.

Displays the ASCII title then asks the user to launch the server or client.
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Color — #682413 in ANSI truecolor
# ---------------------------------------------------------------------------

COLOR = "\033[38;2;96;87;148m"
RESET = "\033[0m"


def _c(text: str) -> str:
    """Wraps text in the project color (DRY helper)."""
    return f"{COLOR}{text}{RESET}"


def _cls() -> None:
    """Clears the terminal screen (cross-platform)."""
    os.system("cls" if os.name == "nt" else "clear")


def _print_title() -> None:
    """
    Reads titre.txt from the project root and prints each line in color.

    Uses Path(__file__) so it works regardless of the current directory.
    """
    # titre.txt is at the project root, 4 levels above this file:
    # src/rat_project/app/main.py → app/ → rat_project/ → src/ → root/
    title_path = Path(__file__).parent.parent.parent.parent / "titre.txt"

    if not title_path.exists():
        print(_c("RAT — Remote Administration Tool"))
        return

    for line in title_path.read_text(encoding="utf-8").splitlines():
        print(_c(line))


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Entry point of the `rat` command.

    Shows the ASCII title then lets the user choose between
    launching the server or the client.
    """
    # Enable ANSI colors on Windows (no-op on Linux)
    os.system("")

    while True:
        _cls()
        _print_title()
        print()
        # Box = 155 chars wide (matches title width exactly)
        # Inner content = 153 chars between the two │ borders
        W = 153
        print(_c("┌" + "─" * W + "┐"))
        print(_c("│" + "  [1]  Start server".ljust(W) + "│"))
        print(_c("│" + "  [2]  Start client".ljust(W) + "│"))
        print(_c("│" + "  [3]  Exit".ljust(W) + "│"))
        print(_c("└" + "─" * W + "┘"))
        print()

        choice = input(_c("rat > ")).strip()

        if choice == "1":
            _cls()
            from rat_project.server.server_app import run_server
            run_server()

        elif choice == "2":
            _cls()
            from rat_project.client.client_app import run_client
            run_client()

        elif choice == "3" or choice.lower() in ("exit", "quit"):
            print(_c("Goodbye."))
            sys.exit(0)

        else:
            print(_c(f"[!] Invalid choice '{choice}'. Enter 1, 2 or 3."))
            input(_c("Press ENTER to continue..."))


if __name__ == "__main__":
    main()
