---
id: LL-298
date: 2026-01-23
severity: high
status: active
category: ci-integrity
---

# CI verification honesty

Before claiming CI passes, inspect the exact candidate SHA, every required PR check, and post-merge default-branch runs. Never promote local tests or a subset of green checks into an all-green claim. Preserve run URL and SHA.
