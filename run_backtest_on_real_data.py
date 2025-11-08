"""
RUN BACKTEST ON REAL MARKET DATA

This script runs the Elite Institutional Strategy on REAL downloaded data
(either from Alpaca, broker export, or other source)

PREREQUISITES:
1. Download real data first:
   - Option A: python download_mt5_data.py (RECOMMENDED - your broker's data)
   - Option B: python download_alpaca_data.py (free historical data)
   - Option C: Use data/spx500_mt5_real.csv if already downloaded

USAGE:
   python run_backtest_on_real_data.py
"""

import pandas as pd
import sys
from datetime import time
import os

# Add src to path
sys.path.append('src')

from run_elite_backtest import EliteBacktestRunner
from generate_realistic_data import resample_to_timeframe


def load_real_data(file_path: str = None):
    """
    Load real market data from CSV

    Args:
        file_path: Path to CSV file (default: data/spy_real_alpaca.csv)

    Returns:
        DataFrame with OHLCV data
    """
    if file_path is None:
        # Try different possible file names (prioritize MT5 broker data)
        possible_files = [
            'data/spx500_mt5_real.csv',         # MT5 broker data (best - real intraday)
            'data/spy_real_alpaca.csv',          # Alpaca data (real intraday)
            'data/spx500_stooq_intraday.csv',    # Stooq expanded (approximate intraday)
            'data/spy_real.csv',                 # Generic real data
            'data/spy_real_data.csv',
            'data/spy_real_daily.csv'
        ]

        file_path = None
        for f in possible_files:
            if os.path.exists(f):
                file_path = f
                break

        if file_path is None:
            print("=" * 80)
            print("❌ ERROR: No real data file found")
            print("=" * 80)
            print("\nPlease download real data first:")
            print("\nOption 1 (RECOMMENDED - Your broker's data):")
            print("   python download_mt5_data.py")
            print("\nOption 2 (Free historical data):")
            print("   python download_alpaca_data.py")
            print("\nOr manually place your data file in data/ folder")
            return None

    print(f"📂 Loading data from: {file_path}")

    try:
        data = pd.read_csv(file_path, index_col=0, parse_dates=True)

        # Ensure DatetimeIndex
        if not isinstance(data.index, pd.DatetimeIndex):
            data.index = pd.to_datetime(data.index, utc=True)

        # Ensure timezone is Eastern
        if data.index.tz is None:
            data.index = data.index.tz_localize('America/New_York')
        elif str(data.index.tz) != 'America/New_York':
            data.index = data.index.tz_convert('America/New_York')

        print(f"✅ Loaded {len(data):,} bars")
        print(f"   Date range: {data.index[0]} to {data.index[-1]}")
        print(f"   Trading days: {len(data.index.normalize().unique())}")

        return data

    except Exception as e:
        print(f"❌ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_real_data_backtest():
    """
    Run backtest on real market data and compare to synthetic results
    """

    print("\n" + "=" * 80)
    print("ELITE INSTITUTIONAL STRATEGY - REAL DATA BACKTEST")
    print("=" * 80)
    print("\nThis is the MOMENT OF TRUTH")
    print("Testing strategy on REAL market data for the first time")
    print("\nWill the 60-75% win rate hold? Let's find out...")
    print("=" * 80)

    # Load real data
    data_1m = load_real_data()

    if data_1m is None:
        return

    # Check data adequacy
    trading_days = len(data_1m.index.normalize().unique())

    print(f"\n📊 Data Adequacy Check:")
    print(f"   Trading days: {trading_days}")

    if trading_days < 20:
        print(f"   ⚠️  WARNING: Less than 20 days of data")
        print(f"      Results may not be statistically significant")
    elif trading_days < 60:
        print(f"   ⚠️  CAUTION: Less than 60 days of data")
        print(f"      More data would give better confidence")
    else:
        print(f"   ✅ Adequate data for testing")

    # Resample to higher timeframes
    print(f"\n🔄 Resampling to multiple timeframes...")

    data_5m = resample_to_timeframe(data_1m, '5min')
    data_15m = resample_to_timeframe(data_1m, '15min')

    print(f"   15-min bars: {len(data_15m):,}")
    print(f"   5-min bars: {len(data_5m):,}")
    print(f"   1-min bars: {len(data_1m):,}")

    # Initialize backtest runner with optimized settings
    print(f"\n⚙️  Initializing strategy with optimized parameters...")
    print(f"   Min confluence: 6/7 (near-perfect setups only)")
    print(f"   Trading window: 9:30 AM - 11:00 AM (first 90 minutes)")
    print(f"   Risk per trade: 0.6%")
    print(f"   Account size: $50,000")

    runner = EliteBacktestRunner()

    # Apply optimized settings
    runner.strategy.min_confluence_score = 6
    runner.strategy.optimal_start = time(9, 30)
    runner.strategy.optimal_end = time(11, 0)

    # Run backtest
    print(f"\n" + "=" * 80)
    print("RUNNING BACKTEST ON REAL DATA...")
    print("=" * 80)

    runner.run_backtest(data_15m, data_5m, data_1m)

    # Analyze results
    print(f"\n" + "=" * 80)
    print("REAL DATA RESULTS")
    print("=" * 80)

    if len(runner.trades) == 0:
        print("\n❌ NO TRADES GENERATED")
        print("\nPossible reasons:")
        print("1. Insufficient data (need at least 30-60 trading days)")
        print("2. Market conditions didn't meet 6/7 confluence criteria")
        print("3. No valid setups in the 9:30-11:00 AM window")
        print("\nRecommendations:")
        print("- Download more data (6+ months recommended)")
        print("- Try lowering confluence to 5/7: runner.strategy.min_confluence_score = 5")
        print("- Expand trading window: runner.strategy.optimal_end = time(15, 0)")
        return

    # Convert trades to DataFrame
    trades_df = pd.DataFrame(runner.trades)

    # Calculate metrics
    total_trades = len(trades_df)
    winning_trades = len(trades_df[trades_df['pnl'] > 0])
    losing_trades = len(trades_df[trades_df['pnl'] <= 0])
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0

    total_pnl = trades_df['pnl'].sum()
    avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
    avg_loss = abs(trades_df[trades_df['pnl'] <= 0]['pnl'].mean()) if losing_trades > 0 else 0
    profit_factor = (avg_win * winning_trades) / (avg_loss * losing_trades) if losing_trades > 0 and avg_loss > 0 else 0

    # Drawdown
    cumulative_pnl = trades_df['pnl'].cumsum()
    running_max = cumulative_pnl.expanding().max()
    drawdown = cumulative_pnl - running_max
    max_dd = abs(drawdown.min()) if len(drawdown) > 0 else 0
    max_dd_pct = (max_dd / 50000) * 100

    # Print results
    print(f"\n📊 PERFORMANCE METRICS:")
    print(f"   Total Trades: {total_trades}")
    print(f"   Winning Trades: {winning_trades}")
    print(f"   Losing Trades: {losing_trades}")
    print(f"   Win Rate: {win_rate:.2f}%")
    print(f"\n💰 P&L:")
    print(f"   Total P&L: ${total_pnl:,.2f}")
    print(f"   Avg Win: ${avg_win:,.2f}")
    print(f"   Avg Loss: ${avg_loss:,.2f}")
    print(f"   Profit Factor: {profit_factor:.2f}")
    print(f"\n📉 Risk Metrics:")
    print(f"   Max Drawdown: ${max_dd:,.2f} ({max_dd_pct:.2f}%)")
    print(f"   Guardian Shield Limit: $1,000 (2%)")

    # Comparison to synthetic results
    print(f"\n" + "=" * 80)
    print("COMPARISON TO SYNTHETIC DATA RESULTS")
    print("=" * 80)

    print(f"\n📊 Synthetic Data Results (for reference):")
    print(f"   Best Case (Seed 42): 75.0% win rate, $5,268 profit")
    print(f"   Average (3 seeds): 60.0% win rate, $3,453 profit")
    print(f"   Worst Case (Seed 999): 48.4% win rate, $1,528 profit")

    print(f"\n📊 Real Data Results:")
    print(f"   Win Rate: {win_rate:.2f}%")
    print(f"   Total P&L: ${total_pnl:,.2f}")

    # Assessment
    print(f"\n" + "=" * 80)
    print("HONEST ASSESSMENT")
    print("=" * 80)

    if win_rate >= 70:
        print(f"\n✅ EXCELLENT: Win rate {win_rate:.2f}% EXCEEDS synthetic best case (75%)")
        print("   Strategy appears to work even BETTER on real data")
        print("   This is VERY promising")
    elif win_rate >= 60:
        print(f"\n✅ GOOD: Win rate {win_rate:.2f}% matches synthetic average (60%)")
        print("   Strategy performance is CONSISTENT with testing")
        print("   This validates the approach")
    elif win_rate >= 50:
        print(f"\n⚠️  ACCEPTABLE: Win rate {win_rate:.2f}% below synthetic average but still profitable")
        print("   Strategy works but not as well as hoped")
        print("   May need refinement")
    else:
        print(f"\n❌ POOR: Win rate {win_rate:.2f}% significantly below expectations")
        print("   Strategy does NOT work as expected on real data")
        print("   Needs major revision or abandonment")

    if profit_factor >= 2.0:
        print(f"\n✅ Profit Factor {profit_factor:.2f} is EXCELLENT (>2.0)")
    elif profit_factor >= 1.5:
        print(f"\n✅ Profit Factor {profit_factor:.2f} is GOOD (>1.5)")
    elif profit_factor >= 1.2:
        print(f"\n⚠️  Profit Factor {profit_factor:.2f} is ACCEPTABLE (>1.2)")
    else:
        print(f"\n❌ Profit Factor {profit_factor:.2f} is TOO LOW (<1.2)")

    if max_dd_pct <= 2.0:
        print(f"\n✅ Max Drawdown {max_dd_pct:.2f}% is within Guardian Shield limit (2%)")
    elif max_dd_pct <= 4.0:
        print(f"\n⚠️  Max Drawdown {max_dd_pct:.2f}% is within daily limit (4%) but above Guardian Shield")
    else:
        print(f"\n❌ Max Drawdown {max_dd_pct:.2f}% EXCEEDS Blue Guardian limits")

    # Final recommendation
    print(f"\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    if win_rate >= 60 and profit_factor >= 1.5 and max_dd_pct <= 4.0:
        print("\n✅ STRATEGY VALIDATED ON REAL DATA")
        print("\nNext steps:")
        print("1. Forward test on demo account (50-100 trades)")
        print("2. If demo results match backtest, proceed to Blue Guardian")
        print("3. Start with $50K challenge")
        print("\nEstimated success probability: 40-60%")
        print("(Better than 5-10% industry average)")

    elif win_rate >= 50 and profit_factor >= 1.2:
        print("\n⚠️  STRATEGY SHOWS PROMISE BUT NEEDS IMPROVEMENT")
        print("\nNext steps:")
        print("1. Analyze losing trades to find patterns")
        print("2. Adjust parameters (confluence, time window)")
        print("3. Forward test on demo to validate improvements")
        print("4. Re-backtest with optimized settings")
        print("\nDo NOT proceed to Blue Guardian yet")

    else:
        print("\n❌ STRATEGY DOES NOT WORK AS EXPECTED")
        print("\nOptions:")
        print("1. Major strategy revision needed")
        print("2. Try different approach entirely")
        print("3. Get more data (6+ months) for better testing")
        print("\nDo NOT use this for Blue Guardian challenge")

    # Save results
    trades_df.to_csv('backtest_results_real_data.csv', index=False)
    print(f"\n💾 Detailed results saved to: backtest_results_real_data.csv")

    print("\n" + "=" * 80)
    print("BACKTEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    run_real_data_backtest()
