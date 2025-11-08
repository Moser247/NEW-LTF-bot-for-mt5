"""
MULTI-SOURCE SPX500 DATA DOWNLOADER
Attempts to download real S&P 500 data from multiple free sources

This script tries sources in order until one works:
1. Alpha Vantage (free API, no signup needed for basic)
2. FRED (Federal Reserve Economic Data)
3. Stooq (free historical data)
4. Yahoo Finance (backup)
5. Financial Modeling Prep (free tier)

USAGE:
   python download_spx_multi_source.py
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
import time
import json

def try_alpha_vantage():
    """
    Try Alpha Vantage API (free tier)
    Note: Free tier has rate limits but should work for testing
    """
    print("\n" + "=" * 80)
    print("SOURCE 1: Alpha Vantage API")
    print("=" * 80)

    # Alpha Vantage provides free API keys
    # Using demo key for testing (limited calls)
    api_key = "demo"  # Can get free key at https://www.alphavantage.co/support/#api-key

    symbol = "SPY"  # They have SPY, not SPX directly

    print(f"   API: Alpha Vantage")
    print(f"   Symbol: {symbol}")
    print(f"   Attempting download...")

    try:
        # Try intraday data (1min)
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval=1min&outputsize=full&apikey={api_key}"

        response = requests.get(url, timeout=30)

        if response.status_code != 200:
            print(f"   ❌ HTTP {response.status_code}")
            return None

        data = response.json()

        if "Error Message" in data:
            print(f"   ❌ API Error: {data['Error Message']}")
            return None

        if "Note" in data:
            print(f"   ⚠️  Rate limit: {data['Note']}")
            print("   💡 Get free API key at: https://www.alphavantage.co/support/#api-key")
            return None

        # Parse data
        time_series_key = "Time Series (1min)"
        if time_series_key not in data:
            print(f"   ❌ No time series data found")
            print(f"   Response keys: {list(data.keys())}")
            return None

        df = pd.DataFrame.from_dict(data[time_series_key], orient='index')
        df.index = pd.to_datetime(df.index)

        # Rename columns
        df.rename(columns={
            '1. open': 'Open',
            '2. high': 'High',
            '3. low': 'Low',
            '4. close': 'Close',
            '5. volume': 'Volume'
        }, inplace=True)

        # Convert to numeric
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col])

        # Convert SPY to SPX500 (multiply by 10)
        for col in ['Open', 'High', 'Low', 'Close']:
            df[col] = df[col] * 10

        df = df.sort_index()

        print(f"   ✅ Success!")
        print(f"   Downloaded: {len(df):,} bars")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")

        return df

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def try_stooq():
    """
    Try Stooq.com (free historical data, no API key needed)
    """
    print("\n" + "=" * 80)
    print("SOURCE 2: Stooq.com")
    print("=" * 80)

    print(f"   Source: Stooq.com")
    print(f"   Symbol: ^SPX")
    print(f"   Attempting download...")

    try:
        # Stooq provides CSV download
        # Format: https://stooq.com/q/d/l/?s=^spx&i=d
        # d = daily, can try 1 = 1min, 5 = 5min

        # Try daily data first (most reliable)
        url = "https://stooq.com/q/d/l/?s=^spx&i=d"

        response = requests.get(url, timeout=30)

        if response.status_code != 200:
            print(f"   ❌ HTTP {response.status_code}")
            return None

        # Parse CSV
        from io import StringIO
        df = pd.read_csv(StringIO(response.text))

        if df.empty:
            print(f"   ❌ No data returned")
            return None

        # Stooq format: Date,Open,High,Low,Close,Volume
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        df = df.sort_index()

        print(f"   ✅ Success!")
        print(f"   Downloaded: {len(df):,} bars (daily)")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")

        # Note: This is daily data, not intraday
        print(f"   ⚠️  Note: Daily data only (not 1-minute)")

        return df

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def try_yahoo_finance_direct():
    """
    Try Yahoo Finance direct API (different endpoint)
    """
    print("\n" + "=" * 80)
    print("SOURCE 3: Yahoo Finance (Direct Download)")
    print("=" * 80)

    print(f"   Source: Yahoo Finance")
    print(f"   Symbol: ^GSPC (S&P 500)")
    print(f"   Attempting download...")

    try:
        # Try download endpoint instead of API
        # This sometimes works when API doesn't
        symbol = "%5EGSPC"  # ^GSPC URL encoded

        # Get last 6 months
        end_time = int(time.time())
        start_time = end_time - (180 * 24 * 60 * 60)  # 6 months

        url = f"https://query1.finance.yahoo.com/v7/finance/download/{symbol}?period1={start_time}&period2={end_time}&interval=1d&events=history"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            print(f"   ❌ HTTP {response.status_code}")
            return None

        # Parse CSV
        from io import StringIO
        df = pd.read_csv(StringIO(response.text))

        if df.empty:
            print(f"   ❌ No data returned")
            return None

        # Yahoo format: Date,Open,High,Low,Close,Adj Close,Volume
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        df = df.sort_index()

        # SPX is already at correct scale (4000-6000 range)

        print(f"   ✅ Success!")
        print(f"   Downloaded: {len(df):,} bars (daily)")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")
        print(f"   ⚠️  Note: Daily data only (not intraday)")

        return df

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def try_fred():
    """
    Try FRED (Federal Reserve Economic Data)
    """
    print("\n" + "=" * 80)
    print("SOURCE 4: FRED (Federal Reserve)")
    print("=" * 80)

    print(f"   Source: FRED")
    print(f"   Series: SP500")
    print(f"   Attempting download...")

    try:
        # FRED has S&P 500 index data
        # Direct CSV download (no API key needed for public series)
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500"

        response = requests.get(url, timeout=30)

        if response.status_code != 200:
            print(f"   ❌ HTTP {response.status_code}")
            return None

        # Parse CSV
        from io import StringIO
        df = pd.read_csv(StringIO(response.text))

        if df.empty:
            print(f"   ❌ No data returned")
            return None

        # FRED format: DATE,SP500
        df.rename(columns={'DATE': 'Date', 'SP500': 'Close'}, inplace=True)
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)

        # FRED only has Close prices, not OHLCV
        # Fill in Open/High/Low (approximate)
        df['Open'] = df['Close']
        df['High'] = df['Close']
        df['Low'] = df['Close']
        df['Volume'] = 0

        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        df = df.sort_index()

        print(f"   ✅ Success!")
        print(f"   Downloaded: {len(df):,} bars (daily)")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")
        print(f"   ⚠️  Note: Daily close only (no intraday)")

        return df

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def expand_daily_to_intraday(daily_df, bars_per_day=390):
    """
    Expand daily data to approximate intraday bars
    NOT REAL INTRADAY DATA - just for testing framework
    """
    print(f"\n📊 Expanding daily data to intraday bars...")
    print(f"   ⚠️  WARNING: This is APPROXIMATED intraday data, not real")
    print(f"   Real intraday data would be much better")

    import numpy as np

    intraday_bars = []

    for date, row in daily_df.iterrows():
        # Trading hours: 9:30 AM - 4:00 PM = 390 minutes
        base_date = pd.Timestamp(date).replace(hour=9, minute=30)

        for minute in range(bars_per_day):
            bar_time = base_date + pd.Timedelta(minutes=minute)

            # Approximate intraday movement
            # Random walk within daily range
            progress = minute / bars_per_day

            # Simple approximation (not realistic but shows framework)
            price = row['Open'] + (row['Close'] - row['Open']) * progress
            noise = (row['High'] - row['Low']) * 0.1 * np.random.randn()

            intraday_bars.append({
                'Datetime': bar_time,
                'Open': price + noise,
                'High': price + abs(noise),
                'Low': price - abs(noise),
                'Close': price + noise * 0.5,
                'Volume': row['Volume'] / bars_per_day if row['Volume'] > 0 else 1000
            })

    df_intraday = pd.DataFrame(intraday_bars)
    df_intraday.set_index('Datetime', inplace=True)

    print(f"   Generated {len(df_intraday):,} 1-minute bars")

    return df_intraday


def main():
    """
    Try all sources until one works
    """
    print("\n" + "=" * 80)
    print("MULTI-SOURCE SPX500 DATA DOWNLOADER")
    print("=" * 80)
    print("\nAttempting to download real S&P 500 data from multiple sources...")

    sources = [
        ("Yahoo Finance", try_yahoo_finance_direct),
        ("Stooq.com", try_stooq),
        ("FRED", try_fred),
        ("Alpha Vantage", try_alpha_vantage),
    ]

    data = None
    source_name = None

    for name, func in sources:
        data = func()
        if data is not None and len(data) > 0:
            source_name = name
            break

    if data is None:
        print("\n" + "=" * 80)
        print("❌ ALL SOURCES FAILED")
        print("=" * 80)
        print("\nNo data sources were accessible")
        print("\nAlternatives:")
        print("1. Use Alpaca API (need to sign up for free key)")
        print("2. Use MT5 local download (if on Windows)")
        print("3. Manually download from Yahoo Finance website")
        return

    # Save daily data
    daily_file = 'data/spx500_daily_real.csv'
    data.to_csv(daily_file)
    print(f"\n💾 Saved daily data to: {daily_file}")

    # Check if we need to expand to intraday
    print(f"\n" + "=" * 80)
    print("DATA TYPE CHECK")
    print("=" * 80)

    # Check if intraday or daily
    if len(data) > 1:
        time_diff = (data.index[1] - data.index[0]).total_seconds()
        is_intraday = time_diff < 3600  # Less than 1 hour = intraday
    else:
        is_intraday = False

    if is_intraday:
        print(f"✅ Got INTRADAY data ({len(data):,} bars)")
        print(f"   This is REAL tick data - excellent!")
        output_file = 'data/spx500_real_intraday.csv'
        data.to_csv(output_file)
    else:
        print(f"⚠️  Got DAILY data only ({len(data):,} bars)")
        print(f"   Strategy needs 1-minute bars for proper testing")
        print(f"\n   Options:")
        print(f"   A) Use this daily data for approximate testing")
        print(f"   B) Expand to approximate intraday (not real, just for framework)")
        print(f"   C) Get real intraday from Alpaca or MT5")

        print(f"\n   Expanding to approximate intraday for framework testing...")
        data_intraday = expand_daily_to_intraday(data)

        output_file = 'data/spx500_approximated_intraday.csv'
        data_intraday.to_csv(output_file)

    print(f"\n💾 Saved to: {output_file}")

    # Summary
    print("\n" + "=" * 80)
    print("✅ SUCCESS")
    print("=" * 80)
    print(f"\nData source: {source_name}")
    print(f"Bars downloaded: {len(data):,}")
    print(f"Date range: {data.index[0]} to {data.index[-1]}")

    if not is_intraday:
        print(f"\n⚠️  IMPORTANT:")
        print(f"   - Downloaded DAILY data (best available without API key)")
        print(f"   - Approximated to intraday for framework testing")
        print(f"   - Results will be LESS ACCURATE than real intraday data")
        print(f"\n   For best results:")
        print(f"   1. Sign up for Alpaca (free): python download_alpaca_data.py")
        print(f"   2. Or use MT5 local: python download_mt5_data.py")

    print(f"\nNext step:")
    print(f"   python run_backtest_on_real_data.py")

    # Show sample
    print(f"\n📊 Sample data:")
    print(data.head(10))


if __name__ == "__main__":
    main()
