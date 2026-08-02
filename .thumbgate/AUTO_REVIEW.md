# Auto-Review Policy (Managed Autonomy)

This policy defines safety boundaries for autonomous operations in the `trading` project.

## Writable roots

Repository writes are limited to source, tests, data, directives, scripts, documentation, and workflow/configuration files. Never mutate `.git/`, dependency caches, or system roots as an implementation shortcut.

## Credential protection

Never echo or persist credential values. Setup and validation code may resolve credentials at action time but must log presence or identifiers only.

## Canonical ledgers

Changes to `data/system_state.json` or `data/trades.json` require a recoverable backup and broker-backed evidence. Tests write to temporary directories.

## Circuit breaker

After three repeated safety rejections for the same action, stop and request explicit guidance.

## Deployment boundary

Force pushes and live trading are prohibited. Only paper validation is authorized.
