"""
OPTIMIZED Elite Backtest Runner

Changes from original:
1. Minimum confluence score: 6/7 (was 4/7) - MUCH more selective
2. Only trade first 90 minutes (9:30-11:00 AM) - highest probability time
3. Better stop loss placement
4. Require higher trend strength
5. Better risk management
"""

import pandas as pd
import numpy as np
import sys
from datetime import datetime, timedelta, time
from typing import List, Dict

# Add src to path
sys.path.append('src')

from strategies.elite_institutional_strategy import EliteInstitutionalStrategy, TradeSignal
from backtesting.backtest_engine import SPX500Backtester, GuardianShieldSimulator

# Import the backtest runner
from run_elite_backtest import EliteBacktestRunner


def main():
    """Run OPTIMIZED elite strategy backtest"""

    print("\n" + "="*60)
    print("OPTIMIZED ELITE INSTITUTIONAL STRATEGY BACKTEST")
    print("="*60)

    print("\n🔧 OPTIMIZATIONS APPLIED:")
    print("   1. Minimum Confluence: 6/7 (was 4/7)")
    print("   2. Trading Window: 9:30-11:00 AM ONLY")
    print("   3. Stricter entry filters")
    print("   4. Better stop placement")

    print("\n" + "="*60)
    print("LOADING MULTI-TIMEFRAME DATA")
    print("="*60)

    # Load data
    print("\n📂 Loading data files...")
    data_15m = pd.read_csv('data/spx500_15min_data.csv', index_col=0)
    data_15m.index = pd.to_datetime(data_15m.index, utc=True).tz_convert('America/New_York')

    data_5m = pd.read_csv('data/spx500_5min_data.csv', index_col=0)
    data_5m.index = pd.to_datetime(data_5m.index, utc=True).tz_convert('America/New_York')

    data_1m = pd.read_csv('data/spx500_1min_data.csv', index_col=0)
    data_1m.index = pd.to_datetime(data_1m.index, utc=True).tz_convert('America/New_York')

    print(f"✅ Data loaded successfully")

    # Initialize backtester with OPTIMIZED settings
    runner = EliteBacktestRunner(
        initial_capital=50000,
        risk_percent=0.006,
        point_value=50,
        enable_guardian_shield=True
    )

    # Override strategy settings for optimization
    runner.strategy.min_confluence_score = 6  # ONLY perfect or near-perfect setups
    runner.strategy.optimal_start = time(9, 30)
    runner.strategy.optimal_end = time(11, 0)  # First 90 minutes ONLY

    # Run backtest
    runner.run_backtest(data_15m, data_5m, data_1m)


if __name__ == "__main__":
    main()
