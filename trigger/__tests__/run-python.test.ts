import { describe, it, expect } from "vitest";
import { runPython } from "../run-python.js";

describe("runPython", () => {
  it("runs a simple Python command and captures stdout", async () => {
    const result = await runPython("-c", ["print('hello from python')"]);
    expect(result.stdout.trim()).toBe("hello from python");
    expect(result.exitCode).toBe(0);
  });

  it("captures stderr on import error", async () => {
    const result = await runPython("-c", [
      "import nonexistent_module_xyz_123",
    ]);
    expect(result.exitCode).not.toBe(0);
    expect(result.stderr).toContain("ModuleNotFoundError");
  });

  it("returns non-zero exit code on syntax error", async () => {
    const result = await runPython("-c", ["def bad syntax"]);
    expect(result.exitCode).not.toBe(0);
  });

  it("passes arguments correctly", async () => {
    const result = await runPython("-c", [
      "import sys; print(sys.argv[1:])",
      "arg1",
      "arg2",
    ]);
    expect(result.stdout).toContain("arg1");
    expect(result.stdout).toContain("arg2");
    expect(result.exitCode).toBe(0);
  });

  it("handles JSON output from Python", async () => {
    const result = await runPython("-c", [
      'import json; print(json.dumps({"status": "ok", "count": 42}))',
    ]);
    expect(result.exitCode).toBe(0);
    const parsed = JSON.parse(result.stdout.trim());
    expect(parsed.status).toBe("ok");
    expect(parsed.count).toBe(42);
  });
});
