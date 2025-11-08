"""
MT5 DATA DOWNLOADER
Pull real historical bar data directly from MetaTrader 5

REQUIREMENTS:
1. MetaTrader 5 terminal installed on your computer
2. MT5 account (demo or live) - OctaFX, Blue Guardian, etc.
3. MT5 terminal must be running (can minimize it)

SETUP:
1. Install MT5: https://www.metatrader5.com/en/download
2. Install Python package:
   pip install MetaTrader5
3. Login to your MT5 account in the terminal
4. Run this script while MT5 is open

USAGE:
   python download_mt5_data.py

This will download real SPX500 data from your broker
"""

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import sys
import pytz

def initialize_mt5():
    """
    Initialize connection to MT5 terminal

    Returns:
        bool: True if successful, False otherwise
    """
    print("=" * 80)
    print("MT5 DATA DOWNLOADER")
    print("=" * 80)

    # Initialize MT5 connection
    if not mt5.initialize():
        print("\n❌ Failed to initialize MT5")
        print(f"   Error: {mt5.last_error()}")
        print("\nTroubleshooting:")
        print("1. Is MetaTrader 5 installed?")
        print("2. Is MT5 terminal running?")
        print("3. Are you logged into an account?")
        print("4. Try: pip install --upgrade MetaTrader5")
        return False

    print("✅ Connected to MT5")

    # Get account info
    account_info = mt5.account_info()
    if account_info is not None:
        print(f"   Account: {account_info.login}")
        print(f"   Server: {account_info.server}")
        print(f"   Balance: ${account_info.balance:,.2f}")
        print(f"   Leverage: 1:{account_info.leverage}")

    return True


def get_available_symbols():
    """
    List available symbols in MT5

    Returns:
        list: Available symbol names
    """
    symbols = mt5.symbols_get()
    if symbols is None or len(symbols) == 0:
        print("\n⚠️  No symbols found")
        return []

    symbol_names = [s.name for s in symbols]
    return symbol_names


def find_spx_symbol(symbols):
    """
    Find the SPX500 symbol name (varies by broker)

    Common names:
    - US500, US500.cash, US500m, US500.m
    - SPX500, SPX500.cash, SPX500m
    - SP500, SP500.cash
    - USA500, USA500.cash

    Returns:
        str: Symbol name or None
    """
    # Possible SPX500 symbol names
    possible_names = [
        'US500', 'US500.cash', 'US500m', 'US500.m',
        'SPX500', 'SPX500.cash', 'SPX500m',
        'SP500', 'SP500.cash', 'SP500m',
        'USA500', 'USA500.cash', 'USA500m',
        'US500Cash', 'SPX500Cash',
        'USTEC', 'NAS100'  # Some brokers label indices differently
    ]

    # Check exact matches first
    for name in possible_names:
        if name in symbols:
            return name

    # Check partial matches
    for symbol in symbols:
        if '500' in symbol.upper() and 'US' in symbol.upper():
            return symbol
        if 'SPX' in symbol.upper() and '500' in symbol.upper():
            return symbol
        if 'SP500' in symbol.upper():
            return symbol

    return None


def download_bars(symbol, months=6, timeframe=mt5.TIMEFRAME_M1):
    """
    Download historical bars from MT5

    Args:
        symbol: Symbol name (e.g., 'US500')
        months: Number of months to download
        timeframe: MT5 timeframe constant

    Returns:
        DataFrame with OHLCV data
    """
    print(f"\n📊 Downloading data...")
    print(f"   Symbol: {symbol}")
    print(f"   Timeframe: 1-minute bars")
    print(f"   Period: {months} months")

    # Calculate date range
    timezone = pytz.timezone("Etc/UTC")
    utc_to = datetime.now(timezone)
    utc_from = utc_to - timedelta(days=months * 30)

    print(f"   From: {utc_from.strftime('%Y-%m-%d')}")
    print(f"   To: {utc_to.strftime('%Y-%m-%d')}")

    # Get bars
    print(f"\n⬇️  Downloading... (this may take 30-60 seconds)")

    try:
        bars = mt5.copy_rates_range(symbol, timeframe, utc_from, utc_to)

        if bars is None or len(bars) == 0:
            print(f"\n❌ No data returned")
            print(f"   Error: {mt5.last_error()}")
            print("\nPossible issues:")
            print(f"1. Symbol '{symbol}' may not have historical data")
            print("2. Date range may be too far back")
            print("3. Broker may not provide 1-minute data for this period")
            print("\nTry:")
            print("- Shorter period (3 months instead of 6)")
            print("- Different timeframe (5-minute: mt5.TIMEFRAME_M5)")
            return None

        print(f"\n✅ Downloaded {len(bars):,} bars")

        # Convert to DataFrame
        data = pd.DataFrame(bars)

        # Convert time to datetime
        data['time'] = pd.to_datetime(data['time'], unit='s')

        # Set timezone to UTC, then convert to Eastern
        data['time'] = data['time'].dt.tz_localize('UTC').dt.tz_convert('America/New_York')

        # Set time as index
        data.set_index('time', inplace=True)

        # Rename columns to match our format
        data.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'tick_volume': 'Volume'
        }, inplace=True)

        # Keep only OHLCV columns
        data = data[['Open', 'High', 'Low', 'Close', 'Volume']]

        # Filter to regular trading hours (9:30 AM - 4:00 PM ET)
        print(f"\n🕐 Filtering to regular trading hours (9:30-16:00 ET)...")
        data_trading_hours = data.between_time('09:30', '16:00')

        if len(data_trading_hours) == 0:
            print(f"\n⚠️  Warning: No data in trading hours (9:30-16:00 ET)")
            print("   This might be because:")
            print("   1. SPX500 data includes extended hours (normal)")
            print("   2. Timezone conversion issue")
            print("\n   Saving ALL data without time filter...")
            data_trading_hours = data
        else:
            print(f"   Before filter: {len(data):,} bars")
            print(f"   After filter: {len(data_trading_hours):,} bars")

        # Summary
        print(f"\n📈 Data Summary:")
        print(f"   Date range: {data_trading_hours.index[0]} to {data_trading_hours.index[-1]}")
        print(f"   Trading days: {len(data_trading_hours.index.normalize().unique())}")
        print(f"   Total bars: {len(data_trading_hours):,}")
        print(f"   Price range: ${data_trading_hours['Low'].min():.2f} to ${data_trading_hours['High'].max():.2f}")
        print(f"   Avg volume/bar: {data_trading_hours['Volume'].mean():,.0f}")

        return data_trading_hours

    except Exception as e:
        print(f"\n❌ Error downloading data: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """
    Main function to download MT5 data
    """

    # Initialize MT5
    if not initialize_mt5():
        return

    try:
        # Get available symbols
        print(f"\n🔍 Searching for SPX500 symbol...")
        symbols = get_available_symbols()

        if len(symbols) == 0:
            print("❌ No symbols available")
            return

        print(f"   Found {len(symbols)} symbols in total")

        # Find SPX500 symbol
        spx_symbol = find_spx_symbol(symbols)

        if spx_symbol is None:
            print("\n❌ Could not find SPX500 symbol automatically")
            print("\nAvailable symbols containing '500':")
            spx_like = [s for s in symbols if '500' in s.upper()]
            if spx_like:
                for s in spx_like[:10]:
                    print(f"   - {s}")
                print("\nPlease edit this script and set:")
                print(f"   spx_symbol = '{spx_like[0]}'  # or whichever is correct")
            else:
                print("\nNo symbols found with '500' in the name")
                print("Your broker might use a different name")
                print("\nFirst 20 symbols:")
                for s in symbols[:20]:
                    print(f"   - {s}")
            return

        print(f"✅ Found SPX500 symbol: {spx_symbol}")

        # Get symbol info
        symbol_info = mt5.symbol_info(spx_symbol)
        if symbol_info is not None:
            print(f"\n📋 Symbol Info:")
            print(f"   Full name: {symbol_info.description}")
            print(f"   Point: {symbol_info.point}")
            print(f"   Spread: {symbol_info.spread}")
            print(f"   Contract size: {symbol_info.trade_contract_size}")

        # Enable symbol (in case it's not in Market Watch)
        if not mt5.symbol_select(spx_symbol, True):
            print(f"\n⚠️  Warning: Could not enable symbol {spx_symbol}")

        # Download data
        data = download_bars(spx_symbol, months=6, timeframe=mt5.TIMEFRAME_M1)

        if data is None:
            return

        # Save to CSV
        output_file = 'data/spx500_mt5_real.csv'
        data.to_csv(output_file)
        print(f"\n💾 Saved to: {output_file}")

        # Success message
        print("\n" + "=" * 80)
        print("✅ SUCCESS - Real MT5 data downloaded")
        print("=" * 80)
        print("\nThis is REAL broker data from your MT5 account")
        print("Same prices and spreads you'll get when trading live")

        print("\nNext steps:")
        print("1. Run backtest: python run_backtest_on_real_data.py")
        print("   (Edit script to load 'data/spx500_mt5_real.csv')")
        print("2. Compare to synthetic results")
        print("3. See if 60-75% win rate holds on YOUR broker's data")

        # Show sample data
        print("\n📊 First 10 bars:")
        print(data.head(10))
        print("\n📊 Last 10 bars:")
        print(data.tail(10))

    finally:
        # Shutdown MT5 connection
        mt5.shutdown()
        print("\n👋 Disconnected from MT5")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("METATRADER 5 DATA DOWNLOADER")
    print("=" * 80)
    print("\nPREREQUISITES:")
    print("1. ✅ MetaTrader 5 installed")
    print("2. ✅ MT5 terminal running")
    print("3. ✅ Logged into account (demo or live)")
    print("4. ✅ pip install MetaTrader5")
    print("\nIf you haven't done these, press Ctrl+C to exit and set up first")
    print("Otherwise, continuing in 3 seconds...")

    try:
        import time
        time.sleep(3)
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        print("\nSetup instructions:")
        print("1. Install MT5: https://www.metatrader5.com/en/download")
        print("2. Open MT5 and login to your account")
        print("3. Install package: pip install MetaTrader5")
        print("4. Run: python download_mt5_data.py")
    except ImportError as e:
        print("\n" + "=" * 80)
        print("❌ ERROR: MetaTrader5 package not installed")
        print("=" * 80)
        print("\nPlease install it:")
        print("   pip install MetaTrader5")
        print("\nIf installation fails, make sure:")
        print("- You're using Python 3.8-3.11 (3.12+ may not work)")
        print("- You're on Windows (MT5 Python API only works on Windows)")
        print("\nOn Mac/Linux:")
        print("- Use Alpaca downloader instead: python download_alpaca_data.py")
        print("- Or export data from MT5 manually and convert")
