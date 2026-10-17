#!/usr/bin/env python3
"""Sample per-process CPU and memory once a second, plus the system GPU utilization.

Each process is tagged with the app responsible for it, the way Activity Monitor groups
WebKit helper processes (WebContent, GPU, Networking) under Safari or a Dock web app.
Writes one JSON line per second until it receives SIGTERM or SIGINT.

Usage: sampler.py OUT.jsonl
"""
import ctypes
import json
import re
import signal
import subprocess
import sys
import time

_lib = ctypes.CDLL(None)
_responsible = getattr(_lib, "responsibility_get_pid_responsible_for_pid", None)
if _responsible:
    _responsible.restype = ctypes.c_int
    _responsible.argtypes = [ctypes.c_int]


def responsible_pid(pid):
    if not _responsible:
        return pid
    r = _responsible(pid)
    return r if r > 0 else pid


def cpu_seconds(s):
    """ps TIME column ("[[dd-]hh:]mm:ss.ss") to seconds."""
    days = 0
    if "-" in s:
        d, s = s.split("-", 1)
        days = int(d)
    sec = 0.0
    for part in s.split(":"):
        sec = sec * 60 + float(part)
    return days * 86400 + sec


def gpu_utilization():
    out = subprocess.run(["ioreg", "-r", "-d", "1", "-w", "0", "-c", "IOAccelerator"],
                         capture_output=True, text=True).stdout
    m = re.search(r'"Device Utilization %"=(\d+)', out)
    return int(m.group(1)) if m else None


def snapshot():
    """{pid: (cpu_seconds, rss_kb, executable_path)}"""
    out = subprocess.run(["ps", "-axo", "pid=,time=,rss=,comm="], capture_output=True, text=True).stdout
    procs = {}
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4:
            procs[int(parts[0])] = (cpu_seconds(parts[1]), int(parts[2]), parts[3])
    return procs


def command_line(pid):
    return subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()


def main():
    out_path = sys.argv[1]
    stop = False

    def on_signal(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    resp_cache = {}  # pid -> (responsible pid, its command line)
    prev, prev_t = snapshot(), time.time()
    with open(out_path, "a") as f:
        while not stop:
            time.sleep(1)
            cur, now = snapshot(), time.time()
            dt = now - prev_t
            procs = []
            for pid, (t, rss, exe) in cur.items():
                if pid not in prev or prev[pid][2] != exe:
                    continue
                cpu = (t - prev[pid][0]) / dt * 100
                name = exe.rsplit("/", 1)[-1]
                webkitish = "WebKit" in name or name in ("Safari", "Web App")
                if cpu < 0.1 and not webkitish:
                    continue  # keep the log small: idle processes are left out
                if pid not in resp_cache:
                    rp = responsible_pid(pid)
                    resp_cache[pid] = (rp, command_line(rp))
                rp, rcmd = resp_cache[pid]
                procs.append([pid, round(cpu, 2), rss, name, rp, rcmd])
            f.write(json.dumps({"t": now, "gpu": gpu_utilization(), "procs": procs}) + "\n")
            f.flush()
            prev, prev_t = cur, now


if __name__ == "__main__":
    main()
