# Security Policy

## Supported Versions

We provide security updates for the following versions of the trading system:

| Version | Supported          |
| ------- | ------------------ |
| main    | ✅ Latest version  |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please report it responsibly.

### How to Report

**Do not open public issues for security vulnerabilities.**

Instead, please report security issues by:

1. Using [GitHub private vulnerability reporting](https://github.com/IgorGanapolsky/trading/security/advisories/new)
2. Include detailed information about the vulnerability
3. Provide steps to reproduce if possible
4. Include any potential impact assessment

### What to Expect

- You will receive acknowledgment within 48 hours
- We will investigate and respond with our assessment within 1 week
- If the vulnerability is accepted, we will work on a fix
- If declined, we will provide an explanation

## Security Best Practices

### For Contributors

- Always use secure coding practices
- Never commit secrets, API keys, or credentials to the repository
- Use environment variables for sensitive data
- Follow the principle of least privilege
- Review all pull requests for potential security issues

### For Users

- Keep dependencies updated
- Use the latest version of the system
- Regularly audit your own implementations
- Monitor for suspicious activity in your usage

## Security Measures

### Automated Scanning

- CodeQL analysis runs on all pull requests
- Dependency scanning for known vulnerabilities
- Secret scanning to prevent credential leaks
- Regular security audits

### Access Control

- Minimal required permissions for all services
- Two-factor authentication required for all maintainers
- Regular access reviews
- Principle of least privilege enforced

## Token Permissions

GitHub Actions workflows use the principle of least privilege:

- `contents: read` - For reading repository contents
- `id-token: write` - For OIDC authentication to cloud providers
- `pull-requests: read` - Only when needed for PR comments

Avoid using `write-all` or overly broad permissions.

## Incident Response

In case of a security incident:

1. Containment: Isolate affected systems
2. Assessment: Evaluate scope and impact
3. Remediation: Apply fixes and patches
4. Communication: Notify stakeholders appropriately
5. Review: Analyze and improve processes

## Dependencies

We maintain security by:
- Regular dependency updates via Dependabot
- Vulnerability scanning
- Minimal dependency footprint
- Pinning to specific versions where appropriate

## Contact

For security-related inquiries, please use the GitHub private vulnerability reporting system.

For non-security related issues, please use the regular issue tracker.