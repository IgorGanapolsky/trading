#!/usr/bin/env python3
"""
Generate Enhanced Dashboard with Category Breakdowns and Graphs

Creates a comprehensive dashboard with:
- Category-specific P/L breakdowns
- Interactive graphs and charts
- Clickable sections
- Time series analysis
"""

import json

import matplotlib

matplotlib.use('Agg')  # Non-interactive backend
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

# Set style
plt.style.use('seaborn-v0_8-darkgrid')


class DashboardGenerator:
    """Generate enhanced dashboard with graphs."""

    def __init__(self):
        self.data_dir = Path('data')
        self.wiki_dir = Path('wiki')
        self.graphs_dir = self.wiki_dir / 'graphs'
        self.graphs_dir.mkdir(parents=True, exist_ok=True)

        self.performance_file = self.data_dir / 'enhanced_performance_log.json'
        self.system_state_file = self.data_dir / 'system_state.json'

    def load_data(self) -> dict:
        """Load all necessary data."""
        data = {
            'performance_log': [],
            'system_state': {},
            'latest_snapshot': None
        }

        # Load performance log
        if self.performance_file.exists():
            with open(self.performance_file) as f:
                data['performance_log'] = json.load(f)
                if data['performance_log']:
                    data['latest_snapshot'] = data['performance_log'][-1]

        # Load system state
        if self.system_state_file.exists():
            with open(self.system_state_file) as f:
                data['system_state'] = json.load(f)

        return data

    def generate_allocation_pie_chart(self, snapshot: dict) -> str:
        """Generate allocation pie chart by category."""

        categories = ['Crypto', 'Equities', 'Options', 'Bonds']
        values = [
            snapshot.get('crypto', {}).get('current_value', 0),
            snapshot.get('equities', {}).get('current_value', 0),
            snapshot.get('options', {}).get('current_value', 0),
            snapshot.get('bonds', {}).get('current_value', 0)
        ]

        # Filter out zero values
        data = [(cat, val) for cat, val in zip(categories, values) if val > 0]

        if not data:
            return None

        categories, values = zip(*data)

        # Create pie chart
        fig, ax = plt.subplots(figsize=(10, 7))
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
        explode = [0.05] * len(values)

        wedges, texts, autotexts = ax.pie(
            values,
            labels=categories,
            autopct='%1.1f%%',
            startangle=90,
            colors=colors,
            explode=explode,
            shadow=True
        )

        # Beautify
        for text in texts:
            text.set_fontsize(12)
            text.set_weight('bold')

        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(10)
            autotext.set_weight('bold')

        ax.set_title('Portfolio Allocation by Category', fontsize=16, weight='bold', pad=20)

        # Save
        filepath = self.graphs_dir / 'allocation_pie.png'
        plt.tight_layout()
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def generate_category_pl_bar_chart(self, snapshot: dict) -> str:
        """Generate P/L bar chart by category."""

        categories = ['Crypto', 'Equities', 'Options', 'Bonds']
        realized = [
            snapshot.get('crypto', {}).get('realized_pl', 0),
            snapshot.get('equities', {}).get('realized_pl', 0),
            snapshot.get('options', {}).get('realized_pl', 0),
            snapshot.get('bonds', {}).get('realized_pl', 0)
        ]
        unrealized = [
            snapshot.get('crypto', {}).get('unrealized_pl', 0),
            snapshot.get('equities', {}).get('unrealized_pl', 0),
            snapshot.get('options', {}).get('unrealized_pl', 0),
            snapshot.get('bonds', {}).get('unrealized_pl', 0)
        ]

        # Create bar chart
        fig, ax = plt.subplots(figsize=(12, 7))

        x = range(len(categories))
        width = 0.35

        bars1 = ax.bar([i - width/2 for i in x], realized, width, label='Realized P/L', color='#4ECDC4')
        bars2 = ax.bar([i + width/2 for i in x], unrealized, width, label='Unrealized P/L', color='#FF6B6B')

        # Add value labels on bars
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                if height != 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'${height:.2f}',
                           ha='center', va='bottom' if height > 0 else 'top',
                           fontsize=9, weight='bold')

        ax.set_xlabel('Category', fontsize=12, weight='bold')
        ax.set_ylabel('P/L ($)', fontsize=12, weight='bold')
        ax.set_title('P/L by Category', fontsize=16, weight='bold', pad=20)
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.legend(fontsize=10)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax.grid(True, alpha=0.3)

        # Save
        filepath = self.graphs_dir / 'category_pl_bars.png'
        plt.tight_layout()
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def generate_time_series(self, performance_log: list[dict]) -> str:
        """Generate time series of total P/L."""

        if len(performance_log) < 2:
            return None

        dates = []
        total_pl = []

        for entry in performance_log:
            date_str = entry.get('date', entry.get('timestamp', ''))
            if date_str:
                try:
                    dates.append(datetime.fromisoformat(date_str.replace('Z', '+00:00')))
                    total_pl.append(entry.get('total_pl', 0))
                except:
                    continue

        if len(dates) < 2:
            return None

        # Create line plot
        fig, ax = plt.subplots(figsize=(14, 7))

        ax.plot(dates, total_pl, marker='o', linewidth=2, markersize=6, color='#4ECDC4')
        ax.fill_between(dates, total_pl, 0, alpha=0.3, color='#4ECDC4')

        ax.set_xlabel('Date', fontsize=12, weight='bold')
        ax.set_ylabel('Total P/L ($)', fontsize=12, weight='bold')
        ax.set_title('Total P/L Over Time', fontsize=16, weight='bold', pad=20)
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='red', linestyle='--', linewidth=1)

        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        plt.xticks(rotation=45)

        # Save
        filepath = self.graphs_dir / 'pl_time_series.png'
        plt.tight_layout()
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def generate_category_time_series(self, performance_log: list[dict]) -> str:
        """Generate time series by category."""

        if len(performance_log) < 2:
            return None

        dates = []
        crypto_pl = []
        equities_pl = []
        options_pl = []
        bonds_pl = []

        for entry in performance_log:
            date_str = entry.get('date', entry.get('timestamp', ''))
            if date_str:
                try:
                    dates.append(datetime.fromisoformat(date_str.replace('Z', '+00:00')))
                    crypto_pl.append(entry.get('crypto', {}).get('total_pl', 0))
                    equities_pl.append(entry.get('equities', {}).get('total_pl', 0))
                    options_pl.append(entry.get('options', {}).get('total_pl', 0))
                    bonds_pl.append(entry.get('bonds', {}).get('total_pl', 0))
                except:
                    continue

        if len(dates) < 2:
            return None

        # Create multi-line plot
        fig, ax = plt.subplots(figsize=(14, 8))

        ax.plot(dates, crypto_pl, marker='o', label='Crypto', linewidth=2, color='#FF6B6B')
        ax.plot(dates, equities_pl, marker='s', label='Equities', linewidth=2, color='#4ECDC4')
        ax.plot(dates, options_pl, marker='^', label='Options', linewidth=2, color='#45B7D1')
        ax.plot(dates, bonds_pl, marker='d', label='Bonds', linewidth=2, color='#FFA07A')

        ax.set_xlabel('Date', fontsize=12, weight='bold')
        ax.set_ylabel('P/L ($)', fontsize=12, weight='bold')
        ax.set_title('P/L by Category Over Time', fontsize=16, weight='bold', pad=20)
        ax.legend(fontsize=10, loc='best')
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        plt.xticks(rotation=45)

        # Save
        filepath = self.graphs_dir / 'category_pl_time_series.png'
        plt.tight_layout()
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def generate_markdown_dashboard(self, data: dict) -> str:
        """Generate enhanced markdown dashboard."""

        snapshot = data.get('latest_snapshot')
        if not snapshot:
            return "# No performance data available yet"

        # Load fresh system state (data loader might have stale cache)
        system_state = {}
        if self.system_state_file.exists():
            with open(self.system_state_file) as f:
                system_state = json.load(f)

        # Load tracker for weekly/monthly summaries
        import sys
        sys.path.insert(0, str(self.data_dir.parent / 'scripts'))
        try:
            from enhanced_performance_tracker import EnhancedPerformanceTracker
            tracker = EnhancedPerformanceTracker()
            weekly = tracker.get_weekly_summary()
            monthly = tracker.get_monthly_summary()
        except Exception as e:
            print(f"Warning: Could not load weekly/monthly summaries: {e}")
            weekly = None
            monthly = None

        # Generate graphs
        print("📊 Generating allocation pie chart...")
        allocation_graph = self.generate_allocation_pie_chart(snapshot)

        print("📈 Generating P/L bar chart...")
        pl_bars = self.generate_category_pl_bar_chart(snapshot)

        print("📉 Generating time series...")
        time_series = self.generate_time_series(data['performance_log'])

        print("📊 Generating category time series...")
        category_series = self.generate_category_time_series(data['performance_log'])

        # Build markdown
        md = []
        md.append("# 📊 Trading Performance Dashboard")
        md.append(f"\n*Last Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC*\n")

        # Summary section with weekly/monthly
        md.append("## 🎯 Performance Summary\n")
        md.append("### Today's Performance\n")
        md.append(f"**Total Equity:** ${snapshot.get('total_equity', 0):,.2f}")
        md.append(f"**Total P/L:** ${snapshot.get('total_pl', 0):+,.2f} ({snapshot.get('total_pl_pct', 0):+.2f}%)")
        md.append(f"**Total Trades:** {snapshot.get('total_trades', 0)}")
        md.append(f"**Win Rate:** {snapshot.get('overall_win_rate', 0):.1f}%")
        md.append(f"**Date:** {snapshot.get('date', 'N/A')}\n")

        # Weekly summary
        if weekly:
            md.append("### 📅 Weekly Summary (Last 7 Days)\n")
            md.append(f"**Total P/L:** ${weekly['total_pl']:+,.2f}")
            md.append(f"**Total Trades:** {weekly['total_trades']}")
            md.append("")
            md.append("| Category | P/L | Trades | Win Rate |")
            md.append("|----------|-----|--------|----------|")
            for cat in ['Crypto', 'Equities', 'Options', 'Bonds']:
                cat_key = cat.lower()
                cat_data = weekly[cat_key]
                pl_emoji = "🟢" if cat_data['total_pl'] > 0 else "🔴" if cat_data['total_pl'] < 0 else "⚪"
                md.append(f"| {pl_emoji} **{cat}** | ${cat_data['total_pl']:+,.2f} | {cat_data['trades']} | {cat_data['win_rate']:.1f}% |")
            md.append("")

        # Monthly summary
        if monthly:
            md.append("### 📆 Monthly Summary (Last 30 Days)\n")
            md.append(f"**Total P/L:** ${monthly['total_pl']:+,.2f}")
            md.append(f"**Total Trades:** {monthly['total_trades']}")
            md.append("")
            md.append("| Category | P/L | Trades | Win Rate |")
            md.append("|----------|-----|--------|----------|")
            for cat in ['Crypto', 'Equities', 'Options', 'Bonds']:
                cat_key = cat.lower()
                cat_data = monthly[cat_key]
                pl_emoji = "🟢" if cat_data['total_pl'] > 0 else "🔴" if cat_data['total_pl'] < 0 else "⚪"
                md.append(f"| {pl_emoji} **{cat}** | ${cat_data['total_pl']:+,.2f} | {cat_data['trades']} | {cat_data['win_rate']:.1f}% |")
            md.append("")

        # Alerts section
        try:
            from category_alerts import CategoryAlerts
            monitor = CategoryAlerts()
            recent_alerts = monitor.get_recent_alerts(hours=24)

            if recent_alerts:
                md.append("## 🚨 Recent Alerts (Last 24 Hours)\n")
                for alert in recent_alerts:
                    severity_emoji = {
                        'info': '🎉',
                        'warning': '⚠️',
                        'critical': '🚨'
                    }.get(alert['severity'], '📢')
                    md.append(f"- {severity_emoji} **{alert['message']}**")
                md.append("")
        except Exception as e:
            print(f"Warning: Could not load alerts: {e}")

        # Graphs
        md.append("## 📈 Visual Analytics\n")

        if allocation_graph:
            md.append("### Portfolio Allocation")
            md.append(f"![Allocation]({allocation_graph})\n")

        if pl_bars:
            md.append("### P/L by Category")
            md.append(f"![P/L Bars]({pl_bars})\n")

        if time_series:
            md.append("### Total P/L Over Time")
            md.append(f"![Time Series]({time_series})\n")

        if category_series:
            md.append("### Category Performance Over Time")
            md.append(f"![Category Series]({category_series})\n")

        # Category breakdowns (collapsible)
        md.append("## 💼 Category Breakdowns\n")

        for cat_name in ['Crypto', 'Equities', 'Options', 'Bonds']:
            cat_key = cat_name.lower()
            cat_data = snapshot.get(cat_key, {})

            md.append("<details>")
            md.append(f"<summary><strong>🔹 {cat_name}</strong></summary>\n")
            md.append(f"**Allocation:** {cat_data.get('allocation_pct', 0):.1f}%")
            md.append(f"**Current Value:** ${cat_data.get('current_value', 0):,.2f}")
            md.append(f"**Total P/L:** ${cat_data.get('total_pl', 0):+,.2f}")
            md.append(f"  - Realized: ${cat_data.get('realized_pl', 0):+,.2f}")
            md.append(f"  - Unrealized: ${cat_data.get('unrealized_pl', 0):+,.2f}")
            md.append(f"**Trades:** {cat_data.get('trades_count', 0)}")
            md.append(f"**Win Rate:** {cat_data.get('win_rate', 0):.1f}%")
            md.append(f"**Best Trade:** ${cat_data.get('best_trade', 0):+,.2f}")
            md.append(f"**Worst Trade:** ${cat_data.get('worst_trade', 0):+,.2f}\n")
            md.append("</details>\n")

        # System state
        md.append("## ⚙️ System State\n")
        account_info = system_state.get('account', {})
        challenge_info = system_state.get('challenge', {})

        md.append(f"**Status:** {challenge_info.get('status', 'UNKNOWN').upper()}")
        md.append(f"**Challenge Day:** {challenge_info.get('current_day', 'N/A')} / {challenge_info.get('total_days', 90)}")
        md.append(f"**Phase:** {challenge_info.get('phase', 'N/A')}")
        md.append(f"**Account Value:** ${account_info.get('current_equity', 0):,.2f}")
        md.append(f"**Cash:** ${account_info.get('cash', 0):,.2f}")
        md.append(f"**Total Account P/L:** ${account_info.get('total_pl', 0):+,.2f} ({account_info.get('total_pl_pct', 0):+.2f}%)")

        return '\n'.join(md)

    def generate(self):
        """Generate complete dashboard."""
        print("🚀 Generating enhanced dashboard with graphs...")

        # Load data
        data = self.load_data()

        # Generate markdown
        markdown = self.generate_markdown_dashboard(data)

        # Save
        dashboard_file = self.wiki_dir / 'Progress-Dashboard.md'
        with open(dashboard_file, 'w') as f:
            f.write(markdown)

        print(f"✅ Dashboard generated: {dashboard_file}")
        print(f"📁 Graphs saved to: {self.graphs_dir}/")

        return dashboard_file


if __name__ == '__main__':
    generator = DashboardGenerator()
    generator.generate()
