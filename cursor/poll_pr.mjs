#!/usr/bin/env node
// poll_pr.mjs  poll a cursor cloud run until its PR url resolves (or run ends).
//
// usage:
//   CURSOR_API_KEY=*** node cursor/poll_pr.mjs \
//     --agent-id AGENT --run-id RUN [--max-seconds 300]
//
// on success prints JSON {ok:true, pr_url, run_status, waited_seconds}.
// on run terminal-error prints {ok:false, error, run_status, waited_seconds}.
// on timeout prints {ok:false, error:"timeout", run_status, waited_seconds}.
//
// called by ames checker when it sees a cursor-runs.json row with
// status=spawned and pr_url=null. once pr_url populates, ames flips the
// row to status=awaiting-review owner=kit and pushes, waking kit.
//
// design: cursor cloud creates the PR asynchronously after the agent's
// first commits, so peeking pr_url at spawn time returns null ~100% of
// the time. exponential backoff 2s, 4s, 8s, 16s, 30s cap, until the
// Run.result.git.branches resolves or the run reaches a terminal state.

import { Agent } from "@cursor/sdk";
import { parseArgs } from "node:util";

const { values: args } = parseArgs({
  options: {
    "agent-id": { type: "string" },
    "run-id": { type: "string" },
    "max-seconds": { type: "string", default: "300" },
  },
});

if (!args["agent-id"] || !args["run-id"]) {
  console.error("poll_pr.mjs: --agent-id and --run-id required");
  process.exit(2);
}

const apiKey = process.env.CURSOR_API_KEY;
if (!apiKey) {
  console.error("CURSOR_API_KEY missing");
  process.exit(2);
}

const maxSeconds = parseInt(args["max-seconds"], 10);
const startedAt = Date.now();
const TERMINAL = new Set(["completed", "error", "failed", "cancelled", "canceled"]);

function extractPrUrl(info) {
  // try several shapes the sdk has shipped across alpha versions
  if (!info) return null;
  if (typeof info.pr_url === "string") return info.pr_url;
  if (typeof info.pullRequestUrl === "string") return info.pullRequestUrl;
  const branches = info?.result?.git?.branches ?? info?.git?.branches ?? [];
  for (const b of branches) {
    if (b?.pullRequestUrl) return b.pullRequestUrl;
    if (b?.pr_url) return b.pr_url;
  }
  return null;
}

async function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

const backoff = [2000, 4000, 8000, 16000, 30000];
let attempt = 0;

try {
  while (true) {
    const waited = Math.floor((Date.now() - startedAt) / 1000);
    if (waited >= maxSeconds) {
      console.log(JSON.stringify({
        ok: false,
        error: "timeout",
        run_status: null,
        waited_seconds: waited,
      }, null, 2));
      process.exit(1);
    }

    let info = null;
    let run_status = null;
    try {
      info = await Agent.getRun(args["run-id"], { runtime: "cloud", agentId: args["agent-id"] });
      run_status = info?.status ?? info?.state ?? null;
    } catch (e) {
      // transient; fall through to backoff
      info = null;
    }

    const pr_url = extractPrUrl(info);
    if (pr_url) {
      console.log(JSON.stringify({
        ok: true,
        pr_url,
        run_status,
        waited_seconds: Math.floor((Date.now() - startedAt) / 1000),
      }, null, 2));
      process.exit(0);
    }

    if (run_status && TERMINAL.has(String(run_status).toLowerCase())) {
      console.log(JSON.stringify({
        ok: false,
        error: "run reached terminal status without pr_url",
        run_status,
        waited_seconds: Math.floor((Date.now() - startedAt) / 1000),
      }, null, 2));
      process.exit(1);
    }

    const delay = backoff[Math.min(attempt, backoff.length - 1)];
    attempt += 1;
    await sleep(delay);
  }
} catch (e) {
  console.log(JSON.stringify({
    ok: false,
    error: e.message,
    code: e.code ?? null,
    waited_seconds: Math.floor((Date.now() - startedAt) / 1000),
  }, null, 2));
  process.exit(1);
}
