#!/bin/bash
# Surface RLHF feedback patterns to Claude at session start
# Created: Jan 6, 2026 - Actually implementing what was promised
#
# Purpose: Read feedback model and show Claude:
# 1. Model confidence (posterior)
# 2. Feature weights (what correlates with bad outcomes)
# 3. Recent feedback stats

CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
MODEL_FILE="$CLAUDE_PROJECT_DIR/models/ml/feedback_model.json"
STATS_FILE="$CLAUDE_PROJECT_DIR/data/feedback/stats.json"

# Check if model exists
if [ ! -f "$MODEL_FILE" ]; then
    # No model yet - that's fine
    exit 0
fi

# Read model directly with Python (minimal imports)
OUTPUT=$(python3 -c "
import json
import os

model_path = '$MODEL_FILE'
stats_path = '$STATS_FILE'

result = {'has_data': False}

if os.path.exists(model_path):
    try:
        model = json.loads(open(model_path).read())
        alpha = model.get('alpha', 1.0)
        beta = model.get('beta', 1.0)
        posterior = alpha / (alpha + beta)
        total_samples = int(alpha + beta - 2)  # Subtract priors

        # Get feature weights
        weights = model.get('feature_weights', {})
        negative_features = [(k, v) for k, v in weights.items() if v < 0]
        positive_features = [(k, v) for k, v in weights.items() if v > 0]

        result = {
            'has_data': total_samples > 0,
            'alpha': alpha,
            'beta': beta,
            'posterior': round(posterior, 3),
            'total_samples': total_samples,
            'negative_features': sorted(negative_features, key=lambda x: x[1])[:5],
            'positive_features': sorted(positive_features, key=lambda x: x[1], reverse=True)[:5],
            'last_updated': model.get('last_updated', 'unknown')
        }
    except Exception as e:
        result['error'] = str(e)

# Also get stats
if os.path.exists(stats_path):
    try:
        stats = json.loads(open(stats_path).read())
        result['stats'] = {
            'total': stats.get('total', 0),
            'positive': stats.get('positive', 0),
            'negative': stats.get('negative', 0),
            'satisfaction': stats.get('satisfaction_rate', 0)
        }
    except:
        pass

print(json.dumps(result))
" 2>/dev/null)

# Parse and display
HAS_DATA=$(echo "$OUTPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('has_data', False))" 2>/dev/null)

if [ "$HAS_DATA" = "True" ]; then
    ALPHA=$(echo "$OUTPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('alpha', 1))" 2>/dev/null)
    BETA=$(echo "$OUTPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('beta', 1))" 2>/dev/null)
    POSTERIOR=$(echo "$OUTPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('posterior', 0.5))" 2>/dev/null)
    TOTAL=$(echo "$OUTPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total_samples', 0))" 2>/dev/null)

    # Get negative features
    NEG_FEATURES=$(echo "$OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
neg = data.get('negative_features', [])
if neg:
    print(', '.join([f'{k}({v:.2f})' for k, v in neg]))
else:
    print('none detected yet')
" 2>/dev/null)

    # Get positive features
    POS_FEATURES=$(echo "$OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
pos = data.get('positive_features', [])
if pos:
    print(', '.join([f'{k}(+{v:.2f})' for k, v in pos]))
else:
    print('none detected yet')
" 2>/dev/null)

    # Get stats
    STATS_LINE=$(echo "$OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
stats = data.get('stats', {})
if stats:
    print(f\"Feedback: {stats.get('positive', 0)} thumbs up, {stats.get('negative', 0)} thumbs down ({stats.get('satisfaction', 0)}% satisfaction)\")
else:
    print('No feedback stats')
" 2>/dev/null)

    echo "═══════════════════════════════════════════════════════════"
    echo "📊 RLHF FEEDBACK MODEL (Thompson Sampling)"
    echo "═══════════════════════════════════════════════════════════"
    echo "Model: α=$ALPHA β=$BETA | Posterior: $POSTERIOR | Samples: $TOTAL"
    echo "$STATS_LINE"
    echo ""
    echo "✅ POSITIVE patterns (keep doing): $POS_FEATURES"
    echo "⚠️  NEGATIVE patterns (avoid): $NEG_FEATURES"
    echo "═══════════════════════════════════════════════════════════"
fi
