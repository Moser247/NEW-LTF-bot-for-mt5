"""
Generate realistic multi-timeframe SPX500 data for backtesting

Creates 1-minute bars that can be resampled to 5min and 15min
Includes realistic market microstructure:
- Intraday volatility patterns
- Trend periods and consolidations
- Volume patterns
- Gaps and momentum moves
- Order block formations
- Fair value gaps
- Liquidity sweeps
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
import pytz


def generate_realistic_spx500_1min(
    days=60,
    start_price=4500,
    seed=42
):
    """
    Generate realistic 1-minute SPX500 data

    Args:
        days: Number of trading days
        start_price: Starting price
        seed: Random seed for reproducibility

    Returns:
        DataFrame with 1-minute OHLCV data
    """
    np.random.seed(seed)

    data_list = []
    current_price = start_price

    # Trading hours: 9:30 AM - 4:00 PM EST (6.5 hours = 390 bars per day)
    start_time = time(9, 30)
    end_time = time(16, 0)

    start_date = datetime.now() - timedelta(days=days)
    est = pytz.timezone('America/New_York')

    # Generate daily trends (some days bullish, some bearish, some neutral)
    daily_trends = []
    for i in range(days):
        rand = np.random.random()
        if rand < 0.35:
            trend = 'bullish'
            daily_drift = np.random.uniform(0.003, 0.01)  # 0.3-1% up
        elif rand < 0.70:
            trend = 'bearish'
            daily_drift = np.random.uniform(-0.01, -0.003)  # 0.3-1% down
        else:
            trend = 'neutral'
            daily_drift = np.random.uniform(-0.002, 0.002)  # Choppy

        daily_trends.append((trend, daily_drift))

    for day_num in range(days):
        # Skip weekends
        current_date = start_date + timedelta(days=day_num)
        if current_date.weekday() >= 5:  # Saturday or Sunday
            continue

        trend, daily_drift = daily_trends[day_num]

        # Opening gap
        gap_percent = np.random.uniform(-0.003, 0.003)  # -0.3% to +0.3%
        day_open = current_price * (1 + gap_percent)
        current_price = day_open

        # Intraday volatility profile
        # Higher at open and close, lower during lunch
        minutes_in_day = []
        current_datetime = est.localize(datetime.combine(current_date.date(), start_time))

        for minute in range(390):  # 6.5 hours * 60 minutes
            # Time-based volatility
            if minute < 30:  # First 30 minutes - high volatility
                base_volatility = 0.0008
            elif minute < 90:  # Next hour - moderate
                base_volatility = 0.0005
            elif minute < 210:  # Lunch (90 min to 210 min) - low
                base_volatility = 0.0003
            elif minute < 330:  # Afternoon - moderate
                base_volatility = 0.0004
            else:  # Last hour - high
                base_volatility = 0.0006

            # Add trend drift
            drift = daily_drift / 390  # Distribute daily move across minutes

            # Random walk with drift
            price_change_percent = np.random.normal(drift, base_volatility)
            new_price = current_price * (1 + price_change_percent)

            # Generate OHLC for this minute
            volatility_points = base_volatility * current_price
            high = new_price + np.random.uniform(0, volatility_points * 2)
            low = new_price - np.random.uniform(0, volatility_points * 2)
            open_price = current_price
            close_price = new_price

            # Ensure OHLC logic is valid
            high = max(high, open_price, close_price)
            low = min(low, open_price, close_price)

            # Generate volume (higher at open and close)
            if minute < 30 or minute > 360:
                base_volume = np.random.uniform(800, 1500)
            elif 90 <= minute <= 210:  # Lunch
                base_volume = np.random.uniform(200, 500)
            else:
                base_volume = np.random.uniform(400, 800)

            # Add volume spikes during big moves
            if abs(price_change_percent) > base_volatility * 2:
                base_volume *= 2

            volume = int(base_volume * (1 + np.random.uniform(-0.3, 0.3)))

            minutes_in_day.append({
                'timestamp': current_datetime,
                'Open': round(open_price, 2),
                'High': round(high, 2),
                'Low': round(low, 2),
                'Close': round(close_price, 2),
                'Volume': volume
            })

            current_price = close_price
            current_datetime += timedelta(minutes=1)

            # Occasionally create momentum moves (for order blocks)
            if np.random.random() < 0.02:  # 2% chance per minute
                momentum_direction = 1 if np.random.random() < 0.5 else -1
                momentum_size = np.random.uniform(10, 25)  # 10-25 points

                # Create 3-5 strong candles in same direction
                num_candles = np.random.randint(3, 6)
                for _ in range(num_candles):
                    if minute >= 390:
                        break

                    move_per_candle = momentum_size / num_candles
                    new_price = current_price + (move_per_candle * momentum_direction)

                    high = max(current_price, new_price) + np.random.uniform(1, 3)
                    low = min(current_price, new_price) - np.random.uniform(1, 3)

                    minutes_in_day.append({
                        'timestamp': current_datetime,
                        'Open': round(current_price, 2),
                        'High': round(high, 2),
                        'Low': round(low, 2),
                        'Close': round(new_price, 2),
                        'Volume': int(base_volume * 3)  # High volume
                    })

                    current_price = new_price
                    current_datetime += timedelta(minutes=1)
                    minute += 1

        data_list.extend(minutes_in_day)

    # Create DataFrame
    df = pd.DataFrame(data_list)
    df.set_index('timestamp', inplace=True)

    print(f"Generated {len(df)} 1-minute bars ({len(df)/390:.0f} trading days)")
    print(f"Date range: {df.index[0].date()} to {df.index[-1].date()}")
    print(f"Price range: {df['Low'].min():.2f} to {df['High'].max():.2f}")

    return df


def resample_to_timeframe(data_1m, timeframe):
    """
    Resample 1-minute data to higher timeframe

    Args:
        data_1m: 1-minute DataFrame with OHLCV
        timeframe: '5T' for 5min, '15T' for 15min

    Returns:
        Resampled DataFrame
    """
    resampled = data_1m.resample(timeframe).agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()

    return resampled


def main():
    """Generate and save multi-timeframe data"""

    print("="*60)
    print("GENERATING REALISTIC SPX500 MULTI-TIMEFRAME DATA")
    print("="*60)

    # Generate 60 days of 1-minute data
    print("\n📊 Generating 1-minute data (60 trading days)...")
    data_1m = generate_realistic_spx500_1min(days=60, start_price=4500)

    # Save 1-minute data
    data_1m.to_csv('data/spx500_1min_data.csv')
    print(f"✅ Saved: data/spx500_1min_data.csv ({len(data_1m)} bars)")

    # Resample to 5-minute
    print("\n📊 Resampling to 5-minute...")
    data_5m = resample_to_timeframe(data_1m, '5T')
    data_5m.to_csv('data/spx500_5min_data.csv')
    print(f"✅ Saved: data/spx500_5min_data.csv ({len(data_5m)} bars)")

    # Resample to 15-minute
    print("\n📊 Resampling to 15-minute...")
    data_15m = resample_to_timeframe(data_1m, '15T')
    data_15m.to_csv('data/spx500_15min_data.csv')
    print(f"✅ Saved: data/spx500_15min_data.csv ({len(data_15m)} bars)")

    print("\n" + "="*60)
    print("✅ DATA GENERATION COMPLETE")
    print("="*60)

    # Display sample
    print("\n📋 Sample of 1-minute data (first 5 bars):")
    print(data_1m.head())


if __name__ == "__main__":
    main()
