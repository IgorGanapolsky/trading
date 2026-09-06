#!/bin/bash

# GitHub Security Remediation Script
# This script automates the process of addressing common GitHub security alerts

set -e  # Exit on any error

echo "Starting GitHub Security Remediation Process..."

# Function to check if running in a git repository
check_git_repo() {
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        echo "Error: Not running in a git repository"
        exit 1
    fi
}

# Function to check GitHub CLI authentication
check_gh_auth() {
    if ! gh auth status > /dev/null 2>&1; then
        echo "Error: GitHub CLI not authenticated. Run 'gh auth login' first."
        exit 1
    fi
}

# Function to backup important files before making changes
backup_files() {
    echo "Creating backups of important files..."
    
    # Backup current pull request template
    if [ -f ".github/pull_request_template.md" ]; then
        cp .github/pull_request_template.md .github/pull_request_template.md.backup
    fi
    
    # Backup current security policy
    if [ -f "SECURITY.md" ]; then
        cp SECURITY.md SECURITY.md.backup
    fi
}

# Function to fix token permissions in workflow files
fix_token_permissions() {
    echo "Fixing token permissions in workflow files..."
    
    # Find and update workflow files with overly broad permissions
    for workflow_file in .github/workflows/*.yml .github/workflows/*.yaml; do
        if [ -f "$workflow_file" ]; then
<<<<<<< HEAD
            # Replace overly broad permissions
            sed -i.bak 's/contents: write # Required for creating PRs and managing repository content/contents: read # Only read access needed for most operations/' "$workflow_file" 2>/dev/null || true
            sed -i.bak 's/contents: write # Required for merging PRs/contents: read # Only read access needed for most operations/' "$workflow_file" 2>/dev/null || true
            
            # Clean up backup file
            rm -f "$workflow_file.bak" 2>/dev/null || true
        fi
    done
}

# Function to update pull request template with security considerations
update_pr_template() {
    echo "Updating pull request template with security considerations..."
    
    PR_TEMPLATE=".github/pull_request_template.md"
    
    if [ -f "$PR_TEMPLATE" ]; then
        # Check if security sections are already present
        if ! grep -q "Security Impact Assessment" "$PR_TEMPLATE"; then
            # Backup current template
            cp "$PR_TEMPLATE" "${PR_TEMPLATE}.backup"
            
            # Insert security assessment section before the Verification section
            sed -i.bak '/## Verification/i\
\
## Security Impact Assessment\
\
Please consider and describe the security implications of your changes:\
\
- [ ] No security impact\
- [ ] Low security impact\
- [ ] Medium security impact\
- [ ] High security impact\
\
Security considerations:\
- Does this change affect credential handling? \
- Does this change modify access controls?\
- Does this change introduce new dependencies?\
- Does this change modify workflow permissions?\
- Have secrets been properly handled without hardcoding?\
' "$PR_TEMPLATE"
            
            # Update verification checklist to include security items
            sed -i.bak '/- \[ \] CI green on this exact head SHA/a\
- [ ] Security implications have been considered and addressed\
- [ ] Dependencies have been reviewed for security vulnerabilities\
- [ ] No hardcoded secrets or credentials have been added' "$PR_TEMPLATE"
            
            # Clean up backup
            rm -f "${PR_TEMPLATE}.bak"
        fi
    fi
}

# Function to enhance security documentation
enhance_security_docs() {
    echo "Enhancing security documentation..."
    
    SECURITY_FILE="SECURITY.md"
    
    if [ -f "$SECURITY_FILE" ]; then
        # Check if enhanced content is already present
        if ! grep -q "Security Response Process" "$SECURITY_FILE"; then
            # Backup current file
            cp "$SECURITY_FILE" "${SECURITY_FILE}.backup"
            
            # Append enhanced security content
            cat >> "$SECURITY_FILE" << 'EOF'

## Security Response Process

When a security vulnerability is reported:

1. The security team will acknowledge receipt of the vulnerability within 48 hours
2. An initial assessment will be conducted to determine severity and impact
3. A fix will be developed and tested in a private branch
4. The fix will be deployed to affected systems
5. A coordinated disclosure will be made according to responsible disclosure practices

## Security Best Practices

### For Contributors

- Always use specific commit hashes for GitHub Actions instead of version tags
- Apply principle of least privilege when setting workflow permissions
||||||| bca54bb45
=======
            # Look for overly broad permissions and suggest using read-all
            if grep -q "contents: write" "$workflow_file" && ! grep -q "permissions: read-all" "$workflow_file"; then
                echo "Found contents: write in $workflow_file - consider using permissions: read-all for better security"
            fi
        fi
    done
}

# Function to update pull request template with security considerations
update_pr_template() {
    echo "Pull request template already updated with security considerations."
}

# Function to enhance security documentation
enhance_security_docs() {
    echo "Enhancing security documentation..."
    
    SECURITY_FILE="SECURITY.md"
    
    if [ -f "$SECURITY_FILE" ]; then
        # Check if enhanced content is already present
        if ! grep -q "Security Response Process" "$SECURITY_FILE"; then
            # Append enhanced security content
            cat >> "$SECURITY_FILE" << 'EOF'

## Security Response Process

When a security vulnerability is reported:

1. The security team will acknowledge receipt of the vulnerability within 48 hours
2. An initial assessment will be conducted to determine severity and impact
3. A fix will be developed and tested in a private branch
4. The fix will be deployed to affected systems
5. A coordinated disclosure will be made according to responsible disclosure practices

## Security Best Practices

### For Contributors

- Always use specific commit hashes for GitHub Actions instead of version tags
- Apply principle of least privilege when setting workflow permissions
- Use `permissions: read-all` when possible for maximum security
>>>>>>> 65d7850d3
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

## Security Scanning

This repository uses automated security scanning tools:

- CodeQL for code analysis
- Dependabot for dependency scanning
- GitHub's secret scanning
- OpenSSF Scorecard for supply chain security
EOF
        fi
    fi
}

# Function to verify pinned dependencies
verify_pinned_dependencies() {
    echo "Verifying pinned dependencies in workflow files..."
    
    # Check if any workflow files use version tags instead of commit hashes
    TAGGED_ACTIONS=$(find .github/workflows/ -name "*.yml" -o -name "*.yaml" -exec grep -l "uses:.*@[v]" {} \; 2>/dev/null || echo "None found")
    
    if [ "$TAGGED_ACTIONS" != "None found" ] && [ -n "$TAGGED_ACTIONS" ]; then
        echo "WARNING: Found workflow files using version tags instead of commit hashes:"
        echo "$TAGGED_ACTIONS"
        echo "These should be updated to use commit hashes for security."
    else
        echo "All workflow files are using commit hashes for GitHub Actions."
    fi
}

# Function to configure branch protection (requires repo owner privileges)
configure_branch_protection() {
    echo "Configuring branch protection rules..."
    
    # Get the current repository owner and name
    REPO_FULL_NAME=$(gh repo view --json nameWithOwner -q '.nameWithOwner')
    OWNER=$(echo "$REPO_FULL_NAME" | cut -d'/' -f1)
    REPO=$(echo "$REPO_FULL_NAME" | cut -d'/' -f2)
    
    echo "Configuring branch protection for $REPO_FULL_NAME..."
    
    # Configure branch protection using GitHub API
    RESPONSE=$(curl -s -w "%{http_code}" -L -X PUT \
      -H "Accept: application/vnd.github+json" \
      -H "Authorization: Bearer $(gh auth token)" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      https://api.github.com/repos/$OWNER/$REPO/branches/main/protection \
      -d '{
        "required_status_checks": {
          "strict": true,
          "contexts": ["Detect Changed Paths", "Run All Tests", "Validate Workflows", "CodeQL", "Dependency Review"]
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
      }')
    
    HTTP_CODE="${RESPONSE: -3}"
    RESPONSE_BODY="${RESPONSE%???}"
    
    if [ "$HTTP_CODE" -eq 200 ] || [ "$HTTP_CODE" -eq 201 ]; then
        echo "✅ Branch protection successfully configured!"
    else
        echo "⚠️  Branch protection configuration failed with HTTP $HTTP_CODE"
        echo "Response: $RESPONSE_BODY"
        echo "This may be because you don't have admin rights on this repository."
    fi
}

# Main execution
main() {
    echo "GitHub Security Remediation Script"
    echo "=================================="
    
    check_git_repo
    check_gh_auth
    backup_files
    
    echo ""
    fix_token_permissions
    
    echo ""
    update_pr_template
    
    echo ""
    enhance_security_docs
    
    echo ""
    verify_pinned_dependencies
    
    echo ""
    read -p "Do you want to configure branch protection? This requires admin rights. (y/N): " -n 1 -r REPLY
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        configure_branch_protection
    else
        echo "Skipping branch protection configuration."
    fi
    
    echo ""
    echo "GitHub Security Remediation Process Complete!"
    echo ""
    echo "Next steps:"
    echo "1. Review the changes made to your files"
    echo "2. Commit and push the changes to your repository"
    echo "3. Verify that security alerts decrease in GitHub Security tab"
    echo "4. If you didn't configure branch protection, do so manually in repository settings"
}

# Run the main function
main "$@"