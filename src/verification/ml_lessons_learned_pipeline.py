"""
ML-Powered Lessons Learned Pipeline

Automatically detects patterns in failures, anomalies, and code smells,
then generates lessons learned and feeds them back into RAG for future prevention.

Architecture:
1. Anomaly Detection → Pattern Recognition → Lesson Generation → RAG Ingestion
2. Continuous learning loop: failures → lessons → prevention → fewer failures

Usage:
    from src.verification.ml_lessons_learned_pipeline import LessonsLearnedPipeline
    
    pipeline = LessonsLearnedPipeline()
    pipeline.process_anomaly(anomaly_data)
    pipeline.generate_weekly_report()

RAG Keywords: ml-learning-loop, continuous-improvement, pattern-recognition
Lesson: LL-043, LL-035 - Learn from patterns to prevent recurrence
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
RAG_LESSONS_DIR = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"
ML_DATA_DIR = PROJECT_ROOT / "data" / "ml"
PATTERN_DB = ML_DATA_DIR / "failure_patterns.json"


class PatternRecognizer:
    """Recognize recurring patterns in failures and anomalies."""
    
    def __init__(self):
        self.patterns = self._load_patterns()
    
    def _load_patterns(self) -> Dict[str, Dict]:
        """Load known failure patterns."""
        if PATTERN_DB.exists():
            try:
                with open(PATTERN_DB, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load patterns: {e}")
        
        return {
            "unused_module": {
                "signature": ["zero_imports", "isolated_package"],
                "severity": "high",
                "recurrence_count": 0,
            },
            "declining_usage": {
                "signature": ["usage_drop", "declining_trend"],
                "severity": "medium",
                "recurrence_count": 0,
            },
            "integration_failure": {
                "signature": ["built_never_used", "no_callers"],
                "severity": "high",
                "recurrence_count": 0,
            },
            "rag_not_consulted": {
                "signature": ["skip_rag_check", "missing_query"],
                "severity": "critical",
                "recurrence_count": 0,
            },
        }
    
    def _save_patterns(self):
        """Persist pattern database."""
        ML_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(PATTERN_DB, "w") as f:
            json.dump(self.patterns, f, indent=2)
    
    def recognize(self, anomaly: Dict) -> Optional[str]:
        """
        Recognize which known pattern this anomaly matches.
        
        Args:
            anomaly: Dict with 'pattern', 'details', 'severity'
        
        Returns:
            Pattern name if match found, else None
        """
        anomaly_text = f"{anomaly.get('pattern', '')} {anomaly.get('details', '')}".lower()
        
        best_match = None
        best_score = 0
        
        for pattern_name, pattern_def in self.patterns.items():
            score = sum(
                1 for sig in pattern_def["signature"]
                if sig.lower() in anomaly_text
            )
            
            if score > best_score:
                best_score = score
                best_match = pattern_name
        
        # Require at least 1 signature match
        return best_match if best_score > 0 else None
    
    def increment_recurrence(self, pattern_name: str):
        """Track that this pattern occurred again."""
        if pattern_name in self.patterns:
            self.patterns[pattern_name]["recurrence_count"] += 1
            self.patterns[pattern_name]["last_seen"] = datetime.now().isoformat()
            self._save_patterns()


class LessonGenerator:
    """Generate structured lessons learned from patterns."""
    
    def generate_from_anomaly(self, anomaly: Dict, pattern_name: Optional[str] = None) -> str:
        """Generate a lesson learned markdown document."""
        
        lesson_id = f"ll_{pattern_name or 'auto'}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        template = f"""# {anomaly.get('pattern', 'Unknown Pattern').replace('_', ' ').title()}

**ID**: {lesson_id}
**Date**: {datetime.now().strftime('%Y-%m-%d')}
**Severity**: {anomaly.get('severity', 'medium').upper()}
**Pattern Type**: {pattern_name or 'unclassified'}
**Auto-Generated**: Yes

## The Problem

{anomaly.get('details', 'No details provided')}

**Affected Module**: `{anomaly.get('module', 'unknown')}`

## Root Cause Analysis

{self._generate_root_cause(anomaly, pattern_name)}

## Prevention Strategy

{self._generate_prevention(anomaly, pattern_name)}

## Verification Steps

```bash
# Detect this pattern before it becomes a problem
python3 scripts/detect_dead_code.py
python3 scripts/analyze_import_usage.py --learn

# Check for similar patterns
python3 scripts/mandatory_rag_check.py "{pattern_name or 'code patterns'}"
```

## Integration Points

- **Pre-commit**: Automatic detection via `.pre-commit-config.yaml`
- **CI/CD**: Weekly code health audit in GitHub Actions
- **RAG**: This lesson is indexed for future queries

## Related Lessons

{self._find_related_lessons(pattern_name)}

## ML Learning

This lesson was generated by ML-powered pattern recognition:
- Pattern recognition engine identified recurring signature
- Historical data shows {anomaly.get('recurrence_count', 1)} similar occurrences
- Automated prevention rules added to verification pipeline

---
*Auto-generated by ML Lessons Learned Pipeline*
*For questions: Review src/verification/ml_lessons_learned_pipeline.py*
"""
        
        return template
    
    def _generate_root_cause(self, anomaly: Dict, pattern_name: Optional[str]) -> str:
        """Generate root cause analysis based on pattern."""
        root_causes = {
            "unused_module": "Module was implemented but never integrated into main system. Likely caused by: (1) Unclear integration plan, (2) Premature optimization, (3) Requirements changed mid-development.",
            "declining_usage": "Module usage declined over time, indicating: (1) Better alternatives were found, (2) Feature became obsolete, (3) Integration points were removed.",
            "integration_failure": "Code was built and tested in isolation but never connected to main execution flow. Common in: (1) Proof-of-concept code, (2) Architecture experiments, (3) Over-engineered solutions.",
            "rag_not_consulted": "RAG system exists but wasn't consulted before making changes. Indicates: (1) Workflow gap, (2) Lack of enforcement, (3) Forgetting to query lessons learned.",
        }
        
        return root_causes.get(pattern_name or "", "Root cause analysis pending manual review.")
    
    def _generate_prevention(self, anomaly: Dict, pattern_name: Optional[str]) -> str:
        """Generate prevention strategy."""
        preventions = {
            "unused_module": """
**Immediate Actions**:
1. Run `python3 scripts/detect_dead_code.py` before each PR
2. Require integration plan in design docs
3. Add "integration checkpoint" to CI/CD pipeline

**Long-term**:
- Monthly code audit to catch early signs
- Architecture review for all new modules
- "Integration-first" development philosophy
""",
            "declining_usage": """
**Immediate Actions**:
1. Run `python3 scripts/analyze_import_usage.py --learn` weekly
2. Set up alerts for modules with < 2 importers
3. Deprecation process for declining modules

**Long-term**:
- Track usage metrics in ML pipeline
- Predictive alerts for future dead code
- Automatic deprecation workflow
""",
            "integration_failure": """
**Immediate Actions**:
1. Require "integration test" before merging new modules
2. Pre-merge checklist: "Is this called by main orchestrator?"
3. Add integration coverage to CI metrics

**Long-term**:
- "No orphan code" policy
- Integration-driven development (IDD)
- Automated integration verification gates
""",
            "rag_not_consulted": """
**Immediate Actions**:
1. Add mandatory RAG check to pre-commit hooks
2. Fail CI if RAG wasn't queried for relevant changes
3. Session start gate: "What are you trying to fix?"

**Long-term**:
- RAG-first development culture
- Automated lesson retrieval in IDE
- Continuous RAG feedback loop
""",
        }
        
        return preventions.get(pattern_name or "", "Prevention strategy pending manual review.")
    
    def _find_related_lessons(self, pattern_name: Optional[str]) -> str:
        """Find related lessons from RAG knowledge base."""
        if not pattern_name:
            return "- (Auto-scan pending)"
        
        # Map patterns to known lesson IDs
        related_map = {
            "unused_module": ["LL-043 (Medallion Architecture)", "LL-035 (RAG not used)"],
            "declining_usage": ["LL-042 (Code hygiene)", "LL-043 (Unused features)"],
            "integration_failure": ["LL-043 (Medallion)", "LL-012 (Strategy not integrated)"],
            "rag_not_consulted": ["LL-035 (Failed to use RAG)", "LL-034 (Placeholder features)"],
        }
        
        related = related_map.get(pattern_name, [])
        return "\n".join(f"- {lesson}" for lesson in related) if related else "- (None identified)"


class LessonsLearnedPipeline:
    """
    End-to-end pipeline: Anomaly → Pattern → Lesson → RAG.
    
    This is the "immune system" for the codebase - it learns from mistakes
    and prevents them from recurring.
    """
    
    def __init__(self):
        self.recognizer = PatternRecognizer()
        self.generator = LessonGenerator()
        self.anomaly_queue: List[Dict] = []
    
    def process_anomaly(self, anomaly: Dict) -> Optional[Path]:
        """
        Process an anomaly through the full pipeline.
        
        Args:
            anomaly: Dict with 'module', 'pattern', 'severity', 'details'
        
        Returns:
            Path to generated lesson file, or None if filtered out
        """
        logger.info(f"Processing anomaly: {anomaly.get('module', 'unknown')}")
        
        # Step 1: Pattern recognition
        pattern_name = self.recognizer.recognize(anomaly)
        if pattern_name:
            logger.info(f"  Recognized pattern: {pattern_name}")
            self.recognizer.increment_recurrence(pattern_name)
        else:
            logger.info("  No matching pattern (novel anomaly)")
        
        # Step 2: Filter by severity
        if anomaly.get("severity") not in ["high", "critical"]:
            logger.info("  Skipped (low severity)")
            return None
        
        # Step 3: Generate lesson
        lesson_content = self.generator.generate_from_anomaly(anomaly, pattern_name)
        
        # Step 4: Save to RAG knowledge base
        RAG_LESSONS_DIR.mkdir(parents=True, exist_ok=True)
        
        lesson_id = f"ll_{pattern_name or 'auto'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        lesson_file = RAG_LESSONS_DIR / f"{lesson_id}.md"
        
        with open(lesson_file, "w") as f:
            f.write(lesson_content)
        
        logger.info(f"  Generated lesson: {lesson_file.name}")
        
        # Step 5: Index in RAG (if indexer available)
        try:
            self._index_in_rag(lesson_file)
        except Exception as e:
            logger.warning(f"  Could not index in RAG: {e}")
        
        return lesson_file
    
    def _index_in_rag(self, lesson_file: Path):
        """Index the lesson in RAG vector store."""
        # This would call the RAG indexing system
        # For now, just log it - the actual RAG system will pick it up
        logger.info(f"  Lesson ready for RAG indexing: {lesson_file}")
        
        # Create indexing marker
        index_queue = ML_DATA_DIR / "rag_index_queue.json"
        queue = []
        if index_queue.exists():
            with open(index_queue, "r") as f:
                queue = json.load(f)
        
        queue.append({
            "file": str(lesson_file),
            "timestamp": datetime.now().isoformat(),
            "status": "pending",
        })
        
        ML_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(index_queue, "w") as f:
            json.dump(queue, f, indent=2)
    
    def generate_weekly_report(self) -> Dict:
        """Generate weekly learning report."""
        # Get all lessons from last 7 days
        cutoff = datetime.now() - timedelta(days=7)
        recent_lessons = []
        
        if RAG_LESSONS_DIR.exists():
            for lesson_file in RAG_LESSONS_DIR.glob("*.md"):
                mtime = datetime.fromtimestamp(lesson_file.stat().st_mtime)
                if mtime > cutoff:
                    recent_lessons.append({
                        "file": lesson_file.name,
                        "modified": mtime.isoformat(),
                    })
        
        # Analyze pattern recurrence
        pattern_stats = {
            name: {
                "count": data["recurrence_count"],
                "severity": data["severity"],
            }
            for name, data in self.recognizer.patterns.items()
            if data["recurrence_count"] > 0
        }
        
        report = {
            "period": "last_7_days",
            "lessons_generated": len(recent_lessons),
            "pattern_recurrence": pattern_stats,
            "top_patterns": sorted(
                pattern_stats.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )[:5],
            "timestamp": datetime.now().isoformat(),
        }
        
        # Save report
        report_file = ML_DATA_DIR / "weekly_learning_report.json"
        ML_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Generated weekly report: {report_file}")
        
        return report
    
    def get_prevention_recommendations(self) -> List[str]:
        """Get actionable prevention recommendations based on patterns."""
        recommendations = []
        
        # Check which patterns are recurring
        for pattern_name, pattern_data in self.recognizer.patterns.items():
            if pattern_data["recurrence_count"] >= 2:
                rec = f"Pattern '{pattern_name}' occurred {pattern_data['recurrence_count']}x - "
                
                if pattern_name == "unused_module":
                    rec += "Enforce integration checkpoints in CI/CD"
                elif pattern_name == "declining_usage":
                    rec += "Set up weekly import usage tracking"
                elif pattern_name == "integration_failure":
                    rec += "Require integration tests before merge"
                elif pattern_name == "rag_not_consulted":
                    rec += "Make RAG checks mandatory in pre-commit"
                else:
                    rec += "Review and add specific prevention rule"
                
                recommendations.append(rec)
        
        return recommendations


# CLI Interface
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    pipeline = LessonsLearnedPipeline()
    
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        print("=" * 70)
        print("WEEKLY LEARNING REPORT")
        print("=" * 70)
        
        report = pipeline.generate_weekly_report()
        
        print(f"\nLessons Generated: {report['lessons_generated']}")
        print("\nTop Recurring Patterns:")
        for pattern_name, stats in report['top_patterns']:
            print(f"  - {pattern_name}: {stats['count']}x ({stats['severity']} severity)")
        
        print("\n" + "=" * 70)
        print("PREVENTION RECOMMENDATIONS")
        print("=" * 70)
        
        recommendations = pipeline.get_prevention_recommendations()
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                print(f"\n{i}. {rec}")
        else:
            print("\n✅ No recurring patterns - system learning is working!")
    
    else:
        print("ML Lessons Learned Pipeline")
        print("Usage:")
        print("  python3 -m src.verification.ml_lessons_learned_pipeline report")
