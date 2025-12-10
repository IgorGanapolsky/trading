# ☁️ Cloud Deployment Guide

## Current Problem

**Local macOS Setup:**
- ❌ Requires Mac to be on 24/7
- ❌ No execution if Mac sleeps/restarts
- ❌ Not production-ready

**Solution: Cloud Deployment** ✅

---

## 🐙 Option 1: GitHub Actions (RECOMMENDED - Easiest)

### Advantages
- ✅ **Free** for public repositories
- ✅ **No infrastructure** to manage
- ✅ **Built-in cron scheduling**
- ✅ **Automatic execution** in cloud
- ✅ **Easy to set up** (5 minutes)

### Setup Steps

#### 1. Add GitHub Secrets

Go to your repository: `Settings → Secrets and variables → Actions → New repository secret`

Add these secrets:
- `ALPACA_API_KEY` - Your Alpaca API key
- `ALPACA_SECRET_KEY` - Your Alpaca secret key
- `OPENROUTER_API_KEY` - Your OpenRouter API key (optional)
- `DAILY_INVESTMENT` - Daily investment amount (default: 10.0)

#### 2. Workflow File

The workflow file is already created: `.github/workflows/daily-trading.yml`

It runs:
- **Schedule**: Every weekday at 9:35 AM EST (1:35 PM UTC)
- **Action**: Executes `scripts/autonomous_trader.py`
- **Logs**: Uploads execution logs as artifacts

#### 3. Enable Workflow

1. Push to GitHub:
   ```bash
   git add .github/workflows/daily-trading.yml
   git commit -m "feat: Add GitHub Actions for daily trading execution"
   git push origin main
   ```

2. Verify workflow:
   - Go to: `Actions` tab in GitHub
   - You should see "Daily Trading Execution" workflow
   - Click "Run workflow" to test manually

#### 4. Monitor Execution

- **View runs**: GitHub → Actions → Daily Trading Execution
- **View logs**: Click on any run → See logs
- **Download artifacts**: Logs are saved as artifacts

### Limitations
- ⚠️ Free tier: 2,000 minutes/month (enough for daily execution)
- ⚠️ State management: Uses GitHub Actions cache (not ideal for long-term state)
- ⚠️ Execution time: Max 10 minutes per run

### Cost
**FREE** (for public repos)

---

## 🚀 Option 2: AWS Lambda + EventBridge (Production)

### Advantages
- ✅ **Serverless** (pay per execution)
- ✅ **Always-on** (no server management)
- ✅ **Reliable** (99.99% uptime SLA)
- ✅ **Scalable** (handles millions of requests)
- ✅ **Persistent state** (via S3/DynamoDB)

### Setup Steps

#### 1. Create Lambda Function

```bash
# Package code
zip -r trading-bot-lambda.zip . -x "*.git*" "*.env*" "venv/*" "data/*" "logs/*"

# Create function
aws lambda create-function \
  --function-name trading-bot \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler lambda_handler.lambda_handler \
  --zip-file fileb://trading-bot-lambda.zip \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables="{
    ALPACA_API_KEY=$ALPACA_KEY,
    ALPACA_SECRET_KEY=$ALPACA_SECRET,
    PAPER_TRADING=true
  }"
```

#### 2. Create EventBridge Rule

```bash
# Create rule (9:35 AM EST = 13:35 UTC)
aws events put-rule \
  --name daily-trading \
  --schedule-expression "cron(35 13 ? * MON-FRI *)" \
  --description "Execute trading bot daily at 9:35 AM EST"

# Add Lambda permission
aws lambda add-permission \
  --function-name trading-bot \
  --statement-id daily-trading \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:REGION:ACCOUNT:rule/daily-trading
```

#### 3. Lambda Handler

The repository now ships with `lambda_handler.py`, so you can zip the repo without any extra scaffolding. The handler loads `.env`, defaults weekend proxies, and invokes `scripts/autonomous_trader.py` so that EventBridge + Lambda can act as a 24/7 failsafe when GitHub Actions are unavailable.

### Cost
**~$0-5/month** (free tier: 1M requests/month)

---

## 🐳 Option 3: Google Cloud Run + Cloud Scheduler

### Advantages
- ✅ **Containerized** (Docker)
- ✅ **Cloud Scheduler** (cron-like)
- ✅ **Free tier**: 2M requests/month
- ✅ **Scalable** and reliable

### Setup Steps

#### 1. Build Docker Image

```bash
# Build image
docker build -t gcr.io/YOUR_PROJECT/trading-bot .

# Push to Google Container Registry
docker push gcr.io/YOUR_PROJECT/trading-bot
```

#### 2. Deploy to Cloud Run

```bash
gcloud run deploy trading-bot \
  --image gcr.io/YOUR_PROJECT/trading-bot \
  --platform managed \
  --region us-east1 \
  --set-env-vars ALPACA_API_KEY=$ALPACA_KEY,ALPACA_SECRET_KEY=$ALPACA_SECRET
```

#### 3. Create Cloud Scheduler Job

```bash
gcloud scheduler jobs create http daily-trading \
  --schedule="35 13 * * 1-5" \
  --uri="https://trading-bot-XXXXX.run.app" \
  --http-method=POST \
  --time-zone="America/New_York"
```

### Cost
**~$0-5/month** (free tier available)

---

## 🖥️ Option 4: VPS (DigitalOcean/Linode)

### Advantages
- ✅ **Always-on** server
- ✅ **Full control**
- ✅ **Docker support**
- ✅ **Simple setup**

### Setup Steps

#### 1. Provision VPS

- **Provider**: DigitalOcean, Linode, AWS EC2
- **Specs**: 2GB RAM, 1 vCPU, 25GB SSD
- **OS**: Ubuntu 22.04 LTS

#### 2. Deploy with Docker

```bash
# SSH into server
ssh user@your-server-ip

# Clone repository
git clone https://github.com/YOUR_USERNAME/trading.git
cd trading

# Create .env file
nano .env
# Add your API keys

# Run with Docker Compose
docker-compose up -d

# Check logs
docker-compose logs -f
```

#### 3. Setup Cron (Alternative)

```bash
# Edit crontab
crontab -e

# Add daily execution (9:35 AM EST)
35 9 * * 1-5 cd /path/to/trading && /path/to/venv/bin/python scripts/autonomous_trader.py >> logs/cron.log 2>&1
```

### Cost
**~$5-10/month** (VPS hosting)

---

## 📊 Comparison

| Option | Cost | Setup Time | Reliability | Best For |
|--------|------|------------|-------------|----------|
| **GitHub Actions** | FREE | 5 min | ⭐⭐⭐⭐ | Quick start |
| **AWS Lambda** | $0-5/mo | 30 min | ⭐⭐⭐⭐⭐ | Production |
| **Google Cloud Run** | $0-5/mo | 30 min | ⭐⭐⭐⭐⭐ | Production |
| **VPS** | $5-10/mo | 1 hour | ⭐⭐⭐⭐ | Full control |

---

## 🎯 Recommendation

1. **START NOW**: GitHub Actions (free, easy, 5 minutes)
2. **SCALE LATER**: AWS Lambda (when you need production reliability)

---

## 🚀 Quick Start (GitHub Actions)

1. **Add secrets** in GitHub (Settings → Secrets)
2. **Push workflow file**:
   ```bash
   git add .github/workflows/daily-trading.yml
   git commit -m "feat: Add cloud deployment via GitHub Actions"
   git push origin main
   ```
3. **Test manually**: GitHub → Actions → Run workflow
4. **Monitor**: Check Actions tab daily

**Done!** Your trading bot now runs in the cloud automatically. 🎉

---

## 📝 Notes

- **State Management**: GitHub Actions uses cache (not ideal for long-term state)
- **Logs**: Available in Actions → Artifacts
- **Failure Alerts**: Setup GitHub notifications or email alerts
- **Cost**: FREE for public repos (2,000 minutes/month)

---

**Next Steps**: Push the workflow file and enable GitHub Actions! 🚀
