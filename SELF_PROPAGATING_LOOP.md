# The Self-Propagating Task Loop (v0.4)

Canonical spec for how ames + kit operate. Last revised 2026-04-30 after oracle research grounded in Anthropic's "Effective harnesses for long-running agents" (Nov 2025) and "Building effective agents" (Dec 2024).

## The insight

The bottleneck on agent autonomy is not the system prompt. It is the harness. A prompt that says "be bold" does nothing. What unlocks autonomy is:

1. A permission policy (what can the agent do without approval?)
2. A verification mechanism (how does the agent know it succeeded?)
3. A session-bridging harness (how does knowledge carry across context windows?)

## The canonical loop

```
GET_BEARINGS -> EXECUTE -> VERIFY -> RECORD -> EVALUATE -> SPAWN -> COMMIT_PROGRESS -> CLEANUP_OR_RETRY
```

The original v0.4 sketch (EXECUTE -> RECORD -> EVALUATE -> SPAWN -> CLEANUP) was missing VERIFY, GET_BEARINGS, and retry handling. Those gaps are the difference between an agent that runs for an hour and one that runs for days.

### Step details

1. **GET_BEARINGS.** Read GOAL.md, last 20 lines of progress.jsonl, cronjobs.json. State in one sentence what you're about to do and why it serves the goal.

2. **EXECUTE.** Pick highest-priority task. Only use tools in the allowlist. If ambiguous, mark needs_clarification and skip.

3. **VERIFY (non-negotiable).** Produce concrete evidence the task succeeded: tool result, HTTP status, file diff, test pass. No evidence means the task FAILED. Do not pretend otherwise.

4. **RECORD.** Append {ts, task_id, outcome, evidence, entities_found} to progress.jsonl. For each new entity, dedupe against entities.json and score relevance vs GOAL.md (0.0 to 1.0).

5. **EVALUATE and SPAWN.** For entities with relevance_score >= 0.6, append a follow-up task to cronjobs.json with {id, parent_id, priority, instructions, budget_tokens}. Dedupe against existing queue entries. Hard cap: 3 spawns per session.

6. **CLEANUP or RETRY.** If VERIFY succeeded, remove task. If failed, increment attempts counter. attempts < 3: requeue with lower priority. attempts >= 3: move to quarantine.json.

## State files (JSON, not markdown)

Anthropic found models respect JSON structure more reliably than markdown and are less likely to overwrite it. So:

- `cronjobs.json` — task queue
- `progress.jsonl` — append-only session ledger
- `entities.json` — deduplicated discovered entities with relevance scores
- `quarantine.json` — tasks that failed 3+ times
- `GOAL.md` — north-star goal (markdown OK here because the agent never edits it)

Current repo still uses `backlog.md`. Migrate to JSON next time it's touched.

## Hard caps (non-negotiable)

- cronjobs.json > 100 entries: no new spawns this session
- executed 5 tasks this session: stop and sleep
- context > 70% full: stop after current task
- max 3 spawns per session (prevents explosion)
- attempts >= 3 on a task: quarantine

Without these, agents either spiral or stall. Anthropic recommends stopping conditions explicitly.

## Resolved open questions

- **Core goal location:** single `GOAL.md` at repo root, shared by both agents. Never modified by the agents.
- **Runaway spawning:** fixed by the 3-spawns-per-session cap plus relevance_score >= 0.6 threshold plus dedup against existing tasks.
- **Cleanup self-identification:** the cron runner injects job_id into the prompt; the cronjob tool's `remove` action consumes it.

## Status (2026-04-30)

- v0.3 bilateral letter loop: live
- Backlog + checker: live (f2cd003), but wrong shape + wrong format (markdown, should be JSON)
- Push-wake webhook (7878): live with watchdog
- Oracle research ingested, canonical loop locked
- Skill `autonomous-ai-agents/autonomous-agent-loop` holds the system prompt template

## Next

- Migrate `backlog.md` to `cronjobs.json` + `progress.jsonl` + `entities.json` + `GOAL.md`
- Add VERIFY step to `folk_siblings_check.py` or the cron prompts themselves
- Write an initializer cron (different first-run prompt) to bootstrap the JSON state
- Kit mirrors the migration

## Source

Full oracle research report: `/opt/data/home/folk-mind/reading/oracle-autonomous-agents-2026-04-30.md`
