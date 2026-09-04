# Security Policy

## Supported Versions

Only the latest `main` branch of this repository is actively maintained and receives security fixes.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| < main  | :x:                |

## Reporting a Vulnerability

We take the security of this trading system seriously. If you discover a potential security vulnerability, please report it responsibly:

1. **Private Vulnerability Reporting**: Use the [GitHub Private Vulnerability Reporting](https://github.com/IgorGanapolsky/trading/security/advisories/new) interface on this repository.
2. **Direct Contact**: You may also reach out directly to the maintainer via GitHub issues with the `security` label or via secure email.
3. **Response Time**: You will receive an initial response acknowledging receipt within 48 hours.
4. **Disclosure**: Please do not publicly disclose the vulnerability until a fix has been released and verified.

## Security Practices

- **Zero-Secret Commits**: All broker API keys, tokens, and credentials must remain in local secure keyrings (macOS Keychain, chmod 600 local vaults) and never be committed to Git.
- **Automated Scanning**: Automated scanning via CodeQL, GitGuardian, Socket Security, and OpenSSF Scorecard runs on all pull requests and commits to `main`.
- **Fail-Closed Risk Controls**: All broker interaction paths enforce deterministic risk checks and paper validation kill switches before order submission.
