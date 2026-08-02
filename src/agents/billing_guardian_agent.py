import json
import logging
import os
import subprocess
from datetime import UTC, datetime

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BillingGuardian")


class BillingGuardianAgent:
    """
    Autonomous guardian to monitor GCP costs and kill expensive unwhitelisted projects.
    Uses Perplexity API for deep research on detected anomalies if needed.
    """

    def __init__(self):
        self.whitelisted_projects = ["igor-trading-2025-v2", "claude-code-learning"]
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")

    def _send_telegram_alert(self, message: str):
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.warning(f"Telegram not configured. Local alert: {message}")
            return

        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {"chat_id": self.telegram_chat_id, "text": message, "parse_mode": "HTML"}
        try:
            httpx.post(url, json=payload, timeout=10.0)
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

    def get_active_projects(self) -> list:
        try:
            result = subprocess.run(
                ["gcloud", "projects", "list", "--filter=lifecycleState=ACTIVE", "--format=json"],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Failed to fetch projects: {e}")
            return []

    def enforce_billing_policies(self):
        logger.info(f"[{datetime.now(UTC).isoformat()}] Billing Guardian checking GCP projects...")
        projects = self.get_active_projects()

        for project in projects:
            pid = project.get("projectId")
            if pid not in self.whitelisted_projects:
                logger.error(f"UNAUTHORIZED PROJECT DETECTED: {pid}. Executing shutdown!")
                self._send_telegram_alert(
                    f"🚨 <b>Billing Guardian Alert</b>\n"
                    f"Unauthorized active project detected: <code>{pid}</code>\n"
                    f"Initiating emergency shutdown to prevent cloud charges."
                )

                try:
                    subprocess.run(["gcloud", "projects", "delete", pid, "--quiet"], check=True)
                    self._send_telegram_alert(
                        f"✅ Successfully deleted project <code>{pid}</code>."
                    )
                    logger.info(f"Deleted project {pid}")
                except Exception as e:
                    logger.error(f"Failed to delete project {pid}: {e}")
                    self._send_telegram_alert(
                        f"❌ Failed to delete project <code>{pid}</code>. Manual intervention required!\n"
                        f"Error: {e}"
                    )

    async def check_anomalies_with_perplexity(self, anomaly_description: str):
        """Use Perplexity to investigate potential billing anomalies or new services."""
        if not self.perplexity_api_key:
            return

        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.perplexity_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "sonar-pro",
            "messages": [
                {"role": "system", "content": "You are a Cloud FinOps security expert."},
                {
                    "role": "user",
                    "content": f"I found this anomaly in my GCP billing/usage: {anomaly_description}. What services could cause this and how do I neutralize it via gcloud CLI?",
                },
            ],
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, headers=headers, json=payload, timeout=30.0)
                if resp.status_code == 200:
                    data = resp.json()
                    advice = data["choices"][0]["message"]["content"]
                    logger.info(f"Perplexity FinOps Advice:\n{advice}")
                    # In a fully autonomous loop, we could parse the gcloud commands from this response
        except Exception as e:
            logger.error(f"Perplexity anomaly check failed: {e}")


if __name__ == "__main__":
    guardian = BillingGuardianAgent()
    guardian.enforce_billing_policies()
