#!/usr/bin/env python3
"""Archive redundant documentation files."""

import shutil
from pathlib import Path

files_to_archive = [
    "docs/CTO_REPORT.md",
    "docs/CEO_BRIEFING.md",
    "docs/CEO_VERIFICATION_GUIDE.md",
    "docs/DASHBOARD_SUMMARY.md",
    "docs/FINAL_DELIVERY_REPORT.md",
    "docs/MISSION_COMPLETE.md",
    "docs/SYSTEM_COMPLETE.md",
    "docs/AUTONOMOUS_SYSTEM_LIVE.md",
    "docs/EVALUATION_SYSTEM_WEEK1.md",
    "docs/DAY17_ANALYSIS.md",
    "docs/103_MONTH_ROI.md",
    "docs/ROI_ANALYSIS.md",
    "docs/BACKTEST_SUMMARY.txt",
    "docs/status/ALPACA_ACCOUNT_STATUS_2025-11-04.md",
    "docs/status/AUTOMATION_STATUS.md",
    "docs/CTO_CFO_DECISION_2025-11-05.md",
    "docs/CTO_CFO_DECISIONS_2025-11-20.md",
    "docs/CTO_CFO_DECISIONS_2025-11-20_DEEP_RESEARCH.md",
    "docs/SENTIMENT_INTEGRATION_REPORT.md",
    "docs/SENTIMENT_AGGREGATOR_SUMMARY.md",
    "docs/REDDIT_SENTIMENT_DELIVERY.md",
    "docs/YOUTUBE_ANALYSIS_EXECUTIVE_SUMMARY.md",
    "docs/youtube_podcast_analysis_2025-11-04.md",
    "docs/youtube_podcast_analysis_2025-11-04.json",
    "docs/PHASE1_INTEGRATION_CHECKLIST.md",
    "docs/PHASE1_INTEGRATION_UPDATED.md",
    "docs/PHASE1_REVISED.md",
    "docs/ACTIVATION_CHECKLIST.md",
    "docs/GEMINI3_READY.md",
    "docs/WORKFLOW_VERIFICATION.md",
    "docs/WORKFLOW_RECOVERY_GUIDE.md",
    "docs/WIKI_SETUP.md",
    "docs/DATA_COLLECTOR_README.md",
    "docs/REDDIT_SENTIMENT_README.md",
    "docs/ORCHESTRATOR_README.md",
    "docs/youtube_analysis/STATUS.md",
    "docs/youtube_analysis/RECOMMENDATIONS_2025-11-04_PRELIMINARY.md",
    "docs/youtube_analysis/RECOMMENDATIONS_2025-11-04_TEMPLATE.md",
    "docs/youtube_analysis/INTEGRATION_SUMMARY.md",
    "docs/youtube_analysis/REPORTING_ENHANCEMENT_SUMMARY.md",
    "docs/youtube_analysis/CEO_SUMMARY_AMZN.md",
    "docs/youtube_analysis/video_1_pltr_analysis.md",
    "docs/youtube_analysis/video_2_top_6_stocks_nov_2025.md",
    "docs/youtube_analysis/video_4_amzn_openai_deal.md",
    "docs/youtube_analysis/youtube_Why_Is_Palantir_Stock_Falling_and_is_it_a_Buying_O_20251105_153934.md",
]

if __name__ == "__main__":
    count = 0
    for file_path in files_to_archive:
        src = Path(file_path)
        if src.exists():
            dst = Path("docs/_archive") / src.relative_to("docs")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            count += 1
            print(f"📦 Archived: {file_path}")

    print(f"\n✅ Archived {count} files")
