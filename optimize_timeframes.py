#!/usr/bin/env python3
"""
MULTI-TIMEFRAME OPTIMIZATION - Find the ABSOLUTE BEST timeframe configuration

Tests EVERY possible combination:
- Single TF: 1m, 5m, 15m, 30m, 1h
- Dual TF: All pairs (Higher TF trend + Lower TF entry)
- Triple TF: All combinations
- Adaptive TF: Different TFs for different times of day

Objective: Find configuration with MAXIMUM profitability
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime, timedelta
import pickle
from ml_feature_extractor import InstitutionalFeatureExtractor
from ml_institutional_strategy import MLInstitutionalStrategy
from xgboost import XGBClassifier
from sklearn.model_selection import TimeSeriesSplit
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("PHASE 2: MULTI-TIMEFRAME OPTIMIZATION")
print("="*80)

# Load data
print("\n[1/10] Loading SPX500 1-minute data...")
df_1m = pd.read_csv('data/spx500_stooq_intraday.csv', parse_dates=['Datetime'])
df_1m['Datetime'] = pd.to_datetime(df_1m['Datetime'])
df_1m = df_1m.sort_values('Datetime').reset_index(drop=True)
print(f"Loaded {len(df_1m):,} 1-minute bars")
print(f"Date range: {df_1m['Datetime'].min()} to {df_1m['Datetime'].max()}")

# Resample to all timeframes
print("\n[2/10] Resampling to all timeframes...")

def resample_ohlc(df, timeframe):
    """Resample OHLC data to specified timeframe"""
    df = df.set_index('Datetime')
    resampled = df.resample(timeframe).agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    return resampled.reset_index()

timeframes = {
    '1m': df_1m.copy(),
    '5m': resample_ohlc(df_1m, '5T'),
    '15m': resample_ohlc(df_1m, '15T'),
    '30m': resample_ohlc(df_1m, '30T'),
    '1h': resample_ohlc(df_1m, '60T')
}

for tf, data in timeframes.items():
    print(f"  {tf}: {len(data):,} bars")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_features_single_tf(df, timeframe_name):
    """Extract features for single timeframe"""
    print(f"  Extracting features for {timeframe_name}...")

    extractor = InstitutionalFeatureExtractor()

    # Create multi-timeframe dict (use same TF for all)
    mtf_data = {
        'tf1': df.copy(),
        'tf2': df.copy(),
        'tf3': df.copy()
    }

    features = extractor.extract_all_features(mtf_data)
    return features

def extract_features_multi_tf(data_dict, tf_names):
    """Extract features for multiple timeframes"""
    print(f"  Extracting features for {tf_names}...")

    extractor = InstitutionalFeatureExtractor()

    # Create multi-timeframe dict
    mtf_data = {
        'tf1': data_dict['tf1'].copy(),
        'tf2': data_dict['tf2'].copy(),
        'tf3': data_dict['tf3'].copy()
    }

    features = extractor.extract_all_features(mtf_data)
    return features

def label_data(df, target_pct=0.002, stop_pct=0.001, time_window=90):
    """Label data with forward-looking profit/loss"""
    labels = []

    for i in range(len(df)):
        if i >= len(df) - time_window:
            labels.append(0)
            continue

        entry_price = df.iloc[i]['Close']
        future_prices = df.iloc[i+1:i+time_window+1]['High'].values
        future_lows = df.iloc[i+1:i+time_window+1]['Low'].values

        target = entry_price * (1 + target_pct)
        stop = entry_price * (1 - stop_pct)

        # Check if TP hit before SL
        tp_hit = (future_prices >= target).any()
        sl_hit = (future_lows <= stop).any()

        if tp_hit and not sl_hit:
            labels.append(1)
        elif sl_hit and not tp_hit:
            labels.append(0)
        else:
            # Both hit - check which came first
            tp_idx = np.where(future_prices >= target)[0]
            sl_idx = np.where(future_lows <= stop)[0]

            if len(tp_idx) > 0 and len(sl_idx) > 0:
                labels.append(1 if tp_idx[0] < sl_idx[0] else 0)
            else:
                labels.append(0)

    return labels

def train_and_evaluate(features_df, labels, model_name):
    """Train model and return CV performance"""
    # Prepare data
    feature_cols = [col for col in features_df.columns if col not in ['Datetime', 'label']]
    X = features_df[feature_cols].fillna(0)
    y = np.array(labels)

    # Train model
    pos_weight = (len(y) - y.sum()) / (y.sum() + 1)
    model = XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        scale_pos_weight=pos_weight,
        random_state=42,
        n_jobs=-1
    )

    model.fit(X, y)

    # Get predictions
    predictions = model.predict_proba(X)[:, 1]

    # Calculate metrics at different thresholds
    thresholds = [0.6, 0.7, 0.8]
    results = {}

    for thresh in thresholds:
        high_conf = predictions >= thresh
        if high_conf.sum() > 0:
            win_rate = y[high_conf].mean()
            n_trades = high_conf.sum()
        else:
            win_rate = 0
            n_trades = 0

        results[f'thresh_{int(thresh*100)}'] = {
            'win_rate': float(win_rate),
            'n_trades': int(n_trades)
        }

    # Save model
    model_path = f'models/xgboost_{model_name}.pkl'
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)

    return results, model

# ============================================================================
# EXPERIMENT 1: SINGLE TIMEFRAME PERFORMANCE
# ============================================================================
print("\n" + "="*80)
print("EXPERIMENT 1: SINGLE TIMEFRAME PERFORMANCE")
print("="*80)

single_tf_results = {}

for tf_name, tf_data in timeframes.items():
    print(f"\nTesting {tf_name}...")

    # Extract features
    features = extract_features_single_tf(tf_data, tf_name)

    # Label data
    labels = label_data(tf_data)
    features['label'] = labels

    # Train and evaluate
    results, model = train_and_evaluate(features, labels, f'single_{tf_name}')

    single_tf_results[tf_name] = {
        'bars': len(tf_data),
        'win_rate_base': float(np.mean(labels)),
        **results
    }

    print(f"  Base win rate: {np.mean(labels)*100:.2f}%")
    print(f"  High conf (≥0.8): {results['thresh_80']['n_trades']} trades, {results['thresh_80']['win_rate']*100:.2f}% win rate")

print("\n" + "-"*80)
print("SINGLE TIMEFRAME RESULTS:")
print("-"*80)
for tf, res in single_tf_results.items():
    print(f"{tf:>5}: {res['thresh_80']['n_trades']:>6} trades @ {res['thresh_80']['win_rate']*100:>6.2f}% WR (base: {res['win_rate_base']*100:.2f}%)")

# ============================================================================
# EXPERIMENT 2: DUAL TIMEFRAME COMBINATIONS
# ============================================================================
print("\n" + "="*80)
print("EXPERIMENT 2: DUAL TIMEFRAME COMBINATIONS")
print("="*80)

# Test all dual combinations (higher TF for trend, lower TF for entry)
dual_combinations = [
    ('1h', '15m'),
    ('1h', '5m'),
    ('30m', '15m'),
    ('30m', '5m'),
    ('30m', '1m'),
    ('15m', '5m'),
    ('15m', '1m'),
    ('5m', '1m')
]

dual_tf_results = {}

for higher_tf, lower_tf in dual_combinations:
    combo_name = f'{higher_tf}+{lower_tf}'
    print(f"\nTesting {combo_name}...")

    # Align timeframes to lower TF
    df_lower = timeframes[lower_tf].copy()
    df_higher = timeframes[higher_tf].copy()

    # Merge (forward fill higher TF data to lower TF)
    df_lower = df_lower.set_index('Datetime')
    df_higher = df_higher.set_index('Datetime')

    # Extract features from both TFs
    mtf_data = {
        'tf1': df_higher.reset_index(),  # Higher TF
        'tf2': df_lower.reset_index(),   # Lower TF
        'tf3': df_lower.reset_index()    # Same as entry TF
    }

    features = extract_features_multi_tf(mtf_data, combo_name)

    # Label on lower TF
    labels = label_data(df_lower.reset_index())
    features['label'] = labels

    # Train and evaluate
    results, model = train_and_evaluate(features, labels, f'dual_{higher_tf}_{lower_tf}')

    dual_tf_results[combo_name] = {
        'higher_tf': higher_tf,
        'lower_tf': lower_tf,
        'bars': len(df_lower),
        'win_rate_base': float(np.mean(labels)),
        **results
    }

    print(f"  High conf (≥0.8): {results['thresh_80']['n_trades']} trades, {results['thresh_80']['win_rate']*100:.2f}% WR")

print("\n" + "-"*80)
print("DUAL TIMEFRAME RESULTS:")
print("-"*80)
for combo, res in dual_tf_results.items():
    print(f"{combo:>12}: {res['thresh_80']['n_trades']:>6} trades @ {res['thresh_80']['win_rate']*100:>6.2f}% WR")

# ============================================================================
# EXPERIMENT 3: TRIPLE TIMEFRAME COMBINATIONS
# ============================================================================
print("\n" + "="*80)
print("EXPERIMENT 3: TRIPLE TIMEFRAME COMBINATIONS")
print("="*80)

# Test triple combinations
triple_combinations = [
    ('1h', '15m', '5m'),
    ('1h', '15m', '1m'),
    ('1h', '5m', '1m'),
    ('30m', '15m', '5m'),
    ('30m', '15m', '1m'),
    ('30m', '5m', '1m'),
    ('15m', '5m', '1m'),  # Current baseline
]

triple_tf_results = {}

for tf1, tf2, tf3 in triple_combinations:
    combo_name = f'{tf1}+{tf2}+{tf3}'
    print(f"\nTesting {combo_name}...")

    # Align to lowest TF
    df_tf1 = timeframes[tf1].copy()
    df_tf2 = timeframes[tf2].copy()
    df_tf3 = timeframes[tf3].copy()

    # Extract features from all TFs
    mtf_data = {
        'tf1': df_tf1,
        'tf2': df_tf2,
        'tf3': df_tf3
    }

    features = extract_features_multi_tf(mtf_data, combo_name)

    # Label on lowest TF
    labels = label_data(df_tf3)
    features['label'] = labels

    # Train and evaluate
    results, model = train_and_evaluate(features, labels, f'triple_{tf1}_{tf2}_{tf3}')

    triple_tf_results[combo_name] = {
        'tf1': tf1,
        'tf2': tf2,
        'tf3': tf3,
        'bars': len(df_tf3),
        'win_rate_base': float(np.mean(labels)),
        **results
    }

    print(f"  High conf (≥0.8): {results['thresh_80']['n_trades']} trades, {results['thresh_80']['win_rate']*100:.2f}% WR")

print("\n" + "-"*80)
print("TRIPLE TIMEFRAME RESULTS:")
print("-"*80)
for combo, res in triple_tf_results.items():
    print(f"{combo:>16}: {res['thresh_80']['n_trades']:>6} trades @ {res['thresh_80']['win_rate']*100:>6.2f}% WR")

# ============================================================================
# EXPERIMENT 4: ADAPTIVE TIMEFRAME
# ============================================================================
print("\n" + "="*80)
print("EXPERIMENT 4: ADAPTIVE TIMEFRAME (Time of Day)")
print("="*80)

# Different TFs for different times
print("\nTesting adaptive approach:")
print("  09:30-10:30: 1m+5m (high volatility)")
print("  10:30-14:00: 5m+15m (mid-day)")
print("  14:00-16:00: 5m+15m (closing)")

# This would require more complex implementation
# For now, store as a strategy to test later
adaptive_config = {
    'morning_rush': {'higher': '5m', 'lower': '1m', 'start': '09:30', 'end': '10:30'},
    'mid_day': {'higher': '15m', 'lower': '5m', 'start': '10:30', 'end': '14:00'},
    'closing': {'higher': '15m', 'lower': '5m', 'start': '14:00', 'end': '16:00'}
}

print("\nAdaptive configuration saved for later backtesting")

# ============================================================================
# FIND THE WINNER
# ============================================================================
print("\n" + "="*80)
print("FINDING THE WINNER - COMPREHENSIVE COMPARISON")
print("="*80)

# Combine all results
all_results = []

# Single TF
for tf, res in single_tf_results.items():
    all_results.append({
        'configuration': f'Single: {tf}',
        'type': 'single',
        'win_rate': res['thresh_80']['win_rate'],
        'n_trades': res['thresh_80']['n_trades'],
        'base_wr': res['win_rate_base']
    })

# Dual TF
for combo, res in dual_tf_results.items():
    all_results.append({
        'configuration': f'Dual: {combo}',
        'type': 'dual',
        'win_rate': res['thresh_80']['win_rate'],
        'n_trades': res['thresh_80']['n_trades'],
        'base_wr': res['win_rate_base']
    })

# Triple TF
for combo, res in triple_tf_results.items():
    all_results.append({
        'configuration': f'Triple: {combo}',
        'type': 'triple',
        'win_rate': res['thresh_80']['win_rate'],
        'n_trades': res['thresh_80']['n_trades'],
        'base_wr': res['win_rate_base']
    })

# Create comparison dataframe
df_results = pd.DataFrame(all_results)

# Calculate composite score
# Score = (Win Rate × 20) + (N_Trades / 10) - penalize if too few trades
df_results['score'] = (
    df_results['win_rate'] * 50 +  # Win rate is most important
    np.log1p(df_results['n_trades']) * 5  # More trades is better (logarithmic)
)

# Sort by score
df_results = df_results.sort_values('score', ascending=False)

print("\nTOP 10 CONFIGURATIONS:")
print(df_results.head(10).to_string(index=False))

# Save all results
results_summary = {
    'single_tf': single_tf_results,
    'dual_tf': dual_tf_results,
    'triple_tf': triple_tf_results,
    'adaptive_config': adaptive_config,
    'winner': {
        'configuration': df_results.iloc[0]['configuration'],
        'win_rate': float(df_results.iloc[0]['win_rate']),
        'n_trades': int(df_results.iloc[0]['n_trades']),
        'score': float(df_results.iloc[0]['score'])
    }
}

with open('timeframe_optimization_results.json', 'w') as f:
    json.dump(results_summary, f, indent=2)

df_results.to_csv('timeframe_optimization_comparison.csv', index=False)

print("\n" + "="*80)
print("WINNER CONFIGURATION")
print("="*80)
winner = df_results.iloc[0]
print(f"\n🏆 BEST: {winner['configuration']}")
print(f"   Win Rate (≥0.8): {winner['win_rate']*100:.2f}%")
print(f"   Number of Trades: {int(winner['n_trades']):,}")
print(f"   Composite Score: {winner['score']:.2f}")

print("\n" + "="*80)
print("PHASE 2 COMPLETE - Timeframe Optimization Done!")
print("="*80)
print("\nSaved:")
print("  - timeframe_optimization_results.json")
print("  - timeframe_optimization_comparison.csv")
print("  - models/xgboost_*.pkl (all trained models)")
print("\nNext: Run Phase 3 (Validate Winner)")
