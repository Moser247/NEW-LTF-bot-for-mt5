"""
Download historical data for backtesting
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import os


class DataDownloader:
    """Download and prepare historical data for backtesting"""

    @staticmethod
    def download_sp500(
        start_date: str = None,
        end_date: str = None,
        interval: str = '5m',  # 5-minute bars
        save_to_file: bool = True,
        filename: str = None
    ) -> pd.DataFrame:
        """
        Download S&P 500 data using yfinance

        Args:
            start_date: Start date (YYYY-MM-DD) or None for last 60 days
            end_date: End date (YYYY-MM-DD) or None for today
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
            save_to_file: Save to CSV file
            filename: Output filename

        Returns:
            DataFrame with OHLCV data
        """
        # Default to last 60 days if not specified
        if end_date is None:
            end_date = datetime.now()
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        if start_date is None:
            # yfinance limits intraday data to last 60 days
            start_date = end_date - timedelta(days=60)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')

        print(f"Downloading S&P 500 data from {start_date.date()} to {end_date.date()}...")
        print(f"Interval: {interval}")

        # Download data (SPY is more liquid than ^GSPC for intraday)
        ticker = 'SPY'  # S&P 500 ETF
        data = yf.download(
            ticker,
            start=start_date,
            end=end_date,
            interval=interval,
            progress=True
        )

        if len(data) == 0:
            print("❌ No data downloaded!")
            return None

        # Clean data
        data = data.dropna()

        # Ensure timezone-aware (convert to EST if needed)
        if data.index.tz is None:
            data.index = data.index.tz_localize('America/New_York')
        else:
            data.index = data.index.tz_convert('America/New_York')

        # Convert SPY to SPX500 approximate values
        # SPY = SPX / 10 approximately
        # So multiply by 10 for SPX500 values
        data['Open'] = data['Open'] * 10
        data['High'] = data['High'] * 10
        data['Low'] = data['Low'] * 10
        data['Close'] = data['Close'] * 10

        print(f"✅ Downloaded {len(data)} bars")
        print(f"   Date range: {data.index[0]} to {data.index[-1]}")
        print(f"   Price range: {data['Close'].min():.2f} to {data['Close'].max():.2f}")

        # Save to file
        if save_to_file:
            if filename is None:
                filename = f"data/spx500_{interval}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"

            # Create data directory if it doesn't exist
            os.makedirs('data', exist_ok=True)

            data.to_csv(filename)
            print(f"💾 Saved to {filename}")

        return data

    @staticmethod
    def load_from_csv(filename: str) -> pd.DataFrame:
        """
        Load data from CSV file

        Args:
            filename: Path to CSV file

        Returns:
            DataFrame with OHLCV data
        """
        data = pd.read_csv(filename, index_col=0, parse_dates=True)

        # Ensure timezone-aware
        if data.index.tz is None:
            data.index = data.index.tz_localize('America/New_York')

        return data

    @staticmethod
    def prepare_for_backtesting(data: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare data for backtesting (additional cleaning)

        Args:
            data: Raw OHLCV data

        Returns:
            Cleaned data ready for backtesting
        """
        # Remove any NaN values
        data = data.dropna()

        # Ensure required columns exist
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        # Filter to regular trading hours (9:30 AM - 4:00 PM EST)
        data = data.between_time('09:30', '16:00')

        # Remove outliers (price jumps > 5%)
        data['price_change_pct'] = data['Close'].pct_change()
        data = data[abs(data['price_change_pct']) < 0.05]  # Remove >5% moves
        data = data.drop('price_change_pct', axis=1)

        return data


if __name__ == "__main__":
    # Example usage
    downloader = DataDownloader()

    # Download last 60 days of 5-minute data
    data = downloader.download_sp500(
        interval='5m',
        save_to_file=True
    )

    print("\nFirst few rows:")
    print(data.head())

    print("\nLast few rows:")
    print(data.tail())
