# Security Policy

## Report a vulnerability privately

Use [GitHub private vulnerability reporting](https://github.com/IgorGanapolsky/trading/security/advisories/new)
for security issues. Do not open a public GitHub Issue for an unpatched
vulnerability, leaked credentials, or exploit details.

Include the affected path and commit, reproducible steps, expected impact, and
the least-sensitive evidence needed to reproduce. Do not paste live API keys,
broker tokens, or account numbers.

## Security Response Process

When a security vulnerability is reported:

1. The security team will acknowledge receipt of the vulnerability within 48 hours
2. An initial assessment will be conducted to determine severity and impact
3. A fix will be developed and tested in a private branch
4. The fix will be deployed to affected systems
5. A coordinated disclosure will be made according to responsible disclosure practices

## Scope

This repository is a paper-first SPY options validation platform.

In scope:

- Credential handling (`get_alpaca_credentials()`, env/Keychain adapters)
- Broker order/risk gates and kill-switch files
- GitHub Actions secrets and workflow permissions
- Dependency and CodeQL findings on `main`
- Branch protection and access controls
- Third-party integrations and API connections

Out of scope:

- Paper-account P/L, strategy expectancy, or cohort sample-size debates
- Asking to remove `data/TRADING_HALTED` or to submit live capital

`main` is the only supported branch. Older revisions are fixed by upgrading.

## Security Best Practices

### For Contributors

- Always use specific commit hashes for GitHub Actions instead of version tags
- Apply principle of least privilege when setting workflow permissions
- Never hardcode secrets or credentials in code
- Use environment variables or GitHub secrets for sensitive data
- Review all dependencies for known vulnerabilities
- Follow secure coding practices

### For Maintainers

- Implement and maintain branch protection rules
- Regularly review and rotate API keys and secrets
- Monitor security alerts and address them promptly
- Keep dependencies up-to-date
- Conduct periodic security reviews

## Supported Versions

Only the latest version of the main branch is supported for security updates. 
Older versions will not receive security patches.

## Research safety

Use the paper Alpaca account only. Do not submit live orders, persist access
after testing, or publish exploit details before a fix is available.

## Security Scanning

This repository uses automated security scanning tools:

- CodeQL for code analysis
- Dependabot for dependency scanning
- GitHub's secret scanning
- OpenSSF Scorecard for supply chain security
