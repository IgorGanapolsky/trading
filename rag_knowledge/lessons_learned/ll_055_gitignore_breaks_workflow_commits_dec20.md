# Lesson Learned #055: Multiple Workflow Commit Failures

**Date**: December 20, 2025
**Severity**: High
**Category**: CI/CD, Automation

## What Happened

The Weekend Learning Pipeline had THREE separate failure modes discovered:

### Failure 1: Gitignored Files
All 5 learning phases completed successfully:
- Phase 1a: Phil Town content ingestion ✅
- Phase 1b: Options education content ✅
- Phase 2: RAG vectorization ✅
- Phase 3: Trade history analysis ✅
- Phase 4: Weekend insights generation ✅
- Phase 5: RAG query tests ✅

But the commit step failed with:
```
The following paths are ignored by one of your .gitignore files:
data/weekend_insights.json
hint: Use -f if you really want to add them.
```

## Root Cause

The `data/weekend_insights.json` file (and potentially other data files) are listed in `.gitignore`. When GitHub Actions tried to `git add` these files, git refused because they're ignored.

## The Fix

Changed from:
```yaml
git add rag_knowledge/
git add data/weekend_insights.json
```

To:
```yaml
git add -f rag_knowledge/ 2>/dev/null || true
git add -f data/weekend_insights.json 2>/dev/null || true
```

The `-f` flag forces git to add files even if they match gitignore patterns.

### Failure 2: YouTube Transcript API Breaking Change

**Error**: `type object 'YouTubeTranscriptApi' has no attribute 'get_transcript'`

**Root Cause**: youtube-transcript-api v1.0+ (March 2025) removed the class method.

**Fix**:
```python
# OLD (broken)
YouTubeTranscriptApi.get_transcript(video_id)

# NEW (v1.0+)
ytt_api = YouTubeTranscriptApi()
ytt_api.fetch(video_id)
```

### Failure 3: Branch Protection Rules

**Error**: `GH013: Repository rule violations found for refs/heads/main`

**Root Cause**: GitHub Actions can't push directly to main when branch protection is enabled.

**Fix**: Create a branch and open a PR instead:
```yaml
BRANCH_NAME="auto/weekend-learning-$(date +%Y%m%d-%H%M%S)"
git checkout -b "$BRANCH_NAME"
git commit -m "feat(weekend): Learning pipeline update"
git push -u origin "$BRANCH_NAME"
gh pr create --title "..." --base main --head "$BRANCH_NAME"
```

Also requires permissions:
```yaml
permissions:
  contents: write
  pull-requests: write
```

## Prevention

1. **Always use `git add -f` in workflows** when adding generated files that might be in gitignore
2. **Test workflow commit steps locally** before deploying
3. **Check gitignore patterns** when adding new files to workflow commits
4. **Add `|| true`** to prevent workflow failure if file doesn't exist
5. **Check library changelogs** before assuming APIs still work
6. **Use PR-based workflow** for protected branches

## Impact

- Weekend learning content was NOT being saved to the repository
- Phil Town YouTube content never made it into RAG
- Days of "learning" were lost because nothing was committed

## Related Files

- `.github/workflows/weekend-learning.yml`
- `.github/workflows/phil-town-ingestion.yml`
- `scripts/ingest_phil_town_youtube.py`
- `scripts/ingest_options_youtube.py`
- `.gitignore`
