# HIGH: Provider proof and shell quoting for public trading claims

**Severity**: HIGH

## Incident

A request to describe the repository as real-money trading conflicted with the
latest broker evidence: the live account snapshot was zero and the live Alpaca
authentication attempt returned unauthorized. During the About update, a
double-quoted shell argument expanded the dollar-prefixed target and briefly
removed the numeric value before immediate correction.

## Root Cause

User intent, configured credentials, authenticated provider state, and public
copy were treated as adjacent facts even though each requires separate proof.
The shell also interpreted a dollar-prefixed monetary target inside double
quotes.

A later coordination command combined a trading branch rename with a Linear
bridge call but used the bridge repository as its working directory. That
renamed the active branch in the wrong repository. The rename was detected
from the immediate readback and reversed without changing files or commits.

## Prevention

Before publishing live-trading or profit language, verify the live broker mode,
funded equity, orders, fills, paired outcomes, and bank settlement as separate
surfaces. Keep public copy honest when any surface is unavailable. Pass literal
dollar text through single-quoted shell arguments and immediately read back
remote metadata after every mutation.

Never combine repository-local Git mutations with commands that must run from
another repository. Run them as separate calls with explicit working
directories, then verify the branch and upstream in both repositories.

## Tags

`provider-proof` `github-about` `shell-quoting` `live-trading` `evidence-boundary`
`wrong-repository` `branch-hygiene`
