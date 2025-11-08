"""
Process Stooq daily data and run backtest
Filters to last 6 months and creates approximate intraday bars
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

print("=" * 80)
print("PROCESSING STOOQ SPX500 DATA")
print("=" * 80)

# Load daily data
print("\n📂 Loading daily SPX data from Stooq...")
data = pd.read_csv('data/spx500_daily_real.csv', index_col=0)
data.index = pd.to_datetime(data.index)
data = data.sort_index()

print(f"   Total data: {len(data):,} days (from {data.index[0].date()} to {data.index[-1].date()})")

# Filter to last 6 months
six_months_ago = datetime.now() - timedelta(days=180)
data_recent = data[data.index >= six_months_ago].copy()

print(f"   Filtered to last 6 months: {len(data_recent):,} days")

# Expand to approximate intraday
print(f"\n🔄 Expanding to 1-minute bars...")
print(f"   ⚠️  WARNING: This is APPROXIMATED, not real tick data")
print(f"   Results will be less accurate than real intraday data")

intraday_bars = []
bars_per_day = 390  # 9:30 AM to 4:00 PM = 390 minutes

for date, row in data_recent.iterrows():
    # Skip if all values are NaN
    if pd.isna(row['Close']):
        continue

    # Trading hours: 9:30 AM - 4:00 PM
    base_date = pd.Timestamp(date).replace(hour=9, minute=30)

    for minute in range(bars_per_day):
        bar_time = base_date + pd.Timedelta(minutes=minute)

        # Approximate intraday movement
        progress = minute / bars_per_day

        # Simple approximation: linear progression from Open to Close
        # with random noise within High/Low range
        price_range = row['High'] - row['Low']
        if price_range == 0 or pd.isna(price_range):
            price_range = row['Close'] * 0.001  # 0.1% range if no range data

        base_price = row['Open'] + (row['Close'] - row['Open']) * progress
        noise = price_range * 0.1 * np.random.randn()

        intraday_bars.append({
            'Datetime': bar_time,
            'Open': base_price + noise * 0.5,
            'High': base_price + abs(noise),
            'Low': base_price - abs(noise),
            'Close': base_price + noise * 0.3,
            'Volume': row['Volume'] / bars_per_day if not pd.isna(row['Volume']) and row['Volume'] > 0 else 1000
        })

df_intraday = pd.DataFrame(intraday_bars)
df_intraday.set_index('Datetime', inplace=True)

# Set timezone to Eastern
df_intraday.index = df_intraday.index.tz_localize('America/New_York')

print(f"   ✅ Generated {len(df_intraday):,} 1-minute bars")
print(f"   Date range: {df_intraday.index[0]} to {df_intraday.index[-1]}")

# Save
output_file = 'data/spx500_stooq_intraday.csv'
df_intraday.to_csv(output_file)
print(f"\n💾 Saved to: {output_file}")

# Show sample
print(f"\n📊 Sample data (first 10 bars):")
print(df_intraday.head(10))

print("\n" + "=" * 80)
print("✅ DATA READY FOR BACKTESTING")
print("=" * 80)
print(f"\nSource: Stooq.com (real daily SPX data)")
print(f"Processing: Expanded to approximate 1-minute bars")
print(f"Bars: {len(df_intraday):,}")
print(f"\n⚠️  IMPORTANT:")
print(f"   This is APPROXIMATE intraday data based on daily OHLC")
print(f"   Results will be LESS ACCURATE than real tick data")
print(f"   For best results, use Alpaca or MT5 for real intraday data")

print(f"\nNext step:")
print(f"   Running backtest now...")
