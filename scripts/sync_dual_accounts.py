import logging
import os

from alpaca.trading.client import TradingClient
from dotenv import load_dotenv
from src.utils.alpaca_client import get_alpaca_credentials, get_brokerage_credentials

# Load environment variables from .env
load_dotenv()

# Silence logging for the sync script
logging.getLogger("src.utils.alpaca_client").setLevel(logging.WARNING)


def main():
    try:
        # 1. Connect to Lab ($100K Paper)
        p_key, p_secret = get_alpaca_credentials()
        if not p_key:
            print("❌ LAB: Paper credentials NOT found in .env!")
            # Debug: print env keys present
            print(f"Env keys present: {[k for k in os.environ if 'ALPACA' in k]}")
            return
        paper_client = TradingClient(p_key, p_secret, paper=True)
        paper_acc = paper_client.get_account()

        # 2. Connect to Field ($200 Live)
        l_key, l_secret = get_brokerage_credentials()
        if not l_key:
            print("❌ FIELD: Brokerage credentials NOT found in .env!")
            return
        live_client = TradingClient(l_key, l_secret, paper=False)
        live_acc = live_client.get_account()

        print("--- DUAL-TRACK SYNC COMPLETE ---")
        print(
            f"LAB ($100K Paper):  ${float(paper_acc.equity):,.2f} [Account: {paper_acc.account_number}]"
        )
        print(
            f"FIELD ($200 Live):  ${float(live_acc.equity):,.2f} [Account: {live_acc.account_number}]"
        )
        print("Strategy Status:    AI-Native Shadowing Active")
        print("North Star Target:  $6,000/month after-tax")

    except Exception as e:
        print(f"❌ FAILED to sync: {e}")


if __name__ == "__main__":
    main()
