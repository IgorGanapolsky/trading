# Always-on agent economics (episode FORMAT)

<!-- FORMAT steal from YT Music episode discussion of always-on consumer AI
     assistants (https://music.youtube.com/watch?v=Xa1jm2VWEHk). Not a family
     ops product / WhatsApp bot SKU. -->

**Source:** [music.youtube.com/watch?v=Xa1jm2VWEHk](https://music.youtube.com/watch?v=Xa1jm2VWEHk)

## Thesis

Highest ROI is **not** more autonomy — it is tighter scope, cheaper inference,
and a measurable trust/reliability loop.

## Mapped onto this lab

| Episode bet                     | Our rail                                               |
| ------------------------------- | ------------------------------------------------------ |
| Narrow high-frequency workflows | `ops_daily_brief` workflows only                       |
| Eval-first OS                   | `eval_first_ledger.py` candidates/actions/outcomes     |
| Tiered inference                | rules → cheap → extract → premium; HydraFusion Cascade |
| Recommend-first                 | `autonomy_default=recommend_only`; never auto-send     |
| Explicit memory                 | provenance on every alert; compact ledgers             |
| Precision > coverage            | `--alert-budget` (default 5)                           |
| Cost per retained household     | KPI: cost per fee-yes / retained ops habit             |

## Commands

```bash
python3 scripts/ops_daily_brief.py --no-log
python3 scripts/eval_first_ledger.py summary
python3 scripts/ralph_gsd_tick.py --ops-brief --no-log
```

## Defer (episode)

- General-purpose do-anything chat as the product
- Fully autonomous email/WhatsApp send
- Broad integrations before retention on core sources
- Unbounded context windows instead of compact provenance-linked memory

## KPIs

weekly retained ops habit · actionable-alert precision · correction rate ·
cost per fee-yes · % of action classes with higher autonomy granted
