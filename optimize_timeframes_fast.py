#!/usr/bin/env python3
"""
FAST MULTI-TIMEFRAME OPTIMIZATION - Practical approach

Instead of re-training models from scratch for each TF combination,
this uses the existing trained models and tests different ML probability
thresholds and filtering strategies.

This is much faster and still finds the optimal configuration.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
import pickle
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("PHASE 2: FAST MULTI-TIMEFRAME OPTIMIZATION")
print("="*80)

# Load existing predictions with all model variants
print("\n[1/5] Loading predictions from all trained models...")

# Load base predictions
df_base = pd.read_csv('ml_predictions.csv')
print(f"Base model predictions: {len(df_base):,} samples")

# Load best-of-best predictions
df_bob = pd.read_csv('ml_best_of_best_predictions.csv')
print(f"Best-of-best predictions: {len(df_bob):,} samples")

# Merge
df = df_base.copy()
df['ml_prob_elite'] = df_bob['ml_prob_elite'].values[:len(df)]
df['ml_prob_top'] = df_bob['ml_prob_top'].values[:len(df)]
df['ml_prob_ensemble'] = df_bob['ml_prob_ensemble'].values[:len(df)]
df['quality_score'] = df_bob['quality_score'].values[:len(df)]
df['ensemble_votes'] = df_bob['ensemble_votes'].values[:len(df)]

print(f"Combined dataset: {len(df):,} samples")

# Load SPX500 data for backtesting
print("\n[2/5] Loading price data...")
price_data = pd.read_csv('data/spx500_stooq_intraday.csv')
price_data['Datetime'] = pd.to_datetime(price_data['Datetime'], utc=True)
price_data = price_data.sort_values('Datetime').reset_index(drop=True)

# Align predictions with price data
df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
price_data['timestamp'] = price_data['Datetime']

# Merge
df_merged = df.merge(price_data[['timestamp', 'Close', 'High', 'Low']],
                     on='timestamp', how='left')

print(f"Merged dataset: {len(df_merged):,} samples with prices")

# ============================================================================
# BACKTEST FUNCTION
# ============================================================================

def backtest_configuration(df, ml_col, threshold, name, max_daily_loss=0.02):
    """
    Fast backtest of a configuration

    Returns: metrics dict
    """
    capital = 100000
    initial_capital = 100000
    trades = []

    for i in range(len(df) - 100):
        row = df.iloc[i]

        # Skip if no signal
        if pd.isna(row[ml_col]) or row[ml_col] < threshold:
            continue

        # Skip if no price data
        if pd.isna(row['Close']):
            continue

        # Entry
        entry_price = row['Close']

        # Position size (1.5% risk for high conf)
        risk_pct = 0.015
        stop_loss = entry_price * 0.999  # 0.1% SL
        risk_per_share = entry_price - stop_loss
        shares = (capital * risk_pct) / risk_per_share

        # Take profit levels
        tp1 = entry_price * 1.0015  # 1.5R
        tp2 = entry_price * 1.0025  # 2.5R
        tp3 = entry_price * 1.0040  # 4.0R

        # Look forward for exit
        exit_price = None
        exit_reason = None

        for j in range(i+1, min(i+61, len(df))):
            future_high = df.iloc[j]['High']
            future_low = df.iloc[j]['Low']

            if pd.isna(future_high) or pd.isna(future_low):
                continue

            # Check TPs
            if future_high >= tp3:
                exit_price = tp3
                exit_reason = 'tp3'
                break
            if future_high >= tp2:
                exit_price = tp2
                exit_reason = 'tp2'
                break
            if future_high >= tp1:
                exit_price = tp1
                exit_reason = 'tp1'
                break

            # Check SL
            if future_low <= stop_loss:
                exit_price = stop_loss
                exit_reason = 'sl'
                break

        # Timeout
        if exit_price is None:
            exit_idx = min(i+60, len(df)-1)
            exit_price = df.iloc[exit_idx]['Close']
            if pd.isna(exit_price):
                continue
            exit_reason = 'timeout'

        # Calculate P/L
        pnl = (exit_price - entry_price) * shares

        # Check daily loss limit
        daily_loss = (initial_capital - capital) / initial_capital
        if daily_loss > max_daily_loss:
            break  # Stop trading for the day

        capital += pnl

        trades.append({
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'exit_reason': exit_reason,
            'ml_prob': row[ml_col],
            'capital': capital
        })

    # Calculate metrics
    if len(trades) == 0:
        return None

    df_trades = pd.DataFrame(trades)
    winning = df_trades[df_trades['pnl'] > 0]
    losing = df_trades[df_trades['pnl'] < 0]

    total_return = (capital - initial_capital) / initial_capital * 100

    # Max drawdown
    max_dd = 0
    peak = initial_capital
    for cap in df_trades['capital'].values:
        if cap > peak:
            peak = cap
        dd = (peak - cap) / peak * 100
        if dd > max_dd:
            max_dd = dd

    return {
        'config_name': name,
        'ml_column': ml_col,
        'threshold': threshold,
        'total_trades': len(trades),
        'winning_trades': len(winning),
        'losing_trades': len(losing),
        'win_rate': len(winning) / len(trades),
        'total_return': total_return,
        'final_capital': capital,
        'max_drawdown': max_dd,
        'avg_win': winning['pnl'].mean() if len(winning) > 0 else 0,
        'avg_loss': losing['pnl'].mean() if len(losing) > 0 else 0,
        'profit_factor': abs(winning['pnl'].sum() / losing['pnl'].sum()) if len(losing) > 0 and losing['pnl'].sum() != 0 else 0
    }

# ============================================================================
# TEST CONFIGURATIONS
# ============================================================================
print("\n" + "="*80)
print("TESTING CONFIGURATIONS")
print("="*80)

configurations = []

# Original model at different thresholds
print("\n[3/5] Testing original model...")
for thresh in [0.6, 0.7, 0.8, 0.9]:
    result = backtest_configuration(
        df_merged,
        'ml_probability',
        thresh,
        f'Original Model (≥{thresh:.1f})'
    )
    if result:
        configurations.append(result)
        print(f"  Threshold ≥{thresh:.1f}: {result['total_trades']} trades, "
              f"{result['win_rate']*100:.1f}% WR, {result['total_return']:.1f}% return")

# Elite filtered model
print("\n[4/5] Testing elite filtered model...")
for thresh in [0.6, 0.7, 0.8]:
    result = backtest_configuration(
        df_merged,
        'ml_prob_elite',
        thresh,
        f'Elite Filtered (≥{thresh:.1f})'
    )
    if result:
        configurations.append(result)
        print(f"  Threshold ≥{thresh:.1f}: {result['total_trades']} trades, "
              f"{result['win_rate']*100:.1f}% WR, {result['total_return']:.1f}% return")

# Top features model
print("\n[5/5] Testing top features model...")
for thresh in [0.6, 0.7, 0.8]:
    result = backtest_configuration(
        df_merged,
        'ml_prob_top',
        thresh,
        f'Top 15 Features (≥{thresh:.1f})'
    )
    if result:
        configurations.append(result)
        print(f"  Threshold ≥{thresh:.1f}: {result['total_trades']} trades, "
              f"{result['win_rate']*100:.1f}% WR, {result['total_return']:.1f}% return")

# Ensemble model
print("\nTesting ensemble model...")
for thresh in [0.6, 0.7, 0.8]:
    result = backtest_configuration(
        df_merged,
        'ml_prob_ensemble',
        thresh,
        f'Ensemble (≥{thresh:.1f})'
    )
    if result:
        configurations.append(result)
        print(f"  Threshold ≥{thresh:.1f}: {result['total_trades']} trades, "
              f"{result['win_rate']*100:.1f}% WR, {result['total_return']:.1f}% return")

# Quality-based filtering (use original model + quality score)
print("\nTesting quality score filtering...")
for min_quality in [2, 3]:
    # Filter by quality
    df_quality = df_merged[df_merged['quality_score'] >= min_quality].copy()

    result = backtest_configuration(
        df_quality,
        'ml_probability',
        0.7,
        f'Original + Quality≥{min_quality}'
    )
    if result:
        configurations.append(result)
        print(f"  Quality ≥{min_quality}: {result['total_trades']} trades, "
              f"{result['win_rate']*100:.1f}% WR, {result['total_return']:.1f}% return")

# Voting ensemble (2/3 or 3/3)
print("\nTesting voting ensemble...")
for min_votes in [2, 3]:
    df_votes = df_merged[df_merged['ensemble_votes'] >= min_votes].copy()

    result = backtest_configuration(
        df_votes,
        'ml_probability',
        0.6,
        f'Ensemble Voting (≥{min_votes}/3)'
    )
    if result:
        configurations.append(result)
        print(f"  {min_votes}/3 votes: {result['total_trades']} trades, "
              f"{result['win_rate']*100:.1f}% WR, {result['total_return']:.1f}% return")

# ============================================================================
# RANK CONFIGURATIONS
# ============================================================================
print("\n" + "="*80)
print("RANKING ALL CONFIGURATIONS")
print("="*80)

df_configs = pd.DataFrame(configurations)

# Calculate composite score
# Weighted by: Win Rate (40%), Total Return (30%), Low Drawdown (20%), Num Trades (10%)
df_configs['score'] = (
    df_configs['win_rate'] * 40 +
    df_configs['total_return'] * 0.3 +
    (1 / (df_configs['max_drawdown'] + 0.1)) * 20 +
    np.log1p(df_configs['total_trades']) * 2
)

# Sort by score
df_configs = df_configs.sort_values('score', ascending=False)

# Save results
df_configs.to_csv('timeframe_optimization_comparison.csv', index=False)

print("\n" + "="*80)
print("TOP 10 CONFIGURATIONS")
print("="*80)

top_10 = df_configs.head(10)[['config_name', 'total_trades', 'win_rate',
                                'total_return', 'max_drawdown', 'profit_factor', 'score']]
top_10['win_rate'] = (top_10['win_rate'] * 100).round(2)
top_10['total_return'] = top_10['total_return'].round(2)
top_10['max_drawdown'] = top_10['max_drawdown'].round(2)
top_10['profit_factor'] = top_10['profit_factor'].round(2)
top_10['score'] = top_10['score'].round(2)

print("\n" + top_10.to_string(index=False))

# ============================================================================
# WINNER
# ============================================================================
winner = df_configs.iloc[0]

print("\n" + "="*80)
print("🏆 WINNER CONFIGURATION")
print("="*80)
print(f"\nConfiguration: {winner['config_name']}")
print(f"Total Trades: {int(winner['total_trades']):,}")
print(f"Win Rate: {winner['win_rate']*100:.2f}%")
print(f"Total Return: {winner['total_return']:.2f}%")
print(f"Max Drawdown: {winner['max_drawdown']:.2f}%")
print(f"Profit Factor: {winner['profit_factor']:.2f}")
print(f"Avg Win: ${winner['avg_win']:.2f}")
print(f"Avg Loss: ${winner['avg_loss']:.2f}")
print(f"Composite Score: {winner['score']:.2f}")

# Calculate weekly/monthly returns
days = (df_merged['timestamp'].max() - df_merged['timestamp'].min()).days
weeks = days / 7
months = days / 30

print(f"\nProjected Performance:")
print(f"  Weekly Return: {winner['total_return'] / weeks:.2f}%")
print(f"  Monthly Return: {winner['total_return'] / months:.2f}%")
print(f"  Trades per Week: {winner['total_trades'] / weeks:.1f}")

# Save winner config
winner_config = {
    'configuration': winner['config_name'],
    'ml_column': winner['ml_column'],
    'threshold': float(winner['threshold']),
    'performance': {
        'total_trades': int(winner['total_trades']),
        'win_rate': float(winner['win_rate']),
        'total_return': float(winner['total_return']),
        'max_drawdown': float(winner['max_drawdown']),
        'profit_factor': float(winner['profit_factor']),
        'weekly_return': float(winner['total_return'] / weeks),
        'monthly_return': float(winner['total_return'] / months)
    },
    'all_results': configurations
}

with open('timeframe_optimization_results.json', 'w') as f:
    json.dump(winner_config, f, indent=2)

print("\n" + "="*80)
print("PHASE 2 COMPLETE - Fast Optimization Done!")
print("="*80)
print("\nFiles saved:")
print("  - timeframe_optimization_results.json")
print("  - timeframe_optimization_comparison.csv")
print("\nNext: Run Phase 4 (Validation)")
