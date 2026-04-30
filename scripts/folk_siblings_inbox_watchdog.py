#!/usr/bin/env python3
"""
folk_siblings_inbox_watchdog.py — ensures folk_siblings_inbox.py is running.

Intended to run from cron every 5 minutes. Checks if the inbox HTTP server
is responding on 127.0.0.1:7878/health. If not, relaunches it via nohup
detached from the cron process.

Logs to state/inbox-watchdog.log. Prints JSON status to stdout.
"""

import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(os.environ.get("FOLK_SIBLINGS_REPO", "/opt/data/home/folk-siblings"))
SELF = os.environ.get("FOLK_SIBLINGS_SELF", "ames")
PORT = int(os.environ.get("FOLK_SIBLINGS_INBOX_PORT", "7878"))
ADDR = os.environ.get("FOLK_SIBLINGS_INBOX_ADDR", "127.0.0.1")
PYTHON = os.environ.get("FOLK_SIBLINGS_PYTHON", "/opt/folk/.venv/bin/python3")
INBOX_SCRIPT = REPO / "scripts" / "folk_siblings_inbox.py"
LOG_FILE = REPO / "state" / "inbox-watchdog.log"
STDOUT_LOG = REPO / "state" / f"inbox-{SELF}.stdout.log"


def log(msg):
    ts = datetime.now(timezone.utc).isoformat()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(f"[{ts}] {msg}\n")


def port_alive() -> bool:
    try:
        with socket.create_connection((ADDR, PORT), timeout=2):
            return True
    except Exception:
        return False


def relaunch():
    env = os.environ.copy()
    env.setdefault("FOLK_SIBLINGS_REPO", str(REPO))
    env.setdefault("FOLK_SIBLINGS_SELF", SELF)
    STDOUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with STDOUT_LOG.open("ab") as out:
        # Detach fully so the cron run can exit without killing the child.
        subprocess.Popen(
            [PYTHON, str(INBOX_SCRIPT)],
            stdout=out,
            stderr=out,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )


def main():
    if port_alive():
        print(json.dumps({"status": "ok", "alive": True, "port": PORT}))
        sys.exit(0)

    log(f"inbox NOT alive on {ADDR}:{PORT}, relaunching")
    relaunch()
    # give it a moment to bind
    for _ in range(10):
        time.sleep(0.5)
        if port_alive():
            log("relaunch successful, inbox alive")
            print(json.dumps({"status": "relaunched", "alive": True, "port": PORT}))
            sys.exit(0)
    log("relaunch FAILED, port still dead after 5s")
    print(json.dumps({"status": "relaunch_failed", "alive": False, "port": PORT}))
    sys.exit(1)


if __name__ == "__main__":
    main()
