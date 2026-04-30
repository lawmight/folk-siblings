#!/usr/bin/env node
// stream.mjs — attach to a running cursor cloud agent by id, print events.
//
// usage:
//   CURSOR_API_KEY=... node stream.mjs --agent-id AGENT --run-id RUN
//
// intended for ames to tail a run it spawned, or for either agent to observe.

import { Agent } from "@cursor/sdk";
import { parseArgs } from "node:util";

const { values: args } = parseArgs({
  options: {
    "agent-id": { type: "string" },
    "run-id": { type: "string" },
    "runtime": { type: "string", default: "cloud" },
    "max-events": { type: "string", default: "200" },
  },
});

const agentId = args["agent-id"];
const runId = args["run-id"];
if (!agentId || !runId) {
  console.error("stream.mjs: --agent-id and --run-id required");
  process.exit(2);
}

const apiKey = process.env.CURSOR_API_KEY;
if (!apiKey) { console.error("CURSOR_API_KEY missing"); process.exit(2); }

const maxEvents = parseInt(args["max-events"], 10);
let count = 0;

try {
  const run = await Agent.getRun(runId, { runtime: args.runtime, agentId, apiKey });
  console.error(`# attached run ${runId} status=${run.status ?? "?"}`);
  if (typeof run.stream === "function") {
    for await (const event of run.stream()) {
      console.log(JSON.stringify({ ts: new Date().toISOString(), event }));
      if (++count >= maxEvents) {
        console.error(`# hit max-events (${maxEvents}), detaching`);
        break;
      }
    }
  } else {
    console.error("# run has no stream(); dumping snapshot");
    console.log(JSON.stringify(run, null, 2));
  }
} catch (e) {
  console.error("err:", e.message);
  process.exit(1);
}
