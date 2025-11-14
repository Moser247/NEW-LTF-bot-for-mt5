#!/usr/bin/env python3
"""
TRAIN ON BEST OF BEST - Find Elite Signals Only

This script implements 3 approaches to training on only the highest quality setups:
1. Filter for elite setups (top 10-20% by multiple criteria)
2. Train using only top 15 most important features
3. Create ensemble of 3 specialized models

Goal: Find the REAL best signals that work, not just data leakage
"""

import pandas as pd
import numpy as np
import pickle
import json
from pathlib import Path
from xgboost import XGBClassifier
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import classification_report, roc_auc_score, precision_recall_curve
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("PHASE 1: TRAIN ON BEST OF BEST ONLY")
print("="*80)

# Load existing training data
print("\n[1/7] Loading ml_training_data.csv...")
df = pd.read_csv('ml_training_data.csv')
print(f"Total samples: {len(df):,}")

# Rename is_profitable to label for consistency
df['label'] = df['is_profitable']
print(f"Profitable setups: {df['label'].sum():,} ({df['label'].mean()*100:.2f}%)")

# Add ML probabilities from previous model
print("\n[2/7] Loading previous ML predictions...")
predictions = pd.read_csv('ml_predictions.csv')
df['ml_prob'] = predictions['ml_probability'].values[:len(df)]
print(f"Average ML probability: {df['ml_prob'].mean():.4f}")

# Calculate quality metrics for each setup
print("\n[3/7] Calculating setup quality metrics...")

# Feature columns (exclude metadata)
feature_cols = [col for col in df.columns if col not in ['timestamp', 'price', 'label', 'is_profitable',
                                                           'max_profit_reached', 'bars_to_target',
                                                           'trade_direction', 'ml_prob']]

# Add quality scores
df['has_high_confluence'] = ((df['confluence_long'] >= 6) | (df['confluence_short'] >= 6)).astype(int)
df['strong_trend'] = ((df['tf_alignment_bullish'] == 1) | (df['tf_alignment_bearish'] == 1)).astype(int)
df['at_key_level'] = ((abs(df['distance_to_vwap']) < df['atr_5m'] * 0.5) |
                       (abs(df['distance_to_poc']) < df['atr_5m'] * 0.5)).astype(int)
df['clean_price_action'] = ((df['body_ratio'] > 0.6) & (df['range'] > df['atr_1m'] * 0.5)).astype(int)

# Composite quality score (0-5)
df['quality_score'] = (
    df['has_high_confluence'] +
    df['strong_trend'] +
    df['at_key_level'] +
    df['clean_price_action'] +
    (df['ml_prob'] > 0.8).astype(int)
)

print("\nQuality Score Distribution:")
print(df.groupby('quality_score').agg({
    'label': ['count', 'sum', 'mean']
}).round(4))

# ============================================================================
# APPROACH 1: ELITE FILTERING - Top 20% by quality
# ============================================================================
print("\n" + "="*80)
print("APPROACH 1: ELITE FILTERING - Train on Top 20% Quality Setups")
print("="*80)

# Filter for elite setups
elite_threshold = df['quality_score'].quantile(0.80)  # Top 20%
df_elite = df[df['quality_score'] >= elite_threshold].copy()

print(f"\nElite threshold: quality_score >= {elite_threshold}")
print(f"Elite samples: {len(df_elite):,} ({len(df_elite)/len(df)*100:.1f}%)")
print(f"Elite win rate: {df_elite['label'].mean()*100:.2f}%")

# Train on elite only
X_elite = df_elite[feature_cols]
y_elite = df_elite['label']

# Handle class imbalance
pos_weight = (len(y_elite) - y_elite.sum()) / y_elite.sum()
print(f"Positive class weight: {pos_weight:.2f}")

# Train model
model_elite = XGBClassifier(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    min_child_weight=5,
    subsample=0.8,
    colsample_bytree=0.8,
    gamma=0.2,
    scale_pos_weight=pos_weight,
    random_state=42,
    n_jobs=-1
)

print("\nTraining elite model...")
model_elite.fit(X_elite, y_elite)

# Cross-validation
print("Running 5-fold cross-validation...")
tscv = TimeSeriesSplit(n_splits=5)
cv_scores = cross_val_score(model_elite, X_elite, y_elite, cv=tscv, scoring='roc_auc', n_jobs=-1)
print(f"CV ROC AUC: {cv_scores.mean():.4f} (+/- {cv_scores.std()*2:.4f})")

# Save model
with open('models/xgboost_elite_filtered.pkl', 'wb') as f:
    pickle.dump(model_elite, f)
print("Saved: models/xgboost_elite_filtered.pkl")

# Results on full dataset
y_pred_elite = model_elite.predict_proba(df[feature_cols])[:, 1]
df['ml_prob_elite'] = y_pred_elite
elite_results = {
    'approach': 'Elite Filtering (Top 20%)',
    'training_samples': len(df_elite),
    'training_win_rate': float(df_elite['label'].mean()),
    'cv_roc_auc': float(cv_scores.mean()),
    'cv_std': float(cv_scores.std()),
    'high_conf_trades': int((y_pred_elite >= 0.8).sum()),
    'high_conf_win_rate': float(df[y_pred_elite >= 0.8]['label'].mean()) if (y_pred_elite >= 0.8).sum() > 0 else 0
}

# ============================================================================
# APPROACH 2: TOP FEATURES ONLY - Use 15 most important features
# ============================================================================
print("\n" + "="*80)
print("APPROACH 2: TOP FEATURES ONLY - Train on 15 Most Important Features")
print("="*80)

# Top 15 features from feature_importance.csv
top_features = [
    'is_bullish', 'upper_wick', 'range', 'lower_wick', 'value_area_width',
    'body_size', 'atr_5m', 'distance_to_vwap', 'distance_to_vah', 'ema_long_dist_1m',
    'ema_cross_1m', 'tf_alignment_bearish', 'above_vwap', 'confluence_short', 'in_value_area'
]

# Verify all features exist
top_features = [f for f in top_features if f in df.columns]
print(f"Using {len(top_features)} top features: {top_features}")

X_top = df[top_features]
y = df['label']

# Train model
pos_weight_full = (len(y) - y.sum()) / y.sum()
model_top = XGBClassifier(
    n_estimators=300,
    max_depth=5,  # Simpler model with fewer features
    learning_rate=0.05,
    min_child_weight=3,
    subsample=0.8,
    colsample_bytree=0.9,
    gamma=0.1,
    scale_pos_weight=pos_weight_full,
    random_state=42,
    n_jobs=-1
)

print("\nTraining top-features model...")
model_top.fit(X_top, y)

# Cross-validation
print("Running 5-fold cross-validation...")
cv_scores_top = cross_val_score(model_top, X_top, y, cv=tscv, scoring='roc_auc', n_jobs=-1)
print(f"CV ROC AUC: {cv_scores_top.mean():.4f} (+/- {cv_scores_top.std()*2:.4f})")

# Save model
with open('models/xgboost_top_features.pkl', 'wb') as f:
    pickle.dump(model_top, f)
print("Saved: models/xgboost_top_features.pkl")

# Results
y_pred_top = model_top.predict_proba(X_top)[:, 1]
df['ml_prob_top'] = y_pred_top
top_results = {
    'approach': 'Top 15 Features',
    'training_samples': len(df),
    'training_win_rate': float(y.mean()),
    'cv_roc_auc': float(cv_scores_top.mean()),
    'cv_std': float(cv_scores_top.std()),
    'high_conf_trades': int((y_pred_top >= 0.8).sum()),
    'high_conf_win_rate': float(df[y_pred_top >= 0.8]['label'].mean()) if (y_pred_top >= 0.8).sum() > 0 else 0
}

# ============================================================================
# APPROACH 3: ENSEMBLE - 3 specialized models
# ============================================================================
print("\n" + "="*80)
print("APPROACH 3: ENSEMBLE - 3 Specialized Models")
print("="*80)

# Model A: Trend-following (strong directional moves)
print("\nModel A: Trend Following Specialist")
trend_features = [
    'is_bullish', 'ema_cross_1m', 'ema_cross_5m', 'ema_cross_15m',
    'tf_alignment_bullish', 'tf_alignment_bearish', 'above_ema50_15m',
    'rsi_1m', 'rsi_5m', 'rsi_15m', 'ema_short_dist_1m', 'ema_long_dist_1m',
    'body_size', 'body_ratio', 'range'
]
trend_features = [f for f in trend_features if f in df.columns]

# Filter for trending conditions (TF alignment or strong momentum)
df_trend = df[(df['tf_alignment_bullish'] == 1) | (df['tf_alignment_bearish'] == 1) |
              (abs(df['rsi_5m'] - 50) > 20)].copy()

print(f"Trend samples: {len(df_trend):,} ({len(df_trend)/len(df)*100:.1f}%)")
print(f"Trend win rate: {df_trend['label'].mean()*100:.2f}%")

X_trend = df_trend[trend_features]
y_trend = df_trend['label']
pos_weight_trend = (len(y_trend) - y_trend.sum()) / y_trend.sum()

model_trend = XGBClassifier(
    n_estimators=200,
    max_depth=5,
    learning_rate=0.05,
    scale_pos_weight=pos_weight_trend,
    random_state=42,
    n_jobs=-1
)
model_trend.fit(X_trend, y_trend)

# Model B: Reversal specialist (at key levels)
print("\nModel B: Reversal Specialist")
reversal_features = [
    'distance_to_vwap', 'distance_to_poc', 'distance_to_vah', 'distance_to_val',
    'above_vwap', 'in_value_area', 'value_area_width',
    'upper_wick', 'lower_wick', 'body_ratio',
    'rsi_5m', 'rsi_15m', 'atr_5m'
]
reversal_features = [f for f in reversal_features if f in df.columns]

# Filter for reversal setups (near key levels with rejection wicks)
df_reversal = df[
    ((abs(df['distance_to_vwap']) < df['atr_5m'] * 0.5) |
     (abs(df['distance_to_poc']) < df['atr_5m'] * 0.5)) &
    ((df['upper_wick'] > df['body_size']) | (df['lower_wick'] > df['body_size']))
].copy()

print(f"Reversal samples: {len(df_reversal):,} ({len(df_reversal)/len(df)*100:.1f}%)")
print(f"Reversal win rate: {df_reversal['label'].mean()*100:.2f}%")

X_reversal = df_reversal[reversal_features]
y_reversal = df_reversal['label']
pos_weight_reversal = (len(y_reversal) - y_reversal.sum()) / y_reversal.sum()

model_reversal = XGBClassifier(
    n_estimators=200,
    max_depth=5,
    learning_rate=0.05,
    scale_pos_weight=pos_weight_reversal,
    random_state=42,
    n_jobs=-1
)
model_reversal.fit(X_reversal, y_reversal)

# Model C: Breakout specialist (high volume + momentum)
print("\nModel C: Breakout Specialist")
breakout_features = [
    'range', 'body_size', 'body_ratio', 'atr_5m', 'atr_ratio_1m',
    'volume_ratio_5m', 'has_bullish_sweep', 'has_bearish_sweep',
    'num_bullish_sweeps', 'num_bearish_sweeps',
    'is_bullish', 'confluence_long', 'confluence_short'
]
breakout_features = [f for f in breakout_features if f in df.columns]

# Filter for breakout conditions (large range + volume)
df_breakout = df[
    (df['range'] > df['atr_1m'] * 1.5) &
    ((df['volume_ratio_5m'] > 1.2) if 'volume_ratio_5m' in df.columns else True)
].copy()

print(f"Breakout samples: {len(df_breakout):,} ({len(df_breakout)/len(df)*100:.1f}%)")
print(f"Breakout win rate: {df_breakout['label'].mean()*100:.2f}%")

X_breakout = df_breakout[breakout_features]
y_breakout = df_breakout['label']
pos_weight_breakout = (len(y_breakout) - y_breakout.sum()) / y_breakout.sum()

model_breakout = XGBClassifier(
    n_estimators=200,
    max_depth=5,
    learning_rate=0.05,
    scale_pos_weight=pos_weight_breakout,
    random_state=42,
    n_jobs=-1
)
model_breakout.fit(X_breakout, y_breakout)

# Save specialized models
with open('models/xgboost_trend_specialist.pkl', 'wb') as f:
    pickle.dump(model_trend, f)
with open('models/xgboost_reversal_specialist.pkl', 'wb') as f:
    pickle.dump(model_reversal, f)
with open('models/xgboost_breakout_specialist.pkl', 'wb') as f:
    pickle.dump(model_breakout, f)
print("\nSaved 3 specialist models")

# Create ensemble predictions
print("\nGenerating ensemble predictions...")

# Get predictions from each specialist
pred_trend = model_trend.predict_proba(df[trend_features])[:, 1]
pred_reversal = model_reversal.predict_proba(df[reversal_features])[:, 1]
pred_breakout = model_breakout.predict_proba(df[breakout_features])[:, 1]

# Average ensemble
df['ml_prob_ensemble'] = (pred_trend + pred_reversal + pred_breakout) / 3

# Voting ensemble (2/3 must agree at high confidence)
df['ensemble_votes'] = ((pred_trend >= 0.7).astype(int) +
                        (pred_reversal >= 0.7).astype(int) +
                        (pred_breakout >= 0.7).astype(int))

ensemble_results = {
    'approach': 'Ensemble (3 Specialists)',
    'training_samples': len(df),
    'training_win_rate': float(y.mean()),
    'high_conf_trades': int((df['ml_prob_ensemble'] >= 0.8).sum()),
    'high_conf_win_rate': float(df[df['ml_prob_ensemble'] >= 0.8]['label'].mean()) if (df['ml_prob_ensemble'] >= 0.8).sum() > 0 else 0,
    'votes_2of3_trades': int((df['ensemble_votes'] >= 2).sum()),
    'votes_2of3_win_rate': float(df[df['ensemble_votes'] >= 2]['label'].mean()) if (df['ensemble_votes'] >= 2).sum() > 0 else 0
}

# ============================================================================
# COMPARISON & RESULTS
# ============================================================================
print("\n" + "="*80)
print("RESULTS COMPARISON - BEST OF BEST APPROACHES")
print("="*80)

results = pd.DataFrame([elite_results, top_results, ensemble_results])
print("\n" + results.to_string(index=False))

# Save all predictions
output_df = df[['timestamp', 'trade_direction', 'label',
                'ml_prob', 'ml_prob_elite', 'ml_prob_top', 'ml_prob_ensemble',
                'quality_score', 'ensemble_votes']].copy()
output_df.to_csv('ml_best_of_best_predictions.csv', index=False)
print("\nSaved: ml_best_of_best_predictions.csv")

# Save summary
summary = {
    'total_samples': len(df),
    'elite_filtered': elite_results,
    'top_features': top_results,
    'ensemble': ensemble_results,
    'top_15_features': top_features,
    'elite_threshold': float(elite_threshold)
}

with open('best_of_best_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)
print("Saved: best_of_best_summary.json")

# ============================================================================
# RECOMMENDATIONS
# ============================================================================
print("\n" + "="*80)
print("RECOMMENDATIONS")
print("="*80)

# Find best approach
best_idx = results['high_conf_win_rate'].idxmax()
best_approach = results.iloc[best_idx]

print(f"\nBEST APPROACH: {best_approach['approach']}")
print(f"High confidence (≥0.80) win rate: {best_approach['high_conf_win_rate']*100:.2f}%")
print(f"High confidence trades: {int(best_approach['high_conf_trades']):,}")

if best_approach['approach'] == 'Elite Filtering (Top 20%)':
    print("\nRECOMMENDATION: Use models/xgboost_elite_filtered.pkl")
    print("This model was trained on only the highest quality setups.")
elif best_approach['approach'] == 'Top 15 Features':
    print("\nRECOMMENDATION: Use models/xgboost_top_features.pkl")
    print("This model uses only the most important features, reducing complexity.")
else:
    print("\nRECOMMENDATION: Use ensemble approach")
    print("Combine all 3 specialist models. Trade when 2/3 models agree.")

print("\n" + "="*80)
print("PHASE 1 COMPLETE - Best of Best Models Trained!")
print("="*80)
print("\nNext: Run Phase 2 (Multi-Timeframe Optimization)")
