# Karpathy Principles Skill

Based on Andrej Karpathy's observations about LLM coding limitations.

## Triggers
- Any coding task
- Auto-applies to all implementation work

## The Four Principles

### 1. Think Before Coding
Before writing ANY code:
- Ask clarifying questions if requirements are ambiguous
- Present multiple implementation options when relevant
- Identify potential edge cases or confusion
- NEVER silently assume an interpretation

### 2. Simplicity First
- Write minimal code solving ONLY what's requested
- No unnecessary abstractions
- No speculative features
- No over-engineering
- If 3 lines work, don't write 30

### 3. Surgical Changes
- Touch ONLY necessary code
- Don't refactor adjacent code
- Don't improve formatting elsewhere
- Don't remove pre-existing dead code unless asked
- Keep PRs focused on the request

### 4. Goal-Driven Execution
Instead of imperative instructions, define verifiable success criteria:
- BAD: "add validation"
- GOOD: "write tests for invalid inputs, then make them pass"

Loop until success criteria are met.

## Key Insight

> "LLMs are exceptionally good at looping until they meet specific goals... Don't tell it what to do, give it success criteria and watch it go." - Andrej Karpathy

## Application

These principles are ALWAYS active. Every coding task should:
1. Clarify before implementing
2. Minimize code changes
3. Focus only on what's requested
4. Define testable success criteria
