#!/usr/bin/env python3
"""
VALIDATE OPTIMAL CONFIGURATION - Proper Walk-Forward Testing

Takes the winning configuration and validates it properly:
1. Walk-forward validation (train on past, test on future)
2. Realistic costs (slippage, commission, spread)
3. Different market conditions (trending, ranging, volatile)
4. Stress testing (what if win rate drops?)

This is the REAL test of profitability!
"""

import pandas as pd
import numpy as np
import json
import pickle
from pathlib import Path
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("PHASE 4: VALIDATE OPTIMAL CONFIGURATION")
print("="*80)

# Load winner configuration
print("\n[1/8] Loading winner configuration...")
with open('timeframe_optimization_results.json', 'r') as f:
    results = json.load(f)

winner_config = results['configuration']
winner_perf = results['performance']
print(f"Winner: {winner_config}")
print(f"Expected win rate: {winner_perf['win_rate']*100:.2f}%")
print(f"Expected trades: {winner_perf['total_trades']:,}")
print(f"ML Column: {results['ml_column']}")
print(f"Threshold: {results['threshold']}")

# Load best of best results
try:
    with open('best_of_best_summary.json', 'r') as f:
        best_of_best = json.load(f)
    print(f"\nBest of Best Approach: {best_of_best['elite_filtered']['approach']}")
except:
    print("\nNo best of best results found, using original model")
    best_of_best = None

# ============================================================================
# WALK-FORWARD VALIDATION
# ============================================================================
print("\n" + "="*80)
print("WALK-FORWARD VALIDATION")
print("="*80)

print("\nLoading data...")
df = pd.read_csv('data/spx500_stooq_intraday.csv')
df['Datetime'] = pd.to_datetime(df['Datetime'], utc=True)
df = df.sort_values('Datetime').reset_index(drop=True)

print(f"Total bars: {len(df):,}")
print(f"Date range: {df['Datetime'].min()} to {df['Datetime'].max()}")

# Load ML predictions first
print("\nLoading ML predictions...")
predictions = pd.read_csv('ml_predictions.csv')
predictions['timestamp'] = pd.to_datetime(predictions['timestamp'], utc=True)

# Merge predictions with price data
df = df.merge(predictions[['timestamp', 'ml_probability']],
              left_on='Datetime', right_on='timestamp', how='left')

# Load best of best predictions if available
try:
    best_predictions = pd.read_csv('ml_best_of_best_predictions.csv')
    best_predictions['timestamp'] = pd.to_datetime(best_predictions['timestamp'], utc=True)

    df = df.merge(best_predictions[['timestamp', 'ml_prob_elite', 'ml_prob_top', 'ml_prob_ensemble']],
                  on='timestamp', how='left')
    use_elite = True
except:
    use_elite = False

# Drop rows without predictions (we only want bars where we have ML predictions)
df = df.dropna(subset=['ml_probability']).reset_index(drop=True)
print(f"Bars with ML predictions: {len(df):,}")

# Now split into periods
df['week'] = df['Datetime'].dt.isocalendar().week
df['year'] = df['Datetime'].dt.year
weeks = df.groupby(['year', 'week']).size().reset_index(drop=True)
n_weeks = len(weeks)

print(f"Total weeks: {n_weeks}")

# Walk-forward: Train on 70%, test on 30%
train_weeks = int(n_weeks * 0.7)
test_weeks = n_weeks - train_weeks

print(f"\nWalk-forward split:")
print(f"  Training weeks: {train_weeks} (70%)")
print(f"  Testing weeks: {test_weeks} (30%)")

# Get date split
week_groups = df.groupby(['year', 'week'])['Datetime'].min().reset_index()
split_date = week_groups.iloc[train_weeks]['Datetime']

df_train = df[df['Datetime'] < split_date].copy()
df_test = df[df['Datetime'] >= split_date].copy()

print(f"\nTraining period: {df_train['Datetime'].min()} to {df_train['Datetime'].max()}")
print(f"Testing period: {df_test['Datetime'].min()} to {df_test['Datetime'].max()}")
print(f"Training bars: {len(df_train):,}")
print(f"Testing bars: {len(df_test):,}")

# ============================================================================
# BACKTEST WITH REALISTIC COSTS
# ============================================================================
print("\n" + "="*80)
print("BACKTEST WITH REALISTIC COSTS")
print("="*80)

def backtest_with_costs(df, ml_prob_col, threshold=0.8, slippage_pct=0.0002,
                        commission=5, spread_pts=1):
    """
    Backtest with realistic trading costs

    Parameters:
    - slippage_pct: 0.02% slippage on entry/exit
    - commission: $5 per trade
    - spread_pts: 1 point spread
    """

    capital = 100000
    equity_curve = [capital]
    trades = []
    position = None

    for i in range(len(df) - 100):
        row = df.iloc[i]

        # Skip if no high confidence signal
        if row[ml_prob_col] < threshold:
            continue

        # Entry
        entry_price = row['Close']
        entry_price += entry_price * slippage_pct  # Slippage
        entry_price += spread_pts  # Spread

        # Position size (1% risk)
        risk_pct = 0.01
        stop_loss = entry_price * 0.999  # 0.1% SL
        risk_per_share = entry_price - stop_loss
        shares = (capital * risk_pct) / risk_per_share

        # Take profit levels
        tp1 = entry_price * 1.0015  # 1.5R (0.15%)
        tp2 = entry_price * 1.0025  # 2.5R
        tp3 = entry_price * 1.0040  # 4.0R

        # Look forward for exit
        exit_price = None
        exit_reason = None
        exit_idx = None

        for j in range(i+1, min(i+61, len(df))):  # 60 minute timeout
            future_high = df.iloc[j]['High']
            future_low = df.iloc[j]['Low']

            # Check TP3
            if future_high >= tp3:
                exit_price = tp3
                exit_reason = 'tp3'
                exit_idx = j
                break

            # Check TP2
            if future_high >= tp2:
                exit_price = tp2
                exit_reason = 'tp2'
                exit_idx = j
                break

            # Check TP1
            if future_high >= tp1:
                exit_price = tp1
                exit_reason = 'tp1'
                exit_idx = j
                break

            # Check SL
            if future_low <= stop_loss:
                exit_price = stop_loss
                exit_reason = 'sl'
                exit_idx = j
                break

        # Timeout
        if exit_price is None:
            exit_idx = min(i+60, len(df)-1)
            exit_price = df.iloc[exit_idx]['Close']
            exit_reason = 'timeout'

        # Apply exit slippage and commission
        exit_price -= exit_price * slippage_pct
        exit_price -= spread_pts

        # Calculate P/L
        gross_pnl = (exit_price - entry_price) * shares
        net_pnl = gross_pnl - (2 * commission)  # Entry + Exit commission

        capital += net_pnl
        equity_curve.append(capital)

        trades.append({
            'entry_time': row['Datetime'],
            'exit_time': df.iloc[exit_idx]['Datetime'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'shares': shares,
            'gross_pnl': gross_pnl,
            'commission': 2 * commission,
            'net_pnl': net_pnl,
            'exit_reason': exit_reason,
            'ml_prob': row[ml_prob_col],
            'capital': capital
        })

    # Calculate metrics
    if len(trades) == 0:
        return None

    df_trades = pd.DataFrame(trades)
    winning_trades = df_trades[df_trades['net_pnl'] > 0]
    losing_trades = df_trades[df_trades['net_pnl'] < 0]

    total_return = (capital - 100000) / 100000 * 100
    max_dd = 0
    peak = 100000

    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd

    metrics = {
        'total_trades': len(trades),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': len(winning_trades) / len(trades) if len(trades) > 0 else 0,
        'total_return': total_return,
        'final_capital': capital,
        'max_drawdown': max_dd,
        'avg_win': winning_trades['net_pnl'].mean() if len(winning_trades) > 0 else 0,
        'avg_loss': losing_trades['net_pnl'].mean() if len(losing_trades) > 0 else 0,
        'profit_factor': abs(winning_trades['net_pnl'].sum() / losing_trades['net_pnl'].sum()) if len(losing_trades) > 0 and losing_trades['net_pnl'].sum() != 0 else 0,
        'total_commission': df_trades['commission'].sum()
    }

    return metrics, df_trades, equity_curve

# Test on training data
print("\n[1/3] Testing on TRAINING data (in-sample)...")
train_metrics, train_trades, train_equity = backtest_with_costs(
    df_train, 'ml_probability', threshold=0.8
)

if train_metrics:
    print(f"Training Results (WITH COSTS):")
    print(f"  Total Trades: {train_metrics['total_trades']}")
    print(f"  Win Rate: {train_metrics['win_rate']*100:.2f}%")
    print(f"  Total Return: {train_metrics['total_return']:.2f}%")
    print(f"  Max Drawdown: {train_metrics['max_drawdown']:.2f}%")
    print(f"  Profit Factor: {train_metrics['profit_factor']:.2f}")
    print(f"  Total Commission: ${train_metrics['total_commission']:.2f}")
else:
    print("No trades generated in training period")

# Test on testing data (OUT-OF-SAMPLE)
print("\n[2/3] Testing on TESTING data (out-of-sample)...")
test_metrics, test_trades, test_equity = backtest_with_costs(
    df_test, 'ml_probability', threshold=0.8
)

if test_metrics:
    print(f"Testing Results (WITH COSTS - OUT OF SAMPLE):")
    print(f"  Total Trades: {test_metrics['total_trades']}")
    print(f"  Win Rate: {test_metrics['win_rate']*100:.2f}%")
    print(f"  Total Return: {test_metrics['total_return']:.2f}%")
    print(f"  Max Drawdown: {test_metrics['max_drawdown']:.2f}%")
    print(f"  Profit Factor: {test_metrics['profit_factor']:.2f}")
    print(f"  Avg Win: ${test_metrics['avg_win']:.2f}")
    print(f"  Avg Loss: ${test_metrics['avg_loss']:.2f}")
else:
    print("No trades generated in testing period")

# Compare different cost scenarios
print("\n[3/3] Testing different cost scenarios...")

cost_scenarios = [
    {'name': 'Optimistic', 'slippage': 0.0001, 'commission': 2, 'spread': 0.5},
    {'name': 'Realistic', 'slippage': 0.0002, 'commission': 5, 'spread': 1.0},
    {'name': 'Conservative', 'slippage': 0.0003, 'commission': 10, 'spread': 2.0},
    {'name': 'Worst Case', 'slippage': 0.0005, 'commission': 15, 'spread': 3.0}
]

scenario_results = []

for scenario in cost_scenarios:
    metrics, _, _ = backtest_with_costs(
        df_test,
        'ml_probability',
        threshold=0.8,
        slippage_pct=scenario['slippage'],
        commission=scenario['commission'],
        spread_pts=scenario['spread']
    )

    if metrics:
        scenario_results.append({
            'scenario': scenario['name'],
            'win_rate': metrics['win_rate'],
            'total_return': metrics['total_return'],
            'max_dd': metrics['max_drawdown'],
            'trades': metrics['total_trades'],
            'pf': metrics['profit_factor']
        })

print("\nCost Scenario Comparison (Out-of-Sample):")
df_scenarios = pd.DataFrame(scenario_results)
print(df_scenarios.to_string(index=False))

# ============================================================================
# MARKET CONDITION ANALYSIS
# ============================================================================
print("\n" + "="*80)
print("MARKET CONDITION ANALYSIS")
print("="*80)

# Calculate market regime
df_test['returns'] = df_test['Close'].pct_change()
df_test['volatility'] = df_test['returns'].rolling(60).std()
df_test['trend'] = (df_test['Close'] > df_test['Close'].rolling(60).mean()).astype(int)

# Categorize days
def categorize_market(row):
    vol = row['volatility']
    trend = row['trend']

    if pd.isna(vol):
        return 'unknown'

    vol_median = df_test['volatility'].median()

    if trend == 1 and vol > vol_median:
        return 'trending_volatile'
    elif trend == 1 and vol <= vol_median:
        return 'trending_calm'
    elif trend == 0 and vol > vol_median:
        return 'ranging_volatile'
    else:
        return 'ranging_calm'

df_test['market_regime'] = df_test.apply(categorize_market, axis=1)

# Test each regime
print("\nPerformance by Market Regime:")
regimes = ['trending_volatile', 'trending_calm', 'ranging_volatile', 'ranging_calm']

regime_performance = []

for regime in regimes:
    df_regime = df_test[df_test['market_regime'] == regime].copy()

    if len(df_regime) == 0:
        continue

    metrics, _, _ = backtest_with_costs(df_regime, 'ml_probability', threshold=0.8)

    if metrics and metrics['total_trades'] > 0:
        regime_performance.append({
            'regime': regime,
            'trades': metrics['total_trades'],
            'win_rate': metrics['win_rate'],
            'return': metrics['total_return'],
            'max_dd': metrics['max_drawdown']
        })

if regime_performance:
    df_regime = pd.DataFrame(regime_performance)
    print(df_regime.to_string(index=False))
else:
    print("Insufficient data for regime analysis")

# ============================================================================
# STRESS TESTING
# ============================================================================
print("\n" + "="*80)
print("STRESS TESTING - What If Win Rate Drops?")
print("="*80)

print("\nSimulating degraded performance...")

# Get actual test trades
if test_trades is not None and len(test_trades) > 0:
    # Simulate win rate drops
    win_rate_drops = [0, 10, 20, 30, 40, 50]  # % drop

    stress_results = []

    for drop_pct in win_rate_drops:
        # Randomly convert winning trades to losses
        test_trades_copy = test_trades.copy()

        winning_idx = test_trades_copy[test_trades_copy['net_pnl'] > 0].index
        n_to_flip = int(len(winning_idx) * drop_pct / 100)

        if n_to_flip > 0:
            flip_idx = np.random.choice(winning_idx, n_to_flip, replace=False)
            # Convert to losses (average loss)
            avg_loss = test_trades_copy[test_trades_copy['net_pnl'] < 0]['net_pnl'].mean()
            test_trades_copy.loc[flip_idx, 'net_pnl'] = avg_loss

        # Recalculate metrics
        total_pnl = test_trades_copy['net_pnl'].sum()
        final_capital = 100000 + total_pnl
        total_return = total_pnl / 100000 * 100

        winning = test_trades_copy[test_trades_copy['net_pnl'] > 0]
        new_win_rate = len(winning) / len(test_trades_copy)

        stress_results.append({
            'win_rate_drop': f'-{drop_pct}%',
            'new_win_rate': new_win_rate * 100,
            'total_return': total_return,
            'final_capital': final_capital,
            'still_profitable': 'YES' if total_return > 0 else 'NO'
        })

    df_stress = pd.DataFrame(stress_results)
    print("\nStress Test Results:")
    print(df_stress.to_string(index=False))

    # Find break-even point
    profitable = df_stress[df_stress['still_profitable'] == 'YES']
    if len(profitable) > 0:
        max_drop = profitable.iloc[-1]['win_rate_drop']
        print(f"\n✅ System remains profitable with up to {max_drop} win rate drop")
    else:
        print("\n❌ System not profitable even with no degradation")

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "="*80)
print("VALIDATION SUMMARY")
print("="*80)

validation_summary = {
    'winner_configuration': winner_config,
    'walk_forward_validation': {
        'training_period': f"{df_train['Datetime'].min()} to {df_train['Datetime'].max()}",
        'testing_period': f"{df_test['Datetime'].min()} to {df_test['Datetime'].max()}",
        'training_performance': train_metrics,
        'testing_performance': test_metrics
    },
    'cost_scenarios': scenario_results,
    'market_regimes': regime_performance if regime_performance else [],
    'stress_test': stress_results if test_trades is not None and len(test_trades) > 0 else []
}

# Save results
with open('validation_results.json', 'w') as f:
    json.dump(validation_summary, f, indent=2, default=str)

print("\n✅ Validation Complete!")
print("\nKey Findings:")

if test_metrics:
    print(f"\n1. OUT-OF-SAMPLE PERFORMANCE:")
    print(f"   Win Rate: {test_metrics['win_rate']*100:.2f}%")
    print(f"   Total Return: {test_metrics['total_return']:.2f}%")
    print(f"   Max Drawdown: {test_metrics['max_drawdown']:.2f}%")
    print(f"   Profit Factor: {test_metrics['profit_factor']:.2f}")

    weeks_tested = (df_test['Datetime'].max() - df_test['Datetime'].min()).days / 7
    weekly_return = test_metrics['total_return'] / weeks_tested if weeks_tested > 0 else 0

    print(f"\n2. REALISTIC EXPECTATIONS:")
    print(f"   Weekly Return: {weekly_return:.2f}%")
    print(f"   Monthly Return: {weekly_return * 4.33:.2f}%")

    print(f"\n3. SUSTAINABILITY:")
    if test_metrics['max_drawdown'] < 5:
        print(f"   ✅ Low drawdown ({test_metrics['max_drawdown']:.2f}%) - sustainable")
    else:
        print(f"   ⚠️  High drawdown ({test_metrics['max_drawdown']:.2f}%) - risky")

    if test_metrics['win_rate'] >= 0.60:
        print(f"   ✅ Good win rate ({test_metrics['win_rate']*100:.2f}%) - reliable")
    else:
        print(f"   ⚠️  Low win rate ({test_metrics['win_rate']*100:.2f}%) - needs work")

print("\n" + "="*80)
print("PHASE 4 COMPLETE - Validation Done!")
print("="*80)
print("\nSaved: validation_results.json")
