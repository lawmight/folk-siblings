#!/usr/bin/env node
// spawn.mjs — ames's entry point. kick off a cursor cloud agent against a repo.
//
// usage:
//   CURSOR_API_KEY=... node spawn.mjs \
//     --repo https://github.com/lawmight/foo \
//     --ref main \
//     --prompt "add a changelog entry for v0.5"
//
// emits a JSON summary to stdout: {run_id, agent_id, status, pr_url?}
// intended to be called by ames's v0.4 EXECUTE step when a cursor-runs.md
// item owned by ames has status=pending.

import { Agent } from "@cursor/sdk";
import { parseArgs } from "node:util";

const { values: args } = parseArgs({
  options: {
    repo: { type: "string" },
    ref: { type: "string", default: "main" },
    prompt: { type: "string" },
    model: { type: "string", default: "composer-2" },
    autoPR: { type: "boolean", default: true },
  },
});

if (!args.repo || !args.prompt) {
  console.error("spawn.mjs: --repo and --prompt required");
  process.exit(2);
}

const apiKey = process.env.CURSOR_API_KEY;
if (!apiKey) {
  console.error("CURSOR_API_KEY missing");
  process.exit(2);
}

try {
  const agent = await Agent.create({
    apiKey,
    model: { id: args.model },
    cloud: {
      repos: [{ url: args.repo, startingRef: args.ref }],
      autoCreatePR: args.autoPR,
    },
  });

  const run = await agent.send(args.prompt);

  // wait for first status so we can capture PR url if created synchronously
  // (cloud runs are async; this is a best-effort peek)
  let pr_url = null;
  try {
    const info = await Agent.getRun(run.id, { runtime: "cloud", agentId: agent.id });
    pr_url = info?.pr_url ?? info?.pullRequestUrl ?? null;
  } catch (_) { /* ignore */ }

  console.log(JSON.stringify({
    ok: true,
    run_id: run.id,
    agent_id: agent.id,
    status: run.status ?? "submitted",
    pr_url,
    spawned_at: new Date().toISOString(),
  }, null, 2));
} catch (e) {
  console.log(JSON.stringify({
    ok: false,
    error: e.message,
    code: e.code ?? null,
  }, null, 2));
  process.exit(1);
}
