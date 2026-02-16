---
title: "Google Doc Sync Setup"
description: "Setup guide for syncing the hackathon system explainer to Google Docs from the devloop."
summary: "Configure service account credentials, document permissions, env vars, and validation steps for automated sync."
hero_image: "/assets/img/agent-loop-diagram.png"
---

# Google Doc Sync Setup

This enables automatic updates of the system explainer into your Google Doc on each loop cycle.

## 1) Create service account credentials
1. In Google Cloud Console, create or select a project.
2. Enable **Google Docs API**.
3. Create a **Service Account**.
4. Create a JSON key and download it.
5. Save it locally at:
   - `.secrets/google-service-account.json`

## 2) Share your target doc with the service account
1. Open your Google Doc.
2. Click Share.
3. Add the service account email (from JSON `client_email`) as **Editor**.

## 3) Configure loop env
Edit `.env.devloop` and set:

```bash
SYNC_GDOC=1
GDRIVE_DOC_URL=https://docs.google.com/document/d/1rnoWCNROrSfAzX2qc49G3A26Tazx0WwyLphrQMDE98Y/edit?usp=sharing
GDRIVE_CREDS_FILE=.secrets/google-service-account.json
```

## 4) Install Python deps in devloop venv
```bash
.venv-devloop/bin/pip install -r requirements.txt
```

## 5) Test one sync manually
```bash
.venv-devloop/bin/python scripts/generate_system_explainer.py --repo-root . --out docs/_reports/hackathon-system-explainer.md
.venv-devloop/bin/python scripts/sync_explainer_to_gdoc.py \
  --doc "$GDRIVE_DOC_URL" \
  --in docs/_reports/hackathon-system-explainer.md \
  --creds "$GDRIVE_CREDS_FILE"
```

## 6) Restart loop agent
```bash
RUN_TARS=1 RUN_RAG=1 ./scripts/devloop_launchagent.sh restart
```

## Notes
- Sync applies enhanced formatting (title banner, heading styles, bullets, numbered lists, code/diagram block styling).
- This is intentionally non-blocking in the loop: if sync fails, the loop continues.
