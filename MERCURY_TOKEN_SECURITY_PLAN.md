# Mercury API Token Security Action Plan

## Issue
An email from Mercury Technologies indicates that the "trading" API token has been inactive for 38 days and will be deleted in 7 days. This token is referenced in the codebase as MERCURY_API_TOKEN.

## Immediate Actions Required

### 1. Verify Current Token Status
- Check if the MERCURY_API_TOKEN is currently set in environment
- Determine if the token is still needed for operations

### 2. Token Rotation or Removal
If the token is still needed:
- Generate a new Mercury API token with appropriate permissions
- Update the environment with the new token
- Test all Mercury-dependent functionality

If the token is no longer needed:
- Remove Mercury-related code if not in use
- Document that Mercury functionality has been deactivated
- Ensure no code paths attempt to use Mercury APIs

### 3. Security Measures
- Never hardcode Mercury API tokens in code
- Use secure credential storage (Keychain, encrypted environment variables)
- Implement proper token rotation procedures
- Ensure Mercury functionality is disabled by default (which it appears to be via MERCURY_LIVE_TRANSFERS_ENABLED=0)

## Current Configuration
From .env.example:
- MERCURY_API_TOKEN= (currently empty)
- MERCURY_ACCOUNT_ID= (currently empty)
- MERCURY_RECIPIENT_ID= (currently empty)
- MERCURY_LIVE_TRANSFERS_ENABLED=0 (correctly disabled)

## Risk Assessment
- The token is currently inactive (MERCURY_LIVE_TRANSFERS_ENABLED=0)
- No live Mercury transfers are occurring
- The code appears to be designed to prevent accidental use
- However, an unused token should still be cleaned up for security hygiene

## Recommended Action
Since the token is unused and the functionality is disabled, the safest approach is to:
1. Let the token expire/delete as Mercury has initiated
2. Confirm Mercury functionality remains disabled
3. Update documentation to reflect Mercury is not currently in use
4. Remove Mercury code if it's no longer planned for use