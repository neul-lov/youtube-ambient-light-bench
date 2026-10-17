#!/usr/bin/env python3
"""Turn a run's events (phase start/end posted by the page) and samples into a table.

CPU is in % of one core, averaged over each phase and summed over the processes the matching
app is responsible for, split by process type. The first and last second of every phase are
skipped. "vs base" is the difference to the average of the phases named "... video only ...".

Usage:
  analyze.py RUN_DIR [--app REGEX]          phases from RUN_DIR/events.jsonl
  analyze.py RUN_DIR --whole LABEL [--app]  one row covering every sample (no page events)

--app matches the responsible app's command line (default: Safari).
"""
import argparse
import json
import os
import re


def kind(name, resp_cmd):
    if "WebContent" in name:
        return "WebContent"
    if name.endswith(".GPU") or name == "com.apple.WebKit.GPU":
        return "GPU proc"
    if "Networking" in name:
        return "Network"
    return "App"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--app", default=r"Safari\.app/Contents/MacOS/Safari")
    ap.add_argument("--whole")
    a = ap.parse_args()
    app = re.compile(a.app)

    samples = [json.loads(l) for l in open(os.path.join(a.run, "samples.jsonl")) if l.strip()]
    if a.whole:
        events = [{"ev": "end", "name": a.whole, "t": samples[-1]["t"] + 1, "_t0": samples[0]["t"] - 1}]
    else:
        events = [json.loads(l) for l in open(os.path.join(a.run, "events.jsonl")) if l.strip()]
        for e in events:
            if e["ev"] in ("ready", "selfcheck", "phaseError", "playError"):
                print({k: v for k, v in e.items() if k not in ("t", "ua")})
    starts = {e["name"]: e["t"] for e in events if e["ev"] == "start"}

    kinds = ["App", "WebContent", "GPU proc", "Network"]
    rows = []
    for e in events:
        if e["ev"] != "end":
            continue
        t0 = e.get("_t0", starts.get(e["name"], e["t"])) + 1
        t1 = e["t"] - 1
        win = [s for s in samples if t0 <= s["t"] <= t1]
        if not win:
            print(f"{e['name'][:44]:44} (no samples: phase shorter than 3 s)")
            continue
        per = dict.fromkeys(kinds, 0.0)
        for s in win:
            for pid, cpu, rss, name, rp, rcmd in s["procs"]:
                if app.search(rcmd):
                    per[kind(name, rcmd)] += cpu / len(win)
        gpu = [s["gpu"] for s in win if s["gpu"] is not None]
        rows.append((e, sum(per.values()), per, sum(gpu) / len(gpu) if gpu else float("nan"), len(win)))

    base = [r[1] for r in rows if "video only" in r[0]["name"]]
    base = sum(base) / len(base) if base else None
    head = f"{'phase':44} {'total':>6} {'vs base':>7} " + " ".join(f"{k:>10}" for k in kinds) + f" {'gpu%':>5}  page stats"
    print(head)
    print("-" * len(head))
    for e, total, per, gpu, n in rows:
        vs = f"{total - base:+7.1f}" if base is not None else "      -"
        stats = {k: e[k] for k in ("fpsDone", "rvfcPerSec", "jsMsPerFrame", "dropped", "errs", "lastErr", "uploadsPerSec", "glow") if e.get(k) not in (None, "")}
        print(f"{e['name'][:44]:44} {total:6.1f} {vs} " + " ".join(f"{per[k]:10.1f}" for k in kinds) + f" {gpu:5.0f}  {stats} (n={n})")


if __name__ == "__main__":
    main()
