/**
 * Pi permission-gate FORMAT (pi.dev extensions/permission-gate analog).
 * Fail-closed on live risk, freehand closes, and halt-file deletion.
 * Does not install MCP. Does not submit orders.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const BASH_DENY = [
  /\bclose_position\b/i,
  /\bclose_all_positions\b/i,
  /\bliquidat/i,
  /submit_order.*SELL/i,
  /\brm\b.*TRADING_HALTED/,
  /\brm\b.*SYSTEM_HALTED/,
  /\bgit push\s+(-f|--force).*main\b/,
];

const WRITE_DENY = [
  /data\/TRADING_HALTED/,
  /data\/SYSTEM_HALTED/,
  /data\/trading_halt\.txt/,
  /src\/core\/trading_constants\.py/,
];

function haystack(input: unknown): string {
  if (typeof input === "string") return input;
  try {
    return JSON.stringify(input ?? {});
  } catch {
    return String(input ?? "");
  }
}

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event) => {
    const blob = haystack(event.input);
    const name = String(event.toolName || "");

    if (name === "bash" || name === "powershell") {
      for (const re of BASH_DENY) {
        if (re.test(blob)) {
          return {
            block: true,
            reason: `trading-live-gate blocked bash: ${re}`,
            terminate: true,
          };
        }
      }
    }

    if (name === "write" || name === "edit") {
      for (const re of WRITE_DENY) {
        if (re.test(blob)) {
          return {
            block: true,
            reason: `trading-live-gate blocked write: ${re}`,
            terminate: true,
          };
        }
      }
    }

    return undefined;
  });
}
