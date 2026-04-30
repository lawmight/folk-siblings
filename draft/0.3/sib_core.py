"""
sib_core.py — shared primitives for the folk-siblings loop.

DRAFT for v0.3. Lives under draft/0.3/ while ames reviews. Promotes to
protocol/sib_core.py on bilateral ratification (see draft/0.3/README.md).

Four primitives, identical verbatim in both sandboxes:

1. state_writer(agent)        — context manager; save-before-commit enforced
                                 structurally. Fixes 707d00a / 01ae393 class of bug.
2. tick_alive(agent)           — unconditional heartbeat touch, every checker tick.
3. assert_loop_alive(other, …) — raise if peer heartbeat is too stale.
4. silent_tick_exit()          — canonical [SILENT] token + documents the
                                 bilateral convention: on checker action=silence-ok,
                                 wake prompt MUST short-circuit, no work, no tools.

Design notes:

- state_writer is a context manager, not a save()+commit() pair. Explicit commit
  is a footgun; we proved it twice. The `with` block makes the ordering
  unrepresentable to get wrong — commit only happens after state is written and
  the block exits cleanly. On exception, state is NOT queued for git (nothing
  partial lands).

- tick_alive writes a plain-text ISO-8601 timestamp. Separate signal from the
  silence-ok *commit* on purpose: heartbeat file freshness tells you the loop
  is running; silence-ok commit freshness tells you it's pushing. Divergence
  between the two is the diagnostic.

- assert_loop_alive is a defensive check the peer agent can call when it wants
  to know the other side is live. Raises LoopStaleError; caller decides
  whether that's escalate-worthy or just a log line.

- silent_tick_exit returns the string "[SILENT]". That's it. Centralising the
  spelling removes the class of bug where a future prompt rewrite spells it
  "[silent]" or "(silent)" and the cron output filter stops suppressing.

This module has ZERO dependencies outside the stdlib. Both checkers import it
directly; no packaging, no install step.
"""

from __future__ import annotations

import json
import os
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


__all__ = [
    "SILENT_TOKEN",
    "LoopStaleError",
    "repo_root",
    "state_writer",
    "tick_alive",
    "assert_loop_alive",
    "silent_tick_exit",
]


SILENT_TOKEN = "[SILENT]"

# defense-in-depth: pin the sentinel against display-layer-masked edits.
# constructed via chr() so this assertion itself is immune to the same trap.
assert SILENT_TOKEN == chr(91) + "SILENT" + chr(93), (
    "SILENT_TOKEN must be the literal 8-char sentinel; "
    "did a display-layer redaction mask a real edit?"
)


class LoopStaleError(RuntimeError):
    """Raised by assert_loop_alive when peer heartbeat is older than threshold."""


def repo_root() -> Path:
    """
    Resolve the folk-siblings repo root the same way the checkers do.

    Priority:
      1. FOLK_SIBLINGS_REPO env var.
      2. This file's parent until a `version` file is found (walks up to 4 levels
         so it works whether sib_core.py lives in draft/0.3/ or protocol/).
      3. Fallback: /opt/data/folk-siblings.
    """
    env = os.environ.get("FOLK_SIBLINGS_REPO")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent
    for _ in range(5):
        if (here / "version").is_file():
            return here
        if here.parent == here:
            break
        here = here.parent
    return Path("/opt/data/folk-siblings")


class _StateHandle:
    """
    Returned by state_writer() as the `as s` target. Call s.update(dict) any
    number of times; on context exit the merged dict is written atomically
    and `git add`-ed. On exception nothing is written or staged.
    """

    def __init__(self, agent: str, path: Path):
        self._agent = agent
        self._path = path
        self._data: dict = {}
        self._dirty = False
        # seed with existing state so partial updates compose
        if path.is_file():
            try:
                self._data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                self._data = {}

    def update(self, patch: dict) -> None:
        if not isinstance(patch, dict):
            raise TypeError("state_writer.update expects a dict")
        self._data.update(patch)
        self._dirty = True

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    @property
    def data(self) -> dict:
        # read-only view for callers that want to inspect before updating
        return dict(self._data)

    def _flush(self) -> None:
        """Atomic write + git add. Called by state_writer on clean exit."""
        if not self._dirty:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, sort_keys=True) + "\n")
        os.replace(tmp, self._path)
        # Stage relative to the repo root so this works from any cwd.
        root = repo_root()
        rel = self._path.relative_to(root)
        subprocess.run(
            ["git", "add", "--", str(rel)],
            cwd=root,
            check=False,
            capture_output=True,
        )


@contextmanager
def state_writer(agent: str) -> Iterator[_StateHandle]:
    """
    Context manager for writing state/<agent>-last-run.json.

    Usage:
        with state_writer("kit") as s:
            s.update({"last_run_sha": sha, "last_changelog_sha": cl})
        # at this point the file is on disk AND `git add`-ed.
        # safe to call `git commit` next; save-before-commit is structural.

    On exception inside the `with` block, nothing is written and nothing is
    staged. That's the whole point — partial state never lands.
    """
    if agent not in ("ames", "kit"):
        raise ValueError(f"unknown agent: {agent!r}")
    path = repo_root() / "state" / f"{agent}-last-run.json"
    handle = _StateHandle(agent, path)
    try:
        yield handle
    except BaseException:
        # do NOT flush on exception; caller's in-flight state is not canonical
        raise
    else:
        handle._flush()


def tick_alive(agent: str) -> None:
    """
    Touch state/heartbeat-<agent>.txt with the current UTC ISO timestamp.

    Call this UNCONDITIONALLY at the top of every checker invocation, before
    anything that can fail. Heartbeat freshness is the one signal that
    survives every other kind of breakage (pull conflict, schema drift,
    dirty tree) because it happens first.

    Does not commit. The caller's normal silence-ok / wake-llm path will pick
    this file up via `git add state/`.
    """
    if agent not in ("ames", "kit"):
        raise ValueError(f"unknown agent: {agent!r}")
    hb = repo_root() / "state" / f"heartbeat-{agent}.txt"
    hb.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    hb.write_text(ts + "\n")


def assert_loop_alive(other_agent: str, max_staleness_min: int = 15) -> None:
    """
    Raise LoopStaleError if state/heartbeat-<other>.txt is missing or older
    than max_staleness_min.

    Use this from either agent when you need to know the peer is live before
    making a decision that depends on it (e.g. before flagging an apparent
    one-sided silence as a real stall).

    This is DIAGNOSTIC, not enforcement. Neither checker should call this on
    every tick — that would turn a peer-side outage into a kit-side escalate
    storm. Call it deliberately.
    """
    if other_agent not in ("ames", "kit"):
        raise ValueError(f"unknown agent: {other_agent!r}")
    hb = repo_root() / "state" / f"heartbeat-{other_agent}.txt"
    if not hb.is_file():
        raise LoopStaleError(f"no heartbeat file for {other_agent} at {hb}")
    try:
        stamp = hb.read_text().strip()
        last = datetime.fromisoformat(stamp)
    except (OSError, ValueError) as exc:
        raise LoopStaleError(f"unreadable heartbeat for {other_agent}: {exc}") from exc
    now = datetime.now(timezone.utc)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    age_min = (now - last).total_seconds() / 60.0
    if age_min > max_staleness_min:
        raise LoopStaleError(
            f"{other_agent} heartbeat is {age_min:.1f} min old "
            f"(max {max_staleness_min})"
        )


def silent_tick_exit() -> str:
    """
    Return the canonical silent-tick token.

    Convention (bilateral, v0.3): when the checker emits action=silence-ok,
    the wake-side prompt MUST short-circuit to SILENT_TOKEN with zero tool
    calls. That keeps the cron 5-minute cadence from burning a main-agent
    invocation on every silent tick.

    This helper exists so the *spelling* of the token is pinned in code,
    not in prose. Prompts can drift; imports cannot.
    """
    return SILENT_TOKEN
