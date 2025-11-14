#!/usr/bin/env python3
"""
PHASE 1: ALTERNATIVE ML MODELS
Test LightGBM, CatBoost, and H2O AutoML vs XGBoost
All tested with proper walk-forward validation
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score, accuracy_score, precision_score, recall_score, f1_score
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

# Will install packages if needed
import subprocess
import sys

def install_package(package):
    """Install package if not available"""
    try:
        __import__(package)
    except ImportError:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Try to import or install packages
packages = ['lightgbm', 'catboost']
for pkg in packages:
    install_package(pkg)

import lightgbm as lgb
import catboost as cb

print("=" * 80)
print("PHASE 1: ALTERNATIVE ML MODELS COMPARISON")
print("=" * 80)
print()

# Load data
print("Loading training data...")
df = pd.read_csv('ml_training_data.csv')
print(f"Total samples: {len(df):,}")

# Prepare features and target
feature_cols = [col for col in df.columns if col not in ['timestamp', 'is_profitable', 'max_profit_reached',
                                                           'bars_to_target', 'trade_direction']]
X = df[feature_cols].fillna(0)
y = df['is_profitable'].astype(int)

print(f"Features: {len(feature_cols)}")
print(f"Class balance: {y.mean():.1%} positive")
print()

# Time series split for proper validation
print("Setting up walk-forward validation (5 folds)...")
tscv = TimeSeriesSplit(n_splits=5)
print()

# Store results
results = []

# ============================================================================
# MODEL 1: XGBoost (Baseline)
# ============================================================================
print("=" * 80)
print("MODEL 1: XGBoost (Baseline)")
print("=" * 80)

xgb_params = {
    'objective': 'binary:logistic',
    'eval_metric': 'auc',
    'max_depth': 6,
    'learning_rate': 0.1,
    'n_estimators': 200,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'random_state': 42,
    'tree_method': 'hist'
}

xgb_scores = []
for fold, (train_idx, val_idx) in enumerate(tscv.split(X), 1):
    X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
    y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

    model = xgb.XGBClassifier(**xgb_params)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    y_pred_proba = model.predict_proba(X_val)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    auc = roc_auc_score(y_val, y_pred_proba)
    acc = accuracy_score(y_val, y_pred)

    xgb_scores.append({'auc': auc, 'accuracy': acc})
    print(f"  Fold {fold}: AUC={auc:.4f}, Accuracy={acc:.4f}")

xgb_avg_auc = np.mean([s['auc'] for s in xgb_scores])
xgb_avg_acc = np.mean([s['accuracy'] for s in xgb_scores])
print(f"  Average: AUC={xgb_avg_auc:.4f} ± {np.std([s['auc'] for s in xgb_scores]):.4f}")
print(f"  Average: Accuracy={xgb_avg_acc:.4f} ± {np.std([s['accuracy'] for s in xgb_scores]):.4f}")
print()

results.append({
    'model': 'XGBoost',
    'avg_auc': xgb_avg_auc,
    'std_auc': np.std([s['auc'] for s in xgb_scores]),
    'avg_accuracy': xgb_avg_acc,
    'std_accuracy': np.std([s['accuracy'] for s in xgb_scores]),
    'training_time': 'Fast'
})

# ============================================================================
# MODEL 2: LightGBM (Microsoft - supposedly faster/better)
# ============================================================================
print("=" * 80)
print("MODEL 2: LightGBM (Microsoft)")
print("=" * 80)
print("Known for: Speed, accuracy, handles imbalanced classes well")
print()

lgb_params = {
    'objective': 'binary',
    'metric': 'auc',
    'max_depth': 6,
    'learning_rate': 0.1,
    'n_estimators': 200,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'random_state': 42,
    'verbose': -1
}

lgb_scores = []
for fold, (train_idx, val_idx) in enumerate(tscv.split(X), 1):
    X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
    y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

    model = lgb.LGBMClassifier(**lgb_params)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)])

    y_pred_proba = model.predict_proba(X_val)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    auc = roc_auc_score(y_val, y_pred_proba)
    acc = accuracy_score(y_val, y_pred)

    lgb_scores.append({'auc': auc, 'accuracy': acc})
    print(f"  Fold {fold}: AUC={auc:.4f}, Accuracy={acc:.4f}")

lgb_avg_auc = np.mean([s['auc'] for s in lgb_scores])
lgb_avg_acc = np.mean([s['accuracy'] for s in lgb_scores])
print(f"  Average: AUC={lgb_avg_auc:.4f} ± {np.std([s['auc'] for s in lgb_scores]):.4f}")
print(f"  Average: Accuracy={lgb_avg_acc:.4f} ± {np.std([s['accuracy'] for s in lgb_scores]):.4f}")

improvement = ((lgb_avg_auc - xgb_avg_auc) / xgb_avg_auc) * 100
print(f"  vs XGBoost: {improvement:+.2f}% AUC improvement")
print()

results.append({
    'model': 'LightGBM',
    'avg_auc': lgb_avg_auc,
    'std_auc': np.std([s['auc'] for s in lgb_scores]),
    'avg_accuracy': lgb_avg_acc,
    'std_accuracy': np.std([s['accuracy'] for s in lgb_scores]),
    'training_time': 'Very Fast'
})

# ============================================================================
# MODEL 3: CatBoost (Yandex - best for categorical features)
# ============================================================================
print("=" * 80)
print("MODEL 3: CatBoost (Yandex)")
print("=" * 80)
print("Known for: Handles categorical features, symmetric trees, robust")
print()

cat_params = {
    'iterations': 200,
    'learning_rate': 0.1,
    'depth': 6,
    'loss_function': 'Logloss',
    'eval_metric': 'AUC',
    'random_seed': 42,
    'verbose': False
}

cat_scores = []
for fold, (train_idx, val_idx) in enumerate(tscv.split(X), 1):
    X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
    y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

    model = cb.CatBoostClassifier(**cat_params)
    model.fit(X_train, y_train, eval_set=(X_val, y_val))

    y_pred_proba = model.predict_proba(X_val)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    auc = roc_auc_score(y_val, y_pred_proba)
    acc = accuracy_score(y_val, y_pred)

    cat_scores.append({'auc': auc, 'accuracy': acc})
    print(f"  Fold {fold}: AUC={auc:.4f}, Accuracy={acc:.4f}")

cat_avg_auc = np.mean([s['auc'] for s in cat_scores])
cat_avg_acc = np.mean([s['accuracy'] for s in cat_scores])
print(f"  Average: AUC={cat_avg_auc:.4f} ± {np.std([s['auc'] for s in cat_scores]):.4f}")
print(f"  Average: Accuracy={cat_avg_acc:.4f} ± {np.std([s['accuracy'] for s in cat_scores]):.4f}")

improvement = ((cat_avg_auc - xgb_avg_auc) / xgb_avg_auc) * 100
print(f"  vs XGBoost: {improvement:+.2f}% AUC improvement")
print()

results.append({
    'model': 'CatBoost',
    'avg_auc': cat_avg_auc,
    'std_auc': np.std([s['auc'] for s in cat_scores]),
    'avg_accuracy': cat_avg_acc,
    'std_accuracy': np.std([s['accuracy'] for s in cat_scores]),
    'training_time': 'Medium'
})

# ============================================================================
# RESULTS COMPARISON
# ============================================================================
print("=" * 80)
print("RESULTS COMPARISON")
print("=" * 80)
print()

results_df = pd.DataFrame(results)
results_df = results_df.sort_values('avg_auc', ascending=False)

print("Model Performance Ranking (by AUC):")
print()
print(results_df.to_string(index=False))
print()

# Find best model
best_model = results_df.iloc[0]['model']
best_auc = results_df.iloc[0]['avg_auc']

print("=" * 80)
print(f"WINNER: {best_model} (AUC: {best_auc:.4f})")
print("=" * 80)
print()

# Statistical significance test
print("Statistical Comparison:")
print()
for i, row in results_df.iterrows():
    if row['model'] != best_model:
        diff = (best_auc - row['avg_auc']) / row['std_auc']
        if diff > 2:
            sig = "***SIGNIFICANTLY BETTER***"
        elif diff > 1:
            sig = "*BETTER*"
        else:
            sig = "~SIMILAR~"
        print(f"{best_model} vs {row['model']}: {sig}")
print()

# ============================================================================
# FEATURE IMPORTANCE COMPARISON
# ============================================================================
print("=" * 80)
print("FEATURE IMPORTANCE COMPARISON")
print("=" * 80)
print()

# Train final models on all data for feature importance
print("Training final models on full dataset...")
print()

# XGBoost
xgb_final = xgb.XGBClassifier(**xgb_params)
xgb_final.fit(X, y, verbose=False)
xgb_importances = pd.DataFrame({
    'feature': feature_cols,
    'xgboost': xgb_final.feature_importances_
})

# LightGBM
lgb_final = lgb.LGBMClassifier(**lgb_params)
lgb_final.fit(X, y)
lgb_importances = pd.DataFrame({
    'feature': feature_cols,
    'lightgbm': lgb_final.feature_importances_
})

# CatBoost
cat_final = cb.CatBoostClassifier(**cat_params)
cat_final.fit(X, y)
cat_importances = pd.DataFrame({
    'feature': feature_cols,
    'catboost': cat_final.feature_importances_
})

# Merge all importances
importance_df = xgb_importances.merge(lgb_importances, on='feature')
importance_df = importance_df.merge(cat_importances, on='feature')

# Normalize to percentages
for col in ['xgboost', 'lightgbm', 'catboost']:
    importance_df[col] = (importance_df[col] / importance_df[col].sum()) * 100

# Add average
importance_df['average'] = importance_df[['xgboost', 'lightgbm', 'catboost']].mean(axis=1)
importance_df = importance_df.sort_values('average', ascending=False)

print("Top 20 Most Important Features (all models):")
print()
print(importance_df.head(20).to_string(index=False))
print()

# Save results
print("Saving results...")
results_df.to_csv('phase1_model_comparison.csv', index=False)
importance_df.to_csv('phase1_feature_importance.csv', index=False)

# Save best model
import pickle
if best_model == 'XGBoost':
    best_model_obj = xgb_final
elif best_model == 'LightGBM':
    best_model_obj = lgb_final
else:
    best_model_obj = cat_final

with open(f'models/{best_model.lower()}_best.pkl', 'wb') as f:
    pickle.dump(best_model_obj, f)

print()
print("=" * 80)
print("PHASE 1 COMPLETE")
print("=" * 80)
print()
print("Files created:")
print("  - phase1_model_comparison.csv")
print("  - phase1_feature_importance.csv")
print(f"  - models/{best_model.lower()}_best.pkl")
print()
print(f"Recommendation: Use {best_model} for Phase 2 (Ensembles)")
print()
