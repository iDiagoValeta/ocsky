"""Running opencode processes, read per platform: /proc on Linux, ps and lsof on macOS and other POSIX
systems, nothing on Windows (a process's working directory needs third-party code there).

Read only. Each reader returns Proc values and the core decides what they mean.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from typing import Dict, List, Tuple

from ocsky.core.model import Proc
from ocsky.core.ports.for_listing_processes import ForListingProcesses


def is_opencode(argv: List[str]) -> bool:
    """True for the real opencode binary. npm's node wrapper is skipped, Windows adds opencode.exe."""
    if not argv:
        return False
    name = re.split(r"[\\/]", argv[0])[-1].lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name == "opencode"


def mode_of(argv: List[str]) -> str:
    return next((a for a in argv[1:] if not a.startswith("-")), "tui")


def parse_etime(text: str) -> int:
    """Seconds from ps's elapsed time, [[dd-]hh:]mm:ss."""
    days, _, rest = text.strip().rpartition("-")
    secs = 0
    for part in rest.split(":"):
        secs = secs * 60 + int(part)
    return secs + int(days or 0) * 86400


def parse_ps(out: str, now: float) -> List[Tuple[int, float, float, List[str]]]:
    """(pid, started, rss MB, argv) of the opencode lines of `ps -axo pid=,rss=,etime=,command=`."""
    rows = []
    for line in out.splitlines():
        fields = line.split(None, 3)
        if len(fields) < 4:
            continue
        argv = fields[3].split()
        if not is_opencode(argv):
            continue
        try:
            rows.append((int(fields[0]), now - parse_etime(fields[2]), int(fields[1]) / 1024, argv))
        except ValueError:
            continue
    return rows


def parse_lsof_cwd(out: str) -> Dict[int, str]:
    """pid -> working directory from `lsof -a -d cwd -Fpn -p ...`."""
    cwds: Dict[int, str] = {}
    pid = None
    for line in out.splitlines():
        if line.startswith("p") and line[1:].isdigit():
            pid = int(line[1:])
        elif line.startswith("n") and pid is not None:
            cwds[pid] = line[1:]
    return cwds


class PsProcesses:
    """macOS and other POSIX systems: ps for the processes, lsof for their working directories."""

    def processes(self) -> List[Proc]:
        try:
            out = subprocess.run(["ps", "-axo", "pid=,rss=,etime=,command="], capture_output=True,
                                 text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            return []
        rows = parse_ps(out, time.time())
        cwds: Dict[int, str] = {}
        if rows:
            try:  # lsof exits 1 when one of the processes is gone; its output is still good
                cwds = parse_lsof_cwd(subprocess.run(
                    ["lsof", "-a", "-d", "cwd", "-Fpn", "-p", ",".join(str(r[0]) for r in rows)],
                    capture_output=True, text=True, timeout=5).stdout)
            except (OSError, subprocess.SubprocessError):
                pass
        procs = [Proc(pid, mode_of(argv), cwds.get(pid, "?"), started, rss)
                 for pid, started, rss, argv in rows]
        return sorted(procs, key=lambda p: p.started)


class ProcfsProcesses:
    """Linux: everything comes from /proc."""

    def processes(self) -> List[Proc]:
        procs: List[Proc] = []
        try:
            with open("/proc/uptime") as f:
                boot = time.time() - float(f.read().split()[0])
            hz = os.sysconf("SC_CLK_TCK")
            page_mb = os.sysconf("SC_PAGE_SIZE") / 1048576
        except (OSError, ValueError):
            return procs
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open("/proc/%s/cmdline" % pid, "rb") as f:
                    argv = [a.decode(errors="replace") for a in f.read().split(b"\0") if a]
                if not is_opencode(argv):
                    continue
                cwd = os.readlink("/proc/%s/cwd" % pid)
                with open("/proc/%s/stat" % pid) as f:
                    stat = f.read().rsplit(")", 1)[1].split()
                with open("/proc/%s/statm" % pid) as f:
                    rss = int(f.read().split()[1]) * page_mb
            except (OSError, IndexError, ValueError):
                continue
            procs.append(Proc(int(pid), mode_of(argv), cwd, boot + int(stat[19]) / hz, rss))
        return sorted(procs, key=lambda p: p.started)


class NoProcesses:
    """Windows: no process list, so the sky shows the sessions without any live process."""

    def processes(self) -> List[Proc]:
        return []


def system_processes(platform: str, has_procfs: bool) -> ForListingProcesses:
    """The reader for this system. `platform` is sys.platform; `has_procfs` says /proc is there."""
    if platform.startswith("win"):
        return NoProcesses()
    if has_procfs:
        return ProcfsProcesses()
    return PsProcesses()
