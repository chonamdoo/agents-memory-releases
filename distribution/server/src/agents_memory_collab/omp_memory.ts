// agents-memory managed adapter. Paths only; no credentials in this file.
import { spawn } from "node:child_process";

export default function (pi: any) {
  pi.on("before_agent_start", async (event: any, ctx: any) => {
    const result: any = await new Promise((resolve) => {
      const child = spawn(__PYTHON__, __ARGS__, { stdio: ["pipe", "pipe", "ignore"] });
      let output = "";
      let settled = false;
      const finish = (value: any) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        child.kill();
        resolve(value);
      };
      const timer = setTimeout(() => finish({ systemMessage: "agents-memory: automatic_memory_deferred" }), 2500);
      child.on("error", () => finish({ systemMessage: "agents-memory: automatic_memory_deferred" }));
      child.stdin.on("error", () => {});
      child.stdout.on("data", (data: Buffer) => {
        output += data.toString("utf8");
        if (Buffer.byteLength(output, "utf8") > 8192) finish({});
      });
      child.on("close", () => {
        try { finish(JSON.parse(output)); } catch { finish({}); }
      });
      child.stdin.end(JSON.stringify({ hook_event_name: "before_agent_start", prompt: event.prompt,
        session_id: ctx.sessionManager.getSessionId() }));
    });
    if (result.systemMessage) ctx.ui.notify(result.systemMessage, "warning");
    if (result.additionalContext) return { message: { customType: "agents-memory.context",
      content: result.additionalContext, display: false } };
  });
}
