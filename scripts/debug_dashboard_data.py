import json
from pathlib import Path

# Simulate the path logic in dashboard/pages/3_💰_Trade_Impact.py
# project_root = Path(__file__).parent.parent.parent
# We are running from root, so we simulate the relative path
current_file = Path("dashboard/pages/3_💰_Trade_Impact.py").resolve()
project_root = current_file.parent.parent.parent
data_dir = project_root / "data"

print("Diagnostic Report")
print("=================")
print(f"Current working directory: {Path.cwd()}")
print(f"Simulated project root: {project_root}")
print(f"Target data directory: {data_dir}")
print(f"Data directory exists? {data_dir.exists()}")

if data_dir.exists():
    print("\nScanning for trade files...")
    trade_files = sorted(data_dir.glob("trades_*.json"))
    print(f"Found {len(trade_files)} trade files.")

    total_trades = 0
    for f in trade_files:
        print(f"  - Reading {f.name}...", end=" ")
        try:
            with open(f) as json_file:
                data = json.load(json_file)
                count = len(data) if isinstance(data, list) else 0
                print(f"Success. ({count} trades)")
                if count > 0:
                    print(f"    Sample keys: {list(data[0].keys())}")
                total_trades += count
        except Exception as e:
            print(f"FAILED: {e}")

    print(f"\nTotal trades found: {total_trades}")
else:
    print("CRITICAL: Data directory not found!")
