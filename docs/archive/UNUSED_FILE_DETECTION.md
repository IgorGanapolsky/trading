# Unused File Detection System

**Created**: November 23, 2025
**Purpose**: Automatically detect and report orphaned files in the codebase
**Location**: `.claude/hooks/detect-unused-files.sh`
**Integrated**: Pre-commit hook (warnings only, non-blocking)

---

## Overview

The Unused File Detection System scans the entire codebase to identify files that are no longer referenced or used, helping maintain a clean and efficient repository.

### What It Detects

1. **Python files** never imported by other files
2. **JSON/data files** never referenced in code
3. **Documentation files** never linked from other docs
4. **Test files** for code that doesn't exist
5. **Scripts** never called by other scripts or workflows
6. **Config files** for tools not in requirements.txt

---

## How It Works

### Detection Methods

#### 1. Age Analysis
- Checks git history for last modification date
- Flags files not modified in **90+ days** (configurable)
- Untracked files use filesystem timestamps

#### 2. Reference Counting
- **Python imports**: Searches for `import module`, `from x import module`
- **JSON/data references**: Searches for filename in `.py` and `.sh` files
- **Documentation links**: Searches for links in other `.md` files
- **Script calls**: Searches for script name in code/workflows
- **Config usage**: Cross-references with `requirements.txt`

#### 3. Special Case Handling
- **Test files**: Checks if corresponding source file exists
- **Config files**: Validates tool is installed
- **Whitelisted files**: Always kept (README.md, main.py, etc.)

---

## Output Format

### Color-Coded Results

```bash
🗑️ UNUSED FILE DETECTION REPORT

HIGH CONFIDENCE (safe to delete):
  ❌ src/old_module.py (last used: 120 days ago, no imports/references)
  ❌ data/old_data.json (last used: 180 days ago, never referenced)
  ❌ tests/test_removed_feature.py (last used: 95 days ago, test for non-existent code)

MEDIUM CONFIDENCE (review before delete):
  ⚠️ scripts/legacy_script.py (last used: 95 days ago, 1 reference)
  ⚠️ docs/OLD_GUIDE.md (last used: 100 days ago, 2 references)

SUMMARY:
  High Confidence: 3 files
  Medium Confidence: 2 files
  Active Files: 45 files
```

### Classification Levels

| Level | Criteria | Action |
|-------|----------|--------|
| **High Confidence** | 0 references, 90+ days old | Safe to delete |
| **Medium Confidence** | 1-2 references, 90+ days old | Review before delete |
| **Keep** | 3+ references or <90 days | Actively used |

---

## Configuration

### Threshold Adjustment

Edit `.claude/hooks/detect-unused-files.sh`:

```bash
# Default: 90 days
DAYS_THRESHOLD=90

# More aggressive: 60 days
DAYS_THRESHOLD=60

# More conservative: 120 days
DAYS_THRESHOLD=120
```

### Whitelist Management

Add files that should never be flagged:

```bash
WHITELIST=(
    "main.py"
    "README.md"
    "LICENSE"
    ".gitignore"
    # Add your files here
    "scripts/critical_script.py"
    "docs/IMPORTANT_GUIDE.md"
)
```

---

## Usage

### Manual Execution

Run standalone anytime:

```bash
# From repository root
./.claude/hooks/detect-unused-files.sh

# With verbose output
bash -x ./.claude/hooks/detect-unused-files.sh
```

### Automatic Execution

Runs automatically on every commit via pre-commit hook:

```bash
git commit -m "your message"

# Output includes:
# 🧹 Running repository hygiene check...
# 🔍 Scanning for unused files (threshold: 90+ days, no references)...
# ✅ No unused files detected! Codebase is clean.
```

### CI/CD Integration

Add to GitHub Actions workflow:

```yaml
- name: Detect Unused Files
  run: |
    bash .claude/hooks/detect-unused-files.sh
    # Exit 0 always (warnings only)
```

---

## Examples

### Example 1: Orphaned Python Module

```bash
❌ src/deprecated/old_strategy.py (last used: 150 days ago, no imports/references)
```

**Analysis**:
- File is 150 days old (5 months)
- No other Python file imports it
- Safe to delete

**Action**:
```bash
git rm src/deprecated/old_strategy.py
git commit -m "Remove unused old_strategy.py module"
```

---

### Example 2: Orphaned Test File

```bash
❌ tests/test_removed_feature.py (last used: 95 days ago, test for non-existent code)
```

**Analysis**:
- Test file for `src/removed_feature.py` which no longer exists
- Test suite may still pass but testing nothing

**Action**:
```bash
git rm tests/test_removed_feature.py
git commit -m "Remove test for deleted feature"
```

---

### Example 3: Unused Config File

```bash
❌ .pylintrc (last used: 120 days ago, config for non-installed tool)
```

**Analysis**:
- Config file for `pylint`
- `requirements.txt` doesn't include `pylint`
- Config is useless

**Action**:
```bash
git rm .pylintrc
git commit -m "Remove unused pylint config"
```

---

### Example 4: Medium Confidence (Review Needed)

```bash
⚠️ scripts/experimental.py (last used: 95 days ago, 1 reference)
```

**Analysis**:
- Has 1 reference (might be in a comment or old doc)
- Need to investigate before deleting

**Action**:
```bash
# Find the reference
grep -r "experimental.py" .

# Review context
# If obsolete → delete
# If active → keep
```

---

## Best Practices

### Weekly Cleanup Routine

```bash
# 1. Run detection
./.claude/hooks/detect-unused-files.sh > unused_files_report.txt

# 2. Review high confidence files
grep "HIGH CONFIDENCE" unused_files_report.txt

# 3. Delete confirmed unused files
git rm <file1> <file2> ...

# 4. Commit cleanup
git commit -m "chore: Remove unused files (weekly cleanup)"
```

### Monthly Deep Clean

```bash
# 1. Lower threshold to 60 days
# Edit DAYS_THRESHOLD=60 in script

# 2. Run detection
./.claude/hooks/detect-unused-files.sh

# 3. Review all medium confidence files
# 4. Archive to separate branch if uncertain
```

---

## Integration with Pre-commit Hook

The script is **non-blocking** - it shows warnings but never prevents commits:

```bash
# Pre-commit hook calls:
if [ -f ".claude/hooks/detect-unused-files.sh" ]; then
    bash .claude/hooks/detect-unused-files.sh
fi
# Exit code: always 0 (warnings only)
```

**Rationale**:
- Unused files aren't urgent (don't block work)
- Developers can review and clean up at their own pace
- Maintains awareness without disrupting workflow

---

## Performance

### Scan Time

| Codebase Size | Scan Time |
|---------------|-----------|
| Small (<100 files) | 1-2 seconds |
| Medium (100-500 files) | 3-5 seconds |
| Large (500-1000 files) | 5-10 seconds |
| Very Large (1000+ files) | 10-20 seconds |

### Optimization Tips

```bash
# Skip certain directories
# Add to script:
git ls-files | grep -v "^vendor/" | grep -v "^node_modules/"

# Limit file types
# Modify detection loops to only check specific extensions
```

---

## Troubleshooting

### Issue: False Positives

**Symptom**: Active files flagged as unused

**Causes**:
1. Dynamic imports not detected (`importlib.import_module()`)
2. Config files with non-standard names
3. Files used only by external tools

**Solution**:
```bash
# Add to whitelist
WHITELIST=(
    "path/to/false/positive.py"
)

# Or reduce threshold
DAYS_THRESHOLD=120
```

---

### Issue: Missing Detections

**Symptom**: Known unused files not flagged

**Causes**:
1. Files modified recently (within threshold)
2. False references (mentioned in comments)
3. Whitelisted by mistake

**Solution**:
```bash
# Lower threshold temporarily
DAYS_THRESHOLD=30

# Check specific file manually
git log --follow -- path/to/file.py
grep -r "file.py" .
```

---

## Metrics & Goals

### Current Status (November 23, 2025)

```
✅ No unused files detected! Codebase is clean.
```

### Target Metrics

- **Zero unused files** in production codebase
- **Monthly cleanup** routine established
- **<5% false positive rate**

### Success Criteria

- [ ] All unused files over 90 days removed
- [ ] Pre-commit integration working smoothly
- [ ] Zero false positives in whitelist
- [ ] Documentation up-to-date

---

## Future Enhancements

### Planned Features

1. **Auto-archiving**: Move unused files to `archive/` branch instead of deleting
2. **Dependency graph**: Visualize file usage relationships
3. **AI-powered analysis**: Use LLM to classify uncertain cases
4. **Integration with IDE**: Show unused file warnings in editor
5. **Historical tracking**: Log cleanup over time, measure codebase health

### Research Areas

- Dead code detection within files (not just whole files)
- Circular dependency detection
- Unused function/class detection
- Import optimization recommendations

---

## Related Documentation

- [Pre-commit Hygiene](../docs/PRECOMMIT_HYGIENE.md)
- [File Size Limits](../.claude/hooks/check-file-sizes.sh)
- [Documentation Structure](../.claude/hooks/check-documentation.sh)

---

## Changelog

**November 23, 2025**:
- ✅ Initial implementation
- ✅ Pre-commit integration
- ✅ Documentation created
- ✅ Tested on codebase (clean result)
