#!/usr/bin/env python3
"""
PHASE 5: PROPER WALK-FORWARD OPTIMIZATION
Test multiple walk-forward schemes:
- Expanding window
- Rolling window
- Purged K-Fold
"""

import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, accuracy_score
from sklearn.model_selection import TimeSeriesSplit
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

print("=" * 80)
print("PHASE 5: WALK-FORWARD OPTIMIZATION")
print("=" * 80)
print()

# Load data
print("Loading training data...")
df = pd.read_csv('ml_training_data.csv')
print(f"Total samples: {len(df):,}")
print()

# Prepare features and target
feature_cols = [col for col in df.columns if col not in ['timestamp', 'is_profitable', 'max_profit_reached',
                                                           'bars_to_target', 'trade_direction']]
X = df[feature_cols].fillna(0)
y = df['is_profitable'].astype(int)

# Results storage
results = []

# ============================================================================
# METHOD 1: EXPANDING WINDOW
# ============================================================================
print("=" * 80)
print("METHOD 1: EXPANDING WINDOW")
print("=" * 80)
print()
print("Train on bars 1-1000, test on 1001-1500")
print("Train on bars 1-1500, test on 1501-2000")
print("Etc. (training set grows)")
print()

# Split data into 5 windows
n_windows = 5
window_size = len(X) // (n_windows + 1)

expanding_results = []

for i in range(1, n_windows + 1):
    train_end = window_size * i
    test_start = train_end
    test_end = min(train_end + window_size, len(X))

    X_train = X.iloc[:train_end]
    y_train = y.iloc[:train_end]
    X_test = X.iloc[test_start:test_end]
    y_test = y.iloc[test_start:test_end]

    print(f"Window {i}:")
    print(f"  Train: 0 -> {train_end} ({len(X_train)} samples)")
    print(f"  Test: {test_start} -> {test_end} ({len(X_test)} samples)")

    # Train model
    model = xgb.XGBClassifier(
        max_depth=6,
        learning_rate=0.1,
        n_estimators=200,
        random_state=42,
        verbosity=0
    )
    model.fit(X_train, y_train)

    # Test
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    auc = roc_auc_score(y_test, y_pred_proba)
    acc = accuracy_score(y_test, y_pred)
    win_rate = y_pred.mean() * 100

    expanding_results.append({
        'window': i,
        'auc': auc,
        'accuracy': acc,
        'win_rate': win_rate
    })

    print(f"  AUC: {auc:.4f}")
    print(f"  Accuracy: {acc:.4f}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print()

expanding_avg_auc = np.mean([r['auc'] for r in expanding_results])
expanding_avg_wr = np.mean([r['win_rate'] for r in expanding_results])

print(f"Expanding Window Average:")
print(f"  AUC: {expanding_avg_auc:.4f} ± {np.std([r['auc'] for r in expanding_results]):.4f}")
print(f"  Win Rate: {expanding_avg_wr:.1f}% ± {np.std([r['win_rate'] for r in expanding_results]):.1f}%")
print()

results.append({
    'method': 'Expanding Window',
    'avg_auc': expanding_avg_auc,
    'std_auc': np.std([r['auc'] for r in expanding_results]),
    'avg_win_rate': expanding_avg_wr,
    'stability': 'High (more data over time)'
})

# ============================================================================
# METHOD 2: ROLLING WINDOW
# ============================================================================
print("=" * 80)
print("METHOD 2: ROLLING WINDOW")
print("=" * 80)
print()
print("Train on bars 1-1000, test on 1001-1500")
print("Train on bars 501-1500, test on 1501-2000")
print("Etc. (training set size constant)")
print()

train_window_size = len(X) // 3
test_window_size = len(X) // 6
n_rolls = 3

rolling_results = []

for i in range(n_rolls):
    train_start = i * test_window_size
    train_end = train_start + train_window_size
    test_start = train_end
    test_end = min(test_start + test_window_size, len(X))

    if test_end - test_start < 100:
        break

    X_train = X.iloc[train_start:train_end]
    y_train = y.iloc[train_start:train_end]
    X_test = X.iloc[test_start:test_end]
    y_test = y.iloc[test_start:test_end]

    print(f"Window {i + 1}:")
    print(f"  Train: {train_start} -> {train_end} ({len(X_train)} samples)")
    print(f"  Test: {test_start} -> {test_end} ({len(X_test)} samples)")

    # Train model
    model = xgb.XGBClassifier(
        max_depth=6,
        learning_rate=0.1,
        n_estimators=200,
        random_state=42,
        verbosity=0
    )
    model.fit(X_train, y_train)

    # Test
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    auc = roc_auc_score(y_test, y_pred_proba)
    acc = accuracy_score(y_test, y_pred)
    win_rate = y_pred.mean() * 100

    rolling_results.append({
        'window': i + 1,
        'auc': auc,
        'accuracy': acc,
        'win_rate': win_rate
    })

    print(f"  AUC: {auc:.4f}")
    print(f"  Accuracy: {acc:.4f}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print()

rolling_avg_auc = np.mean([r['auc'] for r in rolling_results])
rolling_avg_wr = np.mean([r['win_rate'] for r in rolling_results])

print(f"Rolling Window Average:")
print(f"  AUC: {rolling_avg_auc:.4f} ± {np.std([r['auc'] for r in rolling_results]):.4f}")
print(f"  Win Rate: {rolling_avg_wr:.1f}% ± {np.std([r['win_rate'] for r in rolling_results]):.1f}%")
print()

results.append({
    'method': 'Rolling Window',
    'avg_auc': rolling_avg_auc,
    'std_auc': np.std([r['auc'] for r in rolling_results]),
    'avg_win_rate': rolling_avg_wr,
    'stability': 'Medium (adapts to recent data)'
})

# ============================================================================
# METHOD 3: PURGED K-FOLD
# ============================================================================
print("=" * 80)
print("METHOD 3: PURGED K-FOLD")
print("=" * 80)
print()
print("Like K-Fold but removes bars around validation set to prevent leakage")
print()

embargo_pct = 0.05  # Remove 5% before and after validation set

purged_results = []
n_splits = 5
tscv = TimeSeriesSplit(n_splits=n_splits)

for fold, (train_idx, val_idx) in enumerate(tscv.split(X), 1):
    # Calculate embargo size
    embargo_size = int(len(X) * embargo_pct)

    # Remove samples around validation set
    val_start = val_idx[0]
    val_end = val_idx[-1]

    # Purge training samples that are too close to validation
    purge_mask = (train_idx < val_start - embargo_size)
    train_idx_purged = train_idx[purge_mask]

    X_train = X.iloc[train_idx_purged]
    y_train = y.iloc[train_idx_purged]
    X_val = X.iloc[val_idx]
    y_val = y.iloc[val_idx]

    print(f"Fold {fold}:")
    print(f"  Original train samples: {len(train_idx)}")
    print(f"  Purged train samples: {len(train_idx_purged)} (removed {len(train_idx) - len(train_idx_purged)})")
    print(f"  Validation samples: {len(val_idx)}")

    # Train model
    model = xgb.XGBClassifier(
        max_depth=6,
        learning_rate=0.1,
        n_estimators=200,
        random_state=42,
        verbosity=0
    )
    model.fit(X_train, y_train)

    # Test
    y_pred_proba = model.predict_proba(X_val)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    auc = roc_auc_score(y_val, y_pred_proba)
    acc = accuracy_score(y_val, y_pred)
    win_rate = y_pred.mean() * 100

    purged_results.append({
        'fold': fold,
        'auc': auc,
        'accuracy': acc,
        'win_rate': win_rate
    })

    print(f"  AUC: {auc:.4f}")
    print(f"  Accuracy: {acc:.4f}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print()

purged_avg_auc = np.mean([r['auc'] for r in purged_results])
purged_avg_wr = np.mean([r['win_rate'] for r in purged_results])

print(f"Purged K-Fold Average:")
print(f"  AUC: {purged_avg_auc:.4f} ± {np.std([r['auc'] for r in purged_results]):.4f}")
print(f"  Win Rate: {purged_avg_wr:.1f}% ± {np.std([r['win_rate'] for r in purged_results]):.1f}%")
print()

results.append({
    'method': 'Purged K-Fold',
    'avg_auc': purged_avg_auc,
    'std_auc': np.std([r['auc'] for r in purged_results]),
    'avg_win_rate': purged_avg_wr,
    'stability': 'High (prevents leakage)'
})

# ============================================================================
# METHOD 4: STANDARD TIME SERIES SPLIT (Baseline)
# ============================================================================
print("=" * 80)
print("METHOD 4: STANDARD TIME SERIES SPLIT (Baseline)")
print("=" * 80)
print()

standard_results = []
tscv = TimeSeriesSplit(n_splits=5)

for fold, (train_idx, val_idx) in enumerate(tscv.split(X), 1):
    X_train = X.iloc[train_idx]
    y_train = y.iloc[train_idx]
    X_val = X.iloc[val_idx]
    y_val = y.iloc[val_idx]

    # Train model
    model = xgb.XGBClassifier(
        max_depth=6,
        learning_rate=0.1,
        n_estimators=200,
        random_state=42,
        verbosity=0
    )
    model.fit(X_train, y_train)

    # Test
    y_pred_proba = model.predict_proba(X_val)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    auc = roc_auc_score(y_val, y_pred_proba)
    acc = accuracy_score(y_val, y_pred)
    win_rate = y_pred.mean() * 100

    standard_results.append({
        'fold': fold,
        'auc': auc,
        'accuracy': acc,
        'win_rate': win_rate
    })

standard_avg_auc = np.mean([r['auc'] for r in standard_results])
standard_avg_wr = np.mean([r['win_rate'] for r in standard_results])

print(f"Standard TS Split Average:")
print(f"  AUC: {standard_avg_auc:.4f} ± {np.std([r['auc'] for r in standard_results]):.4f}")
print(f"  Win Rate: {standard_avg_wr:.1f}% ± {np.std([r['win_rate'] for r in standard_results]):.1f}%")
print()

results.append({
    'method': 'Standard TS Split',
    'avg_auc': standard_avg_auc,
    'std_auc': np.std([r['auc'] for r in standard_results]),
    'avg_win_rate': standard_avg_wr,
    'stability': 'Medium (baseline)'
})

# ============================================================================
# COMPARISON
# ============================================================================
print("=" * 80)
print("WALK-FORWARD METHOD COMPARISON")
print("=" * 80)
print()

results_df = pd.DataFrame(results)
results_df = results_df.sort_values('avg_auc', ascending=False)

print(results_df.to_string(index=False))
print()

best_method = results_df.iloc[0]['method']
print(f"Best Method: {best_method}")
print()

# ============================================================================
# STABILITY ANALYSIS
# ============================================================================
print("=" * 80)
print("STABILITY ANALYSIS")
print("=" * 80)
print()
print("Lower standard deviation = more stable performance")
print()

stability_df = pd.DataFrame({
    'method': [r['method'] for r in results],
    'std_auc': [r['std_auc'] for r in results]
}).sort_values('std_auc')

print("Most Stable Methods:")
print(stability_df.to_string(index=False))
print()

most_stable = stability_df.iloc[0]['method']
print(f"Most Stable: {most_stable}")
print()

# ============================================================================
# SAVE RESULTS
# ============================================================================
print("=" * 80)
print("SAVING RESULTS")
print("=" * 80)
print()

# Save all window results
pd.DataFrame(expanding_results).to_csv('phase5_expanding_window.csv', index=False)
pd.DataFrame(rolling_results).to_csv('phase5_rolling_window.csv', index=False)
pd.DataFrame(purged_results).to_csv('phase5_purged_kfold.csv', index=False)
pd.DataFrame(standard_results).to_csv('phase5_standard_split.csv', index=False)

# Save comparison
results_df.to_csv('phase5_comparison.csv', index=False)

print("✓ Saved all walk-forward results")
print()

print("=" * 80)
print("PHASE 5 COMPLETE")
print("=" * 80)
print()
print("Files created:")
print("  - phase5_expanding_window.csv")
print("  - phase5_rolling_window.csv")
print("  - phase5_purged_kfold.csv")
print("  - phase5_standard_split.csv")
print("  - phase5_comparison.csv")
print()
print(f"RECOMMENDATION:")
print(f"  Best Performance: {best_method} (AUC: {results_df.iloc[0]['avg_auc']:.4f})")
print(f"  Most Stable: {most_stable} (Std: {stability_df.iloc[0]['std_auc']:.4f})")
print()
print("Use Purged K-Fold for most honest evaluation (prevents data leakage)")
print("Use Expanding Window for production (mimics real trading)")
print()
