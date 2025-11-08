"""
Process REAL SPY data and run backtest

This uses actual historical market data from May-October 2011
"""

import pandas as pd
import numpy as np
from datetime import time
import sys

sys.path.append('src')
from run_elite_backtest import EliteBacktestRunner

print("="*80)
print("PROCESSING REAL MARKET DATA")
print("="*80)

# Load real SPY data
print("\n📂 Loading REAL SPY data from May-October 2011...")
data = pd.read_csv('data/spy_real_daily.csv')

print(f"✅ Loaded {len(data)} rows of REAL market data")
print(f"\nColumns: {list(data.columns)}")
print(f"\nFirst 5 rows:\n{data.head()}")

# Parse dates
print("\n🔧 Processing data...")
data['Date'] = pd.to_datetime(data['Date'], format='%m/%d/%Y %H:%M')
data.set_index('Date', inplace=True)

# Rename columns to standard OHLCV
data = data.rename(columns={'LAST_PRICE': 'Close', 'VOLUME': 'Volume'})

# Since we only have Close price, create OHLC from it
# This is a limitation but better than nothing
data['Open'] = data['Close']
data['High'] = data['Close']
data['Low'] = data['Close']

# Convert SPY to SPX500 (multiply by 10)
print("🔄 Converting SPY to SPX500 equivalent (x10)...")
for col in ['Open', 'High', 'Low', 'Close']:
    data[col] = data[col] * 10

# Keep only standard trading hours (9:30 AM - 4:00 PM)
print("⏰ Filtering to regular trading hours (9:30 AM - 4:00 PM EST)...")
data = data.between_time('09:30', '16:00')

print(f"\n✅ Processed {len(data)} bars")
print(f"   Date range: {data.index[0]} to {data.index[-1]}")
print(f"   Price range: ${data['Low'].min():.2f} to ${data['High'].max():.2f}")
print(f"   Trading days: {len(data.index.normalize().unique())}")

# Resample to 5-minute and 15-minute
print("\n📊 Resampling to multi-timeframe...")

data_5m = data.resample('5min').agg({
    'Open': 'first',
    'High': 'max',
    'Low': 'min',
    'Close': 'last',
    'Volume': 'sum'
}).dropna()

data_15m = data.resample('15min').agg({
    'Open': 'first',
    'High': 'max',
    'Low': 'min',
    'Close': 'last',
    'Volume': 'sum'
}).dropna()

print(f"   1-minute: {len(data)} bars")
print(f"   5-minute: {len(data_5m)} bars")
print(f"   15-minute: {len(data_15m)} bars")

# Save processed data
data.to_csv('data/spy_real_1min_processed.csv')
data_5m.to_csv('data/spy_real_5min_processed.csv')
data_15m.to_csv('data/spy_real_15min_processed.csv')

print(f"\n💾 Saved processed data")

print("\n" + "="*80)
print("RUNNING BACKTEST ON REAL MARKET DATA")
print("="*80)

# Initialize backtest runner
runner = EliteBacktestRunner(
    initial_capital=50000,
    risk_percent=0.006,
    point_value=50,
    enable_guardian_shield=True
)

# Set optimized parameters
runner.strategy.min_confluence_score = 6  # Only 6/7 or 7/7 setups
runner.strategy.optimal_start = time(9, 30)
runner.strategy.optimal_end = time(11, 0)  # First 90 minutes only

# Run backtest
runner.run_backtest(data_15m, data_5m, data)

print("\n" + "="*80)
print("⚠️  IMPORTANT: REAL DATA RESULTS")
print("="*80)
print("\nThis backtest used REAL historical market data from May-October 2011")
print("NOT synthetic/generated data")
print("\nLimitations:")
print("  - Only 1-minute CLOSE prices available (no full OHLC tick data)")
print("  - Data from 2011 (market conditions may differ from 2024)")
print("  - Limited to 6 months of data")
print("\nHowever, these results are MORE RELIABLE than synthetic data tests")
print("="*80)
