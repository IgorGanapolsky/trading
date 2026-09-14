/**
 * Pi permission-gate FORMAT (pi.dev extensions/permission-gate analog).
 * Fail-closed on live risk, freehand closes, halt/kill-switch mutation, and
 * unreviewed `pi install`. Does not submit orders. Does not add MCP.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const PROTECTED_PATHS = [
  /data\/TRADING_HALTED/i,
  /data\/SYSTEM_HALTED/i,
  /data\/trading_halt\.txt/i,
  /src\/core\/trading_constants\.py/i,
  /data\/runtime\/strategy_kill_switch\.json/i,
];

const MUTATION =
  /\b(rm|unlink|mv|sed|tee|Set-Content|Remove-Item|Out-File|del|ni|New-Item|redirection|>|>>)\b/i;

const BASH_DENY = [
  /\bclose_position\b/i,
  /\bclose_all_positions\b/i,
  /\bclose_positions(\.py)?\b/i,
  /\bmanage_positions(\.py)?\b/i,
  /\bliquidat/i,
  /submit_order.*SELL/i,
  /PAPER_TRADING\s*=\s*false/i,
  /--live\b/,
  /\bgit push\s+(-f|--force).*main\b/,
  /\bpi\s+install\b/i,
];

function haystack(input: unknown): string {
  if (typeof input === "string") return input;
  try {
    return JSON.stringify(input ?? {});
  } catch {
    return String(input ?? "");
  }
}

function hitsProtectedPath(blob: string): boolean {
  return PROTECTED_PATHS.some((re) => re.test(blob));
}

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event) => {
    const blob = haystack(event.input);
    const name = String(event.toolName || "").toLowerCase();

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
      if (hitsProtectedPath(blob) && MUTATION.test(blob)) {
        return {
          block: true,
          reason: "trading-live-gate blocked protected-path mutation",
          terminate: true,
        };
      }
    }

    if (name === "write" || name === "edit") {
      if (hitsProtectedPath(blob)) {
        return {
          block: true,
          reason: "trading-live-gate blocked write to protected path",
          terminate: true,
        };
      }
    }

    return undefined;
  });
}
