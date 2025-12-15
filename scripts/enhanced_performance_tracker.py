#!/usr/bin/env python3
"""
Enhanced Performance Tracker with Category Breakdowns

Tracks P/L by category:
- Crypto (BTC, ETH, etc.)
- Equities (stocks)
- Options (calls, puts, spreads)
- Bonds/Treasuries (TLT, IEF, BIL, SHY)

Generates data for dashboard visualization.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass, asdict


@dataclass
class CategoryPerformance:
    """Performance metrics for a specific category."""
    category: str
    realized_pl: float
    unrealized_pl: float
    total_pl: float
    trades_count: int
    win_rate: float
    current_value: float
    allocation_pct: float
    best_trade: float
    worst_trade: float


@dataclass
class PerformanceSnapshot:
    """Complete performance snapshot with category breakdowns."""
    timestamp: str
    date: str
    total_equity: float
    total_pl: float
    total_pl_pct: float
    
    # Category breakdowns
    crypto: CategoryPerformance
    equities: CategoryPerformance
    options: CategoryPerformance
    bonds: CategoryPerformance
    
    # Overall metrics
    total_trades: int
    overall_win_rate: float
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0


class EnhancedPerformanceTracker:
    """Tracks performance with detailed category breakdowns."""
    
    CRYPTO_SYMBOLS = ['BTC', 'ETH', 'SOL', 'BTCUSD', 'ETHUSD', 'SOLUSD']
    BOND_SYMBOLS = ['TLT', 'IEF', 'BIL', 'SHY', 'AGG']
    
    def __init__(self):
        self.data_dir = Path('data')
        self.trades_file_pattern = 'trades_*.json'
        self.performance_file = self.data_dir / 'enhanced_performance_log.json'
        
    def categorize_symbol(self, symbol: str) -> str:
        """Determine category for a symbol."""
        symbol_upper = symbol.upper()
        
        # Check crypto
        for crypto in self.CRYPTO_SYMBOLS:
            if crypto in symbol_upper:
                return 'crypto'
        
        # Check bonds
        if symbol_upper in self.BOND_SYMBOLS:
            return 'bonds'
        
        # Check options (contains 'C' or 'P' followed by dates/strikes)
        if any(c in symbol_upper for c in ['C0', 'P0']) or 'CALL' in symbol_upper or 'PUT' in symbol_upper:
            return 'options'
        
        # Default to equities
        return 'equities'
    
    def analyze_trades(self, date: str = None) -> Dict[str, List[Dict]]:
        """Analyze trades by category for a given date."""
        if date is None:
            date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        trades_file = self.data_dir / f'trades_{date}.json'
        
        if not trades_file.exists():
            return {
                'crypto': [],
                'equities': [],
                'options': [],
                'bonds': []
            }
        
        with open(trades_file) as f:
            trades = json.load(f)
        
        categorized = {
            'crypto': [],
            'equities': [],
            'options': [],
            'bonds': []
        }
        
        for trade in trades:
            symbol = trade.get('symbol', '')
            if symbol:
                category = self.categorize_symbol(symbol)
                categorized[category].append(trade)
        
        return categorized
    
    def calculate_category_performance(
        self, 
        trades: List[Dict],
        current_holdings: Dict[str, Dict],
        closed_trades: List[Dict] = None
    ) -> CategoryPerformance:
        """Calculate performance metrics for a category."""
        
        realized_pl = 0.0
        unrealized_pl = 0.0
        len([t for t in trades if t.get('action') != 'SKIP'])
        winning_trades = 0
        current_value = 0.0
        
        trade_pls = []
        
        # Calculate from today's trades
        for trade in trades:
            if trade.get('action') == 'SKIP':
                continue
            
            # Calculate realized P/L from trade
            pnl = trade.get('pnl', 0) or trade.get('pl', 0)
            if pnl:
                realized_pl += float(pnl)
                trade_pls.append(float(pnl))
                if pnl > 0:
                    winning_trades += 1
        
        # Add realized P/L from closed trades (from system state)
        if closed_trades:
            for closed_trade in closed_trades:
                symbol = closed_trade.get('symbol', '')
                self.categorize_symbol(symbol)
                
                # Only count if this closed trade belongs to this category
                # (caller will filter, but adding check here too)
                pnl = closed_trade.get('pl', 0)
                if pnl:
                    # Don't double-count if already in today's trades
                    realized_pl += float(pnl)
                    trade_pls.append(float(pnl))
                    if pnl > 0:
                        winning_trades += 1
        
        # Calculate unrealized P/L from holdings
        for symbol, holding in current_holdings.items():
            unrealized_pl += float(holding.get('unrealized_pl', 0))
            # Calculate market value from quantity * current_price
            qty = float(holding.get('quantity', 0))
            price = float(holding.get('current_price', 0))
            current_value += qty * price
        
        total_pl = realized_pl + unrealized_pl
        total_trades_count = len(trade_pls)
        win_rate = (winning_trades / total_trades_count * 100) if total_trades_count > 0 else 0.0
        best_trade = max(trade_pls) if trade_pls else 0.0
        worst_trade = min(trade_pls) if trade_pls else 0.0
        
        return CategoryPerformance(
            category='',  # Set by caller
            realized_pl=realized_pl,
            unrealized_pl=unrealized_pl,
            total_pl=total_pl,
            trades_count=total_trades_count,
            win_rate=win_rate,
            current_value=current_value,
            allocation_pct=0.0,  # Calculate later
            best_trade=best_trade,
            worst_trade=worst_trade
        )
    
    def get_current_holdings_by_category(self) -> tuple[Dict[str, Dict[str, Dict]], List[Dict]]:
        """Get current holdings grouped by category from system state, plus closed trades."""
        
        system_state_file = self.data_dir / 'system_state.json'
        if not system_state_file.exists():
            return {
                'crypto': {},
                'equities': {},
                'options': {},
                'bonds': {}
            }, []
        
        with open(system_state_file) as f:
            state = json.load(f)
        
        # Get open positions
        open_positions = state.get('performance', {}).get('open_positions', [])
        
        categorized = {
            'crypto': {},
            'equities': {},
            'options': {},
            'bonds': {}
        }
        
        for position in open_positions:
            symbol = position.get('symbol', '')
            if symbol:
                category = self.categorize_symbol(symbol)
                categorized[category][symbol] = position
        
        # Get closed trades for realized P/L
        closed_trades = state.get('performance', {}).get('closed_trades', [])
        
        return categorized, closed_trades
    
    def generate_snapshot(self, date: str = None) -> PerformanceSnapshot:
        """Generate complete performance snapshot with categories."""
        
        if date is None:
            date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # Get trades by category
        categorized_trades = self.analyze_trades(date)
        
        # Get current holdings by category and closed trades
        holdings_by_cat, closed_trades = self.get_current_holdings_by_category()
        
        # Categorize closed trades
        closed_by_cat = {
            'crypto': [],
            'equities': [],
            'options': [],
            'bonds': []
        }
        for trade in closed_trades:
            symbol = trade.get('symbol', '')
            if symbol:
                category = self.categorize_symbol(symbol)
                closed_by_cat[category].append(trade)
        
        # Calculate performance for each category
        crypto_perf = self.calculate_category_performance(
            categorized_trades['crypto'],
            holdings_by_cat['crypto'],
            closed_by_cat['crypto']
        )
        crypto_perf.category = 'crypto'
        
        equities_perf = self.calculate_category_performance(
            categorized_trades['equities'],
            holdings_by_cat['equities'],
            closed_by_cat['equities']
        )
        equities_perf.category = 'equities'
        
        options_perf = self.calculate_category_performance(
            categorized_trades['options'],
            holdings_by_cat['options'],
            closed_by_cat['options']
        )
        options_perf.category = 'options'
        
        bonds_perf = self.calculate_category_performance(
            categorized_trades['bonds'],
            holdings_by_cat['bonds'],
            closed_by_cat['bonds']
        )
        bonds_perf.category = 'bonds'
        
        # Calculate totals
        total_equity = sum([
            crypto_perf.current_value,
            equities_perf.current_value,
            options_perf.current_value,
            bonds_perf.current_value
        ])
        
        total_pl = sum([
            crypto_perf.total_pl,
            equities_perf.total_pl,
            options_perf.total_pl,
            bonds_perf.total_pl
        ])
        
        total_trades = sum([
            crypto_perf.trades_count,
            equities_perf.trades_count,
            options_perf.trades_count,
            bonds_perf.trades_count
        ])
        
        # Calculate allocation percentages
        if total_equity > 0:
            crypto_perf.allocation_pct = (crypto_perf.current_value / total_equity) * 100
            equities_perf.allocation_pct = (equities_perf.current_value / total_equity) * 100
            options_perf.allocation_pct = (options_perf.current_value / total_equity) * 100
            bonds_perf.allocation_pct = (bonds_perf.current_value / total_equity) * 100
        
        # Calculate overall win rate
        total_winning = 0
        for cat_trades in categorized_trades.values():
            for trade in cat_trades:
                if trade.get('action') != 'SKIP':
                    pnl = trade.get('pnl', 0) or trade.get('pl', 0)
                    if pnl and pnl > 0:
                        total_winning += 1
        
        overall_win_rate = (total_winning / total_trades * 100) if total_trades > 0 else 0.0
        
        total_pl_pct = (total_pl / total_equity * 100) if total_equity > 0 else 0.0
        
        return PerformanceSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            date=date,
            total_equity=total_equity,
            total_pl=total_pl,
            total_pl_pct=total_pl_pct,
            crypto=crypto_perf,
            equities=equities_perf,
            options=options_perf,
            bonds=bonds_perf,
            total_trades=total_trades,
            overall_win_rate=overall_win_rate
        )
    
    def save_snapshot(self, snapshot: PerformanceSnapshot):
        """Save snapshot to enhanced performance log."""
        
        # Load existing log
        if self.performance_file.exists():
            with open(self.performance_file) as f:
                log = json.load(f)
        else:
            log = []
        
        # Add new snapshot
        snapshot_dict = {
            'timestamp': snapshot.timestamp,
            'date': snapshot.date,
            'total_equity': snapshot.total_equity,
            'total_pl': snapshot.total_pl,
            'total_pl_pct': snapshot.total_pl_pct,
            'crypto': asdict(snapshot.crypto),
            'equities': asdict(snapshot.equities),
            'options': asdict(snapshot.options),
            'bonds': asdict(snapshot.bonds),
            'total_trades': snapshot.total_trades,
            'overall_win_rate': snapshot.overall_win_rate,
            'sharpe_ratio': snapshot.sharpe_ratio,
            'max_drawdown': snapshot.max_drawdown
        }
        
        log.append(snapshot_dict)
        
        # Save
        self.data_dir.mkdir(exist_ok=True)
        with open(self.performance_file, 'w') as f:
            json.dump(log, f, indent=2)
        
        print(f"✅ Saved enhanced performance snapshot for {snapshot.date}")
        return snapshot_dict


    def get_weekly_summary(self) -> Dict:
        """Get weekly rollup of category performance."""
        if not self.performance_file.exists():
            return {}
        
        with open(self.performance_file) as f:
            log = json.load(f)
        
        # Get last 7 days
        from datetime import datetime, timedelta
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        weekly_data = []
        for entry in log:
            entry_date = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
            if entry_date >= week_ago:
                weekly_data.append(entry)
        
        if not weekly_data:
            return {}
        
        # Calculate weekly totals
        weekly = {
            'crypto': {'total_pl': 0, 'trades': 0, 'wins': 0},
            'equities': {'total_pl': 0, 'trades': 0, 'wins': 0},
            'options': {'total_pl': 0, 'trades': 0, 'wins': 0},
            'bonds': {'total_pl': 0, 'trades': 0, 'wins': 0},
            'total_pl': 0,
            'total_trades': 0
        }
        
        for entry in weekly_data:
            for cat in ['crypto', 'equities', 'options', 'bonds']:
                cat_data = entry.get(cat, {})
                weekly[cat]['total_pl'] += cat_data.get('total_pl', 0)
                weekly[cat]['trades'] += cat_data.get('trades_count', 0)
                # Estimate wins from win_rate
                win_rate = cat_data.get('win_rate', 0) / 100
                weekly[cat]['wins'] += int(cat_data.get('trades_count', 0) * win_rate)
            
            weekly['total_pl'] += entry.get('total_pl', 0)
            weekly['total_trades'] += entry.get('total_trades', 0)
        
        # Calculate win rates
        for cat in ['crypto', 'equities', 'options', 'bonds']:
            if weekly[cat]['trades'] > 0:
                weekly[cat]['win_rate'] = (weekly[cat]['wins'] / weekly[cat]['trades']) * 100
            else:
                weekly[cat]['win_rate'] = 0
        
        return weekly
    
    def get_monthly_summary(self) -> Dict:
        """Get monthly rollup of category performance."""
        if not self.performance_file.exists():
            return {}
        
        with open(self.performance_file) as f:
            log = json.load(f)
        
        # Get last 30 days
        from datetime import datetime, timedelta
        month_ago = datetime.now(timezone.utc) - timedelta(days=30)
        
        monthly_data = []
        for entry in log:
            entry_date = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
            if entry_date >= month_ago:
                monthly_data.append(entry)
        
        if not monthly_data:
            return {}
        
        # Calculate monthly totals
        monthly = {
            'crypto': {'total_pl': 0, 'trades': 0, 'wins': 0},
            'equities': {'total_pl': 0, 'trades': 0, 'wins': 0},
            'options': {'total_pl': 0, 'trades': 0, 'wins': 0},
            'bonds': {'total_pl': 0, 'trades': 0, 'wins': 0},
            'total_pl': 0,
            'total_trades': 0
        }
        
        for entry in monthly_data:
            for cat in ['crypto', 'equities', 'options', 'bonds']:
                cat_data = entry.get(cat, {})
                monthly[cat]['total_pl'] += cat_data.get('total_pl', 0)
                monthly[cat]['trades'] += cat_data.get('trades_count', 0)
                # Estimate wins from win_rate
                win_rate = cat_data.get('win_rate', 0) / 100
                monthly[cat]['wins'] += int(cat_data.get('trades_count', 0) * win_rate)
            
            monthly['total_pl'] += entry.get('total_pl', 0)
            monthly['total_trades'] += entry.get('total_trades', 0)
        
        # Calculate win rates
        for cat in ['crypto', 'equities', 'options', 'bonds']:
            if monthly[cat]['trades'] > 0:
                monthly[cat]['win_rate'] = (monthly[cat]['wins'] / monthly[cat]['trades']) * 100
            else:
                monthly[cat]['win_rate'] = 0
        
        return monthly


if __name__ == '__main__':
    tracker = EnhancedPerformanceTracker()
    snapshot = tracker.generate_snapshot()
    tracker.save_snapshot(snapshot)
    
    print()
    print("Category Performance (Today):")
    print(f"  Crypto:    ${snapshot.crypto.total_pl:+.2f} ({snapshot.crypto.allocation_pct:.1f}%)")
    print(f"  Equities:  ${snapshot.equities.total_pl:+.2f} ({snapshot.equities.allocation_pct:.1f}%)")
    print(f"  Options:   ${snapshot.options.total_pl:+.2f} ({snapshot.options.allocation_pct:.1f}%)")
    print(f"  Bonds:     ${snapshot.bonds.total_pl:+.2f} ({snapshot.bonds.allocation_pct:.1f}%)")
    print(f"  Total:     ${snapshot.total_pl:+.2f}")
    
    # Show weekly summary
    weekly = tracker.get_weekly_summary()
    if weekly:
        print()
        print("Weekly Summary (Last 7 Days):")
        print(f"  Total P/L:    ${weekly['total_pl']:+.2f}")
        print(f"  Total Trades: {weekly['total_trades']}")
        for cat in ['crypto', 'equities', 'options', 'bonds']:
            print(f"  {cat.capitalize():10} ${weekly[cat]['total_pl']:+8.2f} ({weekly[cat]['trades']} trades, {weekly[cat]['win_rate']:.0f}% win rate)")
    
    # Show monthly summary
    monthly = tracker.get_monthly_summary()
    if monthly:
        print()
        print("Monthly Summary (Last 30 Days):")
        print(f"  Total P/L:    ${monthly['total_pl']:+.2f}")
        print(f"  Total Trades: {monthly['total_trades']}")
        for cat in ['crypto', 'equities', 'options', 'bonds']:
            print(f"  {cat.capitalize():10} ${monthly[cat]['total_pl']:+8.2f} ({monthly[cat]['trades']} trades, {monthly[cat]['win_rate']:.0f}% win rate)")
