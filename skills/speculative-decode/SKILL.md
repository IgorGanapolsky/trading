---
name: speculative-decode
description: >
  N-gram draft-then-verify for trading LLM text (NVIDIA FORMAT). Measure AL.
  Do not vendor TensorRT-LLM or train EAGLE. Slash: /speculative-decode.
---

# Speculative decode (trading)

```bash
python scripts/speculative_decode.py --prefix "..." --corpus "..." --target "..." --D 7
python scripts/speculative_decode.py --choose-d --max-d 16 --prefix "..." --corpus "..." --target "..."
```

`AL` must be measured. `estimated_speedup` is null without AL. Does not override TradeGateway.
