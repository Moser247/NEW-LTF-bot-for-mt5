"""
Simplified backtest runner using sample data
"""

import pandas as pd
import numpy as np
import sys

# Add src to path
sys.path.append('src')

from backtesting.backtest_engine import SPX500Backtester
from strategies.opening_range_breakout import OpeningRangeBreakout
from strategies.vwap_mean_reversion import VWAPMeanReversion

def run_orb_backtest(data):
    """Run Opening Range Breakout backtest"""

    print("\n" + "="*60)
    print("OPENING RANGE BREAKOUT (ORB) BACKTEST")
    print("="*60)

    config = {
        'initial_capital': 50000,
        'risk_percent': 0.006,  # 0.6%
        'enable_guardian_shield': True,
    }

    # Initialize backtester
    backtester = SPX500Backtester(
        data=data,
        initial_capital=config['initial_capital'],
        risk_percent=config['risk_percent'],
        enable_guardian_shield=config['enable_guardian_shield'],
    )

    # Initialize strategy
    orb_strategy = OpeningRangeBreakout()

    # Generate signals
    print("\n📊 Generating ORB signals...")
    signals = orb_strategy.generate_signals(data, backtester)
    print(f"   Found {len(signals)} ORB setups")

    if len(signals) == 0:
        print("❌ No signals generated")
        return None

    # Execute trades
    print("\n⚙️  Executing trades...")
    trades_executed = 0

    for signal in signals:
        # Check if account blown
        if backtester.guardian_shield and backtester.guardian_shield.is_account_blown():
            print("❌ Account blown - stopping backtest")
            break

        # Check daily loss limit
        if backtester.check_daily_loss_limit():
            backtester.new_day_reset()
            continue

        # Check max drawdown
        if backtester.check_max_drawdown():
            print("❌ Max drawdown hit - stopping backtest")
            break

        # Open position
        backtester.positions.append(signal)

        # Simulate trade execution
        entry_time = signal['entry_time']
        future_data = data[data.index > entry_time]

        exit_found = False

        for idx, bar in future_data.iterrows():
            # Check stop loss
            if backtester.check_stop_loss(signal, bar):
                exit_price = signal['stop_loss']
                exit_time = idx
                reason = "Stop Loss"
                exit_found = True

            # Check take profit
            elif backtester.check_take_profit(signal, bar):
                exit_price = signal['take_profit']
                exit_time = idx
                reason = "Take Profit"
                exit_found = True

            if exit_found:
                backtester.close_position(signal, exit_price, exit_time, reason)
                trades_executed += 1
                break

        # Close at end of data if no exit
        if not exit_found and signal in backtester.positions:
            last_bar = future_data.iloc[-1]
            backtester.close_position(
                signal,
                last_bar['Close'],
                future_data.index[-1],
                "End of data"
            )
            trades_executed += 1

    print(f"   Executed {trades_executed} trades")

    # Print results
    backtester.print_results()

    return backtester.get_results()

def run_vwap_backtest(data):
    """Run VWAP Mean Reversion backtest"""

    print("\n" + "="*60)
    print("VWAP MEAN REVERSION BACKTEST")
    print("="*60)

    config = {
        'initial_capital': 50000,
        'risk_percent': 0.006,
        'enable_guardian_shield': True,
    }

    # Initialize backtester
    backtester = SPX500Backtester(
        data=data,
        initial_capital=config['initial_capital'],
        risk_percent=config['risk_percent'],
        enable_guardian_shield=config['enable_guardian_shield'],
    )

    # Initialize strategy
    vwap_strategy = VWAPMeanReversion()

    # Generate signals
    print("\n📊 Generating VWAP signals...")
    signals = vwap_strategy.generate_signals(data, backtester)
    print(f"   Found {len(signals)} VWAP setups")

    if len(signals) == 0:
        print("❌ No signals generated")
        return None

    # Execute trades (same logic as ORB)
    print("\n⚙️  Executing trades...")
    trades_executed = 0

    for signal in signals:
        if backtester.guardian_shield and backtester.guardian_shield.is_account_blown():
            print("❌ Account blown - stopping backtest")
            break

        if backtester.check_daily_loss_limit():
            backtester.new_day_reset()
            continue

        if backtester.check_max_drawdown():
            print("❌ Max drawdown hit - stopping backtest")
            break

        backtester.positions.append(signal)

        entry_time = signal['entry_time']
        future_data = data[data.index > entry_time]

        exit_found = False

        for idx, bar in future_data.iterrows():
            if backtester.check_stop_loss(signal, bar):
                exit_price = signal['stop_loss']
                exit_time = idx
                reason = "Stop Loss"
                exit_found = True

            elif backtester.check_take_profit(signal, bar):
                exit_price = signal['take_profit']
                exit_time = idx
                reason = "Take Profit"
                exit_found = True

            if exit_found:
                backtester.close_position(signal, exit_price, exit_time, reason)
                trades_executed += 1
                break

        if not exit_found and signal in backtester.positions:
            last_bar = future_data.iloc[-1]
            backtester.close_position(
                signal,
                last_bar['Close'],
                future_data.index[-1],
                "End of data"
            )
            trades_executed += 1

    print(f"   Executed {trades_executed} trades")

    # Print results
    backtester.print_results()

    return backtester.get_results()

def main():
    """Main execution"""

    print("="*60)
    print("SPX500 TRADING STRATEGY BACKTESTER")
    print("Blue Guardian Prop Firm Optimized")
    print("="*60)

    # Load sample data
    print("\n📂 Loading data...")
    data = pd.read_csv('data/spx500_sample_data.csv', index_col=0)

    # Convert index to DatetimeIndex (handle timezone-aware strings)
    data.index = pd.to_datetime(data.index, utc=True).tz_convert('America/New_York')

    print(f"✅ Loaded {len(data)} bars")
    print(f"   Date range: {data.index[0].date()} to {data.index[-1].date()}")

    # Count unique trading days
    unique_dates = len(set([d.date() for d in data.index]))
    print(f"   Trading days: {unique_dates}")

    # Configuration
    print("\n⚙️  Configuration:")
    print(f"   Initial Capital: $50,000")
    print(f"   Risk per Trade: 0.6%")
    print(f"   Guardian Shield: Enabled (2% auto-close)")

    # Run backtests
    print("\n" + "="*60)
    print("RUNNING BACKTESTS")
    print("="*60)

    # 1. Opening Range Breakout
    orb_results = run_orb_backtest(data)

    # 2. VWAP Mean Reversion
    vwap_results = run_vwap_backtest(data)

    # Summary
    print("\n" + "="*60)
    print("🏆 BACKTEST SUMMARY")
    print("="*60)

    if orb_results:
        print("\n📈 ORB Strategy:")
        print(f"   Total Return:     {orb_results['metrics']['total_return']:>8.2f}%")
        print(f"   Win Rate:         {orb_results['metrics']['win_rate']:>8.2f}%")
        print(f"   Profit Factor:    {orb_results['metrics']['profit_factor']:>8.2f}")
        print(f"   Sharpe Ratio:     {orb_results['metrics']['sharpe_ratio']:>8.2f}")
        print(f"   Max Drawdown:     {orb_results['metrics']['max_drawdown_pct']:>8.2f}%")
        print(f"   Total Trades:     {orb_results['metrics']['total_trades']:>8}")
        print(f"   Guardian Shields: {orb_results['guardian_shield_triggers']:>8}")

        # Assessment
        if (orb_results['metrics']['win_rate'] >= 65 and
            orb_results['metrics']['max_drawdown_pct'] > -4 and
            orb_results['metrics']['total_return'] > 0):
            print(f"   ✅ Assessment: GOOD - Ready for demo testing")
        elif (orb_results['metrics']['win_rate'] >= 55 and
              orb_results['metrics']['max_drawdown_pct'] > -5):
            print(f"   ⚠️  Assessment: MARGINAL - Needs refinement")
        else:
            print(f"   ❌ Assessment: POOR - Major revision needed")

    if vwap_results:
        print("\n📉 VWAP Strategy:")
        print(f"   Total Return:     {vwap_results['metrics']['total_return']:>8.2f}%")
        print(f"   Win Rate:         {vwap_results['metrics']['win_rate']:>8.2f}%")
        print(f"   Profit Factor:    {vwap_results['metrics']['profit_factor']:>8.2f}")
        print(f"   Sharpe Ratio:     {vwap_results['metrics']['sharpe_ratio']:>8.2f}")
        print(f"   Max Drawdown:     {vwap_results['metrics']['max_drawdown_pct']:>8.2f}%")
        print(f"   Total Trades:     {vwap_results['metrics']['total_trades']:>8}")
        print(f"   Guardian Shields: {vwap_results['guardian_shield_triggers']:>8}")

        # Assessment
        if (vwap_results['metrics']['win_rate'] >= 65 and
            vwap_results['metrics']['max_drawdown_pct'] > -4 and
            vwap_results['metrics']['total_return'] > 0):
            print(f"   ✅ Assessment: GOOD - Ready for demo testing")
        elif (vwap_results['metrics']['win_rate'] >= 55 and
              vwap_results['metrics']['max_drawdown_pct'] > -5):
            print(f"   ⚠️  Assessment: MARGINAL - Needs refinement")
        else:
            print(f"   ❌ Assessment: POOR - Major revision needed")

    print("\n" + "="*60)
    print("📝 NOTES:")
    print("- This is SAMPLE data, not real market data")
    print("- Real market testing required on OctaFX demo")
    print("- Results demonstrate system functionality")
    print("- Actual performance will vary with real data")
    print("="*60)

if __name__ == "__main__":
    main()
