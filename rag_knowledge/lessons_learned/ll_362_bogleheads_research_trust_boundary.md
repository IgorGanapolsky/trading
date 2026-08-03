# HIGH: Isolate forum research from trading policy and public participation

**Severity**: HIGH

## Incident

The repository contained a Bogleheads public RSS reader, but it only wrote a
flat JSON snapshot. It had no stable identifiers, document versions, chunk
metadata, deduplication, searchable index, or explicit separation from the
tool-call gate. It also had no reviewed procedure for authenticated forum
participation.

## Root Cause

Research ingestion, operational lessons, authenticated browsing, and public
posting were treated as one broad capability even though they have different
trust and evidence boundaries. Forum opinions are untrusted inputs, while a
post is an external side effect governed by the forum's current rules.

## Prevention

Ingest only bounded public forum content into an isolated, versioned SQLite
FTS5 research index with provenance, stable hashes, quality gates, and
`gate_effect: none`. Never promote forum text directly into the trading lesson
corpus or use it as broker, edge, tax, or execution evidence. Require
authoritative-source triangulation before creating a reviewed operational
lesson. Keep thread/reply drafting separate from ingestion and never submit a
public post without a specific destination, reviewed content, policy check,
and action-time authorization.

## Tags

`bogleheads` `forum-research` `trust-boundary` `public-posting` `rag-ingestion`
