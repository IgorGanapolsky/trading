# Advise - Search Past Lessons Before Starting Work

Search the lessons learned knowledge base for relevant insights before starting a task.

## Usage

```
/advise <topic or keywords>
```

## How It Works

1. Searches `rag_knowledge/lessons_learned/` for matching patterns
2. Surfaces relevant failures, gotchas, and prevention measures
3. Helps avoid repeating past mistakes

## Procedure

### 1. Extract Search Terms
Parse the user's topic into searchable keywords. Consider:
- Error types (e.g., "import", "config", "API")
- System components (e.g., "trading", "backtest", "CI")
- Problem categories (e.g., "dead code", "filter", "verification")

### 2. Search Lessons Learned
```bash
# Search by filename patterns
ls -la $CLAUDE_PROJECT_DIR/rag_knowledge/lessons_learned/ | grep -i "<keyword>"

# Search by content
grep -l -i "<keyword>" $CLAUDE_PROJECT_DIR/rag_knowledge/lessons_learned/*.md
```

### 3. Read Top Matches
For each matching lesson, extract:
- **Title**: What happened
- **Root Cause**: Why it happened
- **Prevention Measures**: How to avoid it

### 4. Present Summary
Output format:
```
📚 RELEVANT LESSONS FOR: <topic>

1. LL_XXX: <title>
   ⚠️ Root Cause: <summary>
   ✅ Prevention: <key measure>

2. LL_YYY: <title>
   ...

💡 Recommendation: <synthesis of key takeaways>
```

## Example

```
/advise backtest
```

Output:
```
📚 RELEVANT LESSONS FOR: backtest

1. LL_021: Backtest Thresholds in R&D Phase
   ⚠️ Root Cause: Backtest thresholds too strict for R&D exploration
   ✅ Prevention: Use relaxed thresholds during experimentation

2. LL_041: Comprehensive Regression Tests
   ⚠️ Root Cause: Missing test coverage allowed regressions
   ✅ Prevention: Run full test suite before merge

💡 Recommendation: During R&D, prioritize learning over strict validation
```

## Auto-Trigger

This advice is automatically surfaced by the `advise_before_task.sh` hook when task-like prompts are detected. Keywords in your prompt are matched against the lessons database.
