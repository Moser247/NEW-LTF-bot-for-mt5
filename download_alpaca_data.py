"""
ALPACA MARKETS DATA DOWNLOADER
Download real SPY 1-minute historical data for backtesting

SETUP:
1. Sign up at https://alpaca.markets (free)
2. Get API keys from dashboard
3. Set environment variables or edit this file:
   export ALPACA_API_KEY="your_key_here"
   export ALPACA_SECRET_KEY="your_secret_here"

USAGE:
   python download_alpaca_data.py

This will download 6 months of real SPY 1-minute data
"""

import os
import sys
from datetime import datetime, timedelta
import pandas as pd

# Check if alpaca-py is installed
try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
except ImportError:
    print("=" * 80)
    print("ERROR: alpaca-py not installed")
    print("=" * 80)
    print("\nPlease install it:")
    print("   pip install alpaca-py")
    print("\nOr if that fails:")
    print("   pip install alpaca-trade-api")
    print()
    sys.exit(1)


def download_spy_data_alpaca(
    months: int = 6,
    api_key: str = None,
    secret_key: str = None
):
    """
    Download real SPY 1-minute data from Alpaca Markets

    Args:
        months: Number of months of historical data (default 6)
        api_key: Alpaca API key (or set ALPACA_API_KEY env var)
        secret_key: Alpaca secret key (or set ALPACA_SECRET_KEY env var)

    Returns:
        DataFrame with OHLCV data
    """

    print("=" * 80)
    print("DOWNLOADING REAL SPY DATA FROM ALPACA MARKETS")
    print("=" * 80)

    # Get API keys
    if api_key is None:
        api_key = os.getenv('ALPACA_API_KEY')
    if secret_key is None:
        secret_key = os.getenv('ALPACA_SECRET_KEY')

    if not api_key or not secret_key:
        print("\n❌ ERROR: API keys not found")
        print("\nPlease either:")
        print("1. Set environment variables:")
        print("   export ALPACA_API_KEY='your_key_here'")
        print("   export ALPACA_SECRET_KEY='your_secret_here'")
        print("\n2. Or edit this file and add your keys:")
        print("   api_key = 'your_key_here'")
        print("   secret_key = 'your_secret_here'")
        print("\nGet free API keys at: https://alpaca.markets")
        return None

    print(f"\n✅ API keys found")
    print(f"   API Key: {api_key[:8]}...")

    # Initialize client
    try:
        client = StockHistoricalDataClient(api_key, secret_key)
        print("✅ Connected to Alpaca Markets")
    except Exception as e:
        print(f"\n❌ Failed to connect: {e}")
        print("\nCheck your API keys are correct")
        return None

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=months * 30)

    print(f"\n📅 Requesting data:")
    print(f"   Symbol: SPY")
    print(f"   Timeframe: 1-minute bars")
    print(f"   Start: {start_date.strftime('%Y-%m-%d')}")
    print(f"   End: {end_date.strftime('%Y-%m-%d')}")
    print(f"   Duration: ~{months} months")

    # Request data
    print(f"\n⬇️  Downloading... (this may take 30-60 seconds)")

    try:
        request_params = StockBarsRequest(
            symbol_or_symbols=["SPY"],
            timeframe=TimeFrame.Minute,
            start=start_date,
            end=end_date
        )

        bars = client.get_stock_bars(request_params)

        # Convert to DataFrame
        data = bars.df

        if data.empty:
            print("\n❌ No data returned")
            print("   This might mean:")
            print("   - API keys are invalid")
            print("   - Free tier limits exceeded")
            print("   - Date range is invalid")
            return None

        print(f"\n✅ Downloaded {len(data):,} bars")

        # Process data
        print(f"\n📊 Processing data...")

        # Reset index to get timestamp column
        if isinstance(data.index, pd.MultiIndex):
            # Alpaca returns MultiIndex (symbol, timestamp)
            data = data.reset_index()
            data = data[data['symbol'] == 'SPY'].copy()
            data.set_index('timestamp', inplace=True)

        # Rename columns to match our format
        data.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        }, inplace=True)

        # Keep only OHLCV columns
        data = data[['Open', 'High', 'Low', 'Close', 'Volume']]

        # Convert SPY to SPX500 (multiply by 10)
        # SPY tracks S&P 500 at 1/10th the price
        for col in ['Open', 'High', 'Low', 'Close']:
            data[col] = data[col] * 10

        # Ensure timezone is Eastern
        if data.index.tz is None:
            data.index = data.index.tz_localize('America/New_York')
        else:
            data.index = data.index.tz_convert('America/New_York')

        # Filter to regular trading hours only (9:30 AM - 4:00 PM ET)
        data = data.between_time('09:30', '16:00')

        print(f"✅ Filtered to regular trading hours (9:30-16:00 ET)")
        print(f"   Result: {len(data):,} bars")

        # Summary statistics
        print(f"\n📈 Data Summary:")
        print(f"   Date range: {data.index[0]} to {data.index[-1]}")
        print(f"   Trading days: {len(data.index.normalize().unique())}")
        print(f"   Total bars: {len(data):,}")
        print(f"   Price range: ${data['Low'].min():.2f} to ${data['High'].max():.2f}")
        print(f"   Avg volume/bar: {data['Volume'].mean():,.0f}")

        # Save to CSV
        output_file = 'data/spy_real_alpaca.csv'
        data.to_csv(output_file)
        print(f"\n💾 Saved to: {output_file}")

        print("\n" + "=" * 80)
        print("✅ SUCCESS - Real market data downloaded")
        print("=" * 80)
        print("\nNext steps:")
        print("1. Run backtest: python run_backtest_on_real_data.py")
        print("2. Compare to synthetic results")
        print("3. See if 60-75% win rate holds on real data")

        return data

    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        print("\nPossible issues:")
        print("- API rate limit exceeded (wait 1 minute and try again)")
        print("- Invalid API keys")
        print("- Network connection problem")
        print("- Alpaca service temporarily down")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("ALPACA MARKETS DATA DOWNLOADER")
    print("=" * 80)

    # Option 1: Use environment variables
    data = download_spy_data_alpaca(months=6)

    # Option 2: Hardcode your API keys (NOT RECOMMENDED for security)
    # Uncomment and add your keys if you prefer:
    # data = download_spy_data_alpaca(
    #     months=6,
    #     api_key="YOUR_API_KEY_HERE",
    #     secret_key="YOUR_SECRET_KEY_HERE"
    # )

    if data is not None:
        print("\n📊 First 10 bars:")
        print(data.head(10))
        print("\n📊 Last 10 bars:")
        print(data.tail(10))

        print("\n✅ Data ready for backtesting!")
    else:
        print("\n❌ Failed to download data")
        print("\nTroubleshooting:")
        print("1. Sign up at https://alpaca.markets")
        print("2. Get your API keys from the dashboard")
        print("3. Set environment variables or edit this file")
        print("4. Run: python download_alpaca_data.py")
