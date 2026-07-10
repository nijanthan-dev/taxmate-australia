#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ROOT="$(cd "$ROOT" && pwd)"
cd "$ROOT"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/taxmate-mcp.XXXXXX")"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

node - "$TMP_DIR" "$ROOT" <<'NODE'
const childProcess = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const tmpDir = fs.realpathSync(process.argv[2]);
const root = process.argv[3];
const answersPath = path.join(tmpDir, "answers.json");
const guidePath = path.join(tmpDir, "guide.html");
const genericPath = path.join(tmpDir, "generic.json");
const relativeAnswersPath = path.join(tmpDir, "relative-answers.json");
const relativeGuidePath = path.join(tmpDir, "relative-guide.html");
const financeCsvPath = path.join(tmpDir, "sample.csv");
const serverPath = path.join(root, "mcp", "server.cjs");
fs.writeFileSync(
  financeCsvPath,
  "date,description,amount,gst,owner,purpose,evidence,category,type\n" +
    "2026-04-15,OpenAI Codex subscription,33.00,3.00,owner,ABN app development,invoice,software,expense\n",
);

function fail(message) {
  console.error(`error: ${message}`);
  process.exit(1);
}

const requests = [
  { jsonrpc: "2.0", id: 1, method: "tools/list", params: {} },
  {
    jsonrpc: "2.0",
    id: 2,
    method: "tools/call",
    params: { name: "sample_individual_answers", arguments: { cwd: tmpDir, output_path: answersPath } },
  },
  {
    jsonrpc: "2.0",
    id: 3,
    method: "tools/call",
    params: { name: "render_individual_html", arguments: { cwd: tmpDir, answers_path: answersPath, output_path: guidePath } },
  },
  {
    jsonrpc: "2.0",
    id: 4,
    method: "tools/call",
    params: {
      name: "taxmate_run",
      arguments: { cwd: tmpDir, command: "intake", args: ["sample-json", "--output", genericPath] },
    },
  },
  {
    jsonrpc: "2.0",
    id: 5,
    method: "tools/call",
    params: { name: "sample_individual_answers", arguments: { cwd: tmpDir, output_path: "relative-answers.json" } },
  },
  {
    jsonrpc: "2.0",
    id: 6,
    method: "tools/call",
    params: {
      name: "render_individual_html",
      arguments: { cwd: tmpDir, answers_path: "relative-answers.json", output_path: "relative-guide.html" },
    },
  },
  {
    jsonrpc: "2.0",
    id: 7,
    method: "tools/call",
    params: { name: "taxmate_run", arguments: { cwd: tmpDir, command: "finance", args: ["--input", "sample.csv", "--format", "json"] } },
  },
  {
    jsonrpc: "2.0",
    id: 8,
    method: "tools/call",
    params: { name: "taxmate_run", arguments: { cwd: tmpDir, command: "unknown", args: [] } },
  },
  {
    jsonrpc: "2.0",
    id: 9,
    method: "tools/call",
    params: { name: "taxmate_run", arguments: { cwd: tmpDir, command: "intake", args: "" } },
  },
  {
    jsonrpc: "2.0",
    id: 10,
    method: "tools/call",
    params: { name: "sample_individual_answers", arguments: { output_path: "missing-cwd.json" } },
  },
];

const result = childProcess.spawnSync("node", [serverPath, "--stdio"], {
  cwd: root,
  input: `${JSON.stringify(requests)}\n`,
  encoding: "utf8",
  maxBuffer: 10 * 1024 * 1024,
});
if (result.error) throw result.error;
if (result.status !== 0) fail(`MCP server exited ${result.status}: ${result.stderr}`);

const lines = result.stdout.trim().split(/\n+/).filter(Boolean);
if (lines.length !== 1) fail(`expected one batch response line, got ${lines.length}`);
const responses = JSON.parse(lines[0]);
if (!Array.isArray(responses) || responses.length !== requests.length) fail("invalid batch response");

const byId = new Map(responses.map((response) => [response.id, response]));
const tools = byId.get(1)?.result?.tools?.map((tool) => tool.name).sort();
const expectedTools = ["render_individual_html", "sample_individual_answers", "taxmate_run", "validate_taxmate_runtime"];
if (JSON.stringify(tools) !== JSON.stringify(expectedTools)) fail(`unexpected tools: ${JSON.stringify(tools)}`);

for (const id of [2, 3, 4, 5, 6, 7]) {
  const payload = byId.get(id)?.result?.structuredContent;
  if (!payload || payload.ok !== true || payload.exit_code !== 0) {
    fail(`tool ${id} failed: ${JSON.stringify(byId.get(id))}`);
  }
  if (payload.caller_cwd !== tmpDir) fail(`tool ${id} did not use explicit workspace cwd`);
}
const relativeSample = byId.get(5)?.result?.structuredContent;
if (relativeSample.output_path !== relativeAnswersPath) fail("relative sample output was not resolved against workspace cwd");
const relativeRender = byId.get(6)?.result?.structuredContent;
if (relativeRender.answers_path !== relativeAnswersPath || relativeRender.output_path !== relativeGuidePath) {
  fail("relative render paths were not resolved against workspace cwd");
}
const finance = byId.get(7)?.result?.structuredContent;
if (!finance.stdout.includes("OpenAI Codex subscription")) fail("relative finance input was not read from workspace cwd");

const invalid = byId.get(8)?.result;
if (!invalid || invalid.isError !== true || invalid.structuredContent?.ok !== false) fail("invalid command was not rejected");
const invalidArgs = byId.get(9)?.result;
if (!invalidArgs || invalidArgs.isError !== true || invalidArgs.structuredContent?.ok !== false) fail("invalid args were not rejected");
const missingCwd = byId.get(10)?.result;
if (!missingCwd || missingCwd.isError !== true || !missingCwd.structuredContent?.error?.includes("cwd")) {
  fail("relative tool call without cwd was not rejected");
}
if (!fs.existsSync(answersPath)) fail("sample answers were not written");
if (!fs.existsSync(genericPath)) fail("generic sample answers were not written");
if (!fs.existsSync(guidePath)) fail("HTML guide was not written");
if (!fs.existsSync(relativeAnswersPath)) fail("relative sample answers were not written under workspace cwd");
if (!fs.existsSync(relativeGuidePath)) fail("relative HTML guide was not written under workspace cwd");
if (fs.existsSync(path.join(root, "relative-answers.json")) || fs.existsSync(path.join(root, "relative-guide.html"))) {
  fail("relative tool paths leaked into plugin root");
}

const guide = fs.readFileSync(guidePath, "utf8");
for (const token of ["Self-prepared HTML guide", "Accountant review", "Return fields and next actions"]) {
  if (!guide.includes(token)) fail(`HTML guide missing ${token}`);
}
NODE

echo "MCP server smoke test passed"
