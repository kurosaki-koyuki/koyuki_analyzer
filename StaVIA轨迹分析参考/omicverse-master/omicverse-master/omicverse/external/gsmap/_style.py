"""OmicVerse-style console output helpers for the vendored gsMap pipeline."""

from __future__ import annotations

from datetime import datetime


class Colors:
    """ANSI color codes for terminal output styling."""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


EMOJI = {
    "start": "🔍",
    "done": "✅",
    "error": "❌",
    "warning": "⚠️",
    "gpu": "🚀",
    "cpu": "🖥️",
    "bar": "📊",
    "check_mark": "✅",
}


def ov_print_start(step_name: str) -> None:
    """Print an OmicVerse-style step-start banner."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"{EMOJI['start']} [{ts}] {Colors.CYAN}Begin {step_name}{Colors.ENDC}"
    )


def ov_print_done(step_name: str) -> None:
    """Print an OmicVerse-style step-done banner."""
    print(
        f"{EMOJI['done']} {Colors.GREEN}{step_name} completed successfully.{Colors.ENDC}"
    )


def ov_print_time(elapsed_sec: float, label: str = "Time") -> None:
    """Print an OmicVerse-style elapsed-time line."""
    print(
        f"{Colors.BLUE}    {label}: {elapsed_sec:.2f} seconds.{Colors.ENDC}"
    )


def ov_print_warning(msg: str) -> None:
    """Print an OmicVerse-style warning line."""
    print(f"{Colors.WARNING}⚠️  {msg}{Colors.ENDC}")


def ov_print_error(msg: str) -> None:
    """Print an OmicVerse-style error line."""
    print(f"{Colors.FAIL}❌ {msg}{Colors.ENDC}")


def ov_print_info(msg: str) -> None:
    """Print an OmicVerse-style info line."""
    print(f"{Colors.BLUE}    {msg}{Colors.ENDC}")


def ov_print_added(label: str, detail: str) -> None:
    """Print an OmicVerse-style 'Added' summary line."""
    print(f"{Colors.CYAN}        '{label}', {detail}{Colors.ENDC}")
