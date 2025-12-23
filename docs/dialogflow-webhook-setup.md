# Dialogflow CX Webhook Setup

This guide covers deploying and configuring the Dialogflow CX webhook for the trading system's RAG knowledge base.

## Architecture

```
Dialogflow CX Agent
    ↓ (webhook request)
Cloud Run Service (trading-webhook)
    ↓ (query RAG)
LessonsLearnedRAG
    ↓ (search lessons)
rag_knowledge/lessons_learned/*.md
```

## Prerequisites

1. **GCP Project** with Cloud Run API enabled
2. **GitHub Secrets** configured:
   - `GCP_SA_KEY`: Service account JSON key with Cloud Run Admin role
   - `GCP_PROJECT_ID`: Your GCP project ID
3. **Dialogflow CX Agent** created in GCP Console

## Deployment

### Option 1: Automatic Deployment (Recommended)

The webhook auto-deploys via GitHub Actions when changes are pushed to `main`:

```bash
# Triggers deployment automatically
git push origin main
```

**Workflow:** `.github/workflows/deploy-webhook.yml`

**Triggered by changes to:**
- `src/agents/dialogflow_webhook.py`
- `src/rag/**`
- `Dockerfile.webhook`

### Option 2: Manual Deployment

If you have gcloud CLI configured locally:

```bash
# Source gcloud SDK
source /tmp/google-cloud-sdk/google-cloud-sdk/path.bash.inc

# Deploy
gcloud run deploy trading-webhook \
  --source . \
  --dockerfile Dockerfile.webhook \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --timeout 60 \
  --memory 512Mi \
  --cpu 1 \
  --max-instances 3

# Get webhook URL
gcloud run services describe trading-webhook \
  --region us-central1 \
  --format 'value(status.url)'
```

## Dialogflow CX Configuration

### 1. Create Webhook in Dialogflow CX

1. Go to [Dialogflow CX Console](https://dialogflow.cloud.google.com/)
2. Select your agent
3. Navigate to **Manage** → **Webhooks**
4. Click **Create**
5. Configure:
   - **Display name:** Trading System RAG
   - **Webhook URL:** `https://trading-webhook-xxx.run.app/webhook`
   - **Timeout:** 30 seconds
   - **Authentication:** None (public endpoint)

### 2. Configure Default Fallback Intent

1. Go to **Build** → **Flows** → **Default Start Flow**
2. Select **Default Fallback Intent**
3. Under **Fulfillment**, enable **Webhook**
4. Select **Trading System RAG** webhook
5. Save

### 3. Test in Dialogflow CX Console

**IMPORTANT:** Test in Dialogflow CX Console, NOT Vertex AI Studio Chat.

Example queries:
- "What did you learn about trading?"
- "Tell me about calendar awareness"
- "What are the risk management rules?"
- "Show me critical lessons"

## Webhook Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check (returns lesson count) |
| `/health` | GET | Detailed health status |
| `/webhook` | POST | Dialogflow CX webhook handler |
| `/webhook/test` | POST | Local testing endpoint |

## Local Testing

### Test the webhook locally:

```bash
# Start webhook server
python -m uvicorn src.agents.dialogflow_webhook:app --reload --port 8080

# Test health check
curl http://localhost:8080/health

# Test query
curl -X POST http://localhost:8080/webhook/test \
  -H "Content-Type: application/json" \
  -d '{"query": "trading lessons"}'
```

### Test with Dialogflow format:

```bash
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What are critical lessons?",
    "languageCode": "en"
  }'
```

## RAG Integration

The webhook queries `LessonsLearnedRAG` which searches:
- `rag_knowledge/lessons_learned/*.md`

**Query parameters:**
- `top_k`: Number of results (default: 3)
- `severity_filter`: Filter by CRITICAL, HIGH, MEDIUM, LOW

**Response format:**
```json
{
  "fulfillmentResponse": {
    "messages": [
      {
        "text": {
          "text": ["Based on what I've learned about 'trading':\n\n🔴 Lesson 1 (CRITICAL):\n..."]
        }
      }
    ]
  }
}
```

## Monitoring

### View Cloud Run logs:

```bash
gcloud run services logs read trading-webhook \
  --region us-central1 \
  --limit 50
```

### Check deployment status:

```bash
gcloud run services describe trading-webhook \
  --region us-central1 \
  --format yaml
```

## Troubleshooting

### Webhook returns 404

**Cause:** Wrong URL path
**Fix:** Ensure URL ends with `/webhook`: `https://xxx.run.app/webhook`

### Webhook returns 500

**Cause:** RAG initialization failed
**Fix:** Check Cloud Run logs for import errors:
```bash
gcloud run services logs read trading-webhook --region us-central1
```

### Dialogflow not calling webhook

**Cause:** Webhook not configured on fallback intent
**Fix:** Verify:
1. Webhook URL is correct in Dialogflow CX
2. Default Fallback Intent has webhook enabled
3. Testing in Dialogflow CX Console (not Vertex AI Studio)

### No lessons found

**Cause:** `rag_knowledge/` not copied to container
**Fix:** Check `Dockerfile.webhook` includes:
```dockerfile
COPY rag_knowledge/ rag_knowledge/
```

## Security Considerations

**Current Setup:** Public endpoint (`--allow-unauthenticated`)

**For Production:** Enable authentication:

```bash
# Deploy with authentication required
gcloud run deploy trading-webhook \
  --no-allow-unauthenticated \
  ...

# Grant Dialogflow service account access
gcloud run services add-iam-policy-binding trading-webhook \
  --region us-central1 \
  --member "serviceAccount:dialogflow-xxx@xxx.iam.gserviceaccount.com" \
  --role "roles/run.invoker"
```

## Cost Optimization

**Cloud Run Pricing:**
- Free tier: 2M requests/month
- After free tier: $0.40 per million requests
- Memory: $0.0000025 per GB-second
- CPU: $0.00002400 per vCPU-second

**Estimated cost for this webhook:**
- ~100 requests/day = 3K/month
- Average response time: 200ms
- **Monthly cost:** ~$0.05 (within free tier)

## References

- [Dialogflow CX Webhooks](https://cloud.google.com/dialogflow/cx/docs/concept/webhook)
- [Cloud Run Docs](https://cloud.google.com/run/docs)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- Trading System RAG: `src/rag/lessons_learned_rag.py`
