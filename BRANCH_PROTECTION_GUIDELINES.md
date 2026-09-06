# Branch Protection Rules

This document outlines the recommended branch protection settings for the repository to address the "Branch-Protection" security alerts.

## Main Branch Protection Settings

The `main` branch should have the following protections enabled:

### Required Settings
- [ ] Require pull request reviews before merging
  - [ ] Require at least 1 approved review
  - [ ] Dismiss stale pull request approvals when new commits are pushed
  - [ ] Require review from Code Owners (if CODEOWNERS file is present)

- [ ] Require status checks to pass before merging
  - [ ] Require branches to be up to date before merging
  - [ ] Required status checks:
    - CI checks must pass
    - CodeQL analysis must pass
    - Security scanning must pass

- [ ] Require signed commits (recommended)
  - [ ] Require signed commits on the main branch

- [ ] Restrict who can push to matching branches
  - [ ] Allow only specific users/teams to push to main
  - [ ] Prevent force pushes to main branch
  - [ ] Prevent deletion of the main branch

### Additional Recommendations
- Set up branch rules to automatically delete head branches after pull requests are merged
- Configure auto-cancel redundant builds for pull requests
- Use protected branch rules to enforce code review policies

## Implementation

These settings should be configured in the GitHub repository settings under:
Settings → Branches → Branch protection rules → Add rule

Pattern: `main`
Then apply the above settings.

## Rationale

The branch protection settings help prevent:
- Unauthorized direct commits to main
- Accidental or malicious changes without review
- Unvetted code from entering the main branch
- Security vulnerabilities from being introduced without proper review