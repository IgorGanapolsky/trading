# LL-146: GCP Service Account Key Security Fix

**Date**: January 13, 2026
**Category**: Security
**Severity**: CRITICAL

## Summary

Fixed security vulnerability where GCP service account keys were written to `/tmp/` with world-readable permissions (644 default). Added `chmod 600` to restrict access to owner only.

## Affected Workflows
- daily-trading.yml (line 196)
- vertex-rag-pretrade.yml (line 91)
- cleanup-vertex-rag.yml (line 39)

## Root Cause

Default file creation permissions in shell allow read access to all users. On GitHub Actions runners, this is less critical (ephemeral VMs), but follows security best practices and prevents any process on the runner from reading credentials.

## Fix Applied

```bash
# Before (insecure)
echo "$GCP_SA_KEY" > /tmp/gcp_sa_key.json

# After (secure)
echo "$GCP_SA_KEY" > /tmp/gcp_sa_key.json
chmod 600 /tmp/gcp_sa_key.json
```

## Prevention

When writing secrets to files:
1. Always `chmod 600` immediately after creation
2. Delete secret files after use (`rm -f /tmp/secret.json`)
3. Prefer environment variables over files when possible
