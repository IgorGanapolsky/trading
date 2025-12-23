#!/bin/bash
# Auto-generated PR creation script for Dialogflow webhook deployment
# Usage: GITHUB_TOKEN=<token> ./scripts/create_pr_webhook.sh

set -e

REPO="IgorGanapolsky/trading"
BRANCH="claude/deploy-webhook-cloud-run-CZkb8"
BASE="main"

# PR details
TITLE="feat: Dialogflow CX webhook with Cloud Run auto-deployment"
BODY="## Summary
Adds webhook integration between Dialogflow CX and trading system's RAG knowledge base.

## Changes
- **Webhook Handler**: \`src/agents/dialogflow_webhook.py\` - FastAPI server queries LessonsLearnedRAG
- **Auto-Deployment**: \`.github/workflows/deploy-webhook.yml\` - Deploys to Cloud Run on merge
- **Documentation**: \`docs/dialogflow-webhook-setup.md\` - Complete setup guide

## Integration
- Queries \`rag_knowledge/lessons_learned/\` for relevant lessons
- Returns top 3 results with severity indicators (🔴 CRITICAL, 🟡 HIGH, 🟢 LOW)
- Cloud Run config: 512Mi RAM, 1 CPU, 60s timeout, 3 max instances

## Prerequisites for Deployment
GitHub secrets required (add before merging):
- \`GCP_SA_KEY\`: Service account JSON with Cloud Run Admin role
- \`GCP_PROJECT_ID\`: \`igor-trading-2025-v2\`

## Post-Merge Steps
After deployment completes, configure in Dialogflow CX Console:
1. Add webhook URL (from deployment output)
2. Enable webhook on default fallback intent
3. Test in Dialogflow CX (not Vertex AI Studio)

## Cost
~\$0.05/month (within Cloud Run free tier)"

# Check for token
if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ GITHUB_TOKEN not set"
    echo "📝 Manual PR creation URL:"
    echo "   https://github.com/$REPO/pull/new/$BRANCH"
    exit 1
fi

# Create PR
echo "Creating PR for $BRANCH → $BASE..."

RESPONSE=$(curl -s -X POST \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    https://api.github.com/repos/$REPO/pulls \
    -d "$(jq -n \
        --arg title "$TITLE" \
        --arg body "$BODY" \
        --arg head "$BRANCH" \
        --arg base "$BASE" \
        '{title: $title, body: $body, head: $head, base: $base}')")

# Check response
PR_URL=$(echo "$RESPONSE" | jq -r '.html_url // empty')

if [ -z "$PR_URL" ]; then
    echo "❌ PR creation failed:"
    echo "$RESPONSE" | jq '.'
    exit 1
fi

echo "✅ PR created: $PR_URL"
echo ""
echo "📋 Next steps:"
echo "1. Review and merge PR"
echo "2. GitHub Actions will auto-deploy to Cloud Run"
echo "3. Configure webhook URL in Dialogflow CX Console"
