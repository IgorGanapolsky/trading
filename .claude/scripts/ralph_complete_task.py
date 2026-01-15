#!/usr/bin/env python3
"""
Ralph Wiggum Task Completion Script
Marks a task as passes:true in prd.json and logs to progress.txt
Usage: python3 ralph_complete_task.py T001 "Summary of what was done"
"""

import json
import sys
from datetime import datetime
from pathlib import Path

CLAUDE_DIR = Path(__file__).parent.parent
PRD_FILE = CLAUDE_DIR / "prd.json"
PROGRESS_FILE = CLAUDE_DIR / "progress.txt"
STATE_FILE = CLAUDE_DIR / "ralph_state.json"


def complete_task(task_id: str, summary: str) -> bool:
    """Mark a task as complete in prd.json"""
    if not PRD_FILE.exists():
        print(f"ERROR: {PRD_FILE} not found")
        return False

    with open(PRD_FILE) as f:
        prd = json.load(f)

    # Find and update the task
    task_found = False
    for task in prd.get("tasks", []):
        if task.get("id") == task_id:
            task["passes"] = True
            task["completed_at"] = datetime.now().isoformat()
            task["completion_summary"] = summary
            task_found = True

            # Move to completed_tasks
            prd.setdefault("completed_tasks", []).append(task)
            prd["tasks"].remove(task)
            break

    if not task_found:
        print(f"ERROR: Task {task_id} not found in prd.json")
        return False

    # Update metadata
    prd["metadata"]["tasks_completed_this_session"] = prd["metadata"].get("tasks_completed_this_session", 0) + 1
    prd["metadata"]["last_task_completed"] = task_id
    prd["metadata"]["last_iteration_at"] = datetime.now().isoformat()
    prd["last_updated"] = datetime.now().strftime("%Y-%m-%d")

    with open(PRD_FILE, "w") as f:
        json.dump(prd, f, indent=2)

    # Log to progress.txt
    log_progress(task_id, summary)

    print(f"✅ Task {task_id} marked as complete")
    return True


def log_progress(task_id: str, summary: str) -> None:
    """Append completion note to progress.txt"""
    # Get current iteration from state
    iteration = 0
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            state = json.load(f)
            iteration = state.get("iteration", 0)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"""
[{timestamp}] Iteration #{iteration} - Task {task_id} COMPLETE
- {summary}

"""

    with open(PROGRESS_FILE, "a") as f:
        f.write(entry)


def get_next_task() -> dict | None:
    """Get the highest priority pending task"""
    if not PRD_FILE.exists():
        return None

    with open(PRD_FILE) as f:
        prd = json.load(f)

    pending = [t for t in prd.get("tasks", []) if not t.get("passes", False)]
    if not pending:
        return None

    return sorted(pending, key=lambda x: x.get("priority", 99))[0]


def show_status() -> None:
    """Show current PRD status"""
    if not PRD_FILE.exists():
        print("No prd.json found")
        return

    with open(PRD_FILE) as f:
        prd = json.load(f)

    pending = [t for t in prd.get("tasks", []) if not t.get("passes", False)]
    completed = prd.get("completed_tasks", [])

    print("═══════════════════════════════════════════════════════════")
    print(f"📋 PRD STATUS: {len(completed)} done, {len(pending)} remaining")
    print("═══════════════════════════════════════════════════════════")

    if pending:
        print("\n📝 PENDING:")
        for t in sorted(pending, key=lambda x: x.get("priority", 99)):
            print(f"  [{t['id']}] {t['title']} (priority: {t.get('priority', 'N/A')})")

    if completed:
        print("\n✅ COMPLETED:")
        for t in completed[-5:]:  # Last 5
            print(f"  [{t['id']}] {t['title']}")

    print("═══════════════════════════════════════════════════════════")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_status()
    elif sys.argv[1] == "next":
        task = get_next_task()
        if task:
            print(f"Next task: [{task['id']}] {task['title']}")
            print(f"Command: {task.get('command', 'N/A')}")
            print(f"Acceptance: {task.get('acceptance_criteria', 'N/A')}")
        else:
            print("All tasks complete!")
    elif sys.argv[1] == "status":
        show_status()
    elif len(sys.argv) >= 3:
        complete_task(sys.argv[1], " ".join(sys.argv[2:]))
    else:
        print("Usage:")
        print("  python3 ralph_complete_task.py status        # Show PRD status")
        print("  python3 ralph_complete_task.py next          # Get next task")
        print("  python3 ralph_complete_task.py T001 'summary' # Complete task")
