# Security Policy

## Report a vulnerability privately

Use [GitHub private vulnerability reporting](https://github.com/IgorGanapolsky/trading/security/advisories/new)
for security issues. Do not open a public GitHub Issue for an unpatched
vulnerability, leaked credentials, or exploit details.

Include the affected path and commit, reproducible steps, expected impact, and
the least-sensitive evidence needed to reproduce. Do not paste live API keys,
broker tokens, or account numbers.

## Scope

This repository is a paper-first SPY options validation platform.

In scope:

- Credential handling (`get_alpaca_credentials()`, env/Keychain adapters)
- Broker order/risk gates and kill-switch files
- GitHub Actions secrets and workflow permissions
- Dependency and CodeQL findings on `main`

Out of scope:

- Paper-account P/L, strategy expectancy, or cohort sample-size debates
- Asking to remove `data/TRADING_HALTED` or to submit live capital

`main` is the only supported branch. Older revisions are fixed by upgrading.

## Research safety

Use the paper Alpaca account only. Do not submit live orders, persist access
after testing, or publish exploit details before a fix is available.
