import { defineConfig } from "@trigger.dev/sdk";

export default defineConfig({
  // Set your project ref from https://cloud.trigger.dev after login
  project: process.env.TRIGGER_PROJECT_REF ?? "trading-system",
  dirs: ["./trigger"],
  retries: {
    enabledInDev: false,
    default: {
      maxAttempts: 3,
      minTimeoutInMs: 1_000,
      maxTimeoutInMs: 30_000,
      factor: 2,
      randomize: true,
    },
  },
  maxDuration: 600, // 10 minutes max per task
});
