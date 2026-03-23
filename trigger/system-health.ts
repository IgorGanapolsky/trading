/**
 * System Health Check — Runs daily at 8:00 AM ET before market open.
 *
 * Validates: API keys, data integrity, risk limits, circuit breaker state.
 *
 * Calls: scripts/system_health_check.py
 */

import { schedules, logger } from "@trigger.dev/sdk/v3";
import { runPython } from "./run-python.js";

export const systemHealthCheck = schedules.task({
  id: "system-health-check",
  cron: {
    pattern: "0 8 * * 1-5",
    timezone: "America/New_York",
  },
  run: async (payload) => {
    logger.info("Pre-market health check", {
      timestamp: payload.timestamp,
    });

    const result = await runPython("./scripts/system_health_check.py", []);

    const healthy = result.exitCode === 0;
    logger.info("Health check result", { healthy, output: result.stdout });

    if (!healthy) {
      logger.error("System health check FAILED — trading halted", {
        stderr: result.stderr,
        output: result.stdout,
      });
    }

    return {
      checkedAt: new Date().toISOString(),
      healthy,
      rawOutput: result.stdout.trim(),
    };
  },
});
