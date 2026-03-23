/**
 * Utility: Run a Python script and return its output.
 *
 * Uses child_process.execFile (no shell injection risk).
 * Inherits the current process environment so Python scripts
 * have access to ALPACA_API_KEY, etc.
 */

import { spawn } from "node:child_process";

export interface PythonResult {
  stdout: string;
  stderr: string;
  exitCode: number;
}

export function runPython(
  scriptPath: string,
  args: string[] = [],
): Promise<PythonResult> {
  return new Promise((resolve) => {
    const child = spawn("python3", [scriptPath, ...args], {
      timeout: 300_000,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (data: Buffer) => { stdout += data.toString(); });
    child.stderr.on("data", (data: Buffer) => { stderr += data.toString(); });

    child.on("close", (code) => {
      resolve({ stdout, stderr, exitCode: code ?? 1 });
    });

    child.on("error", (err) => {
      resolve({ stdout, stderr: err.message, exitCode: 127 });
    });
  });
}
