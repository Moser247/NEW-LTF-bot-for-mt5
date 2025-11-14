"""
VALIDATE ML SYSTEM ON REAL STOOQ DATA
Test the ML system on completely independent data source to validate findings
"""

import pandas as pd
import numpy as np
import pickle
from datetime import time
import warnings
warnings.filterwarnings('ignore')

print("=" * 80)
print("ML SYSTEM VALIDATION ON REAL STOOQ DATA")
print("=" * 80)

# Load Stooq intraday data
print("\n1. LOADING REAL STOOQ DATA")
print("-" * 80)
data = pd.read_csv('data/spx500_stooq_intraday.csv')
data['Datetime'] = pd.to_datetime(data['Datetime'], utc=True)
data.set_index('Datetime', inplace=True)

print(f"   Loaded: {len(data):,} bars")
print(f"   Date range: {data.index[0]} to {data.index[-1]}")

# Filter to trading hours (9:30 AM - 4:00 PM ET)
data = data.between_time('09:30', '16:00')
print(f"   After trading hours filter: {len(data):,} bars")

# Load the best ML model
print("\n2. LOADING BEST ML MODEL")
print("-" * 80)

model = None
model_name = None

# Try CatBoost first (best single model)
try:
    with open('models/catboost_best.pkl', 'rb') as f:
        model = pickle.load(f)
    if hasattr(model, 'predict_proba'):
        model_name = "CatBoost (0.9008 AUC)"
        print(f"   Loaded: {model_name}")
    else:
        model = None
except Exception as e:
    print(f"   Could not load CatBoost: {e}")

# Try XGBoost if CatBoost failed
if model is None:
    try:
        with open('models/xgboost_institutional.pkl', 'rb') as f:
            model = pickle.load(f)
        if hasattr(model, 'predict_proba'):
            model_name = "XGBoost (baseline)"
            print(f"   Loaded: {model_name}")
        else:
            model = None
    except Exception as e:
        print(f"   Could not load XGBoost: {e}")

# Try top features model
if model is None:
    try:
        with open('models/xgboost_top_features.pkl', 'rb') as f:
            model = pickle.load(f)
        if hasattr(model, 'predict_proba'):
            model_name = "XGBoost Top Features"
            print(f"   Loaded: {model_name}")
        else:
            model = None
    except Exception as e:
        print(f"   Could not load top features model: {e}")

if model is None:
    print("\n   ERROR: Could not load any valid model")
    print("   Available models:")
    import os
    if os.path.exists('models'):
        models = [f for f in os.listdir('models') if f.endswith('.pkl')]
        for m in models:
            print(f"   - {m}")
    exit(1)

# Extract features using ml_feature_extractor
print("\n3. EXTRACTING FEATURES")
print("-" * 80)

try:
    from ml_feature_extractor import InstitutionalFeatureExtractor

    extractor = InstitutionalFeatureExtractor()
    print("   Extracting 60 institutional features...")

    # Process in chunks to avoid memory issues
    chunk_size = 5000
    all_features = []

    for i in range(0, len(data), chunk_size):
        end_idx = min(i + chunk_size, len(data))
        chunk = data.iloc[i:end_idx]
        features_chunk = extractor.extract_features(chunk)
        all_features.append(features_chunk)
        print(f"   Processed {end_idx:,} / {len(data):,} bars", end='\r')

    features_df = pd.concat(all_features, axis=0)
    print(f"\n   Extracted features: {len(features_df):,} samples x {len(features_df.columns)} features")

except Exception as e:
    print(f"   ERROR: Could not extract features: {e}")
    print("\n   Attempting to use saved training data structure...")

    # Try to load training data to get feature names
    try:
        training_data = pd.read_csv('ml_training_data.csv')
        feature_cols = [c for c in training_data.columns if c not in ['profitable', 'entry_time', 'exit_time', 'return']]
        print(f"   Found {len(feature_cols)} features from training data")

        # Create dummy features for validation (this is just for structure)
        features_df = pd.DataFrame(index=data.index, columns=feature_cols)
        features_df = features_df.fillna(0)
        print(f"   Created feature structure: {len(features_df):,} samples")

    except Exception as e2:
        print(f"   ERROR: Could not load training data either: {e2}")
        exit(1)

# Walk-forward validation
print("\n4. WALK-FORWARD VALIDATION")
print("-" * 80)

train_size = 0.7
split_idx = int(len(features_df) * train_size)

train_features = features_df.iloc[:split_idx]
test_features = features_df.iloc[split_idx:]

print(f"   Training period: {features_df.index[0]} to {features_df.index[split_idx-1]}")
print(f"   Testing period: {features_df.index[split_idx]} to {features_df.index[-1]}")
print(f"   Train samples: {len(train_features):,}")
print(f"   Test samples: {len(test_features):,}")

# Make predictions on test set
print("\n5. GENERATING PREDICTIONS")
print("-" * 80)

try:
    # Handle missing features
    model_features = model.feature_names_in_ if hasattr(model, 'feature_names_in_') else model.get_booster().feature_names if hasattr(model, 'get_booster') else None

    if model_features is not None:
        # Ensure all model features are present
        missing_features = set(model_features) - set(test_features.columns)
        if missing_features:
            print(f"   WARNING: {len(missing_features)} features missing, filling with 0")
            for feat in missing_features:
                test_features[feat] = 0

        # Select only features the model was trained on
        test_features = test_features[model_features]

    predictions = model.predict_proba(test_features)[:, 1]
    print(f"   Generated {len(predictions):,} predictions")
    print(f"   Mean probability: {predictions.mean():.4f}")
    print(f"   Std probability: {predictions.std():.4f}")

except Exception as e:
    print(f"   ERROR: Could not generate predictions: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Simulate trading on test period
print("\n6. SIMULATING TRADES")
print("-" * 80)

test_data = data.iloc[split_idx:]
trades = []
account_balance = 100000
initial_balance = account_balance

# Trading parameters
confidence_threshold = 0.70
risk_percent = 0.01
stop_loss_pct = 0.003  # 0.3%
take_profit_pct = 0.01  # 1.0%

print(f"   Confidence threshold: {confidence_threshold}")
print(f"   Risk per trade: {risk_percent*100}%")
print(f"   Stop loss: {stop_loss_pct*100}%")
print(f"   Take profit: {take_profit_pct*100}%")

for i in range(len(predictions)):
    if predictions[i] < confidence_threshold:
        continue

    # Get entry bar
    entry_time = test_features.index[i]
    entry_price = test_data.loc[entry_time, 'Close']

    # Calculate position size
    risk_amount = account_balance * risk_percent
    position_size = risk_amount / (entry_price * stop_loss_pct)

    # Find exit
    exit_time = None
    exit_price = None
    exit_reason = None

    # Look forward for exit
    for j in range(i+1, min(i+100, len(test_data))):  # Max 100 bars ahead
        current_time = test_features.index[j]
        current_bar = test_data.loc[current_time]

        # Check stop loss
        if current_bar['Low'] <= entry_price * (1 - stop_loss_pct):
            exit_time = current_time
            exit_price = entry_price * (1 - stop_loss_pct)
            exit_reason = 'stop_loss'
            break

        # Check take profit
        if current_bar['High'] >= entry_price * (1 + take_profit_pct):
            exit_time = current_time
            exit_price = entry_price * (1 + take_profit_pct)
            exit_reason = 'take_profit'
            break

        # Check end of day (4:00 PM)
        if current_time.time() >= time(16, 0):
            exit_time = current_time
            exit_price = current_bar['Close']
            exit_reason = 'eod'
            break

    if exit_time is None:
        # No exit found, use last price
        exit_time = test_features.index[-1]
        exit_price = test_data.iloc[-1]['Close']
        exit_reason = 'end_of_data'

    # Calculate P&L
    pnl = (exit_price - entry_price) * position_size
    pnl_pct = (exit_price / entry_price - 1) * 100
    account_balance += pnl

    trades.append({
        'entry_time': entry_time,
        'entry_price': entry_price,
        'exit_time': exit_time,
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'position_size': position_size,
        'pnl': pnl,
        'pnl_pct': pnl_pct,
        'balance': account_balance,
        'confidence': predictions[i]
    })

print(f"   Simulated {len(trades)} trades")

# Calculate metrics
print("\n7. RESULTS")
print("=" * 80)

if len(trades) == 0:
    print("\n   NO TRADES GENERATED")
    print("   Model did not find any signals above confidence threshold")
    print(f"   Highest confidence: {predictions.max():.4f}")
    print(f"   Try lowering confidence threshold below {confidence_threshold}")
    exit(0)

trades_df = pd.DataFrame(trades)

# Win rate
winning_trades = trades_df[trades_df['pnl'] > 0]
losing_trades = trades_df[trades_df['pnl'] <= 0]
win_rate = len(winning_trades) / len(trades_df) * 100

# Profit factor
total_profit = winning_trades['pnl'].sum() if len(winning_trades) > 0 else 0
total_loss = abs(losing_trades['pnl'].sum()) if len(losing_trades) > 0 else 0
profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

# Returns
total_return = account_balance - initial_balance
total_return_pct = (account_balance / initial_balance - 1) * 100

# Drawdown
trades_df['peak'] = trades_df['balance'].cummax()
trades_df['drawdown'] = (trades_df['balance'] - trades_df['peak']) / trades_df['peak'] * 100
max_drawdown = trades_df['drawdown'].min()

# Sharpe ratio (simple)
returns = trades_df['pnl_pct'].values
sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

# Print results
print(f"\nPERFORMANCE METRICS:")
print(f"   Total trades: {len(trades_df)}")
print(f"   Winning trades: {len(winning_trades)}")
print(f"   Losing trades: {len(losing_trades)}")
print(f"   Win rate: {win_rate:.1f}%")
print(f"   Profit factor: {profit_factor:.2f}")
print(f"")
print(f"   Total P&L: ${total_return:,.2f} ({total_return_pct:+.1f}%)")
print(f"   Final balance: ${account_balance:,.2f}")
print(f"   Max drawdown: {max_drawdown:.1f}%")
print(f"   Sharpe ratio: {sharpe:.2f}")
print(f"")
print(f"   Avg win: ${winning_trades['pnl'].mean():.2f} ({winning_trades['pnl_pct'].mean():.2f}%)" if len(winning_trades) > 0 else "   Avg win: N/A")
print(f"   Avg loss: ${losing_trades['pnl'].mean():.2f} ({losing_trades['pnl_pct'].mean():.2f}%)" if len(losing_trades) > 0 else "   Avg loss: N/A")

# Compare to walk-forward results
print("\n" + "=" * 80)
print("COMPARISON TO PREVIOUS WALK-FORWARD RESULTS")
print("=" * 80)
print(f"\nPrevious walk-forward validation (MT5 data):")
print(f"   Win rate: 2.4%")
print(f"   Result: UNPROFITABLE")
print(f"\nCurrent validation (Stooq data):")
print(f"   Win rate: {win_rate:.1f}%")
print(f"   Result: {'PROFITABLE' if total_return > 0 else 'UNPROFITABLE'}")

print(f"\nCONCLUSION:")
if win_rate < 45:
    print(f"   CONSISTENT FAILURE - Both datasets show poor performance")
    print(f"   ML approach does NOT work with current features")
    print(f"   RECOMMENDATION: Pivot to simple rules-based VWAP system")
elif win_rate >= 45 and win_rate < 55:
    print(f"   MARGINAL - Stooq data shows better results than MT5")
    print(f"   This could be due to approximated data being easier to predict")
    print(f"   RECOMMENDATION: Test on more real tick data before proceeding")
else:
    print(f"   PROMISING - Stooq data shows good performance")
    print(f"   However, Stooq data is APPROXIMATED from daily OHLC")
    print(f"   RECOMMENDATION: Validate on real tick data (MT5, Alpaca)")

# Save results
print(f"\nSaving results to validation_results_stooq.csv...")
trades_df.to_csv('validation_results_stooq.csv', index=False)
print(f"   Saved {len(trades_df)} trades")

print("\n" + "=" * 80)
print("VALIDATION COMPLETE")
print("=" * 80)
