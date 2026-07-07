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

const tmpDir = process.argv[2];
const root = process.argv[3];
const answersPath = path.join(tmpDir, "answers.json");
const guidePath = path.join(tmpDir, "guide.html");
const genericPath = path.join(tmpDir, "generic.json");
const serverPath = path.join(root, "mcp", "server.cjs");

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
    params: { name: "sample_individual_answers", arguments: { output_path: answersPath } },
  },
  {
    jsonrpc: "2.0",
    id: 3,
    method: "tools/call",
    params: { name: "render_individual_html", arguments: { answers_path: answersPath, output_path: guidePath } },
  },
  {
    jsonrpc: "2.0",
    id: 4,
    method: "tools/call",
    params: {
      name: "taxmate_run",
      arguments: { command: "intake", args: ["sample-json", "--output", genericPath] },
    },
  },
  {
    jsonrpc: "2.0",
    id: 5,
    method: "tools/call",
    params: { name: "taxmate_run", arguments: { command: "unknown", args: [] } },
  },
  {
    jsonrpc: "2.0",
    id: 6,
    method: "tools/call",
    params: { name: "taxmate_run", arguments: { command: "intake", args: "" } },
  },
];

const result = childProcess.spawnSync("node", [serverPath, "--stdio"], {
  cwd: tmpDir,
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

for (const id of [2, 3, 4]) {
  const payload = byId.get(id)?.result?.structuredContent;
  if (!payload || payload.ok !== true || payload.exit_code !== 0) {
    fail(`tool ${id} failed: ${JSON.stringify(byId.get(id))}`);
  }
}
const invalid = byId.get(5)?.result;
if (!invalid || invalid.isError !== true || invalid.structuredContent?.ok !== false) fail("invalid command was not rejected");
const invalidArgs = byId.get(6)?.result;
if (!invalidArgs || invalidArgs.isError !== true || invalidArgs.structuredContent?.ok !== false) fail("invalid args were not rejected");
if (!fs.existsSync(answersPath)) fail("sample answers were not written");
if (!fs.existsSync(genericPath)) fail("generic sample answers were not written");
if (!fs.existsSync(guidePath)) fail("HTML guide was not written");

const guide = fs.readFileSync(guidePath, "utf8");
for (const token of ["Self-prepared HTML guide", "Accountant review", "Manual copy only"]) {
  if (!guide.includes(token)) fail(`HTML guide missing ${token}`);
}
NODE

echo "MCP server smoke test passed"
