# LLM response cache (TNS FORMAT)

<!-- FORMAT steal from The New Stack "Why an old caching trick is your secret
     to lower LLM costs" (Abhilash Rao Mesala, Sep 2026). Not Redis SaaS,
     not provider prompt-cache product. -->

**Source:** [Why an old caching trick is your secret to lower LLM costs](https://thenewstack.io/llm-response-caching-costs/)

## Steal

| Idea                          | Our rail                                                         |
| ----------------------------- | ---------------------------------------------------------------- |
| Exact-match fingerprint       | `SHA-256(normalize(query, ctx, model, settings, source, scope))` |
| Response cache ≠ prompt cache | Skip the model call entirely when hit                            |
| TTL by staleness judgment     | `CATEGORY_TTL` (market/creative/personal = 0)                    |
| Scope isolation               | Different `scope` → different keys                               |
| Validate before write-back    | `is_valid_response` refuses empty/error poison                   |
| Shadow mode                   | `--shadow` logs would-return without serving                     |
| Measure before projecting     | `stats.hit_rate` required before savings claims                  |

## Commands

```bash
python3 scripts/llm_response_cache.py demo
python3 scripts/llm_response_cache.py get --query "…" --category docs
python3 scripts/llm_response_cache.py stats
python3 scripts/ralph_gsd_tick.py --llm-cache-stats
```

## NEVER

- Cache live SPY quotes / personal secrets / creative one-offs
- Share cache entries across access scopes
- Claim % savings without measured hit_rate
- Confuse Anthropic/OpenAI prompt-cache discounts with this gate
