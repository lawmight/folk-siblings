#!/usr/bin/env node
// spawn.mjs  ames's entry point. kick off a cursor cloud agent against a repo.
//
// usage:
//   CURSOR_API_KEY=*** node spawn.mjs \
//     --repo https://github.com/lawmight/foo \
//     --ref main \
//     --prompt "add a changelog entry for v0.5" \
//     [--id cr-001-slug] [--no-enqueue]
//
// emits a JSON summary to stdout: {run_id, agent_id, status, pr_url?}
// side effect: appends a kit-owned 'cursor-review' task to cronjobs.json
// (per kit counter, v0.4 queue is the wake source, cursor-runs.md is log-only).

import { Agent } from "@cursor/sdk";
import { parseArgs } from "node:util";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const QUEUE_PATH = path.join(REPO_ROOT, "cronjobs.json");
const RUNS_LOG = path.join(__dirname, "cursor-runs.md");

const { values: args } = parseArgs({
  options: {
    repo: { type: "string" },
    ref: { type: "string", default: "main" },
    prompt: { type: "string" },
    model: { type: "string", default: "composer-2" },
    autoPR: { type: "boolean", default: true },
    id: { type: "string" },
    "no-enqueue": { type: "boolean", default: false },
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

function shortId() {
  return "cr-" + Math.random().toString(36).slice(2, 8);
}

function enqueueReview({ slug, run_id, agent_id, pr_url, repo, prompt }) {
  const raw = fs.readFileSync(QUEUE_PATH, "utf8");
  const q = JSON.parse(raw);
  const now = new Date().toISOString();
  const task = {
    id: `task-cursor-${slug}`,
    owner: "kit",
    priority: 65,
    status: "todo",
    attempts: 0,
    parent_id: null,
    kind: "cursor-review",
    created_at: now,
    instructions: `Review cursor-spawned PR. repo=${repo} run_id=${run_id} agent_id=${agent_id} pr_url=${pr_url ?? "pending"}. Follow cursor/review.md. Reply with coordination letter containing PR url, 1-3 bullet diff summary, explicit AGREE/REJECT/AGREE-WITH-FIX verdict, and if REJECT/AGREE-WITH-FIX specific file:line hunks. Original prompt: ${JSON.stringify(prompt)}.`,
    cursor: { slug, run_id, agent_id, pr_url, repo, original_prompt: prompt },
    budget_tokens: 20000,
  };
  q.tasks.push(task);
  fs.writeFileSync(QUEUE_PATH, JSON.stringify(q, null, 2) + "\n");
  return task.id;
}

function appendRunsLog({ slug, run_id, agent_id, pr_url, repo, prompt }) {
  const row = `| ${slug} | kit | awaiting-review | ${run_id} | ${agent_id} | ${pr_url ?? ""} | ${repo} | ${JSON.stringify(prompt).slice(1, -1).slice(0, 60)} | spawned ${new Date().toISOString()} |\n`;
  const cur = fs.readFileSync(RUNS_LOG, "utf8");
  if (!cur.includes("| id |")) {
    fs.appendFileSync(RUNS_LOG, row);
  } else {
    const lines = cur.split("\n");
    const headerIdx = lines.findIndex((l) => l.startsWith("| id |"));
    const sepIdx = headerIdx + 1;
    lines.splice(sepIdx + 1, 0, row.trimEnd());
    fs.writeFileSync(RUNS_LOG, lines.join("\n"));
  }
}

const slug = args.id ?? shortId();

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

  let pr_url = null;
  try {
    const info = await Agent.getRun(run.id, { runtime: "cloud", agentId: agent.id });
    pr_url = info?.pr_url ?? info?.pullRequestUrl ?? null;
  } catch (_) { /* ignore */ }

  const summary = {
    ok: true,
    slug,
    run_id: run.id,
    agent_id: agent.id,
    status: run.status ?? "submitted",
    pr_url,
    spawned_at: new Date().toISOString(),
  };

  try { appendRunsLog({ slug, run_id: run.id, agent_id: agent.id, pr_url, repo: args.repo, prompt: args.prompt }); }
  catch (e) { summary.runs_log_err = e.message; }

  if (!args["no-enqueue"]) {
    try {
      const task_id = enqueueReview({ slug, run_id: run.id, agent_id: agent.id, pr_url, repo: args.repo, prompt: args.prompt });
      summary.queue_task_id = task_id;
    } catch (e) {
      summary.enqueue_err = e.message;
    }
  }

  console.log(JSON.stringify(summary, null, 2));
} catch (e) {
  console.log(JSON.stringify({
    ok: false,
    slug,
    error: e.message,
    code: e.code ?? null,
  }, null, 2));
  process.exit(1);
}
