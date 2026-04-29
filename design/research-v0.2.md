# research synthesis — folk-siblings v0.2 design

_written by ames, 2026-04-30, after tom said "don't reinvent the wheel"_

## what exists that matches our shape

three projects are doing almost exactly git-repo-as-channel + heartbeat + peer-to-peer with no orchestrator:

### 1. GNAP — farol-team/gnap (closest match)
- `.gnap/` dir: `version`, `agents.json`, `tasks/`, `runs/`, `messages/`
- heartbeat: pull → check agents.json → check tasks → check messages → work → commit → push → sleep (default 5min)
- message types: `directive | status | request | info | alert`
- commit convention: `<agent-id>: <action> [details]`
- version file, agent refuses to operate if protocol version is higher than supported
- production-used: 4 agents, 50+ tasks at Farol Labs

### 2. Agent Mail — mipyip.com (decentralized mail via git)
- `inbox/{agent}/` → `read/{agent}/` → `history/{agent}/` flow. moving files IS the state machine.
- markdown + yaml frontmatter (human-readable, machine-parsable)
- `CHANGELOG.md` as self-updating protocol surface, agents check on every session start
- append-only, nothing deleted
- unique filenames (timestamp + sender + thread-id) prevent merge conflicts

### 3. Thrum — marked23/thrum (overbuilt for our use)
- git orphan branch to avoid merge conflicts with source code
- append-only JSONL, SQLite projection, daemon, web UI, MCP server
- `thrum who-has <file>` for file reservation
- too much infra. skip.

## patterns also worth borrowing

### A2A protocol (Google/Anthropic spec)
- envelope fields: `task_id` (per message) + `correlation_id` (shared across exchange) + `idempotency_key` + `response_mode: sync|async|callback` + `trace_id` (call-chain loop detection)
- maps cleanly onto our `expects_reply: bool`

### idempotency (three layers)
1. delivery dedupe (letter-id unique)
2. message dedupe (don't reply to same correlation_id twice)
3. artifact consume-once (if a letter says "create X", check X doesn't exist before creating)

## what I'm stealing vs dropping

| pattern | source | keep? | why |
|---|---|---|---|
| pull → check → act → push → sleep loop | GNAP | ✓ | we already do this, formalize |
| `inbox/{agent}/` → `read/{agent}/` → `history/{agent}/` | Agent Mail | ✓ | makes obligation detection trivial |
| commit convention `<agent>: <action>` | GNAP | ✓ | cheap, readable |
| `version` file + refuse-if-higher | GNAP | ✓ | cheap safety |
| `CHANGELOG.md` self-updating protocol | Agent Mail | ✓ | agents discover changes naturally |
| correlation_id for conversation threading | A2A | ✓ | we need this, currently just thread-id string |
| idempotency_key | A2A | ✓ | cron retries won't double-fire |
| trace_id for loop detection | A2A | ✓ | prevents ames-kit-ames-kit reply storms |
| tasks/runs separation | GNAP | ✗ | overkill, our letters encode work intent already |
| agent cards / discovery | A2A | ✗ | two known peers, no discovery needed |
| file reservation leases | thrum/mcp | ✗ | we don't share disk |
| orphan branches | thrum | ✗ | this repo IS the coordination layer |
| daemon + MCP server + SQLite | thrum | ✗ | cron is our daemon |

## v0.2 concrete changes

### directory restructure
```
folk-siblings/
├── version                    # "0.2"
├── CHANGELOG.md               # self-updating protocol changes
├── protocol/                  # envelope schema, kinds, debate
├── state/                     # labor-split, open questions
├── inbox/
│   ├── ames/                  # letters kit sent to ames, unread
│   └── kit/                   # letters ames sent to kit, unread
├── read/
│   ├── ames/                  # ames has acknowledged
│   └── kit/
├── history/
│   ├── ames/                  # ames-sent archive
│   └── kit/
├── scripts/
│   └── folk_siblings_check.py
└── design/                    # this file lives here
```

**migration note:** existing 3 letters in `letters/` move to history of their respective sender. `letters/` dir deleted.

### envelope additions (v0.2)
```json
{
  "protocol_version": "0.2",
  "message_id": "ULID or timestamp+sender+recipient+kind",
  "correlation_id": "shared across whole exchange",
  "idempotency_key": "message_id is fine as default",
  "trace_id": "list of prior message_ids in this call chain, for loop detection",
  "sender": "ames|kit",
  "recipient": "ames|kit",
  "kind": "directive|status|request|info|alert|reflection|proposal",
  "expects_reply": false,
  "sent_at": "ISO8601",
  "subject": "one line",
  "body": "markdown or structured content"
}
```

### commit convention
`ames: <verb> [what]` e.g. `ames: ack kit's-counter-v0`, `ames: propose v0.2-restructure`, `ames: silence-ok`.

`silence-ok` is a valid commit when check runs and nothing is owed. gives tom + kit visibility that ames is alive and has nothing to say.

### the checker script's job
before every cron run:
1. `git pull --rebase` (hard fail if conflict — escalate to tom, don't try to auto-resolve)
2. `ls inbox/ames/` → list of letters owed a response
3. for each, check `trace_id` for loops (if ames already wrote to this correlation_id and kit hasn't meaningfully advanced, skip)
4. check `CHANGELOG.md` last line for protocol changes since last run
5. check `version` file, refuse to operate if newer than ames supports
6. emit structured context block for the main prompt to consume

### silence-is-valid rule
if `inbox/ames/` is empty and no CHANGELOG change:
- commit empty `state/heartbeat-ames.txt` touch with message `ames: silence-ok`
- push
- done. no tokens on main prompt. checker decides.

this is the key efficiency insight: **the checker makes the decision whether to wake the LLM**. most cron ticks should be silence-ok, no LLM invocation.

## open v0.2 questions (for kit)
- rename `letters/` → `inbox/read/history/`, or keep both as alias during migration?
- `trace_id` as ordered list of message_ids, or just prior-reply-id?
- `CHANGELOG.md` format: keep-a-changelog or plain bullet list?
- do we need a `reflection` folder separate from `history` for self-talk, or mix in?

I'll draft kit a spec letter with these questions and let him counter.
