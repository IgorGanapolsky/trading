# Emergency Close Trigger - 2026-01-26T16:35:00Z
#
# ROOT CAUSE: Incomplete iron condor blocking ALL new trades for 3+ days
#
# POSITIONS TO CLOSE:
# - SPY260227C00730000: Long call @ $730 (P/L: +$15)
# - SPY260227P00650000: Long put @ $650 (P/L: -$53)
# - SPY260227P00655000: Short put @ $655 (P/L: +$59)
# - TOTAL P/L: +$21 (will be locked in on close)
#
# This closes the incomplete iron condor and allows trading to resume.
# Phil Town Rule #1: Don't lose money - these positions are profitable.
TRIGGER_1706284500
