# Search stack FORMAT (LinkedIn Engineering)

<!-- FORMAT steal from LinkedIn "Reimagining LinkedIn’s search tech stack"
     (Jan 2026). Not LinkedIn GPU EBR / SGLang / Venice product. -->

**Source:** [Reimagining LinkedIn’s search tech stack](https://www.linkedin.com/blog/engineering/search/reimagining-linkedins-search-stack)

## Steal

| LinkedIn idea                         | Our rail                                 |
| ------------------------------------- | ---------------------------------------- |
| Query understanding (intent + facets) | `understand_query`                       |
| Keyword vs semantic routing           | `route: keyword\|semantic`               |
| Broad retrieve → depth-limited rank   | `ranking_depth_controller`               |
| Score cache                           | `data/runtime/search_score_cache/`       |
| Explain snippets                      | `explain_snippet` with highlighted terms |
| Product-policy grades 0–4             | `policy_grade` + precision@3 hook        |
| Maps to existing zg hybrid            | zg_search when importable                |

## Automation

Integrated tick can probe search health; agents call `search_stack_pipeline`
instead of ad-hoc greps for NL operator questions.

## NEVER

- Claim LinkedIn-scale QPS / GPU exhaustive KNN
- Train SLM teachers here
- Skip keyword route for exact symbol lookups
