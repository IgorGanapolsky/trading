# GitHub Security Remediation Skill

This skill provides a comprehensive approach to addressing GitHub security alerts including token permissions, branch protection, pinned dependencies, and code review processes.

## Problem Categories Addressed

1. **Token-Permissions (High)**: Overly broad permissions in GitHub workflow files
2. **Branch-Protection (High)**: Inadequate branch protection settings
3. **Pinned-Dependencies (Medium)**: Missing commit hash pinning for GitHub Actions
4. **Code Review Process**: Lack of security considerations in review process

## Solution Components

### 1. Token Permission Hardening

#### Workflow Permission Audit and Reduction
- Review all workflow files in `.github/workflows/`
- Apply principle of least privilege: reduce `contents: write` to `contents: read` where possible
- Maintain only necessary permissions for each workflow

#### Example Fix
```yaml
# Before
permissions:
  contents: write
  pull-requests: write

# After  
permissions:
  contents: read  # Reduced from write
  pull-requests: write
```

### 2. Branch Protection Configuration

#### Using GitHub API to Configure Strong Protection
```bash
curl -L -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $(gh auth token)" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/{owner}/{repo}/branches/main/protection \
  -d '{
    "required_status_checks": {
      "strict": true,
      "contexts": ["CI", "CodeQL", "Dependency Review"]
    },
    "required_pull_request_reviews": {
      "required_approving_review_count": 1,
      "dismiss_stale_reviews": true,
      "require_code_owner_reviews": true
    },
    "enforce_admins": true,
    "required_linear_history": true,
    "allow_force_pushes": false,
    "allow_deletions": false,
    "restrictions": null
  }'
```

### 3. Pinned Dependencies Verification

#### Verify All GitHub Actions Use Commit Hashes
- Check all `uses:` statements in workflow files
- Ensure they use specific commit hashes (40-character SHA) instead of version tags
- Example: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` ✅
- Not: `actions/checkout@v3` ❌

### 4. Code Review Process Enhancement

#### Update Pull Request Template
Add security impact assessment sections to `.github/pull_request_template.md`:
- Security Impact Assessment checklist
- Security considerations questions
- Additional verification steps for security implications

### 5. Security Documentation Improvement

#### Update SECURITY.md
- Add Security Response Process
- Expand security best practices
- Include information about security scanning tools
- Define supported versions policy

## Execution Steps

1. **Audit current state**: Examine existing workflow files and security configurations
2. **Apply token permission fixes**: Reduce overly broad permissions
3. **Configure branch protection**: Use GitHub API to set strong protection rules
4. **Verify pinned dependencies**: Ensure all actions use commit hashes
5. **Enhance code review process**: Update PR templates with security sections
6. **Improve documentation**: Update security policies with comprehensive guidelines
7. **Verify implementation**: Confirm all changes are effective

## Verification Commands

```bash
# Check branch protection settings
gh api repos/{owner}/{repo}/branches/main/protection --method GET

# Verify workflow permissions
grep -r "permissions:" .github/workflows/

# List all workflow files
ls -la .github/workflows/
```

## Expected Outcomes

- Reduction in GitHub security alerts
- Improved repository security posture
- Better compliance with security best practices
- Enhanced code review process with security considerations
- Stronger branch protection preventing unauthorized changes