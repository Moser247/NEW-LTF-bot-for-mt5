"""
Main script to run backtests for SPX500 strategies
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

# Add src to path
sys.path.append('src')

from backtesting.backtest_engine import SPX500Backtester, GuardianShieldSimulator
from strategies.opening_range_breakout import OpeningRangeBreakout
from strategies.vwap_mean_reversion import VWAPMeanReversion
from data.data_downloader import DataDownloader


def run_orb_backtest(data: pd.DataFrame, config: dict = None):
    """
    Run Opening Range Breakout backtest

    Args:
        data: Historical OHLCV data
        config: Configuration dictionary

    Returns:
        Backtest results
    """
    if config is None:
        config = {
            'initial_capital': 50000,
            'risk_percent': 0.006,  # 0.6%
            'enable_guardian_shield': True,
        }

    print("\n" + "="*60)
    print("OPENING RANGE BREAKOUT (ORB) BACKTEST")
    print("="*60)

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
    print("\nGenerating ORB signals...")
    signals = orb_strategy.generate_signals(data, backtester)
    print(f"Found {len(signals)} ORB setups")

    if len(signals) == 0:
        print("❌ No signals generated. Check data and strategy parameters.")
        return None

    # Execute trades
    print("\nExecuting trades...")
    for signal in signals:
        # Check if we're still allowed to trade
        if backtester.guardian_shield and backtester.guardian_shield.is_account_blown():
            print("❌ Account blown - stopping backtest")
            break

        # Check daily loss limit
        if backtester.check_daily_loss_limit():
            # Reset for next day
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
        entry_price = signal['entry_price']

        # Find exit (stop loss or take profit)
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
                # Close position
                backtester.close_position(signal, exit_price, exit_time, reason)
                break

        # If no exit found, close at end of data
        if not exit_found and signal in backtester.positions:
            last_bar = future_data.iloc[-1]
            backtester.close_position(
                signal,
                last_bar['Close'],
                future_data.index[-1],
                "End of data"
            )

    # Print results
    backtester.print_results()

    return backtester.get_results()


def run_vwap_backtest(data: pd.DataFrame, config: dict = None):
    """
    Run VWAP Mean Reversion backtest

    Args:
        data: Historical OHLCV data
        config: Configuration dictionary

    Returns:
        Backtest results
    """
    if config is None:
        config = {
            'initial_capital': 50000,
            'risk_percent': 0.006,  # 0.6%
            'enable_guardian_shield': True,
        }

    print("\n" + "="*60)
    print("VWAP MEAN REVERSION BACKTEST")
    print("="*60)

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
    print("\nGenerating VWAP signals...")
    signals = vwap_strategy.generate_signals(data, backtester)
    print(f"Found {len(signals)} VWAP setups")

    if len(signals) == 0:
        print("❌ No signals generated. Check data and strategy parameters.")
        return None

    # Execute trades (same logic as ORB)
    print("\nExecuting trades...")
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
                break

        if not exit_found and signal in backtester.positions:
            last_bar = future_data.iloc[-1]
            backtester.close_position(
                signal,
                last_bar['Close'],
                future_data.index[-1],
                "End of data"
            )

    # Print results
    backtester.print_results()

    return backtester.get_results()


def main():
    """Main execution"""

    print("="*60)
    print("SPX500 TRADING STRATEGY BACKTESTER")
    print("Blue Guardian Prop Firm Optimized")
    print("="*60)

    # Configuration
    config = {
        'initial_capital': 50000,  # Blue Guardian $50K account
        'risk_percent': 0.006,  # 0.6% risk per trade
        'enable_guardian_shield': True,  # Simulate 2% auto-close
    }

    print("\nConfiguration:")
    print(f"  Initial Capital: ${config['initial_capital']:,}")
    print(f"  Risk per Trade: {config['risk_percent']*100}%")
    print(f"  Guardian Shield: {'Enabled' if config['enable_guardian_shield'] else 'Disabled'}")

    # Download data
    print("\n" + "-"*60)
    print("DOWNLOADING DATA")
    print("-"*60)

    downloader = DataDownloader()

    # Try to load existing data first
    data_file = "data/spx500_5m_latest.csv"

    if os.path.exists(data_file):
        print(f"Loading existing data from {data_file}...")
        data = downloader.load_from_csv(data_file)
    else:
        print("Downloading new data...")
        data = downloader.download_sp500(
            interval='5m',
            save_to_file=True,
            filename=data_file
        )

    if data is None or len(data) == 0:
        print("❌ Failed to load data. Exiting.")
        return

    # Prepare data
    print("\nPreparing data for backtesting...")
    data = downloader.prepare_for_backtesting(data)

    print(f"✅ Data ready: {len(data)} bars from {data.index[0].date()} to {data.index[-1].date()}")

    # Run backtests
    print("\n" + "="*60)
    print("RUNNING BACKTESTS")
    print("="*60)

    # 1. Opening Range Breakout
    orb_results = run_orb_backtest(data, config)

    # 2. VWAP Mean Reversion
    vwap_results = run_vwap_backtest(data, config)

    # Summary
    print("\n" + "="*60)
    print("BACKTEST SUMMARY")
    print("="*60)

    if orb_results:
        print("\nORB Strategy:")
        print(f"  Total Return: {orb_results['metrics']['total_return']:.2f}%")
        print(f"  Win Rate: {orb_results['metrics']['win_rate']:.2f}%")
        print(f"  Profit Factor: {orb_results['metrics']['profit_factor']:.2f}")
        print(f"  Max Drawdown: {orb_results['metrics']['max_drawdown_pct']:.2f}%")
        print(f"  Guardian Shield Triggers: {orb_results['guardian_shield_triggers']}")

    if vwap_results:
        print("\nVWAP Strategy:")
        print(f"  Total Return: {vwap_results['metrics']['total_return']:.2f}%")
        print(f"  Win Rate: {vwap_results['metrics']['win_rate']:.2f}%")
        print(f"  Profit Factor: {vwap_results['metrics']['profit_factor']:.2f}")
        print(f"  Max Drawdown: {vwap_results['metrics']['max_drawdown_pct']:.2f}%")
        print(f"  Guardian Shield Triggers: {vwap_results['guardian_shield_triggers']}")

    print("\n" + "="*60)
    print("BACKTEST COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
