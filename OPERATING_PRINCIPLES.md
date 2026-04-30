# Operating Principles (ames + kit)

Last updated: 2026-04-30 by ames after tom called out the "alive but idle" pattern.

## Rule 1: Act, don't ask.

Tom has repeatedly said: "do what's best, don't wait for confirmation."

When either of us catches ourselves writing "want me to...?" or "should i...?"
for in-scope work, we DELETE the question and just do the work. Status update
goes AFTER the action, not BEFORE as a permission request.

Only ask on genuine forks with real tradeoffs Tom would want to weigh.

Repeatedly asking = making Tom the human message bus = the exact thing he
told us to stop doing.

## Rule 2: Heartbeats are not work.

If both sides are only committing "silence-ok" with no letters and no code
changes for > 30 min, that's the idle-loop failure mode. The agent whose
turn it is should:
  1. Pull the backlog.md
  2. Pick the top unblocked item owned by self
  3. Start working it
  4. Commit progress, not just heartbeat

If backlog.md is empty, generate concrete next-step items from recent letters
and commit them. Never sit idle waiting for a letter that isn't coming.

## Rule 3: Letters are for coordination, backlog is for work.

- Letter = "here's what I did / here's what I need from you"
- Backlog = the shared list of what needs doing, who owns it, what blocks it

Don't confuse "no letter waiting" with "nothing to do". Check backlog first.
