"""
Generate sample SPX500 data for backtesting demonstration
Since yfinance has dependency issues, we'll create realistic synthetic data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time

def generate_spx500_sample_data(days=30, start_price=4500):
    """
    Generate realistic SPX500 5-minute bar data

    Args:
        days: Number of trading days
        start_price: Starting price

    Returns:
        DataFrame with OHLCV data
    """
    np.random.seed(42)  # For reproducibility

    data_list = []
    current_price = start_price

    # Trading hours: 9:30 AM - 4:00 PM EST (6.5 hours = 78 bars per day)
    start_time = time(9, 30)
    end_time = time(16, 0)

    start_date = datetime.now() - timedelta(days=days)

    for day in range(days):
        current_date = start_date + timedelta(days=day)

        # Skip weekends
        if current_date.weekday() >= 5:
            continue

        # Daily trend (slightly upward bias like real SPX)
        daily_trend = np.random.normal(0.001, 0.005)  # 0.1% average daily move

        # Opening gap
        gap = np.random.normal(0, 0.003)  # 0.3% average gap
        open_price = current_price * (1 + gap)

        current_bar_time = datetime.combine(current_date.date(), start_time)

        # Generate 5-minute bars for the day
        bars_per_day = 78  # 6.5 hours * 60 / 5 = 78 bars

        for bar in range(bars_per_day):
            # Intraday volatility (higher at open/close)
            hour = current_bar_time.hour + current_bar_time.minute / 60

            if 9.5 <= hour < 10.5 or 15 <= hour < 16:
                # Higher volatility at open and close
                volatility = 0.002  # 0.2%
            elif 12 <= hour < 13:
                # Lower volatility at lunch
                volatility = 0.0005  # 0.05%
            else:
                volatility = 0.001  # 0.1%

            # Generate OHLC for this bar
            bar_open = current_price

            # Random walk with slight trend
            bar_change = np.random.normal(daily_trend / bars_per_day, volatility)
            bar_close = bar_open * (1 + bar_change)

            # High/Low with realistic spread
            high_extra = abs(np.random.normal(0, volatility * 0.5))
            low_extra = abs(np.random.normal(0, volatility * 0.5))

            bar_high = max(bar_open, bar_close) * (1 + high_extra)
            bar_low = min(bar_open, bar_close) * (1 - low_extra)

            # Volume (higher at open/close)
            if 9.5 <= hour < 10 or 15.5 <= hour < 16:
                volume = np.random.randint(80000, 150000)
            else:
                volume = np.random.randint(30000, 80000)

            data_list.append({
                'timestamp': current_bar_time,
                'Open': round(bar_open, 2),
                'High': round(bar_high, 2),
                'Low': round(bar_low, 2),
                'Close': round(bar_close, 2),
                'Volume': volume
            })

            current_price = bar_close
            current_bar_time += timedelta(minutes=5)

            # Stop at market close
            if current_bar_time.time() >= end_time:
                break

    # Create DataFrame
    df = pd.DataFrame(data_list)
    df.set_index('timestamp', inplace=True)

    # Make timezone aware (EST)
    df.index = pd.to_datetime(df.index)
    df.index = df.index.tz_localize('America/New_York')

    return df

if __name__ == "__main__":
    # Generate 30 days of data
    data = generate_spx500_sample_data(days=40)

    # Save to CSV
    data.to_csv('data/spx500_sample_data.csv')

    print(f"Generated {len(data)} bars of sample data")
    print(f"Date range: {data.index[0]} to {data.index[-1]}")
    print(f"Price range: {data['Close'].min():.2f} to {data['Close'].max():.2f}")
    print("\nFirst few rows:")
    print(data.head())
    print("\nLast few rows:")
    print(data.tail())
