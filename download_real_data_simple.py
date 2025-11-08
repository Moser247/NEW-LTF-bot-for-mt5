"""
Download REAL SPY data using direct HTTP requests to Yahoo Finance
No yfinance dependency needed
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
import time

def download_spy_intraday_simple():
    """
    Download real SPY data using Yahoo Finance's API directly

    Yahoo Finance limits:
    - 1m data: Last 7 days only
    - 5m data: Last 60 days
    - We'll try both
    """
    print("="*60)
    print("DOWNLOADING REAL SPY DATA (Direct API)")
    print("="*60)

    # Try to download recent 1-minute data
    print("\n⬇️  Attempting to download 1-minute data (last 7 days)...")

    # Yahoo Finance API endpoint
    # We'll try the download endpoint which gives CSV
    end_time = int(time.time())
    start_time = end_time - (7 * 24 * 60 * 60)  # 7 days ago

    # Try CSV download endpoint
    url = f"https://query1.finance.yahoo.com/v7/finance/download/SPY?period1={start_time}&period2={end_time}&interval=1m&events=history"

    print(f"   URL: {url[:80]}...")

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            print(f"✅ Got response (status 200)")

            # Try to parse as CSV
            from io import StringIO
            data = pd.read_csv(StringIO(response.text))

            if len(data) > 0:
                print(f"✅ Downloaded {len(data)} rows")
                print(f"   Columns: {list(data.columns)}")

                # Convert timestamp to datetime if needed
                if 'Datetime' in data.columns:
                    data['Datetime'] = pd.to_datetime(data['Datetime'])
                    data.set_index('Datetime', inplace=True)
                elif 'Date' in data.columns:
                    data['Date'] = pd.to_datetime(data['Date'])
                    data.set_index('Date', inplace=True)

                # Convert SPY to SPX500 (multiply by 10)
                for col in ['Open', 'High', 'Low', 'Close']:
                    if col in data.columns:
                        data[col] = data[col] * 10

                print(f"\n📊 Data Summary:")
                print(f"   Shape: {data.shape}")
                print(f"   Date range: {data.index[0]} to {data.index[-1]}")
                print(f"   Price range: ${data['Low'].min():.2f} to ${data['High'].max():.2f}")

                # Save
                data.to_csv('data/spy_real_data.csv')
                print(f"\n💾 Saved to: data/spy_real_data.csv")

                return data
            else:
                print(f"❌ No data in response")
        else:
            print(f"❌ HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")

    # If 1m failed, try daily data which is more likely to work
    print("\n⬇️  Trying daily data (1 year)...")

    end_time = int(time.time())
    start_time = end_time - (365 * 24 * 60 * 60)  # 1 year ago

    url = f"https://query1.finance.yahoo.com/v7/finance/download/SPY?period1={start_time}&period2={end_time}&interval=1d&events=history"

    try:
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            print(f"✅ Got response (status 200)")

            from io import StringIO
            data = pd.read_csv(StringIO(response.text))

            if len(data) > 0:
                print(f"✅ Downloaded {len(data)} daily bars")

                # Set index
                data['Date'] = pd.to_datetime(data['Date'])
                data.set_index('Date', inplace=True)

                # Convert SPY to SPX500
                for col in ['Open', 'High', 'Low', 'Close']:
                    if col in data.columns:
                        data[col] = data[col] * 10

                print(f"\n📊 Data Summary:")
                print(f"   Shape: {data.shape}")
                print(f"   Date range: {data.index[0]} to {data.index[-1]}")
                print(f"   Price range: ${data['Low'].min():.2f} to ${data['High'].max():.2f}")

                # Save
                data.to_csv('data/spy_real_daily_data.csv')
                print(f"\n💾 Saved to: data/spy_real_daily_data.csv")

                print("\n⚠️  NOTE: This is DAILY data, not intraday")
                print("   Cannot run intraday strategy backtest on this")
                print("   Will need to test strategy differently or get intraday data from another source")

                return data

        else:
            print(f"❌ HTTP {response.status_code}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

    return None


if __name__ == "__main__":
    data = download_spy_intraday_simple()

    if data is not None:
        print("\n" + "="*60)
        print("✅ SUCCESS - Data downloaded")
        print("="*60)
        print("\nFirst 5 rows:")
        print(data.head())
        print("\nLast 5 rows:")
        print(data.tail())
    else:
        print("\n" + "="*60)
        print("❌ FAILED - Could not download data")
        print("="*60)
        print("\nREASON: Yahoo Finance API restrictions for free tier")
        print("ALTERNATIVE: I'll use the synthetic data already generated")
        print("             OR test with daily data using adapted strategy")
