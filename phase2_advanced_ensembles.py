#!/usr/bin/env python3
"""
PHASE 2: ADVANCED ENSEMBLE TECHNIQUES
Implement stacking, blending, voting, and Bayesian model averaging
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import TimeSeriesSplit, train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
import xgboost as xgb
import lightgbm as lgb
import catboost as cb
import warnings
warnings.filterwarnings('ignore')

print("=" * 80)
print("PHASE 2: ADVANCED ENSEMBLE TECHNIQUES")
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

# Store results
results = []

# ============================================================================
# ENSEMBLE 1: STACKING (Meta-Learning)
# ============================================================================
print("=" * 80)
print("ENSEMBLE 1: STACKING (Meta-Learning)")
print("=" * 80)
print()
print("Architecture:")
print("  Level 0: XGBoost, LightGBM, CatBoost, Random Forest, Extra Trees")
print("  Level 1: Logistic Regression (meta-learner)")
print()

# Split data for stacking
X_train, X_holdout, y_train, y_holdout = train_test_split(
    X, y, test_size=0.2, shuffle=False  # Time series - no shuffle
)

print(f"Training samples: {len(X_train):,}")
print(f"Holdout samples: {len(X_holdout):,}")
print()

# Level 0 models
print("Training Level 0 base models...")
base_models = []

# Model 1: XGBoost
print("  1. XGBoost...")
xgb_model = xgb.XGBClassifier(
    max_depth=6, learning_rate=0.1, n_estimators=200,
    random_state=42, tree_method='hist', verbosity=0
)
xgb_model.fit(X_train, y_train)
base_models.append(('XGBoost', xgb_model))

# Model 2: LightGBM
print("  2. LightGBM...")
lgb_model = lgb.LGBMClassifier(
    max_depth=6, learning_rate=0.1, n_estimators=200,
    random_state=42, verbose=-1
)
lgb_model.fit(X_train, y_train)
base_models.append(('LightGBM', lgb_model))

# Model 3: CatBoost
print("  3. CatBoost...")
cat_model = cb.CatBoostClassifier(
    depth=6, learning_rate=0.1, iterations=200,
    random_seed=42, verbose=False
)
cat_model.fit(X_train, y_train)
base_models.append(('CatBoost', cat_model))

# Model 4: Random Forest
print("  4. Random Forest...")
rf_model = RandomForestClassifier(
    n_estimators=200, max_depth=6, random_state=42, n_jobs=-1
)
rf_model.fit(X_train, y_train)
base_models.append(('RandomForest', rf_model))

# Model 5: Extra Trees
print("  5. Extra Trees...")
et_model = ExtraTreesClassifier(
    n_estimators=200, max_depth=6, random_state=42, n_jobs=-1
)
et_model.fit(X_train, y_train)
base_models.append(('ExtraTrees', et_model))

print()

# Generate Level 0 predictions
print("Generating Level 0 predictions...")
train_meta_features = np.column_stack([
    model.predict_proba(X_train)[:, 1] for _, model in base_models
])
holdout_meta_features = np.column_stack([
    model.predict_proba(X_holdout)[:, 1] for _, model in base_models
])

# Train Level 1 meta-learner
print("Training Level 1 meta-learner (Logistic Regression)...")
meta_model = LogisticRegression(random_state=42, max_iter=1000)
meta_model.fit(train_meta_features, y_train)

# Evaluate stacking
y_pred_proba = meta_model.predict_proba(holdout_meta_features)[:, 1]
stacking_auc = roc_auc_score(y_holdout, y_pred_proba)
stacking_acc = accuracy_score(y_holdout, (y_pred_proba >= 0.5).astype(int))

print(f"  Stacking AUC: {stacking_auc:.4f}")
print(f"  Stacking Accuracy: {stacking_acc:.4f}")
print()

# Show meta-learner weights
print("Meta-learner weights (how much each model contributes):")
for i, (name, _) in enumerate(base_models):
    weight = meta_model.coef_[0][i]
    print(f"  {name}: {weight:+.4f}")
print()

results.append({
    'ensemble': 'Stacking',
    'auc': stacking_auc,
    'accuracy': stacking_acc,
    'num_models': 5,
    'complexity': 'High'
})

# ============================================================================
# ENSEMBLE 2: BLENDING
# ============================================================================
print("=" * 80)
print("ENSEMBLE 2: BLENDING")
print("=" * 80)
print()
print("Architecture:")
print("  Train: 60%, Validation: 20%, Test: 20%")
print("  Use validation predictions to learn blend weights")
print()

# Split data for blending
split1 = int(len(X) * 0.6)
split2 = int(len(X) * 0.8)

X_blend_train = X.iloc[:split1]
y_blend_train = y.iloc[:split1]
X_blend_val = X.iloc[split1:split2]
y_blend_val = y.iloc[split1:split2]
X_blend_test = X.iloc[split2:]
y_blend_test = y.iloc[split2:]

print(f"Training: {len(X_blend_train):,}")
print(f"Validation: {len(X_blend_val):,}")
print(f"Testing: {len(X_blend_test):,}")
print()

# Train models on training set
print("Training models on training set...")
blend_models = []

for name, model_class, params in [
    ('XGBoost', xgb.XGBClassifier, {'max_depth': 6, 'learning_rate': 0.1, 'n_estimators': 200, 'random_state': 42, 'verbosity': 0}),
    ('LightGBM', lgb.LGBMClassifier, {'max_depth': 6, 'learning_rate': 0.1, 'n_estimators': 200, 'random_state': 42, 'verbose': -1}),
    ('CatBoost', cb.CatBoostClassifier, {'depth': 6, 'learning_rate': 0.1, 'iterations': 200, 'random_seed': 42, 'verbose': False}),
]:
    model = model_class(**params)
    model.fit(X_blend_train, y_blend_train)
    blend_models.append((name, model))

# Get validation predictions
val_preds = np.column_stack([
    model.predict_proba(X_blend_val)[:, 1] for _, model in blend_models
])

# Learn blend weights on validation set
blend_meta = LogisticRegression(random_state=42, max_iter=1000)
blend_meta.fit(val_preds, y_blend_val)

# Test on test set
test_preds = np.column_stack([
    model.predict_proba(X_blend_test)[:, 1] for _, model in blend_models
])
y_pred_proba = blend_meta.predict_proba(test_preds)[:, 1]

blending_auc = roc_auc_score(y_blend_test, y_pred_proba)
blending_acc = accuracy_score(y_blend_test, (y_pred_proba >= 0.5).astype(int))

print(f"  Blending AUC: {blending_auc:.4f}")
print(f"  Blending Accuracy: {blending_acc:.4f}")
print()

print("Blend weights:")
for i, (name, _) in enumerate(blend_models):
    weight = blend_meta.coef_[0][i]
    print(f"  {name}: {weight:+.4f}")
print()

results.append({
    'ensemble': 'Blending',
    'auc': blending_auc,
    'accuracy': blending_acc,
    'num_models': 3,
    'complexity': 'Medium'
})

# ============================================================================
# ENSEMBLE 3: WEIGHTED VOTING
# ============================================================================
print("=" * 80)
print("ENSEMBLE 3: WEIGHTED VOTING")
print("=" * 80)
print()
print("Each model weighted by validation performance")
print()

# Use same train/val/test split from blending
# Models already trained above

# Get validation performance for weights
val_aucs = []
for name, model in blend_models:
    val_pred = model.predict_proba(X_blend_val)[:, 1]
    val_auc = roc_auc_score(y_blend_val, val_pred)
    val_aucs.append(val_auc)
    print(f"  {name} validation AUC: {val_auc:.4f}")

# Normalize to weights
weights = np.array(val_aucs) / np.sum(val_aucs)
print()
print("Normalized weights:")
for (name, _), weight in zip(blend_models, weights):
    print(f"  {name}: {weight:.4f}")
print()

# Weighted average on test set
test_preds_list = [model.predict_proba(X_blend_test)[:, 1] for _, model in blend_models]
weighted_avg = np.average(test_preds_list, axis=0, weights=weights)

voting_auc = roc_auc_score(y_blend_test, weighted_avg)
voting_acc = accuracy_score(y_blend_test, (weighted_avg >= 0.5).astype(int))

print(f"  Weighted Voting AUC: {voting_auc:.4f}")
print(f"  Weighted Voting Accuracy: {voting_acc:.4f}")
print()

results.append({
    'ensemble': 'Weighted Voting',
    'auc': voting_auc,
    'accuracy': voting_acc,
    'num_models': 3,
    'complexity': 'Low'
})

# ============================================================================
# ENSEMBLE 4: SIMPLE AVERAGE
# ============================================================================
print("=" * 80)
print("ENSEMBLE 4: SIMPLE AVERAGE (Baseline)")
print("=" * 80)
print()

simple_avg = np.mean(test_preds_list, axis=0)
simple_auc = roc_auc_score(y_blend_test, simple_avg)
simple_acc = accuracy_score(y_blend_test, (simple_avg >= 0.5).astype(int))

print(f"  Simple Average AUC: {simple_auc:.4f}")
print(f"  Simple Average Accuracy: {simple_acc:.4f}")
print()

results.append({
    'ensemble': 'Simple Average',
    'auc': simple_auc,
    'accuracy': simple_acc,
    'num_models': 3,
    'complexity': 'Very Low'
})

# ============================================================================
# ENSEMBLE 5: BAYESIAN MODEL AVERAGING
# ============================================================================
print("=" * 80)
print("ENSEMBLE 5: BAYESIAN MODEL AVERAGING")
print("=" * 80)
print()
print("Weight by posterior probabilities (approximated by validation performance)")
print()

# Use exponential of AUC as "likelihood"
likelihoods = np.exp(np.array(val_aucs))
posteriors = likelihoods / np.sum(likelihoods)

print("Posterior probabilities:")
for (name, _), post in zip(blend_models, posteriors):
    print(f"  {name}: {post:.4f}")
print()

# Bayesian average
bayesian_avg = np.average(test_preds_list, axis=0, weights=posteriors)
bayesian_auc = roc_auc_score(y_blend_test, bayesian_avg)
bayesian_acc = accuracy_score(y_blend_test, (bayesian_avg >= 0.5).astype(int))

print(f"  Bayesian Average AUC: {bayesian_auc:.4f}")
print(f"  Bayesian Average Accuracy: {bayesian_acc:.4f}")
print()

results.append({
    'ensemble': 'Bayesian Average',
    'auc': bayesian_auc,
    'accuracy': bayesian_acc,
    'num_models': 3,
    'complexity': 'Low'
})

# ============================================================================
# RESULTS COMPARISON
# ============================================================================
print("=" * 80)
print("ENSEMBLE COMPARISON")
print("=" * 80)
print()

results_df = pd.DataFrame(results)
results_df = results_df.sort_values('auc', ascending=False)

print(results_df.to_string(index=False))
print()

best_ensemble = results_df.iloc[0]['ensemble']
best_auc = results_df.iloc[0]['auc']

print("=" * 80)
print(f"WINNER: {best_ensemble} (AUC: {best_auc:.4f})")
print("=" * 80)
print()

# Save results
print("Saving results...")
results_df.to_csv('phase2_ensemble_comparison.csv', index=False)

# Save best ensemble
import pickle

ensemble_info = {
    'type': best_ensemble,
    'base_models': base_models if best_ensemble == 'Stacking' else blend_models,
    'meta_model': meta_model if best_ensemble == 'Stacking' else blend_meta,
    'weights': weights if best_ensemble == 'Weighted Voting' else None,
    'auc': best_auc
}

with open('models/best_ensemble.pkl', 'wb') as f:
    pickle.dump(ensemble_info, f)

print()
print("=" * 80)
print("PHASE 2 COMPLETE")
print("=" * 80)
print()
print("Files created:")
print("  - phase2_ensemble_comparison.csv")
print("  - models/best_ensemble.pkl")
print()
print(f"Recommendation: {best_ensemble} achieved best performance")
print()
