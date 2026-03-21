import locale
import platform
import subprocess


def get_system_info() -> str:
    system_name = platform.system()

    if system_name == "Windows":
        command = "systeminfo"
    elif system_name == "Linux":
        command = "uname -a"
    else:
        return f"Unsupported operating system: {system_name}"

    encoding = locale.getpreferredencoding(False)

    completed = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        encoding=encoding,
        errors="replace",
        check=False,
    )

    output = completed.stdout.strip()
    error_output = completed.stderr.strip()

    if output:
        return output

    if error_output:
        return error_output

    return "No output returned"
