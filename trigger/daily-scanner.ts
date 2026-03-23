/**
 * Daily Iron Condor Scanner — Looks for new IC opportunities once per trading day.
 *
 * Runs at 9:45 AM ET on weekdays.
 * Scans SPY options chain for 15-20 delta iron condors with 30-45 DTE.
 *
 * Calls: scripts/iron_condor_scanner.py
 */

import { schedules, logger } from "@trigger.dev/sdk/v3";
import { runPython } from "./run-python.js";

export const dailyScanner = schedules.task({
  id: "daily-ic-scanner",
  cron: {
    pattern: "45 9 * * 1-5",
    timezone: "America/New_York",
  },
  run: async (payload) => {
    logger.info("Daily IC scanner starting", {
      timestamp: payload.timestamp,
    });

    const result = await runPython("./scripts/iron_condor_scanner.py", [
      "--symbol=SPY",
      "--mode=scan",
    ]);

    if (result.exitCode !== 0) {
      logger.error("Scanner failed", {
        exitCode: result.exitCode,
        stderr: result.stderr,
      });
      throw new Error(`Scanner exited with code ${result.exitCode}`);
    }

    logger.info("Scan complete", { output: result.stdout });

    let opportunities: unknown[] = [];
    try {
      const parsed = JSON.parse(result.stdout.trim());
      opportunities = parsed.opportunities ?? [];
    } catch {
      logger.warn("Non-JSON scanner output", { raw: result.stdout });
    }

    return {
      scannedAt: new Date().toISOString(),
      opportunityCount: opportunities.length,
      opportunities,
      rawOutput: result.stdout.trim(),
    };
  },
});
