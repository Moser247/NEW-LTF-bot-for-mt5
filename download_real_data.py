"""
Download REAL SPX500 data using yfinance

We'll download SPY (S&P 500 ETF) as a proxy for SPX500
and convert the prices appropriately
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

def download_real_spy_data(days=60):
    """
    Download real SPY data from Yahoo Finance

    Args:
        days: Number of days of history to download

    Returns:
        DataFrame with 1-minute OHLCV data
    """
    print("="*60)
    print("DOWNLOADING REAL MARKET DATA FROM YAHOO FINANCE")
    print("="*60)

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    print(f"\n📅 Requesting data:")
    print(f"   Symbol: SPY (S&P 500 ETF)")
    print(f"   Start: {start_date.date()}")
    print(f"   End: {end_date.date()}")
    print(f"   Interval: 1 minute")

    try:
        # Download 1-minute data
        print(f"\n⬇️  Downloading from Yahoo Finance...")

        # yfinance limits: 1m data only available for last 7 days
        # Let's get what we can
        ticker = yf.Ticker("SPY")

        # Try 1-minute data (last 7 days max)
        data_1m = ticker.history(period="7d", interval="1m")

        if len(data_1m) > 0:
            print(f"✅ Downloaded {len(data_1m)} 1-minute bars")
            print(f"   Date range: {data_1m.index[0]} to {data_1m.index[-1]}")

            # Convert SPY to SPX500 equivalent (SPY * 10 approximately)
            data_1m['Open'] = data_1m['Open'] * 10
            data_1m['High'] = data_1m['High'] * 10
            data_1m['Low'] = data_1m['Low'] * 10
            data_1m['Close'] = data_1m['Close'] * 10

            # Save
            data_1m.to_csv('data/spy_real_1min_data.csv')
            print(f"💾 Saved to: data/spy_real_1min_data.csv")

            return data_1m
        else:
            print("❌ No 1-minute data returned")

        # Try 5-minute data as backup
        print(f"\n⬇️  Trying 5-minute data (60 days)...")
        data_5m = ticker.history(period="60d", interval="5m")

        if len(data_5m) > 0:
            print(f"✅ Downloaded {len(data_5m)} 5-minute bars")
            print(f"   Date range: {data_5m.index[0]} to {data_5m.index[-1]}")

            # Convert SPY to SPX500
            data_5m['Open'] = data_5m['Open'] * 10
            data_5m['High'] = data_5m['High'] * 10
            data_5m['Low'] = data_5m['Low'] * 10
            data_5m['Close'] = data_5m['Close'] * 10

            # Save
            data_5m.to_csv('data/spy_real_5min_data.csv')
            print(f"💾 Saved to: data/spy_real_5min_data.csv")

            return data_5m
        else:
            print("❌ No 5-minute data returned")

        # Try daily data as last resort
        print(f"\n⬇️  Trying daily data (1 year)...")
        data_daily = ticker.history(period="1y", interval="1d")

        if len(data_daily) > 0:
            print(f"✅ Downloaded {len(data_daily)} daily bars")
            print(f"   Date range: {data_daily.index[0]} to {data_daily.index[-1]}")

            # Convert SPY to SPX500
            data_daily['Open'] = data_daily['Open'] * 10
            data_daily['High'] = data_daily['High'] * 10
            data_daily['Low'] = data_daily['Low'] * 10
            data_daily['Close'] = data_daily['Close'] * 10

            # Save
            data_daily.to_csv('data/spy_real_daily_data.csv')
            print(f"💾 Saved to: data/spy_real_daily_data.csv")

            print("\n⚠️  WARNING: Only daily data available")
            print("   Cannot run intraday strategy backtest on daily data")
            print("   This is a limitation of free Yahoo Finance data")

            return data_daily
        else:
            print("❌ No daily data returned")
            return None

    except Exception as e:
        print(f"\n❌ Error downloading data: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    data = download_real_spy_data()

    if data is not None:
        print("\n" + "="*60)
        print("DATA SUMMARY")
        print("="*60)
        print(f"\nShape: {data.shape}")
        print(f"\nColumns: {list(data.columns)}")
        print(f"\nFirst 5 rows:")
        print(data.head())
        print(f"\nLast 5 rows:")
        print(data.tail())
        print(f"\nPrice range: {data['Low'].min():.2f} to {data['High'].max():.2f}")
    else:
        print("\n❌ Failed to download any data")
