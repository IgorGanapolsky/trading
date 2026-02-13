#!/usr/bin/env node
/**
 * Self-Healing RLHF Maintenance
 *
 * Runs after every feedback capture to auto-repair data integrity issues.
 * Silent when healthy, verbose when fixing.
 *
 * LOCAL ONLY - Never commit to repository
 *
 * Features:
 *   1. Auto-repair corrupt JSONL (multi-line entries, invalid JSON)
 *   2. Re-index LanceDB when stale (feedback_count drift >= 5)
 *   3. Cortex sync check (pending unsynced entries)
 *   4. One-line health status summary
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const FEEDBACK_DIR = path.join(__dirname, '../../memory/feedback');
const FEEDBACK_FILE = path.join(FEEDBACK_DIR, 'feedback-log.jsonl');
const SEQUENCE_FILE = path.join(FEEDBACK_DIR, 'feedback-sequences.jsonl');
const LANCE_STATE_FILE = path.join(FEEDBACK_DIR, 'lance-index-state.json');
const CORTEX_SYNC_FILE = path.join(FEEDBACK_DIR, 'pending_cortex_sync.jsonl');
const SCRIPTS_DIR = __dirname;

/**
 * Repair a JSONL file: fix multi-line entries, remove corrupt lines.
 * Returns { repaired: number, removed: number, total: number }
 */
function repairJsonl(filePath) {
  if (!fs.existsSync(filePath)) return { repaired: 0, removed: 0, total: 0 };

  const raw = fs.readFileSync(filePath, 'utf8');
  if (!raw.trim()) return { repaired: 0, removed: 0, total: 0 };

  const lines = raw.split('\n');
  const validEntries = [];
  let repaired = 0;
  let removed = 0;
  let buffer = '';

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    // Try parsing the line directly
    try {
      JSON.parse(line);
      if (buffer) {
        // We had an incomplete buffer; the previous partial is corrupt
        removed++;
        buffer = '';
      }
      validEntries.push(line);
      continue;
    } catch (_) {
      // Not valid on its own
    }

    // Accumulate into buffer for multi-line JSON repair
    buffer += (buffer ? ' ' : '') + line;

    try {
      JSON.parse(buffer);
      // Multi-line JSON successfully merged into single line
      validEntries.push(buffer);
      repaired++;
      buffer = '';
    } catch (_) {
      // Still incomplete - keep accumulating, but cap at 20 lines
      const bufferLines = buffer.split(' ').length;
      if (bufferLines > 20) {
        removed++;
        buffer = '';
      }
    }
  }

  // Leftover buffer is corrupt
  if (buffer) removed++;

  // Only rewrite if we fixed or removed something
  if (repaired > 0 || removed > 0) {
    const newContent = validEntries.join('\n') + (validEntries.length ? '\n' : '');
    fs.writeFileSync(filePath, newContent);
  }

  return { repaired, removed, total: validEntries.length };
}

/**
 * Count valid lines in a JSONL file
 */
function countJsonlEntries(filePath) {
  if (!fs.existsSync(filePath)) return 0;
  const content = fs.readFileSync(filePath, 'utf8').trim();
  if (!content) return 0;
  return content.split('\n').filter(line => {
    try { JSON.parse(line.trim()); return true; } catch (_) { return false; }
  }).length;
}

/**
 * Check if LanceDB index is stale and re-index if needed.
 * Stale = feedback_count in state file is 5+ behind actual entries.
 */
function checkLanceIndex() {
  if (!fs.existsSync(LANCE_STATE_FILE)) return { stale: false, reindexed: false };

  let state;
  try {
    state = JSON.parse(fs.readFileSync(LANCE_STATE_FILE, 'utf8'));
  } catch (_) {
    return { stale: true, reindexed: false, error: 'corrupt lance-index-state.json' };
  }

  const actualCount = countJsonlEntries(FEEDBACK_FILE);
  const indexedCount = state.feedback_count || 0;
  const drift = actualCount - indexedCount;

  if (drift < 5) return { stale: false, reindexed: false, drift, actualCount, indexedCount };

  // Attempt re-index
  const pythonBin = path.join(SCRIPTS_DIR, 'venv312', 'bin', 'python3');
  const indexScript = path.join(SCRIPTS_DIR, 'semantic-memory-v2.py');

  if (!fs.existsSync(pythonBin) || !fs.existsSync(indexScript)) {
    return { stale: true, reindexed: false, drift, actualCount, indexedCount, error: 'missing venv312 or semantic-memory-v2.py' };
  }

  try {
    execSync(`"${pythonBin}" "${indexScript}" --index`, {
      cwd: SCRIPTS_DIR,
      timeout: 30000,
      stdio: 'pipe'
    });
    return { stale: true, reindexed: true, drift, actualCount, indexedCount };
  } catch (e) {
    return { stale: true, reindexed: false, drift, actualCount, indexedCount, error: e.message?.slice(0, 200) };
  }
}

/**
 * Check for unsynced cortex entries and emit MCP call instructions.
 */
function checkCortexSync() {
  if (!fs.existsSync(CORTEX_SYNC_FILE)) return { pending: 0, entries: [] };

  const content = fs.readFileSync(CORTEX_SYNC_FILE, 'utf8').trim();
  if (!content) return { pending: 0, entries: [] };

  const unsyncedEntries = [];
  const lines = content.split('\n');

  for (const line of lines) {
    if (!line.trim()) continue;
    try {
      const entry = JSON.parse(line.trim());
      if (!entry.synced) {
        unsyncedEntries.push(entry);
      }
    } catch (_) {
      // Skip corrupt lines (will be caught by JSONL repair if added to repair list)
    }
  }

  return { pending: unsyncedEntries.length, entries: unsyncedEntries };
}

/**
 * Main self-heal run. Returns a result object.
 */
function run() {
  const startTime = Date.now();
  const fixes = [];
  let healthy = true;

  // 1. Repair JSONL files
  const feedbackRepair = repairJsonl(FEEDBACK_FILE);
  const sequenceRepair = repairJsonl(SEQUENCE_FILE);

  if (feedbackRepair.repaired > 0 || feedbackRepair.removed > 0) {
    healthy = false;
    fixes.push(`feedback-log.jsonl: repaired=${feedbackRepair.repaired}, removed=${feedbackRepair.removed}, total=${feedbackRepair.total}`);
    console.log(`[self-heal] Fixed feedback-log.jsonl: ${feedbackRepair.repaired} repaired, ${feedbackRepair.removed} removed (${feedbackRepair.total} valid entries)`);
  }

  if (sequenceRepair.repaired > 0 || sequenceRepair.removed > 0) {
    healthy = false;
    fixes.push(`feedback-sequences.jsonl: repaired=${sequenceRepair.repaired}, removed=${sequenceRepair.removed}, total=${sequenceRepair.total}`);
    console.log(`[self-heal] Fixed feedback-sequences.jsonl: ${sequenceRepair.repaired} repaired, ${sequenceRepair.removed} removed (${sequenceRepair.total} valid entries)`);
  }

  // 2. Check LanceDB index staleness
  const lanceResult = checkLanceIndex();
  if (lanceResult.stale) {
    healthy = false;
    if (lanceResult.reindexed) {
      fixes.push(`LanceDB re-indexed: drift was ${lanceResult.drift} (${lanceResult.indexedCount} -> ${lanceResult.actualCount})`);
      console.log(`[self-heal] LanceDB re-indexed: ${lanceResult.indexedCount} -> ${lanceResult.actualCount} entries (drift=${lanceResult.drift})`);
    } else {
      fixes.push(`LanceDB stale (drift=${lanceResult.drift}): ${lanceResult.error || 'unknown error'}`);
      console.log(`[self-heal] LanceDB stale (drift=${lanceResult.drift}) but re-index failed: ${lanceResult.error || 'unknown'}`);
    }
  }

  // 3. Cortex sync check
  const cortexResult = checkCortexSync();
  if (cortexResult.pending > 0) {
    healthy = false;
    fixes.push(`${cortexResult.pending} unsynced cortex entries`);
    console.log(`[self-heal] ${cortexResult.pending} pending cortex sync entries:`);
    cortexResult.entries.forEach(entry => {
      console.log(`  MCP: mcp__memory__remember({ title: "${entry.context?.slice(0, 60) || entry.id}", content: "signal=${entry.signal} intensity=${entry.intensity} context=${entry.context}", tags: ["rlhf", "${entry.signal}"], category: "learning" })`);
    });
  }

  // 4. Summary stats
  const elapsed = Date.now() - startTime;
  const feedbackCount = countJsonlEntries(FEEDBACK_FILE);
  const sequenceCount = countJsonlEntries(SEQUENCE_FILE);

  if (healthy) {
    // Silent when healthy - only print if run standalone
    if (require.main === module) {
      console.log(`[self-heal] OK | ${feedbackCount} feedback, ${sequenceCount} sequences, lance drift=${lanceResult.drift || 0}, cortex pending=${cortexResult.pending} | ${elapsed}ms`);
    }
  } else {
    console.log(`[self-heal] HEALED | ${fixes.length} fixes applied | ${feedbackCount} feedback, ${sequenceCount} sequences | ${elapsed}ms`);
  }

  return {
    healthy,
    elapsed,
    feedbackCount,
    sequenceCount,
    fixes,
    lanceResult,
    cortexResult
  };
}

// CLI execution
if (require.main === module) {
  run();
}

module.exports = { run };
