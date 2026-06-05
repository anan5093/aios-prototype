"""
inject_panic.py — Inject synthetic kernel panic events into mock_logs/kern.log.

Used for testing the AIOS daemon's OOM detection pipeline.
All events use current timestamp. No real kernel interaction.

Run from project root:
    python scripts/inject_panic.py
"""

import logging
import random
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("inject_panic")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HOSTNAME = "aios-dev-host"

# Process names used in injected OOM events
_PROCESS_NAMES = [
    "chrome",
    "firefox",
    "python3",
    "node",
    "java",
    "postgres",
]

# Uptime-counter seed (arbitrary but realistic-looking for current time)
_BOOT_OFFSET_SECONDS = 86400 * 3  # pretend system booted 3 days ago


def _kern_timestamp(dt: datetime) -> str:
    """
    Return a kern.log-style prefix:
    ``Mon DD HH:MM:SS aios-dev-host kernel: [NNNNNNN.NNNNNN]``
    """
    month_abbr = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    day_str = f"{dt.day:2d}"
    date_part = f"{month_abbr[dt.month - 1]} {day_str} {dt.strftime('%H:%M:%S')}"

    # Simulate uptime: boot_offset + seconds-into-today
    seconds_today = (
        dt.hour * 3600 + dt.minute * 60 + dt.second
    )
    uptime_total = _BOOT_OFFSET_SECONDS + seconds_today
    # Add a small random fractional part for realism
    micro = random.randint(100000, 999999)
    uptime_str = f"[{uptime_total:7d}.{micro:06d}]"

    return f"{date_part} {HOSTNAME} kernel: {uptime_str}"


def _build_oom_lines(dt: datetime, process_name: str) -> list[str]:
    """
    Build a pair of kern.log lines for a single OOM kill event.

    Args:
        dt:           Timestamp to use for both lines.
        process_name: Name of the process being killed.

    Returns:
        List of exactly 2 fully-formatted log line strings.
    """
    pid = random.randint(1000, 32767)
    score = random.randint(1, 999)
    total_vm = random.randint(200000, 2000000)
    anon_rss = random.randint(50000, 800000)
    file_rss = random.randint(100, 10000)
    pfx = _kern_timestamp(dt)

    line1 = (
        f"{pfx} Out of memory: Kill process {pid} ({process_name}) "
        f"score {score} or sacrifice child"
    )
    line2 = (
        f"{pfx} Killed process {pid} ({process_name}) "
        f"total-vm:{total_vm} kB, anon-rss:{anon_rss} kB, file-rss:{file_rss} kB"
    )
    return [line1, line2]


def _build_ext4_line(dt: datetime) -> str:
    """
    Build a single EXT4 filesystem error kern.log line.

    Args:
        dt: Timestamp to embed in the line.

    Returns:
        A fully-formatted log line string.
    """
    lineno = random.randint(300, 900)
    worker_idx = random.randint(0, 7)
    pfx = _kern_timestamp(dt)
    return (
        f"{pfx} EXT4-fs error (device nvme0n1p3): "
        f"ext4_validate_block_bitmap_csum:{lineno}: "
        f"comm kworker/u8:{worker_idx}: "
        f"bg block bitmap checksum does not match"
    )


def inject_events(kern_log_path: Path) -> None:
    """
    Append exactly 5 OOM events and 3 EXT4 errors to *kern_log_path*.

    Each injected line is also printed to stdout with the ``[INJECTED]`` prefix.

    Args:
        kern_log_path: Absolute or relative path to the kern.log file.

    Raises:
        FileNotFoundError: If *kern_log_path* does not exist.
        OSError:           On any other I/O error.
    """
    if not kern_log_path.exists():
        raise FileNotFoundError(
            f"kern.log not found at '{kern_log_path}'. "
            "Run 'python scripts/generate_mock_logs.py' first to create the mock log files."
        )

    now = datetime.now()
    injected_lines: list[str] = []

    # --- 5 OOM Killer events -----------------------------------------------
    for i in range(5):
        proc = _PROCESS_NAMES[i % len(_PROCESS_NAMES)]
        oom_pair = _build_oom_lines(now, proc)
        injected_lines.extend(oom_pair)
        logger.debug(f"Prepared OOM event {i + 1}/5 for process '{proc}'")

    # --- 3 EXT4 filesystem errors ------------------------------------------
    for i in range(3):
        ext4_line = _build_ext4_line(now)
        injected_lines.append(ext4_line)
        logger.debug(f"Prepared EXT4 error {i + 1}/3")

    # --- Append to file and echo to stdout ---------------------------------
    try:
        with kern_log_path.open("a", encoding="utf-8") as fh:
            for line in injected_lines:
                fh.write(line + "\n")
                print(f"[INJECTED] {line}")
    except OSError as exc:
        logger.error(f"Failed to write to {kern_log_path}: {exc}")
        raise

    logger.info(
        f"Injected {len(injected_lines)} lines into {kern_log_path} "
        f"(5 OOM events + 3 EXT4 errors)"
    )


def main() -> None:
    """Entry point: locate kern.log and inject synthetic panic events."""
    # Resolve paths relative to project root (one level above scripts/)
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent
    kern_log_path = project_root / "mock_logs" / "kern.log"

    logger.info(f"Target file: {kern_log_path}")

    try:
        inject_events(kern_log_path)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        print(
            f"\nError: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
    except OSError as exc:
        logger.error(f"I/O error during injection: {exc}")
        sys.exit(1)

    print(
        "\nInjection complete: 5 OOM events and 3 EXT4 errors appended to "
        f"{kern_log_path}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
