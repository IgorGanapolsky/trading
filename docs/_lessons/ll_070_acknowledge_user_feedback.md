---
layout: post
title: "Lesson Learned: Always Acknowledge User Feedback (Thumbs Up/Down)"
date: 2026-01-10
---

# Lesson Learned: Always Acknowledge User Feedback (Thumbs Up/Down)

**Date**: December 24, 2025
**Severity**: HIGH
**Category**: User Experience, Reinforcement Learning

## What Happened
User gave "Thumbs down" feedback. Claude failed to:
1. Acknowledge the feedback
2. Ask what was wrong
3. Record it to the RL feedback system
4. Learn from the correction

## Root Cause
- The capture_feedback.sh hook runs silently in the background
- Claude was not aware it should proactively acknowledge and investigate negative feedback
- No visible confirmation that feedback was recorded

## Prevention
1. **When user says "thumbs up" or "thumbs down"**:
   - IMMEDIATELY acknowledge: "Feedback recorded: [positive/negative]"
   - For negative: ASK "What did I do wrong?"
   - Manually call the feedback recording if hook doesn't fire
   
2. **Check feedback directory exists and has recent entries**
3. **Report satisfaction rate periodically**

## Correct Behavior
```
User: Thumbs down
Claude: Feedback recorded (negative). What did I miss or do poorly? I want to learn from this.
```

## Impact
- User frustration when feedback is ignored
- Lost learning opportunity
- RL system doesn't improve without feedback data

## Related Files
- `.claude/hooks/capture_feedback.sh`
- `data/feedback/feedback_YYYY-MM-DD.jsonl`
- `data/feedback/stats.json`
