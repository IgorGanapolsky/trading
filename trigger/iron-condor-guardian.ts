/**
 * Iron Condor Guardian — Monitors open IC positions every 30 minutes during market hours.
 *
 * Exit conditions checked:
 *   1. DTE <= 7 (gamma risk)
 *   2. Loss >= 100% of entry credit (stop-loss)
 *   3. Profit >= 50% of max profit (take-profit)
 *
 * Calls: scripts/iron_condor_guardian.py
 */

import { schedules, logger } from "@trigger.dev/sdk/v3";
import { runPython } from "./run-python.js";

export const ironCondorGuardian = schedules.task({
  id: "iron-condor-guardian",
  cron: {
    pattern: "*/30 9-15 * * 1-5",
    timezone: "America/New_York",
  },
  run: async (payload) => {
    logger.info("Iron Condor Guardian scanning positions", {
      timestamp: payload.timestamp,
      lastRun: payload.lastTimestamp,
    });

    const result = await runPython("./scripts/iron_condor_guardian.py", [
      "--mode=monitor",
    ]);

    if (result.exitCode !== 0) {
      logger.error("Guardian script failed", {
        exitCode: result.exitCode,
        stderr: result.stderr,
      });
      throw new Error(`Guardian exited with code ${result.exitCode}`);
    }

    logger.info("Guardian scan complete", { output: result.stdout });

    let exitActions: string[] = [];
    try {
      const parsed = JSON.parse(result.stdout.trim());
      exitActions = parsed.actions ?? [];
    } catch {
      logger.warn("Non-JSON guardian output", { raw: result.stdout });
    }

    return {
      scannedAt: new Date().toISOString(),
      exitActions,
      rawOutput: result.stdout.trim(),
    };
  },
});
