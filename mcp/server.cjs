"use strict";

const childProcess = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const readline = require("node:readline");

const SERVER_NAME = "taxmate-australia";
const PLUGIN_ROOT = path.resolve(__dirname, "..");
const PLUGIN_MANIFEST = JSON.parse(
  fs.readFileSync(path.join(PLUGIN_ROOT, ".codex-plugin", "plugin.json"), "utf8"),
);
const SERVER_VERSION = PLUGIN_MANIFEST.version || "0.1.0";
const TAXMATE_LAUNCHER = path.join(PLUGIN_ROOT, "scripts", "taxmate");
const MAX_OUTPUT_CHARS = 20000;
const COMMANDS = new Set([
  "calc",
  "coverage",
  "finance",
  "intake",
  "refresh",
  "review-guardrails",
  "skills",
  "taxpack",
  "validate",
  "workbook",
]);
const TOOL_NAMES = {
  run: "taxmate_run",
  sampleIndividualAnswers: "sample_individual_answers",
  renderIndividualHtml: "render_individual_html",
  validateRuntime: "validate_taxmate_runtime",
};

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function objectSchema(properties, required = []) {
  return { type: "object", properties, required, additionalProperties: false };
}

function tool(name, title, description, inputSchema) {
  return { name, title, description, inputSchema };
}

function toolDefinitions() {
  const commandEnum = Array.from(COMMANDS).sort();
  return [
    tool(
      TOOL_NAMES.run,
      "Run TaxMate Command",
      [
        "Run an allowlisted TaxMate Australia runtime command from the installed plugin cache.",
        "Use existing scripts/taxmate command families only. This is a preparation workflow and never lodges or files with the ATO.",
      ].join(" "),
      objectSchema(
        {
          command: {
            type: "string",
            enum: commandEnum,
            description: "Top-level scripts/taxmate command family.",
          },
          args: {
            type: "array",
            items: { type: "string" },
            default: [],
            description: "Arguments to pass after the command. Each entry is passed as one argv item; no shell is used.",
          },
          cwd: {
            type: "string",
            description: "Workspace directory for resolving relative TaxMate command arguments.",
          },
        },
        ["command", "cwd"],
      ),
    ),
    tool(
      TOOL_NAMES.sampleIndividualAnswers,
      "Write Sample Individual Answers",
      "Write synthetic TaxMate individual-return sample answers JSON to an explicit output path.",
      objectSchema(
        {
          output_path: { type: "string", description: "JSON output path." },
          cwd: { type: "string", description: "Workspace directory for resolving relative output_path values." },
        },
        ["output_path", "cwd"],
      ),
    ),
    tool(
      TOOL_NAMES.renderIndividualHtml,
      "Render Individual HTML Guide",
      "Render the TaxMate individual-return print-first HTML guide from answers JSON.",
      objectSchema(
        {
          answers_path: { type: "string", description: "Input answers JSON path." },
          output_path: { type: "string", description: "HTML output path." },
          cwd: { type: "string", description: "Workspace directory for resolving relative answers_path and output_path values." },
        },
        ["answers_path", "output_path", "cwd"],
      ),
    ),
    tool(
      TOOL_NAMES.validateRuntime,
      "Validate TaxMate Runtime",
      "Run TaxMate runtime validation from the installed plugin cache.",
      objectSchema({}),
    ),
  ];
}

function requireString(value, label) {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} must be a non-empty string`);
  return value;
}

function commandArgs(command, args) {
  if (!COMMANDS.has(command)) throw new Error(`unsupported TaxMate command: ${command}`);
  if (args == null) return [];
  if (!Array.isArray(args) || !args.every((item) => typeof item === "string")) {
    throw new Error("args must be an array of strings");
  }
  return args;
}

function resolveCallerCwd(value) {
  return path.resolve(requireString(value, "cwd"));
}

function resolveUserPath(value, callerCwd) {
  const userPath = requireString(value, "path");
  return path.isAbsolute(userPath) ? userPath : path.resolve(callerCwd, userPath);
}

function truncate(text) {
  if (text.length <= MAX_OUTPUT_CHARS) return text;
  return `${text.slice(0, MAX_OUTPUT_CHARS)}\n...[truncated ${text.length - MAX_OUTPUT_CHARS} chars]`;
}

function runTaxmate(command, args, callerCwd) {
  const argv = [command, ...commandArgs(command, args)];
  const result = childProcess.spawnSync(TAXMATE_LAUNCHER, argv, {
    cwd: callerCwd,
    encoding: "utf8",
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: process.env.PYTHONDONTWRITEBYTECODE || "1",
      TAXMATE_AUSTRALIA_ROOT: PLUGIN_ROOT,
    },
    maxBuffer: 5 * 1024 * 1024,
  });
  if (result.error) throw result.error;
  return {
    ok: result.status === 0,
    command,
    args,
    caller_cwd: callerCwd,
    exit_code: result.status,
    signal: result.signal || null,
    stdout: truncate(result.stdout || ""),
    stderr: truncate(result.stderr || ""),
  };
}

function callTool(name, args) {
  if (!isPlainObject(args)) throw new Error("tool arguments must be an object");
  if (name === TOOL_NAMES.run) {
    const callerCwd = resolveCallerCwd(args.cwd);
    return runTaxmate(requireString(args.command, "command"), args.args ?? [], callerCwd);
  }
  if (name === TOOL_NAMES.sampleIndividualAnswers) {
    const callerCwd = resolveCallerCwd(args.cwd);
    const outputPath = resolveUserPath(args.output_path, callerCwd);
    const result = runTaxmate("intake", ["sample-json", "--output", outputPath], callerCwd);
    return { ...result, output_path: outputPath };
  }
  if (name === TOOL_NAMES.renderIndividualHtml) {
    const callerCwd = resolveCallerCwd(args.cwd);
    const answersPath = resolveUserPath(args.answers_path, callerCwd);
    const outputPath = resolveUserPath(args.output_path, callerCwd);
    const result = runTaxmate("intake", ["individual", "--answers", answersPath, "--output", outputPath], callerCwd);
    return { ...result, answers_path: answersPath, output_path: outputPath };
  }
  if (name === TOOL_NAMES.validateRuntime) {
    return runTaxmate("validate", [], PLUGIN_ROOT);
  }
  throw new Error(`unknown TaxMate tool: ${name}`);
}

function toolResult(payload) {
  return {
    content: [{ type: "text", text: JSON.stringify(payload) }],
    structuredContent: payload,
    isError: !payload.ok,
  };
}

function toolError(message) {
  const payload = { ok: false, error: message };
  return {
    content: [{ type: "text", text: JSON.stringify(payload) }],
    structuredContent: payload,
    isError: true,
  };
}

function rpcResponse(id, result) {
  return { jsonrpc: "2.0", id, result };
}

function rpcError(id, code, message) {
  return { jsonrpc: "2.0", id, error: { code, message } };
}

async function handleRpc(message) {
  if (!isPlainObject(message)) return rpcError(null, -32600, "Invalid Request");
  const messageId = message.id;
  const method = message.method;
  const params = isPlainObject(message.params) ? message.params : {};
  if (typeof method !== "string") return messageId != null ? rpcError(messageId, -32600, "Invalid Request") : null;
  if (method.startsWith("notifications/") || method === "$/cancelRequest") return null;
  try {
    if (method === "initialize") {
      return rpcResponse(messageId, {
        protocolVersion: params.protocolVersion || "2024-11-05",
        capabilities: { tools: { listChanged: false } },
        serverInfo: {
          name: SERVER_NAME,
          title: "TaxMate Australia",
          version: SERVER_VERSION,
          description: "Run TaxMate Australia plugin runtime commands from the installed plugin cache.",
        },
        instructions:
          "TaxMate Australia is a preparation aid only. It never lodges, files, submits, or finalises tax material.",
      });
    }
    if (method === "ping") return rpcResponse(messageId, {});
    if (method === "tools/list") return rpcResponse(messageId, { tools: toolDefinitions() });
    if (method === "tools/call") {
      const name = params.name;
      if (typeof name !== "string") return rpcError(messageId, -32602, "tools/call requires a tool name");
      const callArgs = params.arguments || {};
      if (!isPlainObject(callArgs)) return rpcError(messageId, -32602, "tools/call arguments must be an object");
      try {
        return rpcResponse(messageId, toolResult(callTool(name, callArgs)));
      } catch (error) {
        return rpcResponse(messageId, toolError(error && error.message ? error.message : String(error)));
      }
    }
    if (method === "resources/list") return rpcResponse(messageId, { resources: [] });
    if (method === "resources/templates/list") return rpcResponse(messageId, { resourceTemplates: [] });
    if (method === "prompts/list") return rpcResponse(messageId, { prompts: [] });
  } catch (error) {
    return rpcError(messageId, -32000, error && error.message ? error.message : String(error));
  }
  return rpcError(messageId, -32601, `Method not found: ${method}`);
}

function writeRpc(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function runStdio() {
  const rl = readline.createInterface({ input: process.stdin });
  rl.on("line", async (line) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    let decoded;
    try {
      decoded = JSON.parse(trimmed);
    } catch (error) {
      writeRpc(rpcError(null, -32700, `Parse error: ${error.message}`));
      return;
    }
    if (Array.isArray(decoded)) {
      const responses = [];
      for (const request of decoded) {
        const response = await handleRpc(request);
        if (response) responses.push(response);
      }
      if (responses.length) writeRpc(responses);
      return;
    }
    const response = await handleRpc(decoded);
    if (response) writeRpc(response);
  });
}

module.exports = {
  SERVER_NAME,
  SERVER_VERSION,
  COMMANDS,
  TOOL_NAMES,
  toolDefinitions,
  callTool,
  handleRpc,
};

if (require.main === module) {
  runStdio();
}
