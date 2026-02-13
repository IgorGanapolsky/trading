#!/usr/bin/env node
/**
 * Feedback Data Quality Validator
 *
 * Implements prompt engineering best practices for data quality:
 * 1. Schema-level validation (required fields)
 * 2. Semantic validation (logical consistency)
 * 3. Anomaly detection (suspicious patterns)
 * 4. Self-correction (explain flagged issues)
 *
 * Based on: https://www.kdnuggets.com/prompt-engineering-for-data-quality-and-validation-checks
 *
 * Usage:
 *   echo '{"feedback":"positive",...}' | node validate-feedback.js
 *   node validate-feedback.js --audit  # Audit existing feedback log
 *   node validate-feedback.js --stats  # Quality statistics
 *
 * LOCAL ONLY - Do not commit to repository
 */

const fs = require('fs');
const path = require('path');

// Configuration
const FEEDBACK_DIR = path.join(__dirname, '../../memory/feedback');
const FEEDBACK_LOG = path.join(FEEDBACK_DIR, 'feedback-log.jsonl');
const VALIDATION_LOG = path.join(FEEDBACK_DIR, 'validation-issues.jsonl');
const QUALITY_REPORT = path.join(FEEDBACK_DIR, 'quality-report.json');

// =============================================================================
// SCHEMA VALIDATION (Level 1)
// =============================================================================

const REQUIRED_FIELDS = ['timestamp', 'feedback', 'source'];
const VALID_FEEDBACK_VALUES = ['positive', 'negative', 'neutral'];
const VALID_SOURCES = ['auto', 'user', 'hook', 'manual'];
const VALID_REWARD_RANGE = [-1, 1];

function validateSchema(entry) {
  const issues = [];

  // Check required fields
  for (const field of REQUIRED_FIELDS) {
    if (!(field in entry)) {
      issues.push({
        level: 'error',
        field,
        message: `Missing required field: ${field}`,
        suggestion: `Add "${field}" to the feedback entry`
      });
    }
  }

  // Validate feedback value
  if (entry.feedback && !VALID_FEEDBACK_VALUES.includes(entry.feedback)) {
    issues.push({
      level: 'warning',
      field: 'feedback',
      message: `Invalid feedback value: "${entry.feedback}"`,
      suggestion: `Use one of: ${VALID_FEEDBACK_VALUES.join(', ')}`
    });
  }

  // Validate source
  if (entry.source && !VALID_SOURCES.includes(entry.source)) {
    issues.push({
      level: 'warning',
      field: 'source',
      message: `Unknown source: "${entry.source}"`,
      suggestion: `Use one of: ${VALID_SOURCES.join(', ')}`
    });
  }

  // Validate reward range
  if ('reward' in entry) {
    if (typeof entry.reward !== 'number' ||
        entry.reward < VALID_REWARD_RANGE[0] ||
        entry.reward > VALID_REWARD_RANGE[1]) {
      issues.push({
        level: 'error',
        field: 'reward',
        message: `Reward out of range: ${entry.reward}`,
        suggestion: `Reward must be between ${VALID_REWARD_RANGE[0]} and ${VALID_REWARD_RANGE[1]}`
      });
    }
  }

  // Validate timestamp format
  if (entry.timestamp) {
    const ts = new Date(entry.timestamp);
    if (isNaN(ts.getTime())) {
      issues.push({
        level: 'error',
        field: 'timestamp',
        message: `Invalid timestamp format: "${entry.timestamp}"`,
        suggestion: 'Use ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ'
      });
    } else if (ts > new Date()) {
      issues.push({
        level: 'warning',
        field: 'timestamp',
        message: 'Timestamp is in the future',
        suggestion: 'Check system clock synchronization'
      });
    }
  }

  return issues;
}

// =============================================================================
// SEMANTIC VALIDATION (Level 2)
// =============================================================================

function validateSemantics(entry) {
  const issues = [];

  // Feedback-reward consistency
  if (entry.feedback === 'positive' && entry.reward < 0) {
    issues.push({
      level: 'error',
      field: 'reward',
      message: 'Positive feedback but negative reward',
      explanation: 'Semantic inconsistency: positive feedback should have reward >= 0',
      suggestion: 'Either change feedback to "negative" or reward to positive value'
    });
  }

  if (entry.feedback === 'negative' && entry.reward > 0) {
    issues.push({
      level: 'error',
      field: 'reward',
      message: 'Negative feedback but positive reward',
      explanation: 'Semantic inconsistency: negative feedback should have reward <= 0',
      suggestion: 'Either change feedback to "positive" or reward to negative value'
    });
  }

  // Context validation
  if (entry.context) {
    // Empty context with feedback
    if (typeof entry.context === 'string' && entry.context.trim().length < 5) {
      issues.push({
        level: 'warning',
        field: 'context',
        message: 'Context too short to be meaningful',
        explanation: 'Short context reduces ML training value',
        suggestion: 'Provide more descriptive context (at least 10 characters)'
      });
    }

    // Check for placeholder text
    const placeholders = ['TODO', 'FIXME', 'placeholder', 'test', 'example'];
    for (const ph of placeholders) {
      if (typeof entry.context === 'string' &&
          entry.context.toLowerCase().includes(ph.toLowerCase())) {
        issues.push({
          level: 'warning',
          field: 'context',
          message: `Context contains placeholder text: "${ph}"`,
          explanation: 'Placeholder text may indicate incomplete entry',
          suggestion: 'Replace with actual context or remove entry'
        });
        break;
      }
    }
  }

  // Tool-specific validation
  if (entry.tool_name) {
    const validTools = ['Read', 'Write', 'Edit', 'Bash', 'Glob', 'Grep', 'Task', 'WebFetch'];
    if (!validTools.includes(entry.tool_name)) {
      issues.push({
        level: 'info',
        field: 'tool_name',
        message: `Uncommon tool: "${entry.tool_name}"`,
        explanation: 'Tool not in standard list - may be valid but unusual',
        suggestion: 'Verify tool name is correct'
      });
    }
  }

  return issues;
}

// =============================================================================
// ANOMALY DETECTION (Level 3)
// =============================================================================

// Track patterns for anomaly detection
const sessionPatterns = new Map();

function detectAnomalies(entry, allEntries = []) {
  const issues = [];

  // Rapid feedback burst (more than 5 in 1 minute)
  if (entry.timestamp && allEntries.length > 0) {
    const entryTime = new Date(entry.timestamp);
    const recentEntries = allEntries.filter(e => {
      const t = new Date(e.timestamp);
      return Math.abs(entryTime - t) < 60000; // 1 minute
    });

    if (recentEntries.length > 5) {
      issues.push({
        level: 'warning',
        type: 'anomaly',
        message: 'Feedback burst detected',
        explanation: `${recentEntries.length} entries within 1 minute - unusual pattern`,
        suggestion: 'Verify this is not automated noise or duplicate entries'
      });
    }
  }

  // Same feedback repeated exactly
  if (entry.context && allEntries.length > 0) {
    const duplicates = allEntries.filter(e =>
      e.context === entry.context &&
      e.feedback === entry.feedback &&
      e.tool_name === entry.tool_name
    );

    if (duplicates.length > 0) {
      issues.push({
        level: 'warning',
        type: 'anomaly',
        message: 'Duplicate feedback entry',
        explanation: `Found ${duplicates.length} identical entries`,
        suggestion: 'Consider deduplication or review capture logic'
      });
    }
  }

  // All negative or all positive (session imbalance)
  if (allEntries.length >= 10) {
    const positiveCount = allEntries.filter(e => e.feedback === 'positive').length;
    const ratio = positiveCount / allEntries.length;

    if (ratio > 0.95) {
      issues.push({
        level: 'info',
        type: 'anomaly',
        message: 'Feedback heavily skewed positive',
        explanation: `${(ratio * 100).toFixed(1)}% positive - may indicate capture bias`,
        suggestion: 'Review if negative cases are being properly captured'
      });
    } else if (ratio < 0.05) {
      issues.push({
        level: 'warning',
        type: 'anomaly',
        message: 'Feedback heavily skewed negative',
        explanation: `${((1 - ratio) * 100).toFixed(1)}% negative - unusual pattern`,
        suggestion: 'Check for systematic issues or misconfigured error detection'
      });
    }
  }

  // Suspicious context patterns
  if (entry.context) {
    // Check for sensitive data leakage
    const sensitivePatterns = [
      /api[_-]?key/i,
      /password/i,
      /secret/i,
      /token/i,
      /bearer/i,
      /\b[A-Za-z0-9]{32,}\b/  // Long alphanumeric strings (possible keys)
    ];

    for (const pattern of sensitivePatterns) {
      if (pattern.test(entry.context)) {
        issues.push({
          level: 'error',
          type: 'security',
          message: 'Potential sensitive data in context',
          explanation: `Pattern matched: ${pattern.toString()}`,
          suggestion: 'Redact sensitive information before logging'
        });
        break;
      }
    }
  }

  return issues;
}

// =============================================================================
// SELF-CORRECTION (Level 4)
// =============================================================================

function generateCorrections(entry, issues) {
  const corrections = [];

  for (const issue of issues) {
    if (issue.level === 'error') {
      // Auto-correct where possible
      if (issue.field === 'reward' && entry.feedback) {
        const correctedReward = entry.feedback === 'positive' ? 1 :
                               entry.feedback === 'negative' ? -1 : 0;
        corrections.push({
          field: 'reward',
          original: entry.reward,
          corrected: correctedReward,
          reason: 'Auto-corrected to match feedback type'
        });
      }

      if (issue.field === 'timestamp' && !entry.timestamp) {
        corrections.push({
          field: 'timestamp',
          original: null,
          corrected: new Date().toISOString(),
          reason: 'Added missing timestamp'
        });
      }
    }
  }

  return corrections;
}

function applyCorrections(entry, corrections) {
  const corrected = { ...entry };
  for (const c of corrections) {
    corrected[c.field] = c.corrected;
  }
  corrected._corrected = true;
  corrected._corrections = corrections;
  return corrected;
}

// =============================================================================
// MAIN VALIDATION PIPELINE
// =============================================================================

function validateEntry(entry, allEntries = []) {
  const result = {
    valid: true,
    entry,
    issues: [],
    corrections: [],
    correctedEntry: null
  };

  // Level 1: Schema
  result.issues.push(...validateSchema(entry));

  // Level 2: Semantics
  result.issues.push(...validateSemantics(entry));

  // Level 3: Anomalies
  result.issues.push(...detectAnomalies(entry, allEntries));

  // Level 4: Self-correction
  result.corrections = generateCorrections(entry, result.issues);

  // Determine validity
  const hasErrors = result.issues.some(i => i.level === 'error');
  result.valid = !hasErrors;

  // Apply corrections if available
  if (result.corrections.length > 0) {
    result.correctedEntry = applyCorrections(entry, result.corrections);
  }

  return result;
}

// =============================================================================
// CLI INTERFACE
// =============================================================================

function loadFeedbackLog() {
  if (!fs.existsSync(FEEDBACK_LOG)) return [];

  const content = fs.readFileSync(FEEDBACK_LOG, 'utf8');
  return content.trim().split('\n')
    .filter(line => line.trim())
    .map(line => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(e => e !== null);
}

function auditFeedbackLog() {
  console.log('📊 Auditing feedback log...\n');

  const entries = loadFeedbackLog();
  if (entries.length === 0) {
    console.log('No entries to audit.');
    return;
  }

  const results = {
    total: entries.length,
    valid: 0,
    invalid: 0,
    corrected: 0,
    issuesByLevel: { error: 0, warning: 0, info: 0 },
    issuesByField: {}
  };

  const validationIssues = [];

  for (const entry of entries) {
    const validation = validateEntry(entry, entries);

    if (validation.valid) {
      results.valid++;
    } else {
      results.invalid++;
    }

    if (validation.corrections.length > 0) {
      results.corrected++;
    }

    for (const issue of validation.issues) {
      results.issuesByLevel[issue.level] = (results.issuesByLevel[issue.level] || 0) + 1;
      results.issuesByField[issue.field] = (results.issuesByField[issue.field] || 0) + 1;

      validationIssues.push({
        timestamp: entry.timestamp,
        ...issue
      });
    }
  }

  // Save validation issues
  if (validationIssues.length > 0) {
    const issueLog = validationIssues.map(i => JSON.stringify(i)).join('\n');
    fs.writeFileSync(VALIDATION_LOG, issueLog);
  }

  // Save quality report
  const report = {
    ...results,
    validityRate: ((results.valid / results.total) * 100).toFixed(2) + '%',
    auditedAt: new Date().toISOString()
  };
  fs.writeFileSync(QUALITY_REPORT, JSON.stringify(report, null, 2));

  // Print summary
  console.log(`Total entries: ${results.total}`);
  console.log(`Valid: ${results.valid} (${report.validityRate})`);
  console.log(`Invalid: ${results.invalid}`);
  console.log(`Auto-corrected: ${results.corrected}`);
  console.log('\nIssues by level:');
  console.log(`  Errors: ${results.issuesByLevel.error || 0}`);
  console.log(`  Warnings: ${results.issuesByLevel.warning || 0}`);
  console.log(`  Info: ${results.issuesByLevel.info || 0}`);

  if (Object.keys(results.issuesByField).length > 0) {
    console.log('\nTop issue fields:');
    const sorted = Object.entries(results.issuesByField)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);
    for (const [field, count] of sorted) {
      console.log(`  ${field}: ${count}`);
    }
  }

  console.log(`\nDetailed issues saved to: ${VALIDATION_LOG}`);
  console.log(`Quality report saved to: ${QUALITY_REPORT}`);
}

function showStats() {
  if (!fs.existsSync(QUALITY_REPORT)) {
    console.log('No quality report found. Run --audit first.');
    return;
  }

  const report = JSON.parse(fs.readFileSync(QUALITY_REPORT, 'utf8'));
  console.log('📊 Feedback Quality Statistics\n');
  console.log(JSON.stringify(report, null, 2));
}

// Main entry point
async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--audit')) {
    auditFeedbackLog();
  } else if (args.includes('--stats')) {
    showStats();
  } else {
    // Read from stdin (piped input)
    let input = '';

    if (!process.stdin.isTTY) {
      for await (const chunk of process.stdin) {
        input += chunk;
      }
    }

    if (input.trim()) {
      try {
        const entry = JSON.parse(input);
        const allEntries = loadFeedbackLog();
        const result = validateEntry(entry, allEntries);

        if (result.valid) {
          // Output validated (possibly corrected) entry
          const output = result.correctedEntry || result.entry;
          console.log(JSON.stringify(output));
        } else {
          // Output issues to stderr, still output entry to stdout
          console.error('[VALIDATION] Issues found:');
          for (const issue of result.issues) {
            console.error(`  [${issue.level}] ${issue.message}`);
          }
          console.log(JSON.stringify(result.correctedEntry || result.entry));
        }
      } catch (e) {
        console.error(`[VALIDATION] Invalid JSON: ${e.message}`);
        process.exit(1);
      }
    } else {
      console.log('Feedback Data Quality Validator');
      console.log('\nUsage:');
      console.log('  echo \'{"feedback":"positive",...}\' | node validate-feedback.js');
      console.log('  node validate-feedback.js --audit   # Audit existing log');
      console.log('  node validate-feedback.js --stats   # Show statistics');
    }
  }
}

main().catch(console.error);
