# EMERGENCY: Close Losing Put Positions

**Triggered:** 2026-01-13T16:29:00Z
**Action:** CLOSE SHORT PUT POSITIONS IMMEDIATELY
**Priority:** CRITICAL - Rule #1 Protection

## CEO Directive

"We are not allowed to lose money!!!!!"

## Current Risk

- Position: SOFI260206P00024000 (-2 contracts)
- Unrealized P/L: -$7.00
- Assignment Risk: $4,800
- Buying Power: $68.88 (CANNOT cover assignment!)

## Required Action

1. Run emergency-protection workflow to close puts
2. Or run manage-positions workflow
3. Or manually trigger close-put-position workflow

## Workflows Available on Branch

- close-put-position.yml (on claude/research-ml-agent-prediction-T2an1)
- emergency-protection.yml (on main)
- manage-positions.yml (in daily-trading pipeline)
