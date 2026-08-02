# Data contract

`data/` is for compact, reviewable state required to reproduce safety decisions. It is not a general output directory.

Tracked data includes canonical broker/trade ledgers, reviewed strategy state and kill-switch configuration, small fixtures, and the reviewed dependency-free lesson query index. Screenshots, caches, vector/SQLite databases, audit reports, backtests, coverage, reconciliation output, logs, training checkpoints, and duplicate public copies are local/generated.

Tests must write to `tmp_path` or another temporary directory rather than production-shaped paths. Curated source material and lessons live in `rag_knowledge/`; `data/rag/lessons_query.json` is the sole retained query artifact and is rebuilt from curated lessons.

