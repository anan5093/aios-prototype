"""
generate_mock_logs.py — Generate realistic synthetic log files for AIOS prototype testing.

Produces:
  mock_logs/syslog        — System log with memory pressure, OOM, disk events
  mock_logs/kern.log      — Kernel log with OOM killer, CPU lockup, EXT4 errors
  mock_logs/bash_history  — Shell history with monitoring, git, python commands

Run from project root:
    python scripts/generate_mock_logs.py

All output goes to mock_logs/ relative to the project root (one level up from scripts/).
"""

import logging
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging configuration (file-level)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("generate_mock_logs")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEED = 42
HOSTNAME = "aios-dev-host"
USERNAME = "aios-user"
DAYS = 14

# Month abbreviations (indices 0–11)
MONTH_ABBR = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_syslog_ts(dt: datetime) -> str:
    """Return a syslog-style timestamp: 'Mon DD HH:MM:SS'."""
    day_str = f"{dt.day:2d}"  # right-justified, space-padded
    return f"{MONTH_ABBR[dt.month - 1]} {day_str} {dt.strftime('%H:%M:%S')}"


def _fmt_kern_uptime(dt: datetime, base: datetime) -> str:
    """Return a kernel uptime string: '[NNNNNNN.NNNNNN]'."""
    delta = (dt - base).total_seconds()
    seconds_int = int(delta)
    micro = random.randint(0, 999999)
    return f"[{seconds_int:7d}.{micro:06d}]"


def _rand_timestamps(rng: random.Random, n: int, end: datetime, days: int) -> list:
    """Generate *n* sorted random datetimes within the past *days* days."""
    start = end - timedelta(days=days)
    span = (end - start).total_seconds()
    offsets = sorted(rng.uniform(0, span) for _ in range(n))
    return [start + timedelta(seconds=s) for s in offsets]


# Process / service name pools
SYSTEMD_SERVICES = [
    "nginx", "postgresql", "redis", "sshd", "cron", "rsyslog",
    "docker", "aios-daemon", "networkd", "resolved",
]
CRON_JOBS = [
    "backup.sh", "cleanup_logs.sh", "health_check.py",
    "db_vacuum.sh", "sync_data.sh",
]
NM_EVENTS = [
    "NetworkManager: <info> [{}] device (eth0): state change: activated -> disconnected",
    "NetworkManager: <info> [{}] device (eth0): state change: disconnected -> prepare",
    "NetworkManager: <info> [{}] device (eth0): state change: prepare -> config",
    "NetworkManager: <info> [{}] device (eth0): state change: config -> ip-config",
    "NetworkManager: <info> [{}] device (eth0): state change: ip-config -> activated",
    "NetworkManager: <info> [{}] connectivity check started",
]
SSH_EVENTS = [
    f"sshd[{{pid}}]: Accepted publickey for {USERNAME} from 192.168.1.{{src}} port {{port}} ssh2",
    f"sshd[{{pid}}]: Disconnected from user {USERNAME} 192.168.1.{{src}} port {{port}}",
    "sshd[{pid}]: Invalid user admin from 10.0.0.{src} port {port}",
    "sshd[{pid}]: pam_unix(sshd:session): session opened for user {user} by (uid=0)".format(user=USERNAME, pid="{pid}"),
    "sshd[{pid}]: pam_unix(sshd:session): session closed for user {user}".format(user=USERNAME, pid="{pid}"),
]
PROCESS_NAMES = [
    "python3", "chrome", "firefox", "node", "java",
    "postgres", "redis-server", "nginx", "docker-proxy",
    "aios-daemon", "llm-worker", "embed-worker",
]


# ===========================================================================
# SYSLOG GENERATOR
# ===========================================================================

def generate_syslog(rng: random.Random, end_time: datetime) -> list[str]:
    """
    Generate ~600 lines of /var/log/syslog-style content.

    Returns a list of fully-formatted log line strings (no trailing newline).
    """
    logger.info("Generating syslog entries …")
    lines: list[str] = []
    target = 600

    # --- Mandatory: ≥30 memory-pressure WARN entries -----------------------
    n_mem_warn = max(30, rng.randint(30, 40))
    mem_warn_times = _rand_timestamps(rng, n_mem_warn, end_time, DAYS)
    for dt in mem_warn_times:
        avail_mb = rng.randint(150, 900)
        ts = _fmt_syslog_ts(dt)
        pid = rng.randint(100, 9999)
        lines.append(
            f"{ts} {HOSTNAME} kernel[{pid}]: "
            f"WARN: Memory pressure detected. Available: {avail_mb}mb / 7930MB"
        )

    # --- Mandatory: ≥20 failed-allocation ERROR entries --------------------
    n_alloc_err = max(20, rng.randint(20, 30))
    alloc_err_times = _rand_timestamps(rng, n_alloc_err, end_time, DAYS)
    for dt in alloc_err_times:
        req_mb = rng.randint(50, 500)
        proc = rng.choice(PROCESS_NAMES)
        pid = rng.randint(1000, 65535)
        ts = _fmt_syslog_ts(dt)
        lines.append(
            f"{ts} {HOSTNAME} kernel[1]: "
            f"ERROR: Failed to allocate {req_mb}MB for process {proc} (pid {pid})"
        )

    # --- Mandatory: disk I/O timeout (kworker blocked) ---------------------
    n_io_timeout = rng.randint(5, 15)
    io_timeout_times = _rand_timestamps(rng, n_io_timeout, end_time, DAYS)
    base_time = end_time - timedelta(days=DAYS)
    for dt in io_timeout_times:
        uptime = _fmt_kern_uptime(dt, base_time)
        worker_id = rng.randint(0, 7)
        worker_pid = rng.randint(100, 999)
        ts = _fmt_syslog_ts(dt)
        lines.append(
            f"{ts} {HOSTNAME} kernel: {uptime} "
            f"INFO: task kworker/u8:{worker_id}:{worker_pid} blocked for more than 120 seconds"
        )

    # --- Filler: systemd start/stop events ----------------------------------
    remaining = target - len(lines)
    n_systemd = remaining // 4
    systemd_times = _rand_timestamps(rng, n_systemd, end_time, DAYS)
    for dt in systemd_times:
        svc = rng.choice(SYSTEMD_SERVICES)
        action = rng.choice(["Started", "Stopped", "Reloading", "Restarted", "Failed to start"])
        pid = rng.randint(100, 9999)
        ts = _fmt_syslog_ts(dt)
        lines.append(
            f"{ts} {HOSTNAME} systemd[1]: {action} {svc}.service"
        )

    # --- Filler: cron completions -------------------------------------------
    n_cron = remaining // 6
    cron_times = _rand_timestamps(rng, n_cron, end_time, DAYS)
    for dt in cron_times:
        job = rng.choice(CRON_JOBS)
        exit_code = rng.choice([0, 0, 0, 1])
        ts = _fmt_syslog_ts(dt)
        lines.append(
            f"{ts} {HOSTNAME} CRON[{rng.randint(1000, 9999)}]: "
            f"({USERNAME}) CMD (/etc/cron.d/{job}) exit={exit_code}"
        )

    # --- Filler: NetworkManager events --------------------------------------
    n_nm = remaining // 6
    nm_times = _rand_timestamps(rng, n_nm, end_time, DAYS)
    for dt in nm_times:
        tmpl = rng.choice(NM_EVENTS)
        ts = _fmt_syslog_ts(dt)
        lines.append(f"{ts} {HOSTNAME} " + tmpl.format(dt.strftime("%H:%M:%S")))

    # --- Filler: sshd events ------------------------------------------------
    n_ssh = remaining // 6
    ssh_times = _rand_timestamps(rng, n_ssh, end_time, DAYS)
    for dt in ssh_times:
        ts = _fmt_syslog_ts(dt)
        pid = rng.randint(1000, 9999)
        src = rng.randint(10, 254)
        port = rng.randint(40000, 65000)
        tmpl = rng.choice(SSH_EVENTS)
        msg = tmpl.format(pid=pid, src=src, port=port)
        lines.append(f"{ts} {HOSTNAME} {msg}")

    # --- Filler: generic kernel / rsyslog messages -------------------------
    n_misc = max(0, target - len(lines))
    misc_times = _rand_timestamps(rng, n_misc, end_time, DAYS)
    misc_msgs = [
        "kernel: [{}] audit: type=1400 audit({}:1): apparmor=\"ALLOWED\"",
        "rsyslog: rsyslogd was HUPed",
        "kernel: [{}] NET: Registered PF_INET6 protocol family",
        "kernel: [{}] random: crng reseeded on system resumption",
        "dbus-daemon[1]: [system] Activating via systemd: service name='org.freedesktop.nm' unit",
        "kernel: [{}] usb 1-1: USB disconnect, device number 2",
        "kernel: [{}] usb 1-1: new high-speed USB device number 3 using xhci_hcd",
    ]
    for dt in misc_times:
        uptime = _fmt_kern_uptime(dt, base_time)
        ts = _fmt_syslog_ts(dt)
        tmpl = rng.choice(misc_msgs)
        msg = tmpl.format(uptime, uptime)
        lines.append(f"{ts} {HOSTNAME} {msg}")

    # Sort all lines by the chronological position (stable: we use timestamps embedded)
    # Since timestamp strings sort lexicographically within a month, we sort by creation index
    # Instead, re-sort by attaching a sortable key derived from line content is fragile;
    # we collected timestamps separately so just sort by lines list position doesn't work.
    # Simplest approach: regenerate with timestamps attached, then sort.
    tagged: list[tuple[datetime, str]] = []

    def _collect(times: list, line_list: list[str], offset: int) -> None:
        for i, t in enumerate(times):
            tagged.append((t, line_list[offset + i]))

    # rebuild tagged list properly
    tagged2: list[tuple[datetime, str]] = []
    all_dt_iter = (
        list(zip(mem_warn_times, lines[:n_mem_warn]))
        + list(zip(alloc_err_times, lines[n_mem_warn:n_mem_warn + n_alloc_err]))
        + list(zip(io_timeout_times, lines[n_mem_warn + n_alloc_err:n_mem_warn + n_alloc_err + n_io_timeout]))
    )
    # The filler lines are harder to pair back; sort the whole lines list by their embedded timestamp
    # The syslog timestamp prefix "Mon DD HH:MM:SS" is always the first 15 chars
    def _syslog_sort_key(line: str) -> str:
        # Use the raw timestamp prefix for sorting (works within same month)
        return line[:15]

    lines.sort(key=_syslog_sort_key)

    logger.info(f"Generated {len(lines)} syslog lines (target {target})")
    return lines


# ===========================================================================
# KERN.LOG GENERATOR
# ===========================================================================

def generate_kern_log(rng: random.Random, end_time: datetime) -> list[str]:
    """
    Generate ~500 lines of kern.log content.

    Returns a list of fully-formatted log line strings.
    """
    logger.info("Generating kern.log entries …")
    lines: list[str] = []
    target = 500
    base_time = end_time - timedelta(days=DAYS)

    def _kern_prefix(dt: datetime) -> str:
        return f"{_fmt_syslog_ts(dt)} {HOSTNAME} kernel: {_fmt_kern_uptime(dt, base_time)}"

    # --- Mandatory: ≥20 OOM Killer events (pairs of 2 lines each) ----------
    n_oom = max(20, rng.randint(20, 28))
    oom_times = _rand_timestamps(rng, n_oom, end_time, DAYS)
    for dt in oom_times:
        proc = rng.choice(PROCESS_NAMES)
        pid = rng.randint(1000, 32768)
        score = rng.randint(1, 999)
        total_vm = rng.randint(200000, 2000000)
        anon_rss = rng.randint(50000, 800000)
        file_rss = rng.randint(100, 10000)
        pfx = _kern_prefix(dt)
        lines.append(
            f"{pfx} Out of memory: Kill process {pid} ({proc}) score {score} or sacrifice child"
        )
        lines.append(
            f"{pfx} Killed process {pid} ({proc}) "
            f"total-vm:{total_vm} kB, anon-rss:{anon_rss} kB, file-rss:{file_rss} kB"
        )

    # --- Mandatory: CPU soft lockup events ---------------------------------
    n_lockup = rng.randint(5, 12)
    lockup_times = _rand_timestamps(rng, n_lockup, end_time, DAYS)
    for dt in lockup_times:
        cpu_id = rng.randint(0, 7)
        stuck_secs = rng.choice([22, 23, 23, 24])
        proc = rng.choice(PROCESS_NAMES)
        pid = rng.randint(1000, 32768)
        pfx = _kern_prefix(dt)
        lines.append(
            f"{pfx} watchdog: BUG: soft lockup - CPU#{cpu_id} stuck for {stuck_secs}s!"
            f" [{proc}:{pid}]"
        )

    # --- Mandatory: NVMe I/O timeout & queue info ---------------------------
    n_nvme = rng.randint(8, 18)
    nvme_times = _rand_timestamps(rng, n_nvme, end_time, DAYS)
    for i, dt in enumerate(nvme_times):
        pfx = _kern_prefix(dt)
        if i % 3 == 0:
            io_id = rng.randint(0, 127)
            lines.append(f"{pfx} nvme nvme0: I/O {io_id} timeout, reset controller")
        else:
            lines.append(f"{pfx} nvme nvme0: 1/0/0 default/read/poll queues")

    # --- Mandatory: EXT4 filesystem errors ---------------------------------
    n_ext4 = rng.randint(6, 14)
    ext4_times = _rand_timestamps(rng, n_ext4, end_time, DAYS)
    for dt in ext4_times:
        lineno = rng.randint(300, 900)
        worker_id = rng.randint(0, 7)
        worker_pid = rng.randint(100, 999)
        pfx = _kern_prefix(dt)
        lines.append(
            f"{pfx} EXT4-fs error (device nvme0n1p3): "
            f"ext4_validate_block_bitmap_csum:{lineno}: comm kworker/u8:{worker_id}: "
            f"bg block bitmap checksum does not match"
        )

    # --- Mandatory: process exit events ------------------------------------
    n_exit = rng.randint(15, 30)
    exit_times = _rand_timestamps(rng, n_exit, end_time, DAYS)
    for dt in exit_times:
        proc = rng.choice(PROCESS_NAMES)
        pid = rng.randint(1, 32768)
        status = rng.choice([0, 0, 0, 1, 1, 127, 139, 2])
        pfx = _kern_prefix(dt)
        lines.append(f"{pfx} process '{proc}' (pid {pid}) exited with status {status}")

    # --- Filler: general kernel messages -----------------------------------
    remaining = max(0, target - len(lines))
    filler_times = _rand_timestamps(rng, remaining, end_time, DAYS)
    filler_msgs = [
        "ACPI: \_SB_.LNKB: Enabled at IRQ 11",
        "ACPI: \_SB_.LNKC: Enabled at IRQ 10",
        "NET: Registered PF_INET6 protocol family",
        "IPv6: ADDRCONF(NETDEV_UP): eth0: link is not ready",
        "IPv6: ADDRCONF(NETDEV_CHANGE): eth0: link becomes ready",
        "clocksource: tsc-early: mask: 0xffffffffffffffff max_cycles: 0x24093b6b8ee",
        "clocksource: Switched to clocksource tsc",
        "pci 0000:00:02.0: BAR 0: assigned [mem 0xb0000000-0xbfffffff 64bit]",
        "thermal thermal_zone0: critical temperature reached (101 C), shutting down",
        "perf: interrupt took too long (2574 > 2500), lowering kernel.perf_event_max_sample_rate to 77500",
        "audit: type=1400 audit(1234567890.123:456): apparmor=\"DENIED\" operation=\"exec\"",
        "input: AT Translated Set 2 keyboard as /devices/platform/i8042/serio0/input/input0",
        "mce: CPU supports 24 MCE banks",
        "usb 3-1: new SuperSpeed Gen 1 USB device number 4 using xhci_hcd",
        "EXT4-fs (nvme0n1p3): mounted filesystem with ordered data mode",
        "EXT4-fs (nvme0n1p3): re-mounted. Opts: errors=remount-ro",
        "random: crng reseeded on system resumption",
        "igb 0000:00:19.0 eth0: igb: eth0 NIC Link is Up 1000 Mbps Full Duplex",
        "SCSI subsystem initialized",
        "ahci 0000:00:1f.2: version 3.0",
    ]
    for dt in filler_times:
        pfx = _kern_prefix(dt)
        msg = rng.choice(filler_msgs)
        lines.append(f"{pfx} {msg}")

    # Sort by syslog timestamp prefix (first 15 chars)
    lines.sort(key=lambda l: l[:15])

    logger.info(f"Generated {len(lines)} kern.log lines (target {target})")
    return lines


# ===========================================================================
# BASH HISTORY GENERATOR
# ===========================================================================

def generate_bash_history(rng: random.Random) -> list[str]:
    """
    Generate ≥400 lines of bash_history content (one command per line).

    Returns a list of command strings.
    """
    logger.info("Generating bash_history entries …")

    # --- Mandatory one-shot commands ----------------------------------------
    mandatory = [
        # System monitoring
        "top",
        "htop",
        "free -h",
        "df -h",
        "iostat -x 1 5",
        "vmstat 1 5",
        "iotop",
        "nethogs",
        # Process management
        "kill -9 1847",
        "renice -n 10 -p 2341",
        "nice -n 5 python script.py",
        # Systemctl
        "systemctl status nginx",
        "systemctl restart postgresql",
        "systemctl list-units --failed",
        # Journalctl
        "journalctl -n 50",
        "journalctl -u daemon.service -f",
        'journalctl --since "1 hour ago"',
        # Git
        "git status",
        'git commit -m "fix: memory leak in embedder"',
        "git push origin main",
        "git log --oneline -10",
        # Python daemon
        "python daemon/main.py",
        "python -m pytest tests/ -v",
        "pip install -r daemon/requirements.txt",
        # Node/frontend
        "npm run dev",
        "npm install",
        "cd api && node server.js",
        # File ops
        "ls -la data/",
        "cat data/simulation_state.json",
        "tail -f mock_logs/syslog",
    ]

    # --- Extended variant pool to reach ≥400 lines -------------------------
    variants = [
        # Monitoring variants
        "top -b -n 1 | head -20",
        "htop -d 5",
        "free -m",
        "free -g",
        "df -h --output=source,fstype,size,used,avail,pcent",
        "df -i",
        "iostat -x 1 10",
        "iostat -d 1 5",
        "vmstat 2 10",
        "vmstat -s",
        "iotop -o",
        "iotop -b -n 5",
        "nethogs eth0",
        "nethogs -t",
        "sar -u 1 5",
        "sar -r 1 5",
        "sar -d 1 5",
        "mpstat -P ALL 1 5",
        "pidstat -u 1 5",
        "pidstat -d 1 5",
        "dstat --cpu --mem --disk --net",
        "nload eth0",
        "bmon",
        "iftop -i eth0",
        "watch -n 1 free -h",
        "watch -n 2 df -h",
        "watch -n 5 'systemctl list-units --failed'",
        "ps aux --sort=-%mem | head -20",
        "ps aux --sort=-%cpu | head -20",
        "ps aux | grep python",
        "ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%mem | head -15",
        "pgrep -a chrome",
        "pgrep -a python",
        "lsof -i :8080",
        "lsof -i :5432",
        "lsof -i :6379",
        "ss -tunap",
        "netstat -tulnp",
        "strace -p 1847 -c",
        "ltrace -p 2341 -c",
        "perf top",
        "perf stat python daemon/main.py",
        "valgrind --leak-check=full python daemon/main.py",
        # Process management variants
        "kill -15 2341",
        "kill -SIGTERM 3456",
        "pkill -9 chrome",
        "pkill -f 'python daemon'",
        "killall -9 node",
        "renice -n -5 -p 1847",
        "renice -n 15 -p 3456",
        "nice -n -10 ./high_priority_task.sh",
        "nice -n 19 ./low_priority_backup.sh",
        "taskset -c 0-3 python daemon/main.py",
        "chrt -f 50 python daemon/main.py",
        "ulimit -v 4000000",
        "ulimit -a",
        # Systemctl variants
        "systemctl status postgresql",
        "systemctl status redis",
        "systemctl status aios-daemon",
        "systemctl status docker",
        "systemctl start nginx",
        "systemctl stop nginx",
        "systemctl restart redis",
        "systemctl reload nginx",
        "systemctl enable aios-daemon",
        "systemctl disable nginx",
        "systemctl daemon-reload",
        "systemctl list-units --type=service",
        "systemctl list-units --state=failed",
        "systemctl show postgresql --property=MainPID",
        "systemctl cat nginx",
        # Journalctl variants
        "journalctl -n 100",
        "journalctl -n 200 --no-pager",
        "journalctl -u nginx -f",
        "journalctl -u postgresql -n 50",
        "journalctl -u aios-daemon --since today",
        'journalctl --since "2 hours ago" --until "1 hour ago"',
        'journalctl --since "yesterday"',
        "journalctl -p err -n 50",
        "journalctl -p warning -n 100",
        "journalctl -k -n 50",
        "journalctl -k --since today",
        "journalctl --disk-usage",
        "journalctl --vacuum-size=500M",
        "journalctl -b -1 -n 100",
        "journalctl -b 0 -p err",
        # Git variants
        "git diff",
        "git diff HEAD~1",
        "git log --oneline -20",
        "git log --graph --oneline --all -15",
        "git branch -a",
        "git checkout -b feature/oom-detection",
        "git checkout main",
        "git pull origin main",
        "git stash",
        "git stash pop",
        "git add -A",
        "git add daemon/embedder.py",
        'git commit -m "feat: add faiss vector store"',
        'git commit -m "fix: handle zero-norm embeddings"',
        'git commit -m "chore: update requirements"',
        'git commit -m "test: add atlas connection test"',
        "git push origin feature/oom-detection",
        "git tag -a v0.1.0 -m 'initial prototype'",
        "git remote -v",
        "git fetch --all",
        # Python variants
        "python daemon/main.py --debug",
        "python daemon/main.py --log-level=DEBUG",
        "python scripts/generate_mock_logs.py",
        "python scripts/inject_panic.py",
        "python scripts/ingest_mock_logs.py",
        "python scripts/test_atlas_connection.py",
        "python -m pytest tests/ -v --tb=short",
        "python -m pytest tests/test_embedder.py -v",
        "python -m pytest tests/ -k 'test_oom'",
        "python -m pytest tests/ --cov=daemon --cov-report=html",
        "pip install -r requirements.txt",
        "pip install sentence-transformers faiss-cpu pymongo python-dotenv",
        "pip list | grep faiss",
        "pip show sentence-transformers",
        "pip freeze > requirements.txt",
        "python -c 'import faiss; print(faiss.__version__)'",
        "python -c 'from daemon.embedder import EmbeddingService; e=EmbeddingService(); print(e.embed_single(\"test\").shape)'",
        "python -c 'from daemon.faiss_store import FAISSStore; print(\"ok\")'",
        "python -m cProfile -o profile.out daemon/main.py",
        "python -m pstats profile.out",
        # Node/frontend variants
        "npm run build",
        "npm run test",
        "npm run lint",
        "npm audit",
        "npm audit fix",
        "npm update",
        "npm list",
        "cd api && node server.js --port=3000",
        "cd frontend && npm run dev",
        "cd frontend && npm run build",
        "node -e 'console.log(process.version)'",
        "npx nodemon api/server.js",
        # File ops variants
        "ls -la scripts/",
        "ls -la daemon/",
        "ls -la mock_logs/",
        "ls -lh data/",
        "cat mock_logs/syslog | tail -50",
        "cat mock_logs/kern.log | grep OOM",
        "tail -f mock_logs/kern.log",
        "tail -100 mock_logs/syslog",
        "head -50 mock_logs/bash_history",
        "wc -l mock_logs/syslog mock_logs/kern.log mock_logs/bash_history",
        "grep -c 'ERROR' mock_logs/syslog",
        "grep -c 'Out of memory' mock_logs/kern.log",
        "grep -n 'soft lockup' mock_logs/kern.log",
        "grep 'WARN' mock_logs/syslog | tail -20",
        "awk '{print $5}' mock_logs/syslog | sort | uniq -c | sort -rn",
        "sed -n '1,100p' mock_logs/syslog",
        "cut -d' ' -f1-3 mock_logs/syslog | uniq -c | sort -rn | head",
        "less mock_logs/syslog",
        "vim mock_logs/syslog",
        "nano daemon/embedder.py",
        "cat data/simulation_state.json | python -m json.tool",
        "mkdir -p data/backups",
        "cp data/faiss_index.bin data/backups/faiss_index.bin.bak",
        "cp data/faiss_metadata.pkl data/backups/faiss_metadata.pkl.bak",
        "du -sh data/",
        "du -sh mock_logs/",
        "find . -name '*.py' | xargs wc -l | sort -rn | head",
        "find . -name '*.log' -mtime -1",
        "chmod +x scripts/generate_mock_logs.py",
        "chmod +x scripts/inject_panic.py",
        "env | grep ATLAS",
        "cat .env",
        "cp .env.example .env",
        "export PYTHONPATH=$PYTHONPATH:$(pwd)",
        "source venv/bin/activate",
        "deactivate",
        "python -m venv venv",
        "which python",
        "python --version",
        "uname -r",
        "lscpu",
        "lsmem",
        "dmidecode -t memory | grep -i size",
        "cat /proc/meminfo",
        "cat /proc/cpuinfo | grep 'model name' | head -1",
        "uptime",
        "who",
        "last | head -20",
        "history | tail -50",
        "clear",
        "pwd",
        "echo $PATH",
        "echo $PYTHONPATH",
        "export ATLAS_URI='mongodb+srv://user:pass@cluster.mongodb.net/'",
        "unset ATLAS_URI",
        "ssh-keygen -t ed25519 -C 'aios-dev'",
        "scp data/faiss_index.bin remote:/backup/",
        "rsync -avz mock_logs/ remote:/backup/logs/",
        "curl -X POST http://localhost:8080/api/query -d '{\"q\":\"OOM\"}'",
        "curl http://localhost:8080/health",
        "wget https://example.com/dataset.tar.gz",
        "tar -xzf dataset.tar.gz -C data/",
        "gzip -9 mock_logs/syslog",
        "gunzip mock_logs/syslog.gz",
        "diff mock_logs/syslog.old mock_logs/syslog",
        "sort mock_logs/bash_history | uniq | wc -l",
        "make clean",
        "make all",
        "make test",
        "docker ps",
        "docker ps -a",
        "docker logs aios-container --tail 50",
        "docker exec -it aios-container bash",
        "docker-compose up -d",
        "docker-compose down",
        "docker stats --no-stream",
        "tmux new -s aios",
        "tmux attach -t aios",
        "screen -S monitor",
        "nohup python daemon/main.py &",
        "fg %1",
        "jobs",
        "disown %1",
    ]

    # Build the full list: mandatory first, then shuffled variants to fill ≥400
    commands: list[str] = list(mandatory)

    # Shuffle variants and add until we reach ≥400
    rng.shuffle(variants)
    while len(commands) < 400:
        commands.extend(variants)

    # Trim to exactly 400+ (keep first 400 or more)
    commands = commands[:max(400, len(mandatory) + len(variants))]

    # Shuffle the full list for realistic interleaving
    rng.shuffle(commands)

    logger.info(f"Generated {len(commands)} bash_history lines (target ≥400)")
    return commands


# ===========================================================================
# MAIN
# ===========================================================================

def main() -> None:
    """Entry point: generate all three mock log files."""
    rng = random.Random(SEED)
    end_time = datetime.now()

    # Resolve the project root (one level up from this script's directory)
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent
    mock_logs_dir = project_root / "mock_logs"

    logger.info(f"Project root: {project_root}")
    logger.info(f"Mock logs directory: {mock_logs_dir}")

    # Create output directory
    try:
        mock_logs_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {mock_logs_dir}")
    except OSError as exc:
        logger.error(f"Cannot create mock_logs directory: {exc}")
        sys.exit(1)

    # Generate content
    syslog_lines = generate_syslog(rng, end_time)
    kern_lines = generate_kern_log(rng, end_time)
    bash_lines = generate_bash_history(rng)

    # --- Write syslog -------------------------------------------------------
    syslog_path = mock_logs_dir / "syslog"
    try:
        with syslog_path.open("w", encoding="utf-8") as fh:
            fh.write("\n".join(syslog_lines) + "\n")
        logger.info(f"Wrote {len(syslog_lines)} lines to {syslog_path}")
    except OSError as exc:
        logger.error(f"Failed to write syslog: {exc}")
        sys.exit(1)

    # --- Write kern.log -----------------------------------------------------
    kern_path = mock_logs_dir / "kern.log"
    try:
        with kern_path.open("w", encoding="utf-8") as fh:
            fh.write("\n".join(kern_lines) + "\n")
        logger.info(f"Wrote {len(kern_lines)} lines to {kern_path}")
    except OSError as exc:
        logger.error(f"Failed to write kern.log: {exc}")
        sys.exit(1)

    # --- Write bash_history -------------------------------------------------
    bash_path = mock_logs_dir / "bash_history"
    try:
        with bash_path.open("w", encoding="utf-8") as fh:
            fh.write("\n".join(bash_lines) + "\n")
        logger.info(f"Wrote {len(bash_lines)} lines to {bash_path}")
    except OSError as exc:
        logger.error(f"Failed to write bash_history: {exc}")
        sys.exit(1)

    # --- Compute statistics for validation summary --------------------------
    oom_count = sum(
        1 for line in kern_lines
        if "Out of memory: Kill process" in line
    )
    mem_pressure_count = sum(
        1 for line in syslog_lines
        if "WARN: Memory pressure detected" in line
    )
    total_lines = len(syslog_lines) + len(kern_lines) + len(bash_lines)

    # --- Print validation summary to stdout (not logging) ------------------
    print("=== Mock Log Generation Complete ===")
    print(f"Generated mock_logs/syslog:       {len(syslog_lines):>4} lines")
    print(f"Generated mock_logs/kern.log:     {len(kern_lines):>4} lines")
    print(f"Generated mock_logs/bash_history: {len(bash_lines):>4} lines")
    print(f"Total:                            {total_lines:>4} lines")
    print(f"OOM events in kern.log:           {oom_count:>4}")
    print(f"Memory pressure entries in syslog: {mem_pressure_count:>3}")


if __name__ == "__main__":
    main()
