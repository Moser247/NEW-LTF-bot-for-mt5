#!/usr/bin/env python3
"""
PHASE 4: MARKET REGIME DETECTION
Use clustering to find natural market states
Train regime-specific models
Build intelligent regime detector
"""

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, roc_auc_score, accuracy_score
from sklearn.model_selection import TimeSeriesSplit
import xgboost as xgb
import pickle
import warnings
warnings.filterwarnings('ignore')

print("=" * 80)
print("PHASE 4: MARKET REGIME DETECTION")
print("=" * 80)
print()

# Load data
print("Loading training data...")
df = pd.read_csv('ml_training_data.csv')
print(f"Total samples: {len(df):,}")
print()

# Prepare features
feature_cols = [col for col in df.columns if col not in ['timestamp', 'is_profitable', 'max_profit_reached',
                                                           'bars_to_target', 'trade_direction']]
X = df[feature_cols].fillna(0)
y = df['is_profitable'].astype(int)

# ============================================================================
# STEP 1: DETECT REGIMES USING CLUSTERING
# ============================================================================
print("=" * 80)
print("STEP 1: UNSUPERVISED REGIME DETECTION")
print("=" * 80)
print()

# Features for regime detection (volatility, trend, volume)
regime_features = []
for col in ['atr_1m', 'atr_5m', 'atr_ratio_1m', 'rsi_1m', 'rsi_5m',
            'ema_short_dist_1m', 'ema_long_dist_1m', 'volume_ratio_1m',
            'range', 'body_size', 'value_area_width']:
    if col in X.columns:
        regime_features.append(col)

X_regime = X[regime_features].fillna(0)
print(f"Using {len(regime_features)} features for regime detection:")
for feat in regime_features:
    print(f"  - {feat}")
print()

# Standardize features for clustering
scaler = StandardScaler()
X_regime_scaled = scaler.fit_transform(X_regime)

# Test different numbers of clusters
print("Testing different numbers of clusters...")
silhouette_scores = []
for n_clusters in range(2, 8):
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_regime_scaled)
    score = silhouette_score(X_regime_scaled, labels)
    silhouette_scores.append((n_clusters, score))
    print(f"  {n_clusters} clusters: silhouette = {score:.4f}")

# Choose optimal number of clusters
optimal_k = max(silhouette_scores, key=lambda x: x[1])[0]
print()
print(f"Optimal number of clusters: {optimal_k}")
print()

# Fit final clustering
print(f"Fitting K-means with {optimal_k} clusters...")
kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
regime_labels = kmeans.fit_predict(X_regime_scaled)
df['regime'] = regime_labels
print()

# Analyze each regime
print("=" * 80)
print("REGIME CHARACTERISTICS")
print("=" * 80)
print()

regime_stats = []
for regime_id in range(optimal_k):
    regime_data = df[df['regime'] == regime_id]
    regime_X = X[df['regime'] == regime_id]

    # Calculate statistics
    stats = {
        'regime': regime_id,
        'count': len(regime_data),
        'pct_total': len(regime_data) / len(df) * 100,
        'win_rate': regime_data['is_profitable'].mean() * 100,
        'avg_atr_1m': regime_data['atr_1m'].mean() if 'atr_1m' in df.columns else 0,
        'avg_rsi_1m': regime_data['rsi_1m'].mean() if 'rsi_1m' in df.columns else 0,
        'avg_volume': regime_data['volume_ratio_1m'].mean() if 'volume_ratio_1m' in df.columns else 0,
    }

    # Classify regime type based on characteristics
    if stats['avg_atr_1m'] < df['atr_1m'].median():
        volatility = "Low"
    else:
        volatility = "High"

    if 'ema_long_dist_1m' in df.columns:
        avg_trend = regime_data['ema_long_dist_1m'].abs().mean()
        if avg_trend < df['ema_long_dist_1m'].abs().median():
            trend = "Ranging"
        else:
            trend = "Trending"
    else:
        trend = "Unknown"

    stats['volatility'] = volatility
    stats['trend'] = trend
    stats['name'] = f"{trend} {volatility}"

    regime_stats.append(stats)

    print(f"REGIME {regime_id}: {stats['name']}")
    print(f"  Samples: {stats['count']:,} ({stats['pct_total']:.1f}%)")
    print(f"  Win Rate: {stats['win_rate']:.1f}%")
    print(f"  Avg ATR: {stats['avg_atr_1m']:.2f}")
    print(f"  Avg RSI: {stats['avg_rsi_1m']:.1f}")
    print(f"  Avg Volume Ratio: {stats['avg_volume']:.2f}")
    print()

regime_stats_df = pd.DataFrame(regime_stats)
regime_stats_df = regime_stats_df.sort_values('win_rate', ascending=False)

print("Regime Ranking by Win Rate:")
print(regime_stats_df[['regime', 'name', 'win_rate', 'count', 'pct_total']].to_string(index=False))
print()

# ============================================================================
# STEP 2: TRAIN REGIME-SPECIFIC MODELS
# ============================================================================
print("=" * 80)
print("STEP 2: TRAINING REGIME-SPECIFIC MODELS")
print("=" * 80)
print()

regime_models = {}
regime_results = []

for regime_id in range(optimal_k):
    print(f"Training model for REGIME {regime_id} ({regime_stats[regime_id]['name']})...")

    # Get regime data
    regime_mask = (df['regime'] == regime_id)
    X_regime_train = X[regime_mask]
    y_regime_train = y[regime_mask]

    if len(X_regime_train) < 100:
        print(f"  ⚠️  Skipping - insufficient samples ({len(X_regime_train)})")
        print()
        continue

    # Cross-validation
    tscv = TimeSeriesSplit(n_splits=3)
    aucs = []

    for train_idx, val_idx in tscv.split(X_regime_train):
        X_train, X_val = X_regime_train.iloc[train_idx], X_regime_train.iloc[val_idx]
        y_train, y_val = y_regime_train.iloc[train_idx], y_regime_train.iloc[val_idx]

        model = xgb.XGBClassifier(
            max_depth=6,
            learning_rate=0.1,
            n_estimators=200,
            random_state=42,
            verbosity=0
        )
        model.fit(X_train, y_train)

        y_pred = model.predict_proba(X_val)[:, 1]
        auc = roc_auc_score(y_val, y_pred)
        aucs.append(auc)

    avg_auc = np.mean(aucs)

    # Train final model on all regime data
    final_model = xgb.XGBClassifier(
        max_depth=6,
        learning_rate=0.1,
        n_estimators=200,
        random_state=42,
        verbosity=0
    )
    final_model.fit(X_regime_train, y_regime_train)

    regime_models[regime_id] = final_model

    regime_results.append({
        'regime': regime_id,
        'name': regime_stats[regime_id]['name'],
        'samples': len(X_regime_train),
        'win_rate': regime_stats[regime_id]['win_rate'],
        'cv_auc': avg_auc
    })

    print(f"  Samples: {len(X_regime_train):,}")
    print(f"  CV AUC: {avg_auc:.4f} ± {np.std(aucs):.4f}")
    print()

regime_results_df = pd.DataFrame(regime_results)
print("Regime Model Performance:")
print(regime_results_df.to_string(index=False))
print()

# ============================================================================
# STEP 3: BUILD REGIME DETECTOR MODEL
# ============================================================================
print("=" * 80)
print("STEP 3: TRAINING REGIME DETECTOR")
print("=" * 80)
print()
print("Training a model to predict which regime we're in...")
print()

# Train regime detector (predicts regime from features)
detector_X = X[regime_features]
detector_y = df['regime']

tscv = TimeSeriesSplit(n_splits=3)
detector_accs = []

for fold, (train_idx, val_idx) in enumerate(tscv.split(detector_X), 1):
    X_train, X_val = detector_X.iloc[train_idx], detector_X.iloc[val_idx]
    y_train, y_val = detector_y.iloc[train_idx], detector_y.iloc[val_idx]

    # Multi-class classifier
    detector = xgb.XGBClassifier(
        max_depth=4,
        learning_rate=0.1,
        n_estimators=100,
        random_state=42,
        verbosity=0
    )
    detector.fit(X_train, y_train)

    y_pred = detector.predict(X_val)
    acc = accuracy_score(y_val, y_pred)
    detector_accs.append(acc)
    print(f"  Fold {fold}: Accuracy = {acc:.4f}")

detector_avg_acc = np.mean(detector_accs)
print(f"  Average: {detector_avg_acc:.4f} ± {np.std(detector_accs):.4f}")
print()

# Train final detector on all data
final_detector = xgb.XGBClassifier(
    max_depth=4,
    learning_rate=0.1,
    n_estimators=100,
    random_state=42,
    verbosity=0
)
final_detector.fit(detector_X, detector_y)
print("✓ Regime detector trained")
print()

# ============================================================================
# STEP 4: TEST REGIME-AWARE SYSTEM
# ============================================================================
print("=" * 80)
print("STEP 4: TESTING REGIME-AWARE SYSTEM")
print("=" * 80)
print()

# Compare:
# 1. Single model (no regime awareness)
# 2. Regime-aware system (switch models based on regime)

# Split data for testing
split_idx = int(len(X) * 0.7)
X_train_all, X_test_all = X.iloc[:split_idx], X.iloc[split_idx:]
y_train_all, y_test_all = y.iloc[:split_idx], y.iloc[split_idx:]

# Test 1: Single model (baseline)
print("Test 1: SINGLE MODEL (no regime awareness)")
single_model = xgb.XGBClassifier(
    max_depth=6,
    learning_rate=0.1,
    n_estimators=200,
    random_state=42,
    verbosity=0
)
single_model.fit(X_train_all, y_train_all)

y_pred_single = single_model.predict_proba(X_test_all)[:, 1]
single_auc = roc_auc_score(y_test_all, y_pred_single)
single_acc = accuracy_score(y_test_all, (y_pred_single >= 0.5).astype(int))

print(f"  AUC: {single_auc:.4f}")
print(f"  Accuracy: {single_acc:.4f}")
print()

# Test 2: Regime-aware system
print("Test 2: REGIME-AWARE SYSTEM (smart model switching)")

# Detect regimes in test data
detector_X_test = X_test_all[regime_features]
predicted_regimes = final_detector.predict(detector_X_test)

# Make predictions using regime-specific models
y_pred_regime_aware = np.zeros(len(X_test_all))

for regime_id in range(optimal_k):
    if regime_id not in regime_models:
        continue

    regime_mask = (predicted_regimes == regime_id)
    if regime_mask.sum() == 0:
        continue

    X_regime_test = X_test_all[regime_mask]
    y_pred_regime_aware[regime_mask] = regime_models[regime_id].predict_proba(X_regime_test)[:, 1]

regime_auc = roc_auc_score(y_test_all, y_pred_regime_aware)
regime_acc = accuracy_score(y_test_all, (y_pred_regime_aware >= 0.5).astype(int))

print(f"  AUC: {regime_auc:.4f}")
print(f"  Accuracy: {regime_acc:.4f}")
print()

improvement = ((regime_auc - single_auc) / single_auc) * 100
print(f"Improvement over single model: {improvement:+.2f}%")
print()

if improvement > 0:
    print("✅ Regime-aware system IMPROVED performance!")
    recommendation = "USE regime-aware system"
else:
    print("❌ Regime-aware system DID NOT improve performance")
    recommendation = "STICK with single model"
print()

# ============================================================================
# STEP 5: ANALYZE WHICH REGIMES TO TRADE
# ============================================================================
print("=" * 80)
print("STEP 5: WHICH REGIMES SHOULD WE TRADE?")
print("=" * 80)
print()

# Test each regime individually
regime_test_results = []

for regime_id in range(optimal_k):
    regime_mask_test = (predicted_regimes == regime_id)

    if regime_mask_test.sum() < 10:
        continue

    y_test_regime = y_test_all[regime_mask_test]
    y_pred_regime = y_pred_regime_aware[regime_mask_test]

    win_rate = (y_pred_regime >= 0.5).astype(int).mean() if len(y_pred_regime) > 0 else 0

    regime_test_results.append({
        'regime': regime_id,
        'name': regime_stats[regime_id]['name'],
        'test_samples': regime_mask_test.sum(),
        'actual_win_rate': y_test_regime.mean() * 100,
        'predicted_win_rate': win_rate * 100,
        'tradeable': y_test_regime.mean() > 0.55  # 55%+ = tradeable
    })

regime_test_df = pd.DataFrame(regime_test_results)
regime_test_df = regime_test_df.sort_values('actual_win_rate', ascending=False)

print("Out-of-Sample Performance by Regime:")
print(regime_test_df.to_string(index=False))
print()

tradeable_regimes = regime_test_df[regime_test_df['tradeable']]['regime'].tolist()
if tradeable_regimes:
    print(f"✅ TRADEABLE REGIMES: {tradeable_regimes}")
    print(f"   These regimes have >55% win rate")
else:
    print("❌ NO REGIMES are consistently profitable (>55% WR)")
print()

# ============================================================================
# SAVE RESULTS
# ============================================================================
print("=" * 80)
print("SAVING RESULTS")
print("=" * 80)
print()

# Save regime detector
with open('models/regime_detector.pkl', 'wb') as f:
    pickle.dump({
        'detector': final_detector,
        'scaler': scaler,
        'kmeans': kmeans,
        'feature_names': regime_features,
        'optimal_k': optimal_k
    }, f)
print("✓ Saved models/regime_detector.pkl")

# Save regime-specific models
for regime_id, model in regime_models.items():
    with open(f'models/regime_{regime_id}_model.pkl', 'wb') as f:
        pickle.dump(model, f)
print(f"✓ Saved {len(regime_models)} regime-specific models")

# Save regime statistics
regime_stats_df.to_csv('phase4_regime_stats.csv', index=False)
print("✓ Saved phase4_regime_stats.csv")

# Save regime model results
regime_results_df.to_csv('phase4_regime_models.csv', index=False)
print("✓ Saved phase4_regime_models.csv")

# Save test results
regime_test_df.to_csv('phase4_regime_test_results.csv', index=False)
print("✓ Saved phase4_regime_test_results.csv")

# Save comparison
comparison = pd.DataFrame({
    'approach': ['Single Model', 'Regime-Aware'],
    'auc': [single_auc, regime_auc],
    'accuracy': [single_acc, regime_acc],
    'improvement_pct': [0, improvement]
})
comparison.to_csv('phase4_comparison.csv', index=False)
print("✓ Saved phase4_comparison.csv")

print()
print("=" * 80)
print("PHASE 4 COMPLETE")
print("=" * 80)
print()
print("Files created:")
print("  - models/regime_detector.pkl")
print(f"  - models/regime_{{0-{optimal_k-1}}}_model.pkl (regime-specific models)")
print("  - phase4_regime_stats.csv")
print("  - phase4_regime_models.csv")
print("  - phase4_regime_test_results.csv")
print("  - phase4_comparison.csv")
print()
print(f"RECOMMENDATION: {recommendation}")
print()

if tradeable_regimes:
    print("TRADING STRATEGY:")
    print(f"  Only trade when regime detector predicts: {tradeable_regimes}")
    print(f"  Use regime-specific model for that regime")
    print(f"  Expected improvement: {improvement:+.2f}%")
else:
    print("⚠️  WARNING: No regimes are consistently profitable")
    print("   System may need more data or different approach")
print()
