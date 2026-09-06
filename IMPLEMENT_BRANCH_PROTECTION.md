# Branch Protection Implementation Guide

This document provides step-by-step instructions for implementing the branch protection rules outlined in BRANCH_PROTECTION_GUIDELINES.md.

## Steps to Configure Branch Protection in GitHub

### 1. Access Repository Settings
- Navigate to your repository on GitHub
- Click on the "Settings" tab
- In the left sidebar, scroll down to "Code and automation" and click on "Branches"

### 2. Add Branch Protection Rule for `main`
- Click on "Add rule" 
- In the "Branch name pattern" field, enter `main`

### 3. Configure Required Settings

#### Require pull request reviews before merging
- ✅ Check "Require pull request reviews before merging"
- Set "Required number of approvals" to 1
- ✅ Check "Dismiss stale pull request approvals when new commits are pushed"
- ✅ Check "Require review from Code Owners" (if CODEOWNERS file is present)

#### Require status checks to pass before merging
- ✅ Check "Require status checks to pass before merging"
- ✅ Check "Require branches to be up to date before merging"
- Under "Status checks that are required", add:
  - CI checks must pass
  - CodeQL analysis must pass
  - Security scanning must pass

#### Require signed commits (recommended)
- ✅ Check "Require signed commits"

#### Restrict who can push to matching branches
- ✅ Check "Restrict who can push to matching branches"
- Select appropriate users/teams who can push to main
- ✅ Check "Prevent force pushes" 
- ✅ Check "Prevent deletion of the main branch"

### 4. Additional Recommendations
- Configure "Automatically delete head branches after pull requests are merged"
- Set up "Auto-cancel redundant builds for pull requests"

## Verification

After implementing these settings:
1. Verify that direct pushes to `main` are blocked
2. Confirm that pull requests require approval before merging
3. Test that status checks are enforced before merging
4. Ensure that only authorized users can push to the main branch

## Benefits

These branch protection settings will help prevent:
- Unauthorized direct commits to main
- Accidental or malicious changes without review
- Unvetted code from entering the main branch
- Security vulnerabilities from being introduced without proper review

## Next Steps

Once branch protection is implemented, the security scan should show fewer "Branch-Protection" alerts.