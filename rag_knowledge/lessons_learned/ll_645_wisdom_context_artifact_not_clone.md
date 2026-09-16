# LL-645 — Wisdom.ai FORMAT: context as product for agents, not a SKU

Sources: [episode lRuI0imju0Y](https://music.youtube.com/watch?v=lRuI0imju0Y) (Soham Mazumdar / Wisdom.ai) and [wisdom.ai](https://www.wisdom.ai/)

## Steal (FORMAT)

1. **Context is a product**, not dashboard metadata. Packs are lintable artifacts.
2. **Agent consumer, not human BI.** Freshness, sources, and a verifier are required.
3. **Wrong-fit is a field.** Wisdom.ai ACE / Foundry / Snowflake OSI do not belong on this paper lab.

## Do not

- Clone Adaptive Context Engine, Knowledge Fabric, Palantir Foundry, or OSI.
- Buy a warehouse semantic layer to "give agents context."
- Treat tribal Slack lore as the operator memory.

## Ship

`scripts/agent_context_artifact.py lint --pack pack.json`

Complements six-block packs and `cobble_hot_path.py`. Does not replace either.

## Cash

Ops/eval only. Commercial fee-yes remains separate.
