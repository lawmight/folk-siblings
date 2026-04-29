#!/usr/bin/env python3
"""
folk_siblings_check.py — pre-run checker for ames's cron heartbeat.

Philosophy: the checker decides whether to wake the LLM.
Most ticks should be silence-ok with no LLM invocation.

Run before the cron prompt. Writes structured context to stdout,
which the cron prompt reads as its opening fact block.

Exit codes:
  0 = either nothing to do (silence-ok, already pushed) OR LLM should run
  1 = error, escalate to tom

Output contract (stdout JSON):
  {
    "action": "silence-ok" | "wake-llm" | "escalate",
    "summary": "one-line human-readable",
    "version": "0.2",
    "changelog_new_since": "<commit-sha> or null",
    "inbox": [{"path", "sender", "kind", "subject", "correlation_id", "trace_id"}],
    "obligations": ["concise descriptions of what ames owes"],
    "loops_detected": [],
    "last_run_sha": "<sha>"
  }
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/opt/data/home/folk-siblings")
SELF = "ames"
PEER = "kit"
SUPPORTED_VERSION = "0.2"
STATE_FILE = REPO / "state" / "ames-last-run.json"


def run(cmd, cwd=REPO, check=True):
    """Run a shell command, return (stdout, stderr, returncode)."""
    r = subprocess.run(
        cmd,
        cwd=cwd,
        shell=isinstance(cmd, str),
        capture_output=True,
        text=True,
    )
    if check and r.returncode != 0:
        raise RuntimeError(f"cmd failed: {cmd}\nstderr: {r.stderr}")
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def escalate(msg, extra=None):
    out = {"action": "escalate", "summary": msg, "extra": extra or {}}
    print(json.dumps(out, indent=2))
    sys.exit(1)


def git_pull_or_escalate():
    """Pull with rebase. If conflict, escalate to tom. Don't auto-resolve."""
    _, _, rc = run("git fetch origin main", check=False)
    if rc != 0:
        escalate("git fetch failed, network or auth issue")

    # check if we're behind
    local, _, _ = run("git rev-parse HEAD")
    remote, _, _ = run("git rev-parse origin/main")
    if local == remote:
        return local  # nothing new

    # try rebase
    _, stderr, rc = run("git rebase origin/main", check=False)
    if rc != 0:
        # abort and escalate
        run("git rebase --abort", check=False)
        escalate("rebase conflict, tom needs to resolve manually", {"stderr": stderr})
    new_sha, _, _ = run("git rev-parse HEAD")
    return new_sha


def check_version():
    vfile = REPO / "version"
    if not vfile.exists():
        return SUPPORTED_VERSION  # no version file yet, assume ok
    v = vfile.read_text().strip()
    if v > SUPPORTED_VERSION:
        escalate(f"protocol v{v} is newer than ames supports ({SUPPORTED_VERSION})")
    return v


def load_last_run():
    if not STATE_FILE.exists():
        return {"last_sha": None, "last_changelog_sha": None, "replied_correlations": []}
    return json.loads(STATE_FILE.read_text())


def save_last_run(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def changelog_new_since(last_sha):
    """Return newest sha if CHANGELOG.md changed since last_sha, else None."""
    cl = REPO / "CHANGELOG.md"
    if not cl.exists():
        return None
    if last_sha is None:
        # first run, tell the agent the changelog exists
        sha, _, _ = run("git log -1 --pretty=%H -- CHANGELOG.md", check=False)
        return sha or None
    # has CHANGELOG changed since last_sha?
    log, _, rc = run(f"git log {last_sha}..HEAD --pretty=%H -- CHANGELOG.md", check=False)
    if rc != 0 or not log.strip():
        return None
    return log.splitlines()[0]


def scan_inbox():
    """Return list of letters in inbox/ames/ that aren't yet in read/ames/."""
    inbox = REPO / "inbox" / SELF
    if not inbox.exists():
        return []
    letters = []
    for f in sorted(inbox.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except Exception as e:
            # skip malformed but note it
            letters.append({"path": str(f), "error": str(e), "malformed": True})
            continue
        letters.append({
            "path": str(f.relative_to(REPO)),
            "sender": data.get("sender"),
            "kind": data.get("kind"),
            "subject": data.get("subject"),
            "correlation_id": data.get("correlation_id"),
            "trace_id": data.get("trace_id", []),
            "expects_reply": data.get("expects_reply", False),
            "sent_at": data.get("sent_at"),
        })
    return letters


def detect_loops(inbox, replied_correlations):
    """
    Return correlation_ids where ames already replied and kit's new message
    doesn't advance things. Loop guard: if trace_id length > 6, flag regardless.
    """
    loops = []
    for letter in inbox:
        cid = letter.get("correlation_id")
        trace = letter.get("trace_id", [])
        if len(trace) > 6:
            loops.append({"correlation_id": cid, "reason": "trace depth > 6"})
        elif cid and cid in replied_correlations and not letter.get("expects_reply"):
            loops.append({"correlation_id": cid, "reason": "already replied, no fresh ask"})
    return loops


def compute_obligations(inbox, loops):
    looped_cids = {l["correlation_id"] for l in loops}
    obs = []
    for letter in inbox:
        if letter.get("malformed"):
            obs.append(f"malformed letter {letter['path']} — open and triage")
            continue
        cid = letter.get("correlation_id")
        if cid in looped_cids:
            continue  # skip looped
        verb = "ack" if not letter.get("expects_reply") else "reply to"
        obs.append(
            f"{verb} {letter['sender']}'s {letter['kind']}: {letter['subject']!r} ({letter['path']})"
        )
    return obs


def silence_ok_commit():
    """Touch heartbeat file, commit with silence-ok, push."""
    hb = REPO / "state" / f"heartbeat-{SELF}.txt"
    hb.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    hb.write_text(ts + "\n")
    run("git add state/", check=False)
    _, _, rc = run(
        f'git -c user.name="ames (folk-mind)" -c user.email="tom.coustols+ames@gmail.com" '
        f'commit -m "ames: silence-ok {ts}"',
        check=False,
    )
    if rc != 0:
        # nothing staged or already committed, ok
        return
    run("git push origin main", check=False)


def main():
    # 1. pull
    current_sha = git_pull_or_escalate()

    # 2. version check
    version = check_version()

    # 3. load last-run state
    state = load_last_run()

    # 4. changelog check
    cl_new = changelog_new_since(state.get("last_changelog_sha"))

    # 5. scan inbox
    inbox = scan_inbox()

    # 6. loop detection
    loops = detect_loops(inbox, state.get("replied_correlations", []))

    # 7. obligations (excluding looped)
    obligations = compute_obligations(inbox, loops)

    # decision
    should_wake = bool(obligations) or cl_new is not None

    out = {
        "action": "wake-llm" if should_wake else "silence-ok",
        "summary": (
            f"{len(obligations)} obligation(s)"
            + (f", CHANGELOG updated" if cl_new else "")
            + (f", {len(loops)} loop(s) suppressed" if loops else "")
        ) if should_wake else "inbox empty, no changelog change, silence-ok",
        "version": version,
        "changelog_new_since": cl_new,
        "inbox": inbox,
        "obligations": obligations,
        "loops_detected": loops,
        "last_run_sha": state.get("last_sha"),
        "current_sha": current_sha,
    }

    if not should_wake:
        silence_ok_commit()

    # update state (advance last_changelog_sha even on silence, so we don't re-alert)
    new_state = {
        "last_sha": current_sha,
        "last_changelog_sha": cl_new or state.get("last_changelog_sha"),
        "replied_correlations": state.get("replied_correlations", []),
        "last_check_at": datetime.now(timezone.utc).isoformat(),
    }
    save_last_run(new_state)

    print(json.dumps(out, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
