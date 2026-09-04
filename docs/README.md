# Docs

Operator and design docs for the trading lab.

## Start here

| Doc                                                              | Audience        | Purpose                              |
| ---------------------------------------------------------------- | --------------- | ------------------------------------ |
| [operator-guide.md](./operator-guide.md)                         | Human operator  | Daily commands, gates, truth sources |
| [../skills/trading-ops/SKILL.md](../skills/trading-ops/SKILL.md) | Coding agents   | How to operate the repo safely       |
| [AGENT_COORDINATION.md](./AGENT_COORDINATION.md)                 | Multiple agents | Ownership and collision protocol     |
| [../AGENTS.md](../AGENTS.md)                                     | Agents          | Project contribution rules           |
| [../CONTRIBUTING.md](../CONTRIBUTING.md)                         | Humans + agents | PR path                              |

## Strategy & research

| Doc                                                                | Notes                                      |
| ------------------------------------------------------------------ | ------------------------------------------ |
| [operator-guide.md](./operator-guide.md)                           | Current paper strategy and operating gates |
| [research/](./research/)                                           | Edge audits and deep dives                 |
| [RAG_11_STAGES_SPECIFICATION.md](./RAG_11_STAGES_SPECIFICATION.md) | RAG pipeline stages                        |
| [GRAPH_RAG.md](./GRAPH_RAG.md)                                     | Temporal Graph RAG (strategy/lesson/trade) |
| [SUPERMEMORY.md](./SUPERMEMORY.md)                                 | Optional SuperMemory v3/v4 adapter         |
| [EXTENSIONS.md](./EXTENSIONS.md)                                   | Optional provider boundary                 |

## Pitch / archive (not operating truth)

| Doc                                      | Notes                                          |
| ---------------------------------------- | ---------------------------------------------- |
| [INVESTOR_PITCH.md](./INVESTOR_PITCH.md) | Narrative deck; verify numbers against ledgers |

## Data artifacts (generated / live)

Prefer repo-root ledgers over hardcoded README claims:

- `data/system_state.json`
- `data/trades.json`
- `data/runtime/strategy_kill_switch.json`

## Layout inspiration

Docs hub + first-class agent skill layout inspired by [Herdr](https://github.com/herdrdev/herdr)
([agent skill](https://herdr.dev/docs/agent-skill/), [plugins](https://herdr.dev/docs/plugins/)). No affiliation.
