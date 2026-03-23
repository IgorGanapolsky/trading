import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

/**
 * Structural tests for trigger task definitions.
 *
 * These verify that:
 *   1. All expected task files exist
 *   2. Each task exports a schedules.task with the correct id
 *   3. Cron patterns are valid for market hours (ET)
 *   4. Tasks call the correct Python scripts
 */

const TRIGGER_DIR = resolve(import.meta.dirname ?? ".", "..");

const EXPECTED_TASKS = [
  {
    file: "iron-condor-guardian.ts",
    id: "iron-condor-guardian",
    script: "iron_condor_guardian.py",
    cron: "*/30 9-15 * * 1-5",
  },
  {
    file: "position-monitor.ts",
    id: "position-monitor",
    script: "manage_iron_condor_positions.py",
    cron: "*/30 9-16 * * 1-5",
  },
  {
    file: "daily-scanner.ts",
    id: "daily-ic-scanner",
    script: "iron_condor_scanner.py",
    cron: "45 9 * * 1-5",
  },
  {
    file: "system-health.ts",
    id: "system-health-check",
    script: "system_health_check.py",
    cron: "0 8 * * 1-5",
  },
];

describe("Trigger task definitions", () => {
  for (const task of EXPECTED_TASKS) {
    describe(task.id, () => {
      const filePath = resolve(TRIGGER_DIR, task.file);
      const content = existsSync(filePath)
        ? readFileSync(filePath, "utf-8")
        : "";

      it("file exists", () => {
        expect(existsSync(filePath)).toBe(true);
      });

      it("exports a task with correct id", () => {
        expect(content).toContain(`id: "${task.id}"`);
      });

      it("uses schedules.task for cron scheduling", () => {
        expect(content).toContain("schedules.task");
      });

      it("targets correct Python script", () => {
        expect(content).toContain(task.script);
      });

      it("uses America/New_York timezone", () => {
        expect(content).toContain('timezone: "America/New_York"');
      });

      it("only runs on weekdays (1-5)", () => {
        expect(content).toContain("* 1-5");
      });

      it("has correct cron pattern", () => {
        expect(content).toContain(`pattern: "${task.cron}"`);
      });

      it("handles non-zero exit codes", () => {
        expect(content).toContain("exitCode");
      });
    });
  }
});

describe("trigger.config.ts", () => {
  const configPath = resolve(TRIGGER_DIR, "..", "trigger.config.ts");

  it("exists", () => {
    expect(existsSync(configPath)).toBe(true);
  });

  it("configures ./trigger as task directory", () => {
    const content = readFileSync(configPath, "utf-8");
    expect(content).toContain("./trigger");
  });

  it("sets retry configuration", () => {
    const content = readFileSync(configPath, "utf-8");
    expect(content).toContain("retries");
    expect(content).toContain("maxAttempts");
  });

  it("sets max duration", () => {
    const content = readFileSync(configPath, "utf-8");
    expect(content).toContain("maxDuration");
  });
});
