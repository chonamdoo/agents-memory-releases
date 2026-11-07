// agents-memory managed adapter. Paths only; no credentials in this file.
import { spawn } from "node:child_process";
import type { ExtensionAPI, ExtensionContext } from "@oh-my-pi/pi-coding-agent/extensibility/extensions/types";

type Result = { systemMessage?: string; additionalContext?: string };
type HostEvent = { type?: string; prompt?: string; reason?: string };

export default function (pi: ExtensionAPI) {
  let revision = 0;
  let context = "";
  let contextSession = "";
  let refreshed = false;
  const refresh = async (name: string, event: HostEvent, ctx: ExtensionContext) => {
    const current = ++revision;
    const session = ctx.sessionManager.getSessionId();
    context = "";
    contextSession = session;
    refreshed = false;
    const { promise, resolve } = Promise.withResolvers<Result>();
    const child = spawn(__PYTHON__, __ARGS__, { stdio: ["pipe", "pipe", "ignore"] });
    let output = "";
    let settled = false;
    const finish = (value: Result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      child.kill();
      resolve(value);
    };
    const timer = setTimeout(() => finish({ systemMessage: "agents-memory: automatic_memory_deferred" }), 2500);
    child.on("error", () => finish({ systemMessage: "agents-memory: automatic_memory_deferred" }));
    child.stdin.on("error", () => {});
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (data: string) => {
      output += data;
      if (Buffer.byteLength(output, "utf8") > 8192) finish({});
    });
    child.on("close", () => {
      try {
        const value: unknown = JSON.parse(output);
        if (value === null || typeof value !== "object") return finish({});
        finish({
          systemMessage: "systemMessage" in value && typeof value.systemMessage === "string" ? value.systemMessage : undefined,
          additionalContext: "additionalContext" in value && typeof value.additionalContext === "string" ? value.additionalContext : undefined,
        });
      } catch { finish({}); }
    });
    const payload: { hook_event_name: string; session_id: string; prompt?: string; source?: string } = {
      hook_event_name: name, session_id: session,
    };
    if (name === "before_agent_start") payload.prompt = event.prompt;
    if (name === "session_switch") payload.source = event.reason;
    child.stdin.end(JSON.stringify(payload));
    const result = await promise;
    if (current !== revision || session !== ctx.sessionManager.getSessionId()) return;
    refreshed = true;
    if (result.systemMessage && ctx.hasUI) ctx.ui.notify(result.systemMessage, "warning");
    if (typeof result.additionalContext === "string" && Buffer.byteLength(result.additionalContext, "utf8") <= 4096) {
      context = result.additionalContext;
    }
  };
  pi.on("before_agent_start", async (event, ctx) => {
    await refresh("before_agent_start", event, ctx);
  });
  pi.on("session_start", async (event, ctx) => {
    await refresh("session_start", event, ctx);
  });
  pi.on("session_switch", async (event, ctx) => {
    await refresh("session_switch", event, ctx);
  });
  pi.on("session_compact", async (event, ctx) => {
    await refresh("session_compact", event, ctx);
  });
  pi.on("context", async (event, ctx) => {
    if (!refreshed || contextSession !== ctx.sessionManager.getSessionId()) {
      await refresh("context", {}, ctx);
    }
    const messages = event.messages.filter((message) =>
      message.role !== "custom" || message.customType !== "agents-memory.context");
    if (context && contextSession === ctx.sessionManager.getSessionId()) {
      messages.push({ role: "custom", customType: "agents-memory.context",
        content: context, display: false, timestamp: Date.now() });
    }
    return { messages };
  });
}
