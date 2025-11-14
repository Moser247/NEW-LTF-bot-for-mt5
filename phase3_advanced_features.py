#!/usr/bin/env python3
"""
PHASE 3: ADVANCED FEATURE ENGINEERING 2.0
Create interaction features, polynomial features, time aggregations, regime features
Expand from 60 features to 200+ features
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import PolynomialFeatures
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

print("=" * 80)
print("PHASE 3: ADVANCED FEATURE ENGINEERING 2.0")
print("=" * 80)
print()

# Load data
print("Loading training data...")
df = pd.read_csv('ml_training_data.csv')
print(f"Original samples: {len(df):,}")

# Prepare base features
feature_cols = [col for col in df.columns if col not in ['timestamp', 'is_profitable', 'max_profit_reached',
                                                           'bars_to_target', 'trade_direction']]
X_base = df[feature_cols].fillna(0)
y = df['is_profitable'].astype(int)

print(f"Base features: {len(feature_cols)}")
print()

# Start with base features
X_enhanced = X_base.copy()
new_features_info = []

# ============================================================================
# 1. INTERACTION FEATURES
# ============================================================================
print("=" * 80)
print("1. CREATING INTERACTION FEATURES")
print("=" * 80)
print()
print("Multiplying important features together to capture non-linear relationships")
print()

# Define key feature groups for interactions
interaction_pairs = [
    # Order block + FVG interactions
    ('bullish_ob_strength', 'bullish_fvg_size', 'ob_fvg_bullish_power'),
    ('bearish_ob_strength', 'bearish_fvg_size', 'ob_fvg_bearish_power'),

    # Confluence interactions
    ('confluence_long', 'bullish_ob_strength', 'confluence_ob_long'),
    ('confluence_short', 'bearish_ob_strength', 'confluence_ob_short'),

    # Time + Volatility regime
    ('hour', 'atr_1m', 'time_volatility_regime'),
    ('minutes_from_open', 'atr_ratio_1m', 'session_volatility'),

    # VWAP + Volume
    ('distance_to_vwap', 'volume_ratio_1m', 'vwap_volume_strength'),
    ('distance_to_poc', 'value_area_width', 'poc_value_strength'),

    # Price action + Structure
    ('body_ratio', 'atr_ratio_1m', 'normalized_body'),
    ('upper_wick', 'lower_wick', 'wick_interaction'),

    # Multi-timeframe alignment
    ('ema_cross_1m', 'ema_cross_5m', 'tf_ema_alignment'),
    ('rsi_1m', 'rsi_5m', 'tf_rsi_alignment'),
]

for feature1, feature2, new_name in interaction_pairs:
    if feature1 in X_enhanced.columns and feature2 in X_enhanced.columns:
        X_enhanced[new_name] = X_enhanced[feature1] * X_enhanced[feature2]
        new_features_info.append({'type': 'interaction', 'name': new_name})

print(f"Created {len(interaction_pairs)} interaction features")
print()

# ============================================================================
# 2. POLYNOMIAL FEATURES
# ============================================================================
print("=" * 80)
print("2. CREATING POLYNOMIAL FEATURES")
print("=" * 80)
print()
print("Squares, cubes, and roots of important features")
print()

# Key features for polynomial expansion
poly_features = [
    'atr_1m', 'atr_5m', 'range', 'body_size',
    'upper_wick', 'lower_wick', 'value_area_width',
    'distance_to_vwap', 'bullish_ob_strength', 'bearish_ob_strength'
]

for feat in poly_features:
    if feat in X_enhanced.columns:
        # Square
        X_enhanced[f'{feat}_squared'] = X_enhanced[feat] ** 2
        new_features_info.append({'type': 'polynomial', 'name': f'{feat}_squared'})

        # Square root (add small constant to avoid sqrt(0))
        X_enhanced[f'{feat}_sqrt'] = np.sqrt(X_enhanced[feat] + 1e-8)
        new_features_info.append({'type': 'polynomial', 'name': f'{feat}_sqrt'})

        # Log transform (add 1 to avoid log(0))
        X_enhanced[f'{feat}_log'] = np.log1p(X_enhanced[feat].abs())
        new_features_info.append({'type': 'polynomial', 'name': f'{feat}_log'})

print(f"Created {len(poly_features) * 3} polynomial features")
print()

# ============================================================================
# 3. TIME-BASED AGGREGATIONS
# ============================================================================
print("=" * 80)
print("3. CREATING TIME-BASED AGGREGATIONS")
print("=" * 80)
print()
print("Rolling statistics over different windows")
print()

# Features to aggregate
agg_features = [
    'atr_1m', 'rsi_1m', 'volume_ratio_1m', 'body_size', 'range',
    'distance_to_vwap', 'bullish_ob_strength', 'bearish_ob_strength'
]

# Rolling windows
windows = [5, 10, 20]

for feat in agg_features:
    if feat in X_enhanced.columns:
        for window in windows:
            # Rolling mean
            X_enhanced[f'{feat}_ma{window}'] = X_enhanced[feat].rolling(window, min_periods=1).mean()
            new_features_info.append({'type': 'rolling', 'name': f'{feat}_ma{window}'})

            # Rolling std
            X_enhanced[f'{feat}_std{window}'] = X_enhanced[feat].rolling(window, min_periods=1).std().fillna(0)
            new_features_info.append({'type': 'rolling', 'name': f'{feat}_std{window}'})

            # Rolling max
            X_enhanced[f'{feat}_max{window}'] = X_enhanced[feat].rolling(window, min_periods=1).max()
            new_features_info.append({'type': 'rolling', 'name': f'{feat}_max{window}'})

            # Rolling min
            X_enhanced[f'{feat}_min{window}'] = X_enhanced[feat].rolling(window, min_periods=1).min()
            new_features_info.append({'type': 'rolling', 'name': f'{feat}_min{window}'})

print(f"Created {len(agg_features) * len(windows) * 4} rolling features")
print()

# ============================================================================
# 4. RATE OF CHANGE FEATURES
# ============================================================================
print("=" * 80)
print("4. CREATING RATE OF CHANGE FEATURES")
print("=" * 80)
print()
print("How fast are features changing")
print()

roc_features = ['atr_1m', 'rsi_1m', 'distance_to_vwap', 'volume_ratio_1m']
roc_periods = [1, 3, 5]

for feat in roc_features:
    if feat in X_enhanced.columns:
        for period in roc_periods:
            X_enhanced[f'{feat}_roc{period}'] = X_enhanced[feat].diff(period).fillna(0)
            new_features_info.append({'type': 'roc', 'name': f'{feat}_roc{period}'})

print(f"Created {len(roc_features) * len(roc_periods)} rate of change features")
print()

# ============================================================================
# 5. REGIME FEATURES
# ============================================================================
print("=" * 80)
print("5. CREATING REGIME FEATURES")
print("=" * 80)
print()
print("Market state indicators")
print()

# Volatility regime
if 'atr_1m' in X_enhanced.columns:
    atr_median = X_enhanced['atr_1m'].median()
    atr_75 = X_enhanced['atr_1m'].quantile(0.75)

    X_enhanced['volatility_regime'] = 0  # Low
    X_enhanced.loc[X_enhanced['atr_1m'] > atr_median, 'volatility_regime'] = 1  # Medium
    X_enhanced.loc[X_enhanced['atr_1m'] > atr_75, 'volatility_regime'] = 2  # High
    new_features_info.append({'type': 'regime', 'name': 'volatility_regime'})

# Trend strength
if 'ema_short_dist_1m' in X_enhanced.columns and 'ema_long_dist_1m' in X_enhanced.columns:
    X_enhanced['trend_strength'] = np.abs(X_enhanced['ema_long_dist_1m'])
    new_features_info.append({'type': 'regime', 'name': 'trend_strength'})

    X_enhanced['trend_direction'] = np.sign(X_enhanced['ema_long_dist_1m'])
    new_features_info.append({'type': 'regime', 'name': 'trend_direction'})

# Time regime (session)
if 'hour' in X_enhanced.columns:
    X_enhanced['is_asia_session'] = ((X_enhanced['hour'] >= 0) & (X_enhanced['hour'] < 8)).astype(int)
    X_enhanced['is_london_session'] = ((X_enhanced['hour'] >= 8) & (X_enhanced['hour'] < 13)).astype(int)
    X_enhanced['is_ny_session'] = ((X_enhanced['hour'] >= 13) & (X_enhanced['hour'] < 20)).astype(int)
    new_features_info.append({'type': 'regime', 'name': 'is_asia_session'})
    new_features_info.append({'type': 'regime', 'name': 'is_london_session'})
    new_features_info.append({'type': 'regime', 'name': 'is_ny_session'})

# Volume regime
if 'volume_ratio_1m' in X_enhanced.columns:
    vol_median = X_enhanced['volume_ratio_1m'].median()
    vol_75 = X_enhanced['volume_ratio_1m'].quantile(0.75)

    X_enhanced['volume_regime'] = 0  # Low
    X_enhanced.loc[X_enhanced['volume_ratio_1m'] > vol_median, 'volume_regime'] = 1  # Medium
    X_enhanced.loc[X_enhanced['volume_ratio_1m'] > vol_75, 'volume_regime'] = 2  # High
    new_features_info.append({'type': 'regime', 'name': 'volume_regime'})

print(f"Created {sum(1 for f in new_features_info if f['type'] == 'regime')} regime features")
print()

# ============================================================================
# 6. PATTERN RECOGNITION FEATURES
# ============================================================================
print("=" * 80)
print("6. CREATING PATTERN RECOGNITION FEATURES")
print("=" * 80)
print()
print("Candlestick and price patterns")
print()

# Doji (small body, large wicks)
if 'body_ratio' in X_enhanced.columns:
    X_enhanced['is_doji'] = (X_enhanced['body_ratio'] < 0.1).astype(int)
    new_features_info.append({'type': 'pattern', 'name': 'is_doji'})

# Hammer (small body, large lower wick)
if all(col in X_enhanced.columns for col in ['body_ratio', 'lower_wick', 'upper_wick']):
    X_enhanced['is_hammer'] = (
        (X_enhanced['body_ratio'] < 0.3) &
        (X_enhanced['lower_wick'] > X_enhanced['upper_wick'] * 2)
    ).astype(int)
    new_features_info.append({'type': 'pattern', 'name': 'is_hammer'})

# Shooting star (small body, large upper wick)
if all(col in X_enhanced.columns for col in ['body_ratio', 'upper_wick', 'lower_wick']):
    X_enhanced['is_shooting_star'] = (
        (X_enhanced['body_ratio'] < 0.3) &
        (X_enhanced['upper_wick'] > X_enhanced['lower_wick'] * 2)
    ).astype(int)
    new_features_info.append({'type': 'pattern', 'name': 'is_shooting_star'})

# Engulfing (compare with previous candle)
if 'body_size' in X_enhanced.columns:
    prev_body = X_enhanced['body_size'].shift(1).fillna(0)
    X_enhanced['is_engulfing'] = (X_enhanced['body_size'] > prev_body * 1.5).astype(int)
    new_features_info.append({'type': 'pattern', 'name': 'is_engulfing'})

# Large range bar
if 'range' in X_enhanced.columns:
    range_75 = X_enhanced['range'].quantile(0.75)
    X_enhanced['is_large_range'] = (X_enhanced['range'] > range_75).astype(int)
    new_features_info.append({'type': 'pattern', 'name': 'is_large_range'})

print(f"Created {sum(1 for f in new_features_info if f['type'] == 'pattern')} pattern features")
print()

# ============================================================================
# 7. MICROSTRUCTURE FEATURES
# ============================================================================
print("=" * 80)
print("7. CREATING MICROSTRUCTURE FEATURES")
print("=" * 80)
print()
print("Order flow proxies and market microstructure")
print()

# Bid-ask spread proxy (use range as proxy)
if 'range' in X_enhanced.columns and 'atr_1m' in X_enhanced.columns:
    X_enhanced['spread_proxy'] = X_enhanced['range'] / (X_enhanced['atr_1m'] + 1e-8)
    new_features_info.append({'type': 'microstructure', 'name': 'spread_proxy'})

# Price momentum
if 'is_bullish' in X_enhanced.columns and 'body_size' in X_enhanced.columns:
    X_enhanced['price_momentum'] = X_enhanced['is_bullish'].apply(lambda x: 1 if x else -1) * X_enhanced['body_size']
    new_features_info.append({'type': 'microstructure', 'name': 'price_momentum'})

    # Cumulative momentum
    X_enhanced['cumulative_momentum'] = X_enhanced['price_momentum'].rolling(10, min_periods=1).sum()
    new_features_info.append({'type': 'microstructure', 'name': 'cumulative_momentum'})

# Buying/Selling pressure
if all(col in X_enhanced.columns for col in ['upper_wick', 'lower_wick', 'body_size']):
    X_enhanced['buying_pressure'] = X_enhanced['lower_wick'] / (X_enhanced['range'] + 1e-8)
    X_enhanced['selling_pressure'] = X_enhanced['upper_wick'] / (X_enhanced['range'] + 1e-8)
    new_features_info.append({'type': 'microstructure', 'name': 'buying_pressure'})
    new_features_info.append({'type': 'microstructure', 'name': 'selling_pressure'})

print(f"Created {sum(1 for f in new_features_info if f['type'] == 'microstructure')} microstructure features")
print()

# ============================================================================
# SUMMARY
# ============================================================================
print("=" * 80)
print("FEATURE ENGINEERING SUMMARY")
print("=" * 80)
print()

# Count by type
feature_counts = {}
for info in new_features_info:
    feature_counts[info['type']] = feature_counts.get(info['type'], 0) + 1

print("New features by type:")
for ftype, count in sorted(feature_counts.items()):
    print(f"  {ftype}: {count}")
print()

print(f"Original features: {len(feature_cols)}")
print(f"New features: {len(new_features_info)}")
print(f"Total features: {len(X_enhanced.columns)}")
print()

# Fill any NaN values
X_enhanced = X_enhanced.fillna(0)

# ============================================================================
# TEST IMPROVEMENT
# ============================================================================
print("=" * 80)
print("TESTING IMPROVEMENT WITH NEW FEATURES")
print("=" * 80)
print()

# Compare baseline vs enhanced features
tscv = TimeSeriesSplit(n_splits=3)

print("Training XGBoost with BASELINE features...")
baseline_aucs = []
for fold, (train_idx, val_idx) in enumerate(tscv.split(X_base), 1):
    X_train, X_val = X_base.iloc[train_idx], X_base.iloc[val_idx]
    y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

    model = xgb.XGBClassifier(max_depth=6, learning_rate=0.1, n_estimators=200, random_state=42, verbosity=0)
    model.fit(X_train, y_train)

    y_pred = model.predict_proba(X_val)[:, 1]
    auc = roc_auc_score(y_val, y_pred)
    baseline_aucs.append(auc)
    print(f"  Fold {fold}: AUC = {auc:.4f}")

baseline_avg = np.mean(baseline_aucs)
print(f"  Average: {baseline_avg:.4f} ± {np.std(baseline_aucs):.4f}")
print()

print("Training XGBoost with ENHANCED features...")
enhanced_aucs = []
for fold, (train_idx, val_idx) in enumerate(tscv.split(X_enhanced), 1):
    X_train, X_val = X_enhanced.iloc[train_idx], X_enhanced.iloc[val_idx]
    y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

    model = xgb.XGBClassifier(max_depth=6, learning_rate=0.1, n_estimators=200, random_state=42, verbosity=0)
    model.fit(X_train, y_train)

    y_pred = model.predict_proba(X_val)[:, 1]
    auc = roc_auc_score(y_val, y_pred)
    enhanced_aucs.append(auc)
    print(f"  Fold {fold}: AUC = {auc:.4f}")

enhanced_avg = np.mean(enhanced_aucs)
print(f"  Average: {enhanced_avg:.4f} ± {np.std(enhanced_aucs):.4f}")
print()

improvement = ((enhanced_avg - baseline_avg) / baseline_avg) * 100
print(f"Improvement: {improvement:+.2f}%")
print()

if improvement > 0:
    print("✅ Advanced features IMPROVED performance!")
else:
    print("❌ Advanced features DID NOT improve performance")
    print("   Possible overfitting or noise added")
print()

# ============================================================================
# SAVE RESULTS
# ============================================================================
print("=" * 80)
print("SAVING RESULTS")
print("=" * 80)
print()

# Save enhanced dataset
X_enhanced['is_profitable'] = y
X_enhanced['timestamp'] = df['timestamp']
X_enhanced['max_profit_reached'] = df['max_profit_reached']
X_enhanced['bars_to_target'] = df['bars_to_target']
X_enhanced['trade_direction'] = df['trade_direction']

X_enhanced.to_csv('ml_training_data_enhanced.csv', index=False)
print("✓ Saved ml_training_data_enhanced.csv")

# Save feature info
feature_info_df = pd.DataFrame(new_features_info)
feature_info_df.to_csv('phase3_new_features.csv', index=False)
print("✓ Saved phase3_new_features.csv")

# Save comparison results
comparison_df = pd.DataFrame({
    'feature_set': ['Baseline', 'Enhanced'],
    'num_features': [len(X_base.columns), len(X_enhanced.columns) - 5],  # -5 for target and metadata
    'avg_auc': [baseline_avg, enhanced_avg],
    'std_auc': [np.std(baseline_aucs), np.std(enhanced_aucs)],
    'improvement_pct': [0, improvement]
})
comparison_df.to_csv('phase3_comparison.csv', index=False)
print("✓ Saved phase3_comparison.csv")

print()
print("=" * 80)
print("PHASE 3 COMPLETE")
print("=" * 80)
print()
print("Files created:")
print("  - ml_training_data_enhanced.csv (expanded dataset)")
print("  - phase3_new_features.csv (feature catalog)")
print("  - phase3_comparison.csv (performance comparison)")
print()

if improvement > 0:
    print(f"✅ RECOMMENDATION: Use enhanced features ({len(X_enhanced.columns)-5} features)")
    print(f"   Performance gain: {improvement:+.2f}%")
else:
    print("⚠️  RECOMMENDATION: Stick with baseline features")
    print("   Advanced features may cause overfitting")
print()
