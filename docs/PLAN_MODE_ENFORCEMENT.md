# 🧠 Plan Mode Enforcement (Opus 4.5)

**Last Updated**: December 1, 2025
**Source of Truth**: [ClaudeLog - Plan Mode](https://www.claudelog.com/mechanics/plan-mode/)

Plan Mode is now **mandatory** for every substantive change. This document explains how to activate it, what artifacts it must produce, and how the new guardrail (`scripts/verify_plan_mode.py`) blocks commits that skip the workflow.

---

## Why Plan Mode?

Claude Code Plan Mode separates research from execution:

1. **Shift+Tab, Shift+Tab** → Claude enters Plan Mode.
2. Only read/research tools are available (Read, LS, Glob, Grep, Task, WebSearch, etc.).
3. Claude drafts a structured plan (Opus 4.5 writes `plan.md`).
4. You review and approve the plan before *any* file edits or shell commands run.
5. Upon approval, Claude exits Plan Mode and executes with Sonnet 4.5.

This prevents accidental edits, enforces consistent planning, and matches the safety guarantees described on ClaudeLog.

---

## Required Workflow

1. **Enter Plan Mode**
   Press `Shift+Tab` twice. Claude confirms Plan Mode is active.

2. **Capture Context in `plan.md`**
   Claude creates/updates a root-level `plan.md` containing:
   - `## Metadata` (task, owner, status, approval timestamp, validity window)
   - `## Clarifying Questions` (table or bullets with resolutions)
   - `## Execution Plan` (ordered steps)
   - `## Approval` (checked items showing CTO approval)
   - `## Exit Checklist` (checkboxes for validation steps)

3. **Review & Approve**
   Keep `Status: APPROVED` only when the plan is ready. If the plan needs revisions, set `Status: DRAFT` so the guard fails (prevents execution).

4. **Exit Plan Mode and Execute**
   Press `Shift+Tab` again. Claude double-confirms before editing. Follow the approved plan verbatim.

5. **Update Exit Checklist**
   When tasks finish, check off the exit items and log the session in `claude-progress.txt`.

---

## Guardrail: `scripts/verify_plan_mode.py`

The pre-commit hook now runs:

```bash
python3 scripts/verify_plan_mode.py --plan-file plan.md --max-age-minutes 180
```

It blocks commits if:

- `plan.md` is missing or older than 180 minutes (mtime check).
- Any required section is absent.
- `Status:` is not `APPROVED`.
- `Approved at:` is missing.
- Execution Plan lacks numbered steps.
- Approval section does not contain a checked “Approved” item.
- Exit Checklist has no checkboxes.

To refresh the plan:

1. Enter Plan Mode.
2. Update clarifications/steps.
3. Re-approve and exit Plan Mode.
4. Re-run `python3 scripts/verify_plan_mode.py` (or try to commit) to confirm compliance.

---

## Plan Template (Managed Only in Plan Mode)

```
# Plan Mode Session: <Title>
> Managed in Claude Code Plan Mode. Do not edit outside Plan Mode.

## Metadata
- Task: <description>
- Owner: <name/agent>
- Status: APPROVED
- Approved at: YYYY-MM-DDTHH:MM:SSZ
- Valid for (minutes): 180

## Clarifying Questions
| # | Question | Resolution | Status |
|---|----------|------------|--------|
| 1 | ... | ... | Resolved |

## Execution Plan
1. ...
2. ...

## Approval
- [x] Requirements captured
- [x] Clarifications resolved
- [x] CTO Approval — <name> @ timestamp

## Exit Checklist
- [ ] Tests/lints executed
- [ ] Docs updated
- [ ] Logged in claude-progress.txt
```

---

## FAQs

**What if I just need to tweak a typo?**
Still go through Plan Mode. Small edits can reuse the existing plan by updating the metadata/steps and re-approving—Plan Mode opens instantly with `Shift+Tab`.

**Can I bypass the guard?**
No. The guard is part of `.claude/hooks/pre-commit`. Skipping it violates the CEO’s “No manual anything” directive. If an emergency fix is required, regenerate a minimal plan first (takes under a minute).

**Where should `plan.md` live?**
Root directory. The hygiene hook now exempts `plan.md` so it stays beside README and CLAUDE.md, matching ClaudeLog’s default behavior.

---

## Related References

- [docs/PLAN.md](docs/PLAN.md) – Master roadmap now references Plan Mode enforcement.
- `.claude/CLAUDE.md` – Updated Chain of Command + automation rules include Plan Mode mandates.
- `.claude/hooks/pre-commit` – Runs the guard script and protects `plan.md`.
- `scripts/verify_plan_mode.py` – Source of the enforcement logic.

**Bottom line**: No plan, no execution. Activate Plan Mode, capture the plan, approve it, then ship.
