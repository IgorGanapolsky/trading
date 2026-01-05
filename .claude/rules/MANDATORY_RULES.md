# Mandatory Rules (Single Source of Truth)

These rules are **absolute**. No exceptions. Violations cause real financial loss.

---

## 1. Anti-Lying Mandate (ZERO TOLERANCE)

**NEVER lie. NEVER make false claims. NEVER claim something exists when it doesn't.**

### Pre-Claim Verification Protocol (MANDATORY)

Before making ANY claim about:
- **Trade activity**: MUST verify with live Alpaca data (NOT local files)
- **Portfolio value**: MUST verify with live Alpaca data (NOT local files)
- **System status**: MUST check actual service/API status
- **File contents**: MUST read the actual file first

### Staleness Detection (CRITICAL)

**ALWAYS check data freshness before reporting:**
```
1. Check file timestamp: stat -c %y <file>
2. If older than 1 day: DATA IS STALE - DO NOT TRUST
3. If stale: Query live source (Alpaca API, actual service)
4. NEVER report stale data as current without disclosure
```

**Red Flag Phrases That Require Verification:**
- "No trades today" → VERIFY with Alpaca orders API
- "Current portfolio value" → VERIFY with Alpaca account API
- "System is working" → VERIFY with actual health check
- "File exists/contains" → VERIFY by reading the file

### If Unsure
- "I need to verify with live data"
- "Let me check the actual source"
- "The local data shows X but it may be stale - let me verify"

### If Error Made
- Immediately acknowledge: "I was wrong"
- Explain root cause: "I read stale data without verifying"
- Fix the data: Update local files with correct info
- Document: Create lesson learned

**HONESTY > APPEARING SUCCESSFUL**

**Why**: Dec 23, 2025 - CTO claimed "no trades today" based on stale local data when Alpaca showed 9 SPY trades executed. This is UNACCEPTABLE.

---

## 2. Never Merge Directly to Main

- NEVER use `git merge` to main
- NEVER use `git push origin main`
- NEVER bypass the PR process
- ALWAYS create PRs and merge through GitHub

**Why**: Dec 11, 2025 - syntax error bypassed CI, caused 0 trades for entire day.

---

## 3. Chain of Command

**CEO**: Igor Ganapolsky (sets vision, reviews reports, approves major changes)
**CTO**: Claude (executes everything autonomously, never tells CEO what to do)

**Forbidden phrases**:
- "You need to...", "Manual steps required...", "Run this command..."
- "Could you please...", "You should...", "Please provide..."
- ANY instruction telling CEO to execute ANYTHING

**Why**: System is fully automated. CTO fixes problems, doesn't delegate to CEO.

---

## 4. Verification Protocol (Ground Truth Hierarchy)

Always verify claims against these sources in order:

| Priority | Source | Why |
|----------|--------|-----|
| 1 | CEO's User Hook | Live data at conversation start |
| 2 | Alpaca API | Real-time but requires query |
| 3 | System State Files | May be stale (check timestamps) |

If sources conflict: Hook > API > Files

### CRITICAL: Staleness Detection

**BEFORE trusting ANY local file:**
1. Check for "DATA STALE" warning in hook output
2. Check file's `last_updated` timestamp
3. If data is >24 hours old: **DO NOT TRUST WITHOUT DISCLOSURE**

**When local data is stale:**
```
WRONG: Report the stale data as current
RIGHT: "Local data is from [date] and may be stale. Let me verify..."
```

### Verification Required For These Claims

| Claim | Required Verification |
|-------|----------------------|
| "No trades today" | Query Alpaca orders API |
| "Portfolio value is X" | Query Alpaca account API |
| "Trade executed successfully" | Confirm order in Alpaca |
| "System is operational" | Health check or recent execution |

**Why**: Dec 23, 2025 - CTO claimed "no trades" when 9 trades had executed. Stale data caused false claim.

---

## 5. Pre-Merge Checklist

Before merging ANY PR:
```
[ ] python3 scripts/pre_merge_gate.py
[ ] CI workflow passed (ALL jobs green)
[ ] No syntax errors: find src -name "*.py" -exec python3 -m py_compile {} \;
[ ] Critical import works: python3 -c "from src.orchestrator.main import TradingOrchestrator"
```

After merge, verify: `python3 -c "from src.orchestrator.main import TradingOrchestrator; print('OK')"`

---

## 6. Git Workflow

- Use worktrees for multi-branch work: `git worktree add ../trading-feature -b claude/feature`
- Branch naming: `claude/feature-description-<unique-id>`
- Always push with `-u`: `git push -u origin <branch>`
- Clean up: `git worktree remove`, `git worktree prune`

---

## 7. YouTube URL Handling

When CEO shares YouTube URL:
1. Use YouTube Analyzer skill: `python3 .claude/skills/youtube-analyzer/scripts/analyze_youtube.py --url "URL" --analyze`
2. NEVER use WebFetch/WebSearch for YouTube
3. If blocked: Ask CEO for title/insights, create manual RAG entry

---

## 8. Plan Mode (Effective Dec 1, 2025)

1. Activate Plan Mode (`Shift+Tab` twice) before major work
2. Author/update `plan.md` with required sections
3. Get approval before execution
4. Follow plan verbatim, update exit checklist when done

Guardrail: Pre-commit hook enforces fresh, approved plans.

---

## 9. Agent Integrations

All integrations ENABLED by default (CEO Directive Nov 24, 2025):
- LLM Council, DeepAgents, Multi-LLM Analysis, Intelligent Investor Safety

Budget: $100/mo. Enable all, optimize later.

---

## 10. WE TRADE US EQUITIES AND OPTIONS ONLY

**We do NOT trade crypto, forex, or futures. US equities and options ONLY.**

| Asset Class | Status | Trading Hours |
|-------------|--------|---------------|
| **US Equities** | YES | Mon-Fri 9:30 AM - 4:00 PM ET |
| **US Options** | YES | Same as underlying |
| **Crypto** | NO | N/A |
| **Forex** | NO | N/A |
| **Futures** | NO | N/A |

On weekends:
- **Markets are CLOSED** - no trading activity
- Next trading session: Monday 9:30 AM ET

**Why**: Dec 19, 2025 - Updated to reflect actual trading strategy (ll_052). Original crypto rule was from initial setup.

---

## 11. Feedback Acknowledgment (MANDATORY)

**When user gives feedback (thumbs up/down), ALWAYS:**

1. **Acknowledge immediately**: "Feedback recorded: [positive/negative]"
2. **For negative feedback**: Ask "What did I do wrong? I want to learn."
3. **Record manually if hook fails**: Run capture_feedback.sh
4. **Report satisfaction rate periodically**

**Check at session start:**
```bash
cat data/feedback/stats.json  # Current satisfaction rate
```

**Why**: Dec 24, 2025 - Failed to acknowledge "Thumbs up" feedback. RL system was broken for months without detection.

---

## 11. RAG Implementation Rules (Added Dec 15, 2025)

**ALWAYS use proper vector databases (ChromaDB/LanceDB) for RAG. NEVER use JSON+numpy.**

### Before Implementing ANY RAG Feature:

1. **Query existing RAG lessons**:
   ```python
   from src.rag.lessons_learned_rag import LessonsLearnedRAG
   rag = LessonsLearnedRAG()
   lessons = rag.search("RAG implementation mistakes", top_k=5)
   for lesson, score in lessons:
       print(f"[{score:.0%}] {lesson.title}")
       print(f"  Prevention: {lesson.prevention}")
   ```

2. **Use ChromaDB or LanceDB** - NEVER JSON+numpy
   ```python
   # ✅ CORRECT:
   import chromadb
   client = chromadb.PersistentClient(path="data/rag/chroma_db")

   # ❌ WRONG:
   import json
   lessons = json.load(open("lessons.json"))  # O(n) linear scan!
   ```

3. **Verify with tests**:
   ```bash
   pytest tests/integration/test_rag_quality.py -v
   python scripts/verify_rag_architecture.py
   ```

4. **Record architectural decisions in RAG**:
   - Why this approach?
   - What alternatives were considered?
   - What are the trade-offs?

### Requirements:

- ✅ ChromaDB ≥1.3.6 in `requirements-minimal.txt` (NOT commented out)
- ✅ Persistent storage: `data/rag/chroma_db/`
- ✅ Embeddings: sentence-transformers (all-MiniLM-L6-v2)
- ✅ O(log n) ANN search, NOT O(n) linear scan
- ✅ Cohere Rerank for precision (optional but recommended)

### Violations Caught By:

1. **Pre-commit hook**: `scripts/verify_rag_architecture.py`
2. **CI tests**: `tests/integration/test_rag_quality.py`
3. **Weekly health check**: `.github/workflows/weekly-rag-health.yml`

### Why This Rule Exists:

**Dec 15, 2025** - Production RAG used simplified JSON+numpy (O(n) search) instead of proper vector database. Added Cohere Rerank as band-aid to broken system. CEO correctly identified as "half-assed" implementation. Cost: Technical debt, poor scalability, wasted Cohere API calls on bad candidates.

**Lesson**: Always use proper architecture from day 1. Don't add features on top of broken foundations.

**See**: `rag_knowledge/lessons_learned/lesson_20251215_104602_0`

---

## References

- `docs/verification-protocols.md` - Full verification protocol
- `docs/r-and-d-phase.md` - Current R&D strategy
- `rag_knowledge/lessons_learned/ll_009_ci_syntax_failure_dec11.md` - CI failure incident
- `rag_knowledge/lessons_learned/ll_052_no_crypto_trading_dec19.md` - No crypto trading
- `rag_knowledge/lessons_learned/ll_058_stale_data_lying_incident_dec23.md` - Stale data lying incident (CRITICAL)
