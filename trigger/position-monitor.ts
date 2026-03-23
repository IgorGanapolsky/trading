/**
 * Position Monitor — Tracks all open positions and syncs state.
 *
 * Runs every 30 minutes during market hours.
 * Syncs Alpaca positions -> system_state.json and checks for anomalies.
 *
 * Calls: scripts/manage_iron_condor_positions.py
 */

import { schedules, logger } from "@trigger.dev/sdk/v3";
import { runPython } from "./run-python.js";

export const positionMonitor = schedules.task({
  id: "position-monitor",
  cron: {
    pattern: "*/30 9-16 * * 1-5",
    timezone: "America/New_York",
  },
  run: async (payload) => {
    logger.info("Position monitor running", {
      timestamp: payload.timestamp,
    });

    const result = await runPython(
      "./scripts/manage_iron_condor_positions.py",
      ["--sync"],
    );

    if (result.exitCode !== 0) {
      logger.error("Position sync failed", {
        exitCode: result.exitCode,
        stderr: result.stderr,
      });
      throw new Error(`Position sync exited with code ${result.exitCode}`);
    }

    logger.info("Position sync complete", { output: result.stdout });

    return {
      syncedAt: new Date().toISOString(),
      rawOutput: result.stdout.trim(),
    };
  },
});
