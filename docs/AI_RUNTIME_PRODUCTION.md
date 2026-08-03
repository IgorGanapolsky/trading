# AI runtime production contract

This contract covers optional LLM and retrieval decision support. It does not
authorize live trading, establish strategy edge, or replace the deterministic
risk and broker-reconciliation gates.

## Boundaries

- Order authorization remains deterministic Python.
- Runtime telemetry accepts identifiers, scores, counts, versions, and route
  metadata. It has no prompt or response parameter.
- Prompt, response, authorization, password, secret, and API-key attributes are
  redacted before persistence.
- A telemetry write failure increments `dropped_spans`, records
  `last_write_error`, and makes `persistence_healthy` false. It is never silently
  reported as healthy.
- Missing LLM credentials produce a warning and the explicit summary
  `deterministic paths only`; they do not produce a false configured status.

## Required trace chain

Use one `trace_id` across retrieval, model calls, schema validation, tool calls,
deterministic gates, and broker reconciliation. Each operation emits one child
span containing only the metadata appropriate to that stage.

Required LLM metadata:

- provider, route, and model
- prompt and completion token counts
- latency and estimated cost basis
- schema name and validation result
- retry, timeout, error, or abstention outcome

Required retrieval metadata:

- tenant and ACL decision
- index and corpus version
- cache hit or miss
- lexical, dense, and rerank scores
- result count, retrieval miss, stale index, or permission denial outcome

## Health acceptance

Production AI health is acceptable only when route reporting is truthful,
structured telemetry persistence is healthy, schema failures and abstentions are
visible, and the trace contains no prompt, response, or credential material.
Provider-private logging is supplemental and must not be described as covering
traffic that used another provider or gateway.
