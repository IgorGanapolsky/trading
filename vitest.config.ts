import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["trigger/__tests__/**/*.test.ts", "contest/**/*.test.js"],
    testTimeout: 30_000,
  },
});
