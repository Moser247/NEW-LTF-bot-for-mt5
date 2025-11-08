"""
COMPREHENSIVE STRESS TEST

Run strategy on multiple different datasets to see if results hold
"""

import pandas as pd
import numpy as np
import sys
from generate_realistic_data import generate_realistic_spx500_1min, resample_to_timeframe
sys.path.append('src')
from run_elite_backtest import EliteBacktestRunner
from datetime import time


def run_stress_test():
    """Run backtest on multiple scenarios"""

    print("\n" + "="*80)
    print("COMPREHENSIVE STRESS TEST - MULTIPLE SCENARIOS")
    print("="*80)
    print("\nTesting strategy robustness across different market conditions")
    print("and random seeds to see if 75% win rate was just luck...")
    print("\n" + "="*80)

    results_summary = []

    # Scenario 1: Original data (seed=42)
    print("\n" + "="*80)
    print("SCENARIO 1: Original Synthetic Data (Seed=42)")
    print("="*80)

    data_1m = pd.read_csv('data/spx500_1min_data.csv', index_col=0)
    data_1m.index = pd.to_datetime(data_1m.index, utc=True).tz_convert('America/New_York')

    data_5m = resample_to_timeframe(data_1m, '5min')
    data_15m = resample_to_timeframe(data_1m, '15min')

    runner = EliteBacktestRunner()
    runner.strategy.min_confluence_score = 6
    runner.strategy.optimal_start = time(9, 30)
    runner.strategy.optimal_end = time(11, 0)

    runner.run_backtest(data_15m, data_5m, data_1m)

    if len(runner.trades) > 0:
        trades_df = pd.DataFrame(runner.trades)
        win_rate = (len(trades_df[trades_df['pnl'] > 0]) / len(trades_df)) * 100
        total_pnl = trades_df['pnl'].sum()
        max_dd = min(0, trades_df['pnl'].cumsum().min())

        results_summary.append({
            'scenario': 'Original (Seed 42)',
            'trades': len(trades_df),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'max_dd': max_dd
        })

    # Scenario 2: Different random seed
    print("\n" + "="*80)
    print("SCENARIO 2: Different Random Seed (Seed=123)")
    print("="*80)
    print("Testing if results change with different random data...")

    data_1m = generate_realistic_spx500_1min(days=60, start_price=4500, seed=123)
    data_5m = resample_to_timeframe(data_1m, '5min')
    data_15m = resample_to_timeframe(data_1m, '15min')

    runner = EliteBacktestRunner()
    runner.strategy.min_confluence_score = 6
    runner.strategy.optimal_start = time(9, 30)
    runner.strategy.optimal_end = time(11, 0)

    runner.run_backtest(data_15m, data_5m, data_1m)

    if len(runner.trades) > 0:
        trades_df = pd.DataFrame(runner.trades)
        win_rate = (len(trades_df[trades_df['pnl'] > 0]) / len(trades_df)) * 100
        total_pnl = trades_df['pnl'].sum()
        max_dd = min(0, trades_df['pnl'].cumsum().min())

        results_summary.append({
            'scenario': 'Seed 123',
            'trades': len(trades_df),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'max_dd': max_dd
        })

    # Scenario 3: Another seed
    print("\n" + "="*80)
    print("SCENARIO 3: Another Random Seed (Seed=999)")
    print("="*80)

    data_1m = generate_realistic_spx500_1min(days=60, start_price=4500, seed=999)
    data_5m = resample_to_timeframe(data_1m, '5min')
    data_15m = resample_to_timeframe(data_1m, '15min')

    runner = EliteBacktestRunner()
    runner.strategy.min_confluence_score = 6
    runner.strategy.optimal_start = time(9, 30)
    runner.strategy.optimal_end = time(11, 0)

    runner.run_backtest(data_15m, data_5m, data_1m)

    if len(runner.trades) > 0:
        trades_df = pd.DataFrame(runner.trades)
        win_rate = (len(trades_df[trades_df['pnl'] > 0]) / len(trades_df)) * 100
        total_pnl = trades_df['pnl'].sum()
        max_dd = min(0, trades_df['pnl'].cumsum().min())

        results_summary.append({
            'scenario': 'Seed 999',
            'trades': len(trades_df),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'max_dd': max_dd
        })

    # Summary
    print("\n" + "="*80)
    print("STRESS TEST SUMMARY")
    print("="*80)

    summary_df = pd.DataFrame(results_summary)
    print("\n" + str(summary_df.to_string(index=False)))

    print("\n📊 STATISTICS ACROSS SCENARIOS:")
    print(f"   Average Win Rate: {summary_df['win_rate'].mean():.2f}%")
    print(f"   Std Dev Win Rate: {summary_df['win_rate'].std():.2f}%")
    print(f"   Min Win Rate: {summary_df['win_rate'].min():.2f}%")
    print(f"   Max Win Rate: {summary_df['win_rate'].max():.2f}%")

    print(f"\n   Average Total P&L: ${summary_df['total_pnl'].mean():.2f}")
    print(f"   Std Dev P&L: ${summary_df['total_pnl'].std():.2f}")

    print(f"\n   Average Trades: {summary_df['trades'].mean():.1f}")

    print("\n" + "="*80)
    print("HONEST ASSESSMENT")
    print("="*80)

    avg_wr = summary_df['win_rate'].mean()
    std_wr = summary_df['win_rate'].std()

    if std_wr > 15:
        print(f"\n⚠️  HIGH VARIANCE: Win rate varies significantly ({std_wr:.1f}% std dev)")
        print("   This suggests results are UNSTABLE and depend heavily on market conditions")
        print("   Strategy may not have robust edge")
    elif std_wr > 10:
        print(f"\n⚠️  MODERATE VARIANCE: Win rate shows some variation ({std_wr:.1f}% std dev)")
        print("   Results somewhat dependent on conditions")
        print("   Needs more testing to confirm edge")
    else:
        print(f"\n✅ LOW VARIANCE: Win rate is consistent ({std_wr:.1f}% std dev)")
        print("   Strategy appears robust across different scenarios")

    if avg_wr >= 70:
        print(f"\n✅ Average win rate {avg_wr:.1f}% meets 70% target")
    elif avg_wr >= 60:
        print(f"\n⚠️  Average win rate {avg_wr:.1f}% below 70% target but acceptable")
    else:
        print(f"\n❌ Average win rate {avg_wr:.1f}% significantly below target")

    print("\n⚠️  REMEMBER: These are all SYNTHETIC DATA tests")
    print("   Real market performance WILL BE DIFFERENT")
    print("   Validation on real data is ESSENTIAL")


if __name__ == "__main__":
    run_stress_test()
