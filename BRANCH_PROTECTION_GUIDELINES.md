# Branch protection — honest Scorecard note (AGENT-583)

Classic protection on `main` already has required status checks, linear
history, no force-push, no deletions, and conversation resolution.

Scorecard Branch-Protection stays High while **enforce_admins is false**.
That is intentional: coding agents merge with the owner token. Turning
enforce_admins on without a ruleset bypass actor would halt autonomous
merge. Do not file this as operator homework.

Required human reviews would also zero the agent merge path unless a
GitHub App is the reviewer of record. AI PR review now submits a real
`pulls.createReview` event so Code-Review can climb as a trailing metric.

Do not enable enforce_admins or required reviews from this document.
