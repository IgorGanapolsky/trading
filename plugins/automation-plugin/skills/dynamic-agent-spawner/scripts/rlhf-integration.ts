#!/usr/bin/env ts-node
/**
 * RLHF Integration with Hybrid MemAlign + Cortex
 * Connects thumbs up/down feedback to BOTH memory systems:
 * - MemAlign: Fast semantic search for agent decisions
 * - Cortex: Human-readable audit trail for oversight
 */

import { MemAlign, type Feedback } from "./memalign.ts";
import { CortexWriter, type CortexEntry } from "./cortex-writer.ts";
import { readFileSync, existsSync, writeFileSync } from "fs";
import { join } from "path";

interface RLHFEvent {
  taskId: string;
  agentDecision: string;
  feedback: "thumbs_up" | "thumbs_down";
  context: string;
  timestamp: string;
}

class RLHFIntegration {
  private memAlign: MemAlign;
  private cortex: CortexWriter;
  private pendingFeedbackFiles: string[];
  private pendingFeedbackFile: string;

  constructor() {
    this.memAlign = new MemAlign();
    this.cortex = new CortexWriter();
    const memoryRoot = join(process.cwd(), ".claude", "memory");
    this.pendingFeedbackFiles = [
      join(memoryRoot, "feedback", "pending_cortex_sync.jsonl"),
      join(memoryRoot, "pending_cortex_sync.jsonl"),
    ];
    this.pendingFeedbackFile = this.resolvePendingFile();
  }

  private resolvePendingFile(): string {
    for (const candidate of this.pendingFeedbackFiles) {
      if (existsSync(candidate)) {
        return candidate;
      }
    }
    return this.pendingFeedbackFiles[0];
  }

  /**
   * Process pending RLHF feedback and sync to BOTH MemAlign + Cortex
   */
  async syncPendingFeedback(): Promise<void> {
    this.pendingFeedbackFile = this.resolvePendingFile();
    if (!existsSync(this.pendingFeedbackFile)) {
      console.log("ℹ️  No pending feedback to sync");
      return;
    }

    const content = readFileSync(this.pendingFeedbackFile, "utf-8");
    const lines = content
      .trim()
      .split("\n")
      .filter((l) => l.length > 0);

    if (lines.length === 0) {
      console.log("ℹ️  No pending feedback to sync");
      return;
    }

    console.log(
      `🔄 Syncing ${lines.length} pending feedback entries to hybrid memory...`,
    );

    for (const line of lines) {
      try {
        const event: RLHFEvent = JSON.parse(line);
        await this.processFeedback(event);
      } catch (error) {
        console.error(`⚠️  Failed to process feedback: ${error}`);
      }
    }

    // Clear pending file after successful sync
    writeFileSync(this.pendingFeedbackFile, "");
    console.log("✅ Hybrid memory sync complete");
    console.log(
      "   - MemAlign: Semantic principles + episodic memories updated",
    );
    console.log("   - Cortex: Human-readable audit trail appended");
  }

  /**
   * Process individual feedback event - writes to BOTH MemAlign + Cortex
   */
  private async processFeedback(event: RLHFEvent): Promise<void> {
    const sentiment = event.feedback === "thumbs_up" ? "positive" : "negative";
    const naturalFeedback = this.generateNaturalLanguageFeedback(event);

    // 1. MemAlign: Fast semantic search for agents
    const feedback: Feedback = {
      taskId: event.taskId,
      agentDecision: event.agentDecision,
      userFeedback: naturalFeedback,
      sentiment,
      timestamp: event.timestamp,
    };

    const memAlignResult = await this.memAlign.learn(feedback);

    // 2. Cortex: Human-readable audit trail
    // Extract the first principle from MemAlign's learning
    const principle = event.agentDecision; // Simplified - in production, extract from Claude's response
    const domain = this.inferDomain(event.context);

    const cortexEntry: CortexEntry = {
      timestamp: event.timestamp,
      taskId: event.taskId,
      principle,
      context: event.context,
      sentiment,
      confidence: sentiment === "positive" ? 0.8 : 0.5, // Positive feedback increases confidence
      domain,
    };

    await this.cortex.appendFeedback(cortexEntry);
  }

  /**
   * Infer domain from context
   */
  private inferDomain(context: string): string {
    const contextLower = context.toLowerCase();
    if (contextLower.includes("pr") || contextLower.includes("pull request")) {
      return "pr-review";
    }
    if (
      contextLower.includes("ci") ||
      contextLower.includes("test") ||
      contextLower.includes("build")
    ) {
      return "ci-validation";
    }
    if (contextLower.includes("ado") || contextLower.includes("work item")) {
      return "ado-automation";
    }
    return "general";
  }

  /**
   * Generate natural language feedback from RLHF event
   */
  private generateNaturalLanguageFeedback(event: RLHFEvent): string {
    if (event.feedback === "thumbs_up") {
      return `The agent's decision was correct: ${event.agentDecision}. Context: ${event.context}`;
    } else {
      return `The agent's decision was incorrect: ${event.agentDecision}. This approach should be avoided in similar situations. Context: ${event.context}`;
    }
  }

  /**
   * Record immediate feedback (real-time)
   */
  async recordFeedback(
    taskId: string,
    agentDecision: string,
    feedback: "thumbs_up" | "thumbs_down",
    context: string,
  ): Promise<void> {
    const event: RLHFEvent = {
      taskId,
      agentDecision,
      feedback,
      context,
      timestamp: new Date().toISOString(),
    };

    await this.processFeedback(event);
  }
}

// CLI Interface
async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  const rlhf = new RLHFIntegration();

  switch (command) {
    case "sync":
      await rlhf.syncPendingFeedback();
      break;

    case "record": {
      const taskId = args[1] || "unknown";
      const decision = args[2] || "unknown";
      const feedback = (args[3] as "thumbs_up" | "thumbs_down") || "thumbs_up";
      const context = args.slice(4).join(" ") || "";
      await rlhf.recordFeedback(taskId, decision, feedback, context);
      break;
    }

    default:
      console.log(`
RLHF Integration with Hybrid MemAlign + Cortex

Usage:
  rlhf-integration.ts sync
  rlhf-integration.ts record <task-id> <decision> <thumbs_up|thumbs_down> <context>

Examples:
  rlhf-integration.ts sync
  rlhf-integration.ts record "PR-175" "Require plugin tests" thumbs_down "SKILL.md is documentation"

Memory Systems:
  - MemAlign: Fast semantic search for agent decisions (.claude/memory/memalign/)
  - Cortex: Human-readable audit trail (.claude/memory/lessons-learned.memory.md)
      `);
  }
}

if (require.main === module) {
  main().catch(console.error);
}

export { RLHFIntegration };
