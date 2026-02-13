#!/usr/bin/env node
/**
 * Thumbs Up/Down Feedback Capture for RLHF-style Learning
 *
 * Captures user feedback (thumbs up/down) with conversation context
 * and stores it for RAG/ML pipeline processing.
 *
 * Enhanced with SEQUENCE TRACKING for LSTM/Transformer training.
 *
 * LOCAL ONLY - Never commit to repository
 *
 * Usage:
 *   node capture-feedback.js --feedback=up --context="Answered xAPI question correctly"
 *   node capture-feedback.js --feedback=down --context="Gave surface-level answer"
 *   node capture-feedback.js --feedback=up --context="Read actual code files" --tags="code-reading,implementation"
 *   node capture-feedback.js --stats
 *   node capture-feedback.js --export-training
 */

const fs = require('fs');
const path = require('path');

// Configuration
const FEEDBACK_DIR = path.join(__dirname, '../../memory/feedback');
const FEEDBACK_FILE = path.join(FEEDBACK_DIR, 'feedback-log.jsonl');
const SEQUENCE_FILE = path.join(FEEDBACK_DIR, 'feedback-sequences.jsonl');
const SUMMARY_FILE = path.join(FEEDBACK_DIR, 'feedback-summary.json');
const TRAINING_EXPORT_DIR = path.join(FEEDBACK_DIR, 'training-data');
const PATTERNS_FILE = path.join(FEEDBACK_DIR, 'success-patterns.md'); // File-based distillation
const DIVERSITY_FILE = path.join(FEEDBACK_DIR, 'diversity-tracking.json');

// Sequence tracking for LSTM/Transformer
const SEQUENCE_WINDOW = 10; // Track last N interactions for pattern learning

// Domain categories for diversity tracking (prevents representation collapse)
const DOMAIN_CATEGORIES = [
  'testing', 'security', 'performance', 'ui-components', 'api-integration',
  'git-workflow', 'documentation', 'debugging', 'architecture', 'data-modeling'
];

/**
 * Parse command line arguments
 */
function parseArgs() {
  const args = {};
  process.argv.slice(2).forEach(arg => {
    if (arg.startsWith('--')) {
      const [key, ...valueParts] = arg.slice(2).split('=');
      args[key] = valueParts.join('=') || true;
    }
  });
  return args;
}

/**
 * Ensure feedback directory exists
 */
function ensureDirectories() {
  [FEEDBACK_DIR, TRAINING_EXPORT_DIR].forEach(dir => {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  });
}

/**
 * Load existing summary or create new one
 */
function loadSummary() {
  if (fs.existsSync(SUMMARY_FILE)) {
    return JSON.parse(fs.readFileSync(SUMMARY_FILE, 'utf8'));
  }
  return {
    totalFeedback: 0,
    thumbsUp: 0,
    thumbsDown: 0,
    lastUpdated: null,
    currentSessionId: null,
    sequenceCount: 0,
    topPatterns: {
      positive: {},
      negative: {}
    },
    // For LSTM/Transformer: track action->outcome patterns
    actionOutcomes: {},
    // Track streaks for momentum
    currentStreak: { type: null, count: 0 },
    longestPositiveStreak: 0,
    longestNegativeStreak: 0
  };
}

/**
 * Load recent feedback for sequence building
 */
function loadRecentFeedback(limit = SEQUENCE_WINDOW) {
  if (!fs.existsSync(FEEDBACK_FILE)) return [];

  const lines = fs.readFileSync(FEEDBACK_FILE, 'utf8').trim().split('\n').filter(Boolean);
  return lines.slice(-limit).map(line => JSON.parse(line));
}

/**
 * Build sequence features for LSTM/Transformer training
 */
function buildSequenceFeatures(recentFeedback, currentEntry) {
  const sequence = [...recentFeedback, currentEntry];

  // Extract features for time-series model
  return {
    // Sequence of rewards: [-1, 1, 1, -1, 1, ...]
    rewardSequence: sequence.map(f => f.reward),

    // Tag frequency in recent window
    tagFrequency: sequence.reduce((acc, f) => {
      (f.tags || []).forEach(tag => {
        acc[tag] = (acc[tag] || 0) + 1;
      });
      return acc;
    }, {}),

    // Momentum: recent trend
    recentTrend: calculateTrend(sequence.slice(-5).map(f => f.reward)),

    // Time gaps between feedback (for temporal patterns)
    timeGaps: calculateTimeGaps(sequence),

    // Context embeddings placeholder (for future semantic analysis)
    contextHashes: sequence.map(f => hashContext(f.context)),

    // Action patterns: what actions led to what outcomes
    actionPatterns: extractActionPatterns(sequence),
  };
}

/**
 * Calculate trend from recent rewards
 */
function calculateTrend(rewards) {
  if (rewards.length < 2) return 0;
  const recent = rewards.slice(-3);
  const sum = recent.reduce((a, b) => a + b, 0);
  return sum / recent.length; // -1 to 1 scale
}

/**
 * Calculate time gaps between feedback entries
 */
function calculateTimeGaps(sequence) {
  if (sequence.length < 2) return [];
  const gaps = [];
  for (let i = 1; i < sequence.length; i++) {
    const prev = new Date(sequence[i-1].timestamp).getTime();
    const curr = new Date(sequence[i].timestamp).getTime();
    gaps.push((curr - prev) / 1000 / 60); // Minutes
  }
  return gaps;
}

/**
 * Simple hash for context (for pattern matching)
 */
function hashContext(context) {
  if (!context) return 0;
  let hash = 0;
  for (let i = 0; i < context.length; i++) {
    const char = context.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return hash;
}

/**
 * Extract action->outcome patterns for predictive learning
 */
function extractActionPatterns(sequence) {
  const patterns = {};
  sequence.forEach(f => {
    (f.tags || []).forEach(tag => {
      if (!patterns[tag]) {
        patterns[tag] = { positive: 0, negative: 0 };
      }
      if (f.reward > 0) patterns[tag].positive++;
      else patterns[tag].negative++;
    });
  });
  return patterns;
}

/**
 * Save sequence for LSTM/Transformer training
 */
function saveSequence(sequenceFeatures, currentEntry) {
  ensureDirectories();

  const sequenceEntry = {
    id: `seq_${Date.now()}`,
    timestamp: new Date().toISOString(),
    targetReward: currentEntry.reward,
    targetTags: currentEntry.tags,
    features: sequenceFeatures,
    // Label for supervised learning
    label: currentEntry.reward > 0 ? 'positive' : 'negative'
  };

  fs.appendFileSync(SEQUENCE_FILE, JSON.stringify(sequenceEntry) + '\n');
  return sequenceEntry;
}

/**
 * Save feedback entry to JSONL file
 */
function saveFeedback(entry) {
  ensureDirectories();

  // Append to JSONL (one JSON object per line)
  fs.appendFileSync(FEEDBACK_FILE, JSON.stringify(entry) + '\n');

  // Build and save sequence for LSTM/Transformer
  const recentFeedback = loadRecentFeedback();
  const sequenceFeatures = buildSequenceFeatures(recentFeedback, entry);
  saveSequence(sequenceFeatures, entry);

  // Update summary
  const summary = loadSummary();
  summary.totalFeedback++;
  summary.sequenceCount++;
  summary.lastUpdated = new Date().toISOString();

  // Update streak tracking
  if (entry.feedback === 'up') {
    summary.thumbsUp++;
    if (summary.currentStreak.type === 'positive') {
      summary.currentStreak.count++;
    } else {
      summary.currentStreak = { type: 'positive', count: 1 };
    }
    summary.longestPositiveStreak = Math.max(
      summary.longestPositiveStreak,
      summary.currentStreak.count
    );

    // Track positive patterns
    if (entry.tags) {
      entry.tags.forEach(tag => {
        summary.topPatterns.positive[tag] = (summary.topPatterns.positive[tag] || 0) + 1;
      });
    }
  } else {
    summary.thumbsDown++;
    if (summary.currentStreak.type === 'negative') {
      summary.currentStreak.count++;
    } else {
      summary.currentStreak = { type: 'negative', count: 1 };
    }
    summary.longestNegativeStreak = Math.max(
      summary.longestNegativeStreak,
      summary.currentStreak.count
    );

    // Track negative patterns
    if (entry.tags) {
      entry.tags.forEach(tag => {
        summary.topPatterns.negative[tag] = (summary.topPatterns.negative[tag] || 0) + 1;
      });
    }
  }

  // Update action->outcome tracking
  if (entry.tags) {
    entry.tags.forEach(tag => {
      if (!summary.actionOutcomes[tag]) {
        summary.actionOutcomes[tag] = { positive: 0, negative: 0, ratio: 0 };
      }
      if (entry.reward > 0) {
        summary.actionOutcomes[tag].positive++;
      } else {
        summary.actionOutcomes[tag].negative++;
      }
      const total = summary.actionOutcomes[tag].positive + summary.actionOutcomes[tag].negative;
      summary.actionOutcomes[tag].ratio = summary.actionOutcomes[tag].positive / total;
    });
  }

  fs.writeFileSync(SUMMARY_FILE, JSON.stringify(summary, null, 2));

  // Update diversity tracking (prevents representation collapse)
  updateDiversityTracking(entry);

  // Update file-based success patterns (distillation for future sessions)
  if (entry.feedback === 'up' && entry.richContext?.outcomeCategory?.includes('success')) {
    updateSuccessPatterns(entry);
  }

  return summary;
}

/**
 * Track diversity across domains (prevents RL plateau from NeurIPS 2025)
 */
function updateDiversityTracking(entry) {
  let diversity = { domains: {}, lastUpdated: null, diversityScore: 0 };

  if (fs.existsSync(DIVERSITY_FILE)) {
    diversity = JSON.parse(fs.readFileSync(DIVERSITY_FILE, 'utf8'));
  }

  const domain = entry.richContext?.domain || 'general';

  if (!diversity.domains[domain]) {
    diversity.domains[domain] = { count: 0, positive: 0, negative: 0, lastSeen: null };
  }

  diversity.domains[domain].count++;
  diversity.domains[domain].lastSeen = new Date().toISOString();
  if (entry.reward > 0) {
    diversity.domains[domain].positive++;
  } else {
    diversity.domains[domain].negative++;
  }

  // Calculate diversity score (higher = more balanced across domains)
  const totalFeedback = Object.values(diversity.domains).reduce((sum, d) => sum + d.count, 0);
  const domainCount = Object.keys(diversity.domains).length;
  const idealPerDomain = totalFeedback / DOMAIN_CATEGORIES.length;
  const variance = Object.values(diversity.domains).reduce((sum, d) => {
    return sum + Math.pow(d.count - idealPerDomain, 2);
  }, 0) / domainCount;

  diversity.diversityScore = Math.max(0, 100 - Math.sqrt(variance) * 10).toFixed(1);
  diversity.lastUpdated = new Date().toISOString();
  diversity.recommendation = diversity.diversityScore < 50
    ? `Low diversity (${diversity.diversityScore}%). Try feedback in: ${DOMAIN_CATEGORIES.filter(d => !diversity.domains[d]).join(', ')}`
    : `Good diversity (${diversity.diversityScore}%)`;

  fs.writeFileSync(DIVERSITY_FILE, JSON.stringify(diversity, null, 2));
}

/**
 * File-based distillation: Write success patterns to markdown (LlamaIndex "files are all you need" pattern)
 */
function updateSuccessPatterns(entry) {
  let patternsContent = '# Success Patterns (Auto-Distilled)\n\n';
  patternsContent += '> Auto-generated from positive feedback. Claude reads this at session start.\n\n';

  if (fs.existsSync(PATTERNS_FILE)) {
    patternsContent = fs.readFileSync(PATTERNS_FILE, 'utf8');
  }

  const timestamp = new Date().toISOString().split('T')[0];
  const domain = entry.richContext?.domain || 'general';
  const outcome = entry.richContext?.outcomeCategory || 'success';

  // Append new pattern
  const newPattern = `\n## ${domain} (${timestamp})\n` +
    `**Outcome:** ${outcome}\n` +
    `**Context:** ${entry.context}\n` +
    `**Tags:** ${entry.tags.join(', ')}\n` +
    `**Action:** ${entry.actionType}\n`;

  // Check if we already have this domain section, update it; otherwise append
  if (!patternsContent.includes(`## ${domain}`)) {
    patternsContent += newPattern;
  }

  // Keep file under 50KB (trim oldest entries if needed)
  if (patternsContent.length > 50000) {
    const sections = patternsContent.split('\n## ');
    patternsContent = sections[0] + '\n## ' + sections.slice(-20).join('\n## ');
  }

  fs.writeFileSync(PATTERNS_FILE, patternsContent);
}

/**
 * Generate feedback entry
 */
function createFeedbackEntry(args) {
  const feedback = args.feedback?.toLowerCase();

  if (!feedback || !['up', 'down', 'thumbsup', 'thumbsdown', '👍', '👎', '+', '-'].includes(feedback)) {
    throw new Error('Invalid feedback. Use: up, down, thumbsup, thumbsdown, 👍, 👎, +, or -');
  }

  // Normalize feedback
  const normalizedFeedback = ['up', 'thumbsup', '👍', '+'].includes(feedback) ? 'up' : 'down';

  // Parse tags
  const tags = args.tags ? args.tags.split(',').map(t => t.trim()) : [];

  // Parse action type (what Claude was doing)
  const actionType = args.action || inferActionType(args.context, tags);

  // Rich context for representation depth (NeurIPS 2025 insight)
  const richContext = {
    description: args.context || '',
    domain: args.domain || inferDomain(args.context, tags),
    filePaths: args.files ? args.files.split(',').map(f => f.trim()) : [],
    errorType: args.error || null,
    outcomeCategory: args.outcome || inferOutcome(normalizedFeedback, args.context),
  };

  // Decision trace for interpretability (Goodfire 2026: process reward model data)
  // Captures WHY the agent behaved the way it did, not just WHAT happened
  const decisionTrace = {
    observations: args.observations
      ? args.observations.split('|').map(o => o.trim())
      : inferObservations(args.context),
    reasoning: args.reasoning
      ? args.reasoning.split('|').map(r => r.trim())
      : [],
    alternatives: args.alternatives
      ? args.alternatives.split('|').map(a => a.trim())
      : [],
    chosenPath: args.chosen || '',
    confidence: args.confidence ? parseFloat(args.confidence) : null,
  };

  return {
    id: `fb_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    timestamp: new Date().toISOString(),
    feedback: normalizedFeedback,
    reward: normalizedFeedback === 'up' ? 1 : -1,
    context: args.context || '',
    richContext,
    decisionTrace,
    tags,
    actionType,
    sessionId: process.env.CLAUDE_SESSION_ID || `session_${new Date().toISOString().split('T')[0]}`,
    metadata: {
      cwd: process.cwd(),
      branch: getBranch(),
    }
  };
}

/**
 * Infer observations from context (what the agent saw before acting)
 */
function inferObservations(context) {
  if (!context) return [];
  const observations = [];
  const cl = context.toLowerCase();
  if (cl.includes('read') || cl.includes('checked')) observations.push('read-existing-code');
  if (cl.includes('test')) observations.push('verified-with-tests');
  if (cl.includes('search') || cl.includes('grep') || cl.includes('found')) observations.push('searched-codebase');
  if (cl.includes('pr') || cl.includes('review')) observations.push('reviewed-pr-context');
  if (cl.includes('existing') || cl.includes('reuse') || cl.includes('util')) observations.push('found-existing-utility');
  if (cl.includes('doc') || cl.includes('api')) observations.push('consulted-documentation');
  return observations;
}

/**
 * Infer domain category from context (for diversity tracking)
 */
function inferDomain(context, tags) {
  const contextLower = (context || '').toLowerCase();
  const tagSet = new Set(tags.map(t => t.toLowerCase()));

  if (tagSet.has('test') || contextLower.includes('test')) return 'testing';
  if (tagSet.has('security') || contextLower.includes('secret') || contextLower.includes('vulnerability')) return 'security';
  if (tagSet.has('perf') || contextLower.includes('performance') || contextLower.includes('slow')) return 'performance';
  if (tagSet.has('ui') || contextLower.includes('component') || contextLower.includes('screen')) return 'ui-components';
  if (tagSet.has('api') || contextLower.includes('xapi') || contextLower.includes('endpoint')) return 'api-integration';
  if (tagSet.has('git') || contextLower.includes('commit') || contextLower.includes('pr')) return 'git-workflow';
  if (tagSet.has('doc') || contextLower.includes('readme') || contextLower.includes('documentation')) return 'documentation';
  if (tagSet.has('debug') || contextLower.includes('error') || contextLower.includes('fix')) return 'debugging';
  if (tagSet.has('arch') || contextLower.includes('structure') || contextLower.includes('design')) return 'architecture';
  if (tagSet.has('data') || contextLower.includes('model') || contextLower.includes('schema')) return 'data-modeling';

  return 'general';
}

/**
 * Infer outcome category (beyond binary thumbs)
 */
function inferOutcome(feedback, context) {
  const contextLower = (context || '').toLowerCase();

  if (feedback === 'up') {
    if (contextLower.includes('first try') || contextLower.includes('immediately')) return 'quick-success';
    if (contextLower.includes('thorough') || contextLower.includes('comprehensive')) return 'deep-success';
    if (contextLower.includes('creative') || contextLower.includes('novel')) return 'creative-success';
    return 'standard-success';
  } else {
    if (contextLower.includes('wrong') || contextLower.includes('incorrect')) return 'factual-error';
    if (contextLower.includes('shallow') || contextLower.includes('surface')) return 'insufficient-depth';
    if (contextLower.includes('slow') || contextLower.includes('took too long')) return 'efficiency-issue';
    if (contextLower.includes('assumption') || contextLower.includes('guessed')) return 'false-assumption';
    return 'standard-failure';
  }
}

/**
 * Infer action type from context/tags
 */
function inferActionType(context, tags) {
  const contextLower = (context || '').toLowerCase();
  const tagSet = new Set(tags.map(t => t.toLowerCase()));

  if (tagSet.has('code-reading') || contextLower.includes('read')) return 'code-reading';
  if (tagSet.has('implementation') || contextLower.includes('implement')) return 'implementation';
  if (tagSet.has('shallow-answer') || contextLower.includes('surface')) return 'shallow-answer';
  if (tagSet.has('docs') || contextLower.includes('doc')) return 'documentation';
  if (tagSet.has('search') || contextLower.includes('search')) return 'search';
  if (tagSet.has('commit') || contextLower.includes('commit')) return 'git-operation';
  if (tagSet.has('test') || contextLower.includes('test')) return 'testing';

  return 'general';
}

/**
 * Get current git branch
 */
function getBranch() {
  try {
    const { execSync } = require('child_process');
    return execSync('git branch --show-current', { encoding: 'utf8' }).trim();
  } catch {
    return null;
  }
}

/**
 * Export training data for LSTM/Transformer
 */
function exportTrainingData() {
  ensureDirectories();

  if (!fs.existsSync(SEQUENCE_FILE)) {
    console.log('\n❌ No sequence data found. Capture more feedback first.\n');
    return;
  }

  const sequences = fs.readFileSync(SEQUENCE_FILE, 'utf8')
    .trim()
    .split('\n')
    .filter(Boolean)
    .map(line => JSON.parse(line));

  if (sequences.length < 10) {
    console.log(`\n⚠️  Only ${sequences.length} sequences. Need at least 10 for training.\n`);
  }

  // Export formats for different frameworks
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');

  // 1. PyTorch/TensorFlow format (JSON with arrays)
  const pytorchData = {
    metadata: {
      exportDate: new Date().toISOString(),
      sequenceCount: sequences.length,
      windowSize: SEQUENCE_WINDOW,
      features: ['rewardSequence', 'recentTrend', 'timeGaps']
    },
    sequences: sequences.map(s => ({
      X: {
        rewardSequence: s.features.rewardSequence,
        trend: s.features.recentTrend,
        timeGaps: s.features.timeGaps,
      },
      y: s.targetReward,
      label: s.label
    }))
  };

  const pytorchFile = path.join(TRAINING_EXPORT_DIR, `training-pytorch-${timestamp}.json`);
  fs.writeFileSync(pytorchFile, JSON.stringify(pytorchData, null, 2));

  // 2. CSV format for quick analysis
  const csvHeaders = 'sequence_id,timestamp,target_reward,label,recent_trend,seq_length\n';
  const csvRows = sequences.map(s =>
    `${s.id},${s.timestamp},${s.targetReward},${s.label},${s.features.recentTrend},${s.features.rewardSequence.length}`
  ).join('\n');

  const csvFile = path.join(TRAINING_EXPORT_DIR, `training-summary-${timestamp}.csv`);
  fs.writeFileSync(csvFile, csvHeaders + csvRows);

  // 3. Action patterns analysis
  const actionAnalysis = analyzeActionPatterns(sequences);
  const analysisFile = path.join(TRAINING_EXPORT_DIR, `action-analysis-${timestamp}.json`);
  fs.writeFileSync(analysisFile, JSON.stringify(actionAnalysis, null, 2));

  console.log('\n📊 Training Data Exported');
  console.log('═══════════════════════════════════════');
  console.log(`   Sequences: ${sequences.length}`);
  console.log(`   PyTorch:   ${pytorchFile}`);
  console.log(`   CSV:       ${csvFile}`);
  console.log(`   Analysis:  ${analysisFile}`);
  console.log('\n💡 Next Steps:');
  console.log('   1. Use PyTorch JSON for LSTM/Transformer training');
  console.log('   2. Review action-analysis for pattern insights');
  console.log('   3. Aim for 50+ sequences before training');
  console.log('═══════════════════════════════════════\n');
}

/**
 * Analyze action patterns across all sequences
 */
function analyzeActionPatterns(sequences) {
  const allPatterns = {};

  sequences.forEach(s => {
    const patterns = s.features.actionPatterns || {};
    Object.entries(patterns).forEach(([tag, counts]) => {
      if (!allPatterns[tag]) {
        allPatterns[tag] = { positive: 0, negative: 0, total: 0, successRate: 0 };
      }
      allPatterns[tag].positive += counts.positive;
      allPatterns[tag].negative += counts.negative;
      allPatterns[tag].total += counts.positive + counts.negative;
    });
  });

  // Calculate success rates
  Object.keys(allPatterns).forEach(tag => {
    const p = allPatterns[tag];
    p.successRate = p.total > 0 ? (p.positive / p.total * 100).toFixed(1) + '%' : 'N/A';
  });

  // Sort by total occurrences
  const sorted = Object.entries(allPatterns)
    .sort((a, b) => b[1].total - a[1].total)
    .reduce((acc, [k, v]) => ({ ...acc, [k]: v }), {});

  return {
    exportDate: new Date().toISOString(),
    totalSequences: sequences.length,
    actionPatterns: sorted,
    recommendations: generateRecommendations(sorted)
  };
}

/**
 * Generate recommendations based on action patterns
 */
function generateRecommendations(patterns) {
  const recs = [];

  Object.entries(patterns).forEach(([tag, data]) => {
    const rate = data.positive / (data.total || 1);

    if (rate < 0.5 && data.total >= 3) {
      recs.push({
        type: 'avoid',
        action: tag,
        reason: `Low success rate (${(rate * 100).toFixed(0)}%) - consider alternative approaches`,
        successRate: rate
      });
    } else if (rate > 0.8 && data.total >= 3) {
      recs.push({
        type: 'continue',
        action: tag,
        reason: `High success rate (${(rate * 100).toFixed(0)}%) - keep doing this`,
        successRate: rate
      });
    }
  });

  return recs.sort((a, b) => a.successRate - b.successRate);
}

/**
 * Display summary stats
 */
function displayStats(summary) {
  const ratio = summary.thumbsUp / (summary.thumbsDown || 1);
  const emoji = ratio >= 2 ? '🟢' : ratio >= 1 ? '🟡' : '🔴';

  console.log('\n📊 Feedback Summary (RLHF Training Data)');
  console.log('═══════════════════════════════════════');
  console.log(`${emoji} Total: ${summary.totalFeedback} | 👍 ${summary.thumbsUp} | 👎 ${summary.thumbsDown}`);
  console.log(`   Ratio: ${ratio.toFixed(2)} (${ratio >= 1 ? 'positive' : 'needs improvement'})`);
  console.log(`   Sequences: ${summary.sequenceCount || 0} (for LSTM/Transformer)`);

  // Streak info
  if (summary.currentStreak?.count > 1) {
    const streakEmoji = summary.currentStreak.type === 'positive' ? '🔥' : '❄️';
    console.log(`   ${streakEmoji} Current streak: ${summary.currentStreak.count} ${summary.currentStreak.type}`);
  }

  if (summary.longestPositiveStreak > 2) {
    console.log(`   🏆 Best streak: ${summary.longestPositiveStreak} positive`);
  }

  if (Object.keys(summary.topPatterns?.positive || {}).length > 0) {
    console.log('\n✅ Top Positive Patterns:');
    Object.entries(summary.topPatterns.positive)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .forEach(([tag, count]) => console.log(`   ${tag}: ${count}`));
  }

  if (Object.keys(summary.topPatterns?.negative || {}).length > 0) {
    console.log('\n❌ Top Negative Patterns:');
    Object.entries(summary.topPatterns.negative)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .forEach(([tag, count]) => console.log(`   ${tag}: ${count}`));
  }

  // Action success rates
  if (Object.keys(summary.actionOutcomes || {}).length > 0) {
    console.log('\n📈 Action Success Rates:');
    Object.entries(summary.actionOutcomes)
      .filter(([_, data]) => (data.positive + data.negative) >= 2)
      .sort((a, b) => b[1].ratio - a[1].ratio)
      .slice(0, 5)
      .forEach(([action, data]) => {
        const pct = (data.ratio * 100).toFixed(0);
        const bar = '█'.repeat(Math.round(data.ratio * 10)) + '░'.repeat(10 - Math.round(data.ratio * 10));
        console.log(`   ${action}: ${bar} ${pct}%`);
      });
  }

  // Diversity tracking (NeurIPS 2025 insight)
  if (fs.existsSync(DIVERSITY_FILE)) {
    const diversity = JSON.parse(fs.readFileSync(DIVERSITY_FILE, 'utf8'));
    console.log('\n🎯 Diversity Score (prevents RL plateau):');
    console.log(`   Score: ${diversity.diversityScore}%`);
    console.log(`   Domains covered: ${Object.keys(diversity.domains).length}/${DOMAIN_CATEGORIES.length}`);
    if (diversity.recommendation) {
      console.log(`   ${diversity.recommendation}`);
    }
  }

  // Success patterns file (file-based distillation)
  if (fs.existsSync(PATTERNS_FILE)) {
    const patterns = fs.readFileSync(PATTERNS_FILE, 'utf8');
    const patternCount = (patterns.match(/^## /gm) || []).length;
    console.log(`\n📚 Distilled Patterns: ${patternCount} success patterns in success-patterns.md`);
  }

  console.log('\n═══════════════════════════════════════');
  console.log('💡 Commands:');
  console.log('   --export-training   Export data for LSTM/Transformer');
  console.log('   --diversity         Show diversity breakdown');
  console.log('   --patterns          View distilled success patterns');
  console.log('═══════════════════════════════════════\n');
}

/**
 * Display diversity breakdown
 */
function displayDiversity() {
  if (!fs.existsSync(DIVERSITY_FILE)) {
    console.log('\n❌ No diversity data yet. Capture more feedback first.\n');
    return;
  }

  const diversity = JSON.parse(fs.readFileSync(DIVERSITY_FILE, 'utf8'));

  console.log('\n🎯 Domain Diversity Analysis (NeurIPS 2025)');
  console.log('═══════════════════════════════════════════');
  console.log(`   Overall Score: ${diversity.diversityScore}%`);
  console.log(`   Domains with feedback: ${Object.keys(diversity.domains).length}/${DOMAIN_CATEGORIES.length}`);
  console.log('\n   Per-Domain Breakdown:');

  DOMAIN_CATEGORIES.forEach(domain => {
    const data = diversity.domains[domain];
    if (data) {
      const rate = data.count > 0 ? ((data.positive / data.count) * 100).toFixed(0) : 0;
      const bar = '█'.repeat(Math.min(10, data.count)) + '░'.repeat(Math.max(0, 10 - data.count));
      console.log(`   ${domain.padEnd(15)} ${bar} ${data.count} (${rate}% positive)`);
    } else {
      console.log(`   ${domain.padEnd(15)} ░░░░░░░░░░ 0 (no feedback)`);
    }
  });

  console.log('\n   💡 For balanced learning, provide feedback across all domains.');
  console.log('═══════════════════════════════════════════\n');
}

/**
 * Display distilled success patterns
 */
function displayPatterns() {
  if (!fs.existsSync(PATTERNS_FILE)) {
    console.log('\n❌ No success patterns yet. Get some thumbs up feedback first!\n');
    return;
  }

  const patterns = fs.readFileSync(PATTERNS_FILE, 'utf8');
  console.log('\n📚 Distilled Success Patterns (File-Based Memory)');
  console.log('═══════════════════════════════════════════════════');
  console.log(patterns);
  console.log('═══════════════════════════════════════════════════\n');
}

/**
 * Main execution
 */
function main() {
  const args = parseArgs();

  // Export training data
  if (args['export-training'] || args.export) {
    exportTrainingData();
    return;
  }

  // Show diversity breakdown
  if (args.diversity) {
    displayDiversity();
    return;
  }

  // Show distilled patterns
  if (args.patterns) {
    displayPatterns();
    return;
  }

  // Show stats only
  if (args.stats || args.summary) {
    const summary = loadSummary();
    displayStats(summary);
    return;
  }

  // Show help
  if (args.help || Object.keys(args).length === 0) {
    console.log(`
Thumbs Up/Down Feedback Capture (RLHF + LSTM/Transformer Ready)
═══════════════════════════════════════════════════════════════

Usage:
  node capture-feedback.js --feedback=up --context="Description"
  node capture-feedback.js --feedback=down --context="What went wrong" --tags="tag1,tag2"
  node capture-feedback.js --stats
  node capture-feedback.js --export-training

Options:
  --feedback       Required. up/down/thumbsup/thumbsdown/👍/👎/+/-
  --context        Description of what happened (for learning)
  --tags           Comma-separated tags for pattern tracking
  --action         Action type (auto-inferred if not provided)
  --observations   Pipe-separated observations (what agent saw before acting)
  --reasoning      Pipe-separated reasoning steps (WHY agent made choices)
  --alternatives   Pipe-separated alternatives considered but rejected
  --chosen         The path/approach that was chosen
  --confidence     Agent confidence level (0.0-1.0)
  --stats          Show feedback summary
  --export-training  Export data for LSTM/Transformer training

Examples:
  👍 With decision trace (Goodfire interpretability):
    node capture-feedback.js --feedback=up \\
      --context="Used formatPrice() instead of hand-coding currency" \\
      --observations="found existing formatCurrency util|checked how ProductGrid uses it" \\
      --reasoning="reuse shared utility over duplicating logic|i18n compliance" \\
      --alternatives="toFixed(2) with $ prefix|Intl.NumberFormat inline" \\
      --chosen="formatPrice from shared utils" \\
      --confidence=0.95 \\
      --tags="code-reuse,i18n"

  👎 With decision trace:
    node capture-feedback.js --feedback=down \\
      --context="Assumed test framework without checking" \\
      --reasoning="skipped reading package.json|assumed jest" \\
      --tags="false-assumption"

Training Pipeline:
  1. Capture feedback with context, decision trace, and tags
  2. System automatically builds sequences for time-series learning
  3. Decision traces enable process reward model training (not just outcome)
  4. Export with --export-training when you have 50+ entries

Storage (LOCAL ONLY - excluded from git):
  Feedback log:     .claude/memory/feedback/feedback-log.jsonl
  Sequences:        .claude/memory/feedback/feedback-sequences.jsonl
  Summary:          .claude/memory/feedback/feedback-summary.json
  Training exports: .claude/memory/feedback/training-data/
`);
    return;
  }

  try {
    const entry = createFeedbackEntry(args);
    const summary = saveFeedback(entry);

    const emoji = entry.feedback === 'up' ? '👍' : '👎';
    console.log(`\n${emoji} Feedback captured!`);
    console.log(`   ID: ${entry.id}`);
    console.log(`   Reward: ${entry.reward > 0 ? '+1' : '-1'}`);
    console.log(`   Action: ${entry.actionType}`);
    if (entry.context) console.log(`   Context: ${entry.context}`);
    if (entry.tags.length) console.log(`   Tags: ${entry.tags.join(', ')}`);
    console.log(`   Sequence #${summary.sequenceCount} saved for LSTM/Transformer`);

    displayStats(summary);

  } catch (error) {
    console.error(`\n❌ Error: ${error.message}\n`);
    process.exit(1);
  }
}

main();
