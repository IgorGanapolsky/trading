---
description: Map Pi connectors to trading CLIs (no MCP packages)
---

# Connectors

Pi core has no MCP. Do not install third-party Pi MCP packages in this repo.

| Intent                      | Connector                                                                          |
| --------------------------- | ---------------------------------------------------------------------------------- |
| Status / equity / positions | `scripts/spy_put_credit.py --status` (or `pi_trading_bridge.py status` if present) |
| Next paper structure        | `scripts/spy_put_credit.py --dry-run`                                              |
| Exits                       | `scripts/spy_put_credit.py --manage-exits --dry-run`                               |
| n→30 gate                   | `scripts/put_credit_cohort_scorecard.py --json`                                    |
| Inventory                   | `scripts/audit_open_inventory.py`                                                  |
| Linear / GitHub             | Grok/Claude MCP already wired; do not duplicate via `pi install`                   |

Grok MCP servers (Linear, GitHub, BrowserOS) stay on Grok. Pi uses the table above.
