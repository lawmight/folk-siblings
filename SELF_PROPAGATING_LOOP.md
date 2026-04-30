# The Self-Propagating Task Loop (v0.4)

Tom's vision for how ames + kit should operate, as of 2026-04-30.

Each task in cronjobs.json follows this lifecycle:

1. EXECUTE. Do the assigned task.
2. RECORD. Keep track of interesting entities surfaced during execution (people, repos, articles, tools, ideas, open questions).
3. EVALUATE. Look at the core goal. Did this execution produce anything that advances the goal?
4. SPAWN. If yes, write a new cronjob with specific follow-up instructions pointing at the new entity. Not a vague 'investigate further' — a concrete action on a concrete target.
5. CLEANUP. Delete the current task from the queue (if one-shot). Sleep.

## Why this shape

Backlogs + polling is passive. This is active. Each successful task creates its own children, so the agent's attention fans out into the territory worth exploring instead of grinding the same list forever.

It means:
- Cron queue is dynamic, not static
- Tasks carry their own termination (cleanup step)
- The goal is the only durable state; tasks are ephemeral
- Entities discovered become first-class follow-up targets

## Implementation requirements

Every cron prompt must end with the Evaluate+Spawn+Cleanup block:

- A fixed "goal" string the agent compares against
- An "interesting entities" list collected during execution
- Criteria for what counts as goal-relevant
- Permission + mechanism to write a new cronjob (cronjob tool, already available)
- Permission + mechanism to delete self (cronjob action=remove with own job_id)

## Open questions

- Where does the "core goal" live? Single file both agents read? Per-agent?
- How do we avoid runaway spawning (N tasks each spawning M children → explosion)?
  Probably: hard cap on queue depth per agent, plus evaluate step must reject
  low-confidence matches.
- How does cleanup know its own job_id? The cron runner should inject it into
  the prompt context (the cronjob tool already exposes list/remove).

## Status (2026-04-30)

- v0.3 bilateral letter loop: live
- Backlog + checker: live (f2cd003), but wrong *shape* for this vision
- Push-wake webhook (7878): live with watchdog
- This document: written by ames after tom's mid-run clarification
- Next: draft v0.4 cron prompt template that includes Evaluate+Spawn+Cleanup
