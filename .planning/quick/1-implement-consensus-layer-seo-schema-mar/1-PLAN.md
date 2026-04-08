---
phase: quick-seo-schema-mar
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/_posts/2026-03-23-iron-condor-71k-trade-study.md
  - docs/llms.txt
  - docs/_includes/schema_org.html
  - docs/_layouts/post.html
autonomous: true
requirements: [SEO-01, SEO-02, SEO-03]

must_haves:
  truths:
    - "Blog post on 71K trade study exists and is published at a canonical URL"
    - "Schema.org JSON-LD markup is injected into post pages"
    - "llms.txt reflects the new post and updated content snapshot"
  artifacts:
    - path: "docs/_posts/2026-03-23-iron-condor-71k-trade-study.md"
      provides: "71K trade study blog post with full frontmatter and content"
    - path: "docs/_includes/schema_org.html"
      provides: "Reusable JSON-LD schema snippet for Article/BlogPosting type"
    - path: "docs/llms.txt"
      provides: "Updated LLM manifest with new post and current snapshot counts"
  key_links:
    - from: "docs/_layouts/post.html"
      to: "docs/_includes/schema_org.html"
      via: "Jekyll include"
      pattern: "include schema_org.html"
    - from: "docs/_posts/2026-03-23-iron-condor-71k-trade-study.md"
      to: "rag_knowledge/lessons_learned/LL-323_Iron_Condor_Management_71K_Study_Jan31.md"
      via: "content derived from"
      pattern: "71,417"
---

<objective>
Ship three SEO deliverables for the AI Trading Journey site: (1) a blog post adapting the
LL-323 iron condor 71K-trade study, (2) structured Schema.org JSON-LD markup injected into
post pages, and (3) an updated llms.txt manifest that reflects current content.

Purpose: Improve search discoverability for high-value "iron condor management" queries and
make content machine-readable for LLM crawlers.
Output: One new Jekyll post, one schema include, one updated manifest.
</objective>

<execution_context>
@/Users/ganapolsky_i/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ganapolsky_i/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/ganapolsky_i/workspace/git/igor/trading/.planning/STATE.md
@/Users/ganapolsky_i/workspace/git/igor/trading/docs/_config.yml
@/Users/ganapolsky_i/workspace/git/igor/trading/docs/index.md
@/Users/ganapolsky_i/workspace/git/igor/trading/docs/llms.txt
@/Users/ganapolsky_i/workspace/git/igor/trading/rag_knowledge/lessons_learned/LL-323_Iron_Condor_Management_71K_Study_Jan31.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Publish 71K Iron Condor Trade Study Blog Post</name>
  <files>docs/_posts/2026-03-23-iron-condor-71k-trade-study.md</files>
  <action>
Create a Jekyll blog post at `docs/_posts/2026-03-23-iron-condor-71k-trade-study.md` derived
from LL-323. Use this exact frontmatter:

```yaml
---
title: "What 71,417 Iron Condor Trades Teach Us About Management"
date: 2026-03-23
last_modified_at: "2026-03-23"
description: "Analysis of 71,417 SPY iron condor trades (2007-2017) reveals the 50% profit target and 7 DTE exit rules that maximize capital efficiency and win rate."
tags: [iron-condor, options-strategy, backtesting, spy, capital-efficiency, win-rate]
categories: [research]
canonical_url: https://igorganapolsky.github.io/trading/2026/03/23/iron-condor-71k-trade-study/
image: /trading/assets/og-image.png
schema_type: BlogPosting
---
```

Post body (markdown, ~500 words) must cover:
1. Intro: 71,417 trades, SPY, 2007-2017, two delta setups (16-delta vs 30-delta)
2. Key finding table: Profit Target | Win Rate | Avg Days Held (25%/50%/75%/expiration)
3. Section: "The 50%/50% Rule" — why 50% profit target + 200% stop-loss transforms risk:reward from 3:1 to 1.5:1
4. Section: "VIX Regime Matters" — 30-delta condors in VIX > 20 significantly outperform
5. Section: "Capital Efficiency" — 2-3 trades/month vs 1 at expiration = 24-36 capital turns/year
6. Section: "How We Apply This" — our 15-20 delta setup, 50% profit close, 7 DTE exit (cite LL-268)
7. Closing: link to sources (projectfinance.com study, arXiv 2501.12397)

Do NOT fabricate numbers. Use only values present in LL-323 verbatim.
  </action>
  <verify>
    Check file exists: `ls -la docs/_posts/2026-03-23-iron-condor-71k-trade-study.md`
    Confirm key numbers present: `grep "71,417\|50%\|85%" docs/_posts/2026-03-23-iron-condor-71k-trade-study.md`
  </verify>
  <done>File exists at correct path, contains 71,417, win rate tables, and 50%/50% rule section. Frontmatter includes schema_type field.</done>
</task>

<task type="auto">
  <name>Task 2: Add Schema.org JSON-LD Include and Wire to Post Layout</name>
  <files>docs/_includes/schema_org.html, docs/_layouts/post.html</files>
  <action>
Step A — Create `docs/_includes/schema_org.html`:

```html
{% if page.schema_type %}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "{{ page.schema_type | default: 'BlogPosting' }}",
  "headline": {{ page.title | jsonify }},
  "description": {{ page.description | jsonify }},
  "datePublished": "{{ page.date | date_to_xmlschema }}",
  "dateModified": "{{ page.last_modified_at | default: page.date | date_to_xmlschema }}",
  "author": {
    "@type": "Person",
    "name": "Igor Ganapolsky"
  },
  "publisher": {
    "@type": "Organization",
    "name": "AI Trading Journey",
    "url": "https://igorganapolsky.github.io/trading/"
  },
  "url": "{{ page.canonical_url | default: page.url | absolute_url }}",
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": "{{ page.canonical_url | default: page.url | absolute_url }}"
  }{% if page.image %},
  "image": "{{ page.image | absolute_url }}"{% endif %}
}
</script>
{% endif %}
```

Step B — Read `docs/_layouts/post.html`. If it does not exist, read `docs/_layouts/default.html`
or check `_layouts/` for the active post layout used by theme minima. Minima uses its own gem
layouts; if no override file exists, create `docs/_layouts/post.html` that extends minima by
adding the include just before `</head>` or at top of `<body>`:

```html
---
layout: default
---
{% include schema_org.html %}
{{ content }}
```

If `docs/_layouts/post.html` already exists, add `{% include schema_org.html %}` as the first
line after the frontmatter closing `---` (before any existing `{{ content }}`).

Do NOT modify theme gem files. Only add/edit files inside `docs/`.
  </action>
  <verify>
    `ls docs/_includes/schema_org.html`
    `grep "schema_org" docs/_layouts/post.html`
    `grep "application/ld+json" docs/_includes/schema_org.html`
  </verify>
  <done>`docs/_includes/schema_org.html` exists with valid JSON-LD template. `docs/_layouts/post.html` includes the schema_org snippet. Posts with `schema_type` in frontmatter will render structured data.</done>
</task>

<task type="auto">
  <name>Task 3: Update llms.txt Manifest</name>
  <files>docs/llms.txt</files>
  <action>
Read `docs/llms.txt`. Update the following fields only — do not change anything else:

1. `Blog posts published:` — increment from 58 to 59
2. `Latest blog post date:` — change from `2026-02-23` to `2026-03-23`
3. Under `## Recent Posts`, prepend (do not remove existing entries, just add at top):
   ```
   - [What 71,417 Iron Condor Trades Teach Us About Management](https://igorganapolsky.github.io/trading/2026/03/23/iron-condor-71k-trade-study/) - 2026-03-23
   ```
   Remove the oldest entry at the bottom of the Recent Posts list to keep the list at 12 items.

Note: llms.txt says it is auto-generated by `scripts/generate_llms_manifest.py`. Edit it
directly here since the generator runs on CI and will next run after this commit. The manual
edit is the source data; CI will overwrite counts on next run. This is the correct flow.
  </action>
  <verify>
    `grep "Blog posts published: 59" docs/llms.txt`
    `grep "2026-03-23" docs/llms.txt`
    `grep "71,417" docs/llms.txt`
  </verify>
  <done>llms.txt shows 59 posts, latest date 2026-03-23, and new post URL in Recent Posts section.</done>
</task>

</tasks>

<verification>
After all tasks:
1. `ls docs/_posts/2026-03-23-iron-condor-71k-trade-study.md` — exists
2. `grep "71,417" docs/_posts/2026-03-23-iron-condor-71k-trade-study.md` — finds study data
3. `grep "application/ld+json" docs/_includes/schema_org.html` — schema include present
4. `grep "schema_org" docs/_layouts/post.html` — wired to layout
5. `grep "Blog posts published: 59" docs/llms.txt` — manifest updated
</verification>

<success_criteria>
- Blog post at `docs/_posts/2026-03-23-iron-condor-71k-trade-study.md` with correct frontmatter and LL-323 data
- Schema.org JSON-LD include renders for posts with `schema_type` frontmatter key
- llms.txt reflects 59 posts, new post URL, date 2026-03-23
- No fabricated numbers — all stats match LL-323 exactly
</success_criteria>

<output>
After completion, create `.planning/quick/1-implement-consensus-layer-seo-schema-mar/1-SUMMARY.md`
</output>
