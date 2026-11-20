// Stagehand audit-90: persistent driver holding ONE Stagehand 4.4.0 +
// headless-Chromium session for the whole battery run.
//
// Protocol (JSON lines on stdin/stdout; stderr is diagnostics only):
//   -> {"id": N, "task": "<task text>", "html": "<full page document>"}
//   <- {"id": N, "answer": "<extracted answer>" | null,
//       "generateCalls": <stub generate calls this request>,
//       "error": null | "<message>"}
//   -> {"cmd": "ping"}  <- {"ok": true, "id": null}
//   -> {"cmd": "shutdown"}  -> closes Stagehand, exits 0.
//
// The driver is transport only: it writes the given HTML to a scratch
// file, gotos it, and runs stagehand.extract(task, {answer: string}).
// Every model decision lives in the deterministic stub
// (stagehand-pin-stub.py on port 18090); the generate callback below
// is the same thin adapter the pin-gate probe used (POST Stagehand's
// messages to the stub, return text + parsed structuredContent).
// No API key, no network model call.
//
// Usage: node stagehand_driver.mjs [scratch-page-path]
//   scratch page defaults to
//   evals/reports/real_agents/stagehand/driver-page.html
import { createRequire } from "node:module";
import fs from "node:fs";
import readline from "node:readline";

const require = createRequire(
  "/home/hatch/workspace/hackathons/trustrun/trustrun-venvs/stagehand-venv/package.json"
);
// Stagehand 4.4.0 ships ESM-only ("exports" has "import" but no
// "require"), so require("@browserbasehq/stagehand") throws
// ERR_PACKAGE_PATH_NOT_EXPORTED. Import its dist entry directly
// (file URL, anchored at the venv like the require above). zod
// keeps its require entry, so it stays on require.
const { Stagehand, localBrowser } = await import(
  "file:///home/hatch/workspace/hackathons/trustrun/trustrun-venvs/stagehand-venv/node_modules/@browserbasehq/stagehand/dist/index.mjs"
);
const { z } = require("zod");

const STUB = "http://127.0.0.1:18090/v1/chat/completions";
const SCRATCH =
  process.argv[2] ||
  "/home/hatch/workspace/hackathons/trustrun/evals/reports/real_agents/stagehand/driver-page.html";
const CHROME =
  "/home/hatch/.cache/ms-playwright/chromium-1254/chrome-linux64/chrome";

let calls = 0;
function blocksToText(content) {
  const blocks = Array.isArray(content) ? content : [content];
  return blocks
    .map((b) =>
      b.type === "text" ? b.text : b.type === "image" ? "[image]" : `[${b.type}]`
    )
    .join("\n");
}
async function generate(params) {
  calls += 1;
  const messages = [];
  if (params.systemPrompt)
    messages.push({ role: "system", content: params.systemPrompt });
  for (const m of params.messages)
    messages.push({ role: m.role, content: blocksToText(m.content) });
  const body = { model: "deterministic-stub-v1", messages };
  if (params.responseFormat?.type === "json_schema") {
    body.response_format = {
      type: "json_schema",
      json_schema: {
        name: params.responseFormat.name,
        schema: params.responseFormat.schema,
      },
    };
  }
  const res = await fetch(STUB, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`stub HTTP ${res.status}`);
  const data = await res.json();
  const text = data.choices?.[0]?.message?.content ?? "";
  if (params.responseFormat?.type === "json_schema") {
    let structured;
    try {
      structured = JSON.parse(text);
    } catch {
      structured = {};
    }
    return {
      role: "assistant",
      content: { type: "text", text },
      outputFormat: "json_schema",
      structuredContent: structured,
    };
  }
  return {
    role: "assistant",
    content: { type: "text", text },
    outputFormat: "text",
  };
}

const browser = await localBrowser.launch({
  headless: true,
  executablePath: CHROME,
  args: ["--no-sandbox"],
});
const stagehand = await Stagehand.create({
  browser,
  model: { generate },
  logging: { level: "error", format: "pretty" },
});
const page = await stagehand.browser.context.activePage();

const out = (obj) => process.stdout.write(JSON.stringify(obj) + "\n");
out({ ready: true, id: null });

const rl = readline.createInterface({ input: process.stdin });
let closing = false;
rl.on("line", async (line) => {
  if (!line.trim() || closing) return;
  let req;
  try {
    req = JSON.parse(line);
  } catch {
    return;
  }
  if (req.cmd === "ping") {
    out({ ok: true, id: req.id ?? null });
    return;
  }
  if (req.cmd === "shutdown") {
    closing = true;
    try {
      await stagehand.close();
    } catch {}
    out({ ok: true, id: req.id ?? null });
    process.exit(0);
  }
  const callsBefore = calls;
  try {
    fs.writeFileSync(SCRATCH, req.html ?? "", "utf-8");
    await page.goto(`file://${SCRATCH}`);
    const r = await stagehand.extract(
      req.task,
      z.object({ answer: z.string() })
    );
    out({
      id: req.id,
      answer: r?.data?.answer ?? null,
      generateCalls: calls - callsBefore,
      error: null,
    });
  } catch (e) {
    out({
      id: req.id,
      answer: null,
      generateCalls: calls - callsBefore,
      error: String(e?.message ?? e).slice(0, 500),
    });
  }
});
rl.on("close", async () => {
  if (closing) return;
  closing = true;
  try {
    await stagehand.close();
  } catch {}
  process.exit(0);
});
