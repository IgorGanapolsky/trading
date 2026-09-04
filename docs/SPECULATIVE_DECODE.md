# Speculative decoding — n-gram FORMAT steal (not TensorRT)

Linear: [AGENT-574](https://linear.app/igorganapolsky/issue/AGENT-574/speculative-decode-n-gram-draft-then-verify-nvidia-format-not-tensorrt)

Source: [NVIDIA: Co-Designing AI Models Using Speculative Decoding](https://developer.nvidia.com/blog/co-designing-ai-models-using-speculative-decoding-for-faster-llm-inference/)

## What we stole

1. **Draft-then-verify.** Propose `D` tokens; the target accepts until the first mismatch. Output matches sequential decoding (`lossless`).
2. **Suffix / n-gram drafter.** NVIDIA's table lists this as model-free, O(1) lookup, no training. That is the only mechanism we ship.
3. **Guideline 4.** Increase `D` only while measured acceptance length `AL` justifies draft cost. `estimated_speedup` is `AL / (1 + Od)` from **our** measurements, or `null`.

## What we did not ship

TensorRT-LLM, EAGLE-3/MTP/DFlash training, Model-Optimizer, SPEED-Bench as a product, NVIDIA's published speedup curves as ours, GPU GEMM/attention tile rules (need their hardware).

## Operator

```bash
python scripts/speculative_decode.py --prefix "paper spy put" \
  --corpus "paper spy put credit skip live paper spy put credit skip live" \
  --target "credit skip live blocked" --D 3
python scripts/speculative_decode.py --choose-d --max-d 8 --prefix "..." --corpus "..." --target "..."
```

Optional LLM opinions stay advisory. Hard risk limits in Python are never overridden. Paper only.
