#!/usr/bin/env python3
"""
YouTube Podcast Analyzer
Extracts trading insights from YouTube videos using transcripts and AI analysis
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi as _YouTubeTranscriptApi

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.core.multi_llm_analysis import MultiLLMAnalyzer


class YouTubePodcastAnalyzer:
    """Analyzes YouTube podcast videos for trading insights"""

    def __init__(self, use_llm: bool = False):
        """Initialize analyzer

        Args:
            use_llm: Whether to use MultiLLM analysis (requires OpenRouter API key)
        """
        self.use_llm = use_llm
        self.llm_analyzer = None

        if use_llm:
            try:
                self.llm_analyzer = MultiLLMAnalyzer()
                print("[INFO] MultiLLM analyzer enabled")
            except ValueError as e:
                print(f"[WARNING] MultiLLM unavailable: {e}")
                print("[INFO] Using keyword-based analysis instead")
                self.use_llm = False

        self.cache_dir = Path(__file__).parent.parent / "data" / "youtube_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_video_metadata(self, video_id: str) -> dict:
        """
        Get video metadata using yt-dlp

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with video metadata
        """
        print(f"\n[INFO] Fetching metadata for video {video_id}...")

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=False
                )

                metadata = {
                    "video_id": video_id,
                    "title": info.get("title", "Unknown"),
                    "channel": info.get("channel", "Unknown"),
                    "upload_date": info.get("upload_date", "Unknown"),
                    "duration": info.get("duration", 0),
                    "description": info.get("description", ""),
                    "view_count": info.get("view_count", 0),
                }

                print(f"[SUCCESS] Title: {metadata['title']}")
                print(f"[SUCCESS] Channel: {metadata['channel']}")
                print(f"[SUCCESS] Duration: {metadata['duration']}s")

                return metadata

        except Exception as e:
            print(f"[ERROR] Failed to get metadata: {e}")
            return {
                "video_id": video_id,
                "title": "Unknown",
                "channel": "Unknown",
                "error": str(e),
            }

    def get_transcript(self, video_id: str) -> str | None:
        """
        Get video transcript using youtube-transcript-api

        Args:
            video_id: YouTube video ID

        Returns:
            Transcript text or None if unavailable
        """
        print(f"\n[INFO] Fetching transcript for video {video_id}...")

        # Check cache first
        cache_file = self.cache_dir / f"{video_id}_transcript.txt"
        if cache_file.exists():
            print("[CACHE] Using cached transcript")
            return cache_file.read_text()

        try:
            # Create instance and fetch transcript
            api = _YouTubeTranscriptApi()
            fetched = api.fetch(video_id, languages=["en"])

            # Extract text from fetched transcript snippets
            transcript_text = " ".join([snippet.text for snippet in fetched.snippets])

            # Cache the transcript
            cache_file.write_text(transcript_text)

            print(f"[SUCCESS] Transcript fetched ({len(transcript_text)} chars)")
            return transcript_text

        except Exception as e:
            print(f"[ERROR] Failed to get transcript: {e}")
            return None

    def keyword_analysis(self, transcript: str) -> dict:
        """
        Perform keyword-based analysis when LLM is unavailable

        Args:
            transcript: Video transcript text

        Returns:
            Dictionary with extracted patterns
        """
        # Define trading-related keywords and patterns
        keywords = {
            "strategies": [
                "momentum",
                "trend following",
                "mean reversion",
                "breakout",
                "swing trading",
                "day trading",
                "scalping",
                "position trading",
                "long term",
                "short term",
            ],
            "indicators": [
                "macd",
                "rsi",
                "moving average",
                "bollinger",
                "stochastic",
                "volume",
                "ema",
                "sma",
                "fibonacci",
                "pivot",
                "support",
                "resistance",
            ],
            "risk_management": [
                "stop loss",
                "position sizing",
                "risk reward",
                "drawdown",
                "risk management",
                "portfolio",
                "diversification",
                "correlation",
            ],
            "tools": [
                "python",
                "algorithm",
                "backtest",
                "machine learning",
                "ai",
                "neural",
                "reinforcement learning",
                "api",
                "automation",
                "bot",
            ],
            "performance": [
                "sharpe",
                "sortino",
                "win rate",
                "profit factor",
                "expectancy",
                "returns",
                "alpha",
                "beta",
                "volatility",
            ],
        }

        # Count keyword occurrences
        transcript_lower = transcript.lower()
        results = {}

        for category, words in keywords.items():
            found = {}
            for word in words:
                count = transcript_lower.count(word.lower())
                if count > 0:
                    found[word] = count
            if found:
                results[category] = sorted(found.items(), key=lambda x: x[1], reverse=True)

        return results

    def format_keyword_analysis(self, keyword_results: dict, metadata: dict) -> str:
        """
        Format keyword analysis as markdown

        Args:
            keyword_results: Results from keyword_analysis
            metadata: Video metadata

        Returns:
            Formatted markdown analysis
        """
        analysis = """### Keyword-Based Analysis

**Note**: This analysis uses keyword extraction. For deeper insights, enable MultiLLM analysis.

"""

        if keyword_results.get("strategies"):
            analysis += "\n**Trading Strategies Mentioned**:\n"
            for keyword, count in keyword_results["strategies"][:5]:
                analysis += f"- {keyword.title()}: {count} mentions\n"

        if keyword_results.get("indicators"):
            analysis += "\n**Technical Indicators**:\n"
            for keyword, count in keyword_results["indicators"][:5]:
                analysis += f"- {keyword.upper()}: {count} mentions\n"

        if keyword_results.get("risk_management"):
            analysis += "\n**Risk Management Topics**:\n"
            for keyword, count in keyword_results["risk_management"][:5]:
                analysis += f"- {keyword.title()}: {count} mentions\n"

        if keyword_results.get("tools"):
            analysis += "\n**Tools & Technology**:\n"
            for keyword, count in keyword_results["tools"][:5]:
                analysis += f"- {keyword.title()}: {count} mentions\n"

        if keyword_results.get("performance"):
            analysis += "\n**Performance Metrics**:\n"
            for keyword, count in keyword_results["performance"][:5]:
                analysis += f"- {keyword.title()}: {count} mentions\n"

        # Summary
        total_mentions = sum(sum(count for _, count in items) for items in keyword_results.values())

        analysis += f"""
**Summary**:
- Total trading-related keyword mentions: {total_mentions}
- Primary focus: {max(keyword_results.keys(), key=lambda k: sum(c for _, c in keyword_results[k])) if keyword_results else "Unknown"}

**Actionable Insights**:
Based on keyword frequency, this video appears to focus on:
"""

        # Top insights based on most mentioned categories
        sorted_categories = sorted(
            keyword_results.items(),
            key=lambda x: sum(count for _, count in x[1]),
            reverse=True,
        )

        for category, items in sorted_categories[:3]:
            top_item = items[0][0] if items else "N/A"
            analysis += f"- **{category.replace('_', ' ').title()}**: Focus on {top_item}\n"

        return analysis

    def analyze_transcript(self, metadata: dict, transcript: str) -> dict:
        """
        Analyze transcript for trading insights using MultiLLM or keyword analysis

        Args:
            metadata: Video metadata
            transcript: Video transcript text

        Returns:
            Dictionary with extracted insights
        """
        if self.use_llm and self.llm_analyzer:
            print("\n[INFO] Analyzing transcript with MultiLLM...")
            return self._llm_analysis(metadata, transcript)
        else:
            print("\n[INFO] Analyzing transcript with keyword extraction...")
            return self._keyword_analysis_wrapper(metadata, transcript)

    def _keyword_analysis_wrapper(self, metadata: dict, transcript: str) -> dict:
        """
        Wrapper for keyword-based analysis

        Args:
            metadata: Video metadata
            transcript: Video transcript text

        Returns:
            Dictionary with extracted insights
        """
        try:
            # Perform keyword analysis
            keyword_results = self.keyword_analysis(transcript)

            # Format as markdown
            analysis_text = self.format_keyword_analysis(keyword_results, metadata)

            print("[SUCCESS] Keyword analysis complete")

            return {
                "video_id": metadata["video_id"],
                "title": metadata["title"],
                "channel": metadata["channel"],
                "analysis": analysis_text,
                "analysis_type": "keyword",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            print(f"[ERROR] Analysis failed: {e}")
            return {
                "video_id": metadata["video_id"],
                "title": metadata["title"],
                "channel": metadata["channel"],
                "analysis": f"ERROR: {str(e)}",
                "analysis_type": "error",
                "timestamp": datetime.now().isoformat(),
            }

    def _llm_analysis(self, metadata: dict, transcript: str) -> dict:
        """
        LLM-based analysis (when OpenRouter is available)

        Args:
            metadata: Video metadata
            transcript: Video transcript text

        Returns:
            Dictionary with extracted insights
        """
        # Truncate transcript if too long (max ~15k chars for API limits)
        max_chars = 15000
        if len(transcript) > max_chars:
            print(f"[INFO] Truncating transcript from {len(transcript)} to {max_chars} chars")
            transcript = transcript[:max_chars] + "..."

        analysis_prompt = f"""
Analyze this YouTube trading podcast transcript and extract actionable insights.

VIDEO: {metadata.get("title", "Unknown")}
CHANNEL: {metadata.get("channel", "Unknown")}

TRANSCRIPT:
{transcript}

Extract the following information:

1. MAIN TOPICS (3-5 bullet points):
   - What are the primary subjects discussed?

2. TRADING STRATEGIES MENTIONED:
   - Specific strategies or systems discussed
   - Entry/exit criteria
   - Position sizing approaches

3. TECHNICAL INDICATORS:
   - Which indicators are mentioned (MACD, RSI, Volume, etc.)?
   - How are they used?
   - Specific parameter settings mentioned?

4. RISK MANAGEMENT:
   - Stop-loss approaches
   - Position sizing rules
   - Drawdown management
   - Circuit breakers

5. TOOLS & PLATFORMS:
   - Trading platforms mentioned
   - Data providers
   - Analysis tools
   - Automation approaches

6. QUANTITATIVE METHODS:
   - Backtesting approaches
   - Statistical methods
   - Machine learning / AI usage
   - Performance metrics

7. ACTIONABLE INSIGHTS:
   - Top 3-5 specific takeaways we can implement
   - Prioritized by impact and feasibility

8. RELEVANCE TO OUR SYSTEM:
   - How do these insights apply to our momentum + RL trading system?
   - Which ideas should we prioritize implementing?

Format as structured markdown with clear sections.
"""

        try:
            # Use MultiLLM for comprehensive analysis
            analysis = self.llm_analyzer.analyze_sentiment(
                symbol="YOUTUBE_ANALYSIS", context=analysis_prompt
            )

            # Extract the analysis text
            if isinstance(analysis, dict) and "summary" in analysis:
                analysis_text = analysis["summary"]
            else:
                analysis_text = str(analysis)

            print(f"[SUCCESS] LLM analysis complete ({len(analysis_text)} chars)")

            return {
                "video_id": metadata["video_id"],
                "title": metadata["title"],
                "channel": metadata["channel"],
                "analysis": analysis_text,
                "analysis_type": "llm",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            print(f"[ERROR] LLM analysis failed: {e}")
            return {
                "video_id": metadata["video_id"],
                "title": metadata["title"],
                "channel": metadata["channel"],
                "analysis": f"ERROR: {str(e)}",
                "analysis_type": "error",
                "timestamp": datetime.now().isoformat(),
            }

    def analyze_video(self, video_id: str) -> dict:
        """
        Complete analysis pipeline for a single video

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with complete analysis
        """
        print(f"\n{'=' * 80}")
        print(f"ANALYZING VIDEO: {video_id}")
        print(f"{'=' * 80}")

        # Step 1: Get metadata
        metadata = self.get_video_metadata(video_id)

        # Step 2: Get transcript
        transcript = self.get_transcript(video_id)

        if transcript is None:
            return {
                "video_id": video_id,
                "metadata": metadata,
                "error": "Transcript unavailable",
                "analysis": None,
            }

        # Step 3: Analyze
        analysis = self.analyze_transcript(metadata, transcript)

        return {
            "video_id": video_id,
            "metadata": metadata,
            "transcript_length": len(transcript),
            "analysis": analysis,
        }

    def analyze_multiple_videos(self, video_ids: list[str]) -> dict:
        """
        Analyze multiple videos and generate comprehensive report

        Args:
            video_ids: List of YouTube video IDs

        Returns:
            Dictionary with all analyses and cross-video insights
        """
        print(f"\n{'#' * 80}")
        print(f"ANALYZING {len(video_ids)} VIDEOS")
        print(f"{'#' * 80}")

        results = []

        # Analyze each video
        for i, video_id in enumerate(video_ids, 1):
            print(f"\n[PROGRESS] Video {i}/{len(video_ids)}")
            result = self.analyze_video(video_id)
            results.append(result)

        # Generate cross-video analysis
        print(f"\n{'=' * 80}")
        print("GENERATING CROSS-VIDEO ANALYSIS")
        print(f"{'=' * 80}")

        cross_analysis = self.generate_cross_video_analysis(results)

        return {
            "individual_analyses": results,
            "cross_video_analysis": cross_analysis,
            "total_videos": len(video_ids),
            "successful_analyses": sum(1 for r in results if r.get("analysis")),
            "timestamp": datetime.now().isoformat(),
        }

    def generate_cross_video_analysis(self, results: list[dict]) -> str:
        """
        Generate cross-video pattern analysis using MultiLLM or keyword aggregation

        Args:
            results: List of individual video analysis results

        Returns:
            Cross-video insights as markdown text
        """
        # Extract all successful analyses
        analyses = [
            f"VIDEO: {r['metadata']['title']}\nCHANNEL: {r['metadata']['channel']}\n\n{r['analysis']['analysis']}"
            for r in results
            if r.get("analysis") and "analysis" in r["analysis"]
        ]

        if not analyses:
            return "ERROR: No successful analyses to compare"

        # Use keyword-based cross-analysis if LLM unavailable
        if not self.use_llm or not self.llm_analyzer:
            return self._generate_keyword_cross_analysis(results)

        cross_analysis_prompt = f"""
You are analyzing multiple YouTube trading podcast videos to identify patterns and actionable insights.

Here are the individual video analyses:

{chr(10).join(["=" * 80 + chr(10) + "VIDEO " + str(i + 1) + ":" + chr(10) + "=" * 80 + chr(10) + analysis + chr(10) for i, analysis in enumerate(analyses)])}

Based on these analyses, provide:

1. COMMON THEMES (Top 5):
   - What patterns appear across multiple videos?
   - Which concepts are mentioned most frequently?

2. STRATEGY CONSENSUS:
   - Which trading strategies are most recommended?
   - Are there common entry/exit patterns?
   - What position sizing approaches are favored?

3. INDICATOR PATTERNS:
   - Which technical indicators are most popular?
   - How are they typically used together?
   - Any specific parameter settings mentioned multiple times?

4. RISK MANAGEMENT CONSENSUS:
   - Common risk management rules
   - Stop-loss best practices
   - Drawdown management approaches

5. TOOLS & TECHNOLOGY:
   - Most recommended platforms
   - Data sources mentioned
   - Automation approaches

6. PRIORITY ACTION ITEMS:
   - Top 10 specific improvements for our momentum + RL system
   - Ranked by: (1) Impact potential, (2) Ease of implementation, (3) Frequency mentioned
   - Include specific implementation notes

7. SYSTEM ENHANCEMENT ROADMAP:
   - Phase 1 (Week 1-2): Immediate wins
   - Phase 2 (Week 3-4): Medium-term improvements
   - Phase 3 (Month 2-3): Advanced features

Format as structured markdown with clear sections and actionable recommendations.
"""

        try:
            # Use MultiLLM for cross-video analysis
            cross_analysis = self.llm_analyzer.analyze_sentiment(
                symbol="CROSS_VIDEO_ANALYSIS", context=cross_analysis_prompt
            )

            if isinstance(cross_analysis, dict) and "summary" in cross_analysis:
                return cross_analysis["summary"]
            else:
                return str(cross_analysis)

        except Exception as e:
            return f"ERROR: Cross-video analysis failed: {str(e)}"

    def _generate_keyword_cross_analysis(self, results: list[dict]) -> str:
        """
        Generate cross-video analysis using keyword aggregation

        Args:
            results: List of individual video analysis results

        Returns:
            Cross-video insights as markdown text
        """
        # Aggregate all transcripts
        all_keywords = {
            "strategies": {},
            "indicators": {},
            "risk_management": {},
            "tools": {},
            "performance": {},
        }

        for result in results:
            if result.get("analysis") and result["analysis"].get("analysis_type") == "keyword":
                # Re-analyze transcript to get keyword counts
                transcript_cache = self.cache_dir / f"{result['video_id']}_transcript.txt"
                if transcript_cache.exists():
                    transcript = transcript_cache.read_text()
                    keywords = self.keyword_analysis(transcript)

                    # Aggregate
                    for category, items in keywords.items():
                        for keyword, count in items:
                            if keyword not in all_keywords[category]:
                                all_keywords[category][keyword] = 0
                            all_keywords[category][keyword] += count

        # Generate summary
        analysis = """## Cross-Video Keyword Analysis

**Analysis Method**: Keyword aggregation across all videos

"""

        for category in all_keywords:
            if all_keywords[category]:
                sorted_items = sorted(
                    all_keywords[category].items(), key=lambda x: x[1], reverse=True
                )
                analysis += f"\n### {category.replace('_', ' ').title()}\n"
                for keyword, count in sorted_items[:10]:
                    analysis += (
                        f"- **{keyword.title()}**: {count} total mentions across all videos\n"
                    )

        # Generate actionable recommendations
        analysis += """
### Priority Action Items

Based on keyword frequency across all videos, prioritize:

"""

        # Top strategies
        if all_keywords["strategies"]:
            top_strategy = max(all_keywords["strategies"].items(), key=lambda x: x[1])
            analysis += f"1. **{top_strategy[0].title()} Strategy**: Mentioned {top_strategy[1]} times - investigate implementation\n"

        # Top indicators
        if all_keywords["indicators"]:
            top_indicators = sorted(
                all_keywords["indicators"].items(), key=lambda x: x[1], reverse=True
            )[:3]
            analysis += f"2. **Technical Indicators**: Focus on {', '.join(i[0].upper() for i in top_indicators)}\n"

        # Top risk management
        if all_keywords["risk_management"]:
            top_risk = max(all_keywords["risk_management"].items(), key=lambda x: x[1])
            analysis += (
                f"3. **Risk Management**: Implement {top_risk[0]} (mentioned {top_risk[1]} times)\n"
            )

        # Top tools
        if all_keywords["tools"]:
            top_tools = sorted(all_keywords["tools"].items(), key=lambda x: x[1], reverse=True)[:3]
            analysis += f"4. **Tools/Technology**: Consider {', '.join(t[0] for t in top_tools)}\n"

        analysis += """
### Recommended Implementation Phases

**Phase 1 (Week 1-2)**: Implement most-mentioned technical indicators
**Phase 2 (Week 3-4)**: Add risk management practices from videos
**Phase 3 (Month 2-3)**: Explore automation tools and strategies

**Note**: For deeper insights, enable MultiLLM analysis with OpenRouter API key.
"""

        return analysis

    def save_report(self, analysis_results: dict, output_path: Path):
        """
        Save analysis results as markdown report

        Args:
            analysis_results: Complete analysis results
            output_path: Path to save report
        """
        print("\n[INFO] Generating markdown report...")

        report = f"""# YouTube Podcast Analysis Report

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Total Videos Analyzed**: {analysis_results["total_videos"]}
**Successful Analyses**: {analysis_results["successful_analyses"]}

---

## Cross-Video Insights

{analysis_results["cross_video_analysis"]}

---

## Individual Video Analyses

"""

        for i, result in enumerate(analysis_results["individual_analyses"], 1):
            metadata = result["metadata"]
            analysis = result.get("analysis")

            # Handle None analysis
            if analysis is None:
                analysis_text = result.get("error", "ERROR: Analysis unavailable")
            elif isinstance(analysis, dict):
                analysis_text = analysis.get("analysis", "ERROR: Analysis unavailable")
            else:
                analysis_text = str(analysis)

            report += f"""
### Video {i}: {metadata.get("title", "Unknown")}

**Channel**: {metadata.get("channel", "Unknown")}
**Video ID**: {result["video_id"]}
**URL**: https://www.youtube.com/watch?v={result["video_id"]}
**Duration**: {metadata.get("duration", 0)}s ({metadata.get("duration", 0) // 60} min)
**Upload Date**: {metadata.get("upload_date", "Unknown")}
**Transcript Length**: {result.get("transcript_length", "N/A")} chars

#### Analysis

{analysis_text}

---

"""

        # Save report
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)

        print(f"[SUCCESS] Report saved to: {output_path}")

        # Also save JSON for programmatic access
        json_path = output_path.with_suffix(".json")
        json_path.write_text(json.dumps(analysis_results, indent=2))

        print(f"[SUCCESS] JSON saved to: {json_path}")


def main():
    """Main execution"""

    # Video IDs provided by CEO
    video_ids = [
        "MTAQFCy98HQ",
        "zIiTLWLEym4",
        "KvfZI964TEM",
        "m_rPOUJprKU",
        "mr4Pw66_490",
    ]

    print("\n" + "=" * 80)
    print("YOUTUBE PODCAST ANALYZER")
    print("=" * 80)
    print(f"\nAnalyzing {len(video_ids)} videos for trading insights...")

    # Initialize analyzer
    analyzer = YouTubePodcastAnalyzer()

    # Analyze all videos
    results = analyzer.analyze_multiple_videos(video_ids)

    # Save report
    report_path = (
        Path(__file__).parent.parent
        / "docs"
        / f"youtube_podcast_analysis_{datetime.now().strftime('%Y-%m-%d')}.md"
    )
    analyzer.save_report(results, report_path)

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\nReport: {report_path}")
    print(f"JSON: {report_path.with_suffix('.json')}")
    print("\nNext steps:")
    print("1. Review the report for actionable insights")
    print("2. Prioritize implementation items")
    print("3. Integrate learnings into trading system")
    print("\n")


if __name__ == "__main__":
    main()
