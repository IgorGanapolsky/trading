# Lesson Learned: Dead Code and Dormant Systems

**ID**: LL-010
**Date**: 2025-12-11
**Severity**: HIGH
**Category**: Code Quality, System Integration
**Impact**: 0% win rate due to dormant systems and dead code

## What Happened
The trading system had ~22% dead code (5,376 lines) including:
- **ML Pipeline**: trainer.py, inference.py, dqn_agent.py all broken (missing dependencies, NotImplementedError)
- **Unused Strategies**: credit_spreads, mean_reversion, wheel (0 production references)
- **Orphaned Agents**: crypto_learner, safety_orchestrator (never instantiated)
- **Dormant Features**: 6 major systems disabled by default (DeepAgents, Elite Orchestrator, etc.)

Additionally, critical functions like `manage_positions()` existed but were NEVER CALLED in execution flow.

## Root Cause
1. **No Dead Code Detection**: No automated check for unused code
2. **No Integration Testing**: Functions existed but weren't tested in actual flow
3. **Conservative Defaults**: Features defaulted to disabled without clear enablement path
4. **Architectural Drift**: New orchestrator was built but old strategies never wired in

## Impact
- 0% live win rate (positions never closed because `manage_positions()` never called)
- Mental toughness coaching sat unused despite 46 interventions
- RAG sentiment analysis orphaned in GrowthStrategy
- ML pipeline completely non-functional

## Fix Applied
1. Deleted 14 dead files (-5,376 lines)
2. Enabled 6 dormant systems by default
3. Wired mental toughness into Gate 0 of trading flow
4. Added `manage_positions()` call to crypto strategy
5. Re-enabled GrowthStrategy with RAG in orchestrator

## Prevention Rules
1. **Pre-commit Hook**: Dead code detector script
2. **CI Check**: Verify all registered functions are called
3. **RAG Lessons Learned**: Store this knowledge for future reference
4. **Integration Tests**: Test complete trading flow, not just units
5. **Feature Flag Audit**: Weekly review of disabled features

## Tags
`dead-code` `integration` `feature-flags` `ml-pipeline` `testing`
