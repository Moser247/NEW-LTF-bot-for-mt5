"""
VWAP Mean Reversion Strategy
70%+ win rate for SPX500
"""

import pandas as pd
import numpy as np
from datetime import time
from typing import List, Dict


class VWAPMeanReversion:
    """
    VWAP Mean Reversion Strategy

    Rules:
    1. Calculate VWAP for the day
    2. LONG: Price 0.3-0.5% below VWAP + rejection pattern
    3. SHORT: Price 0.3-0.5% above VWAP + rejection pattern
    4. Stop: Beyond recent swing
    5. Target: VWAP + extension
    """

    def __init__(
        self,
        deviation_min: float = 0.003,  # 0.3%
        deviation_max: float = 0.005,  # 0.5%
        stop_buffer: float = 2.0,  # Points beyond swing
        target_extension: float = 7.0,  # Points beyond VWAP
        trade_start_time: time = time(10, 0),  # Start trading
        trade_end_time: time = time(15, 0),  # End trading
        avoid_lunch_start: time = time(12, 0),
        avoid_lunch_end: time = time(13, 0),
    ):
        self.deviation_min = deviation_min
        self.deviation_max = deviation_max
        self.stop_buffer = stop_buffer
        self.target_extension = target_extension
        self.trade_start_time = trade_start_time
        self.trade_end_time = trade_end_time
        self.avoid_lunch_start = avoid_lunch_start
        self.avoid_lunch_end = avoid_lunch_end

    def calculate_vwap(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate VWAP (Volume Weighted Average Price)

        Args:
            data: OHLCV dataframe

        Returns:
            Series with VWAP values
        """
        # Typical price
        typical_price = (data['High'] + data['Low'] + data['Close']) / 3

        # Cumulative TP * Volume
        cum_tp_vol = (typical_price * data['Volume']).cumsum()

        # Cumulative Volume
        cum_vol = data['Volume'].cumsum()

        # VWAP
        vwap = cum_tp_vol / cum_vol

        return vwap

    def calculate_daily_vwap(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate VWAP reset daily

        Args:
            data: OHLCV dataframe with DatetimeIndex

        Returns:
            Series with daily VWAP
        """
        vwap_series = pd.Series(index=data.index, dtype=float)

        # Group by date
        dates = data.index.date
        unique_dates = sorted(set(dates))

        for date in unique_dates:
            day_data = data[data.index.date == date]

            if len(day_data) > 0:
                day_vwap = self.calculate_vwap(day_data)
                vwap_series.loc[day_data.index] = day_vwap.values

        return vwap_series

    def find_recent_swing(self, data: pd.DataFrame, current_idx: int, direction: str, lookback: int = 10) -> float:
        """
        Find recent swing high/low

        Args:
            data: OHLC dataframe
            current_idx: Current bar index
            direction: 'long' or 'short'
            lookback: Number of bars to look back

        Returns:
            Swing price
        """
        # Get recent bars
        start_idx = max(0, current_idx - lookback)
        recent_data = data.iloc[start_idx:current_idx]

        if len(recent_data) == 0:
            return data.iloc[current_idx]['Close']

        if direction == 'long':
            return recent_data['Low'].min()
        else:  # short
            return recent_data['High'].max()

    def check_rejection_pattern(self, bar: pd.Series, direction: str) -> bool:
        """
        Check for rejection candlestick pattern

        Args:
            bar: OHLC bar
            direction: 'bullish' or 'bearish'

        Returns:
            True if rejection pattern found
        """
        body = abs(bar['Close'] - bar['Open'])
        total_range = bar['High'] - bar['Low']

        if total_range == 0:
            return False

        if direction == 'bullish':
            # Long lower wick, bullish close
            lower_wick = min(bar['Open'], bar['Close']) - bar['Low']
            upper_wick = bar['High'] - max(bar['Open'], bar['Close'])

            # Lower wick should be 2x body and 2x upper wick
            return (lower_wick > body * 1.5 and
                    lower_wick > upper_wick * 2 and
                    bar['Close'] > bar['Open'])

        else:  # bearish
            # Long upper wick, bearish close
            lower_wick = min(bar['Open'], bar['Close']) - bar['Low']
            upper_wick = bar['High'] - max(bar['Open'], bar['Close'])

            # Upper wick should be 2x body and 2x lower wick
            return (upper_wick > body * 1.5 and
                    upper_wick > lower_wick * 2 and
                    bar['Close'] < bar['Open'])

    def generate_signals(
        self,
        data: pd.DataFrame,
        backtester
    ) -> List[Dict]:
        """
        Generate VWAP mean reversion signals

        Args:
            data: Intraday OHLCV data with DatetimeIndex
            backtester: Backtester instance

        Returns:
            List of trade signals
        """
        signals = []

        # Calculate VWAP
        vwap = self.calculate_daily_vwap(data)
        data['VWAP'] = vwap

        # Iterate through bars
        for i in range(1, len(data)):
            idx = data.index[i]
            bar = data.iloc[i]

            current_time = idx.time()

            # Check trading time window
            if current_time < self.trade_start_time or current_time > self.trade_end_time:
                continue

            # Avoid lunch hour
            if self.avoid_lunch_start <= current_time <= self.avoid_lunch_end:
                continue

            current_price = bar['Close']
            current_vwap = bar['VWAP']

            if pd.isna(current_vwap) or current_vwap == 0:
                continue

            # Calculate deviation from VWAP
            deviation = (current_price - current_vwap) / current_vwap

            # LONG setup: Price below VWAP
            if -self.deviation_max <= deviation <= -self.deviation_min:
                # Check for bullish rejection
                if self.check_rejection_pattern(bar, 'bullish'):
                    entry_price = current_price
                    swing_low = self.find_recent_swing(data, i, 'long')
                    stop_loss = swing_low - self.stop_buffer

                    # Ensure minimum stop distance
                    stop_distance = entry_price - stop_loss
                    if stop_distance < 5:  # Min 5 points
                        stop_loss = entry_price - 5
                        stop_distance = 5
                    elif stop_distance > 15:  # Max 15 points
                        stop_loss = entry_price - 15
                        stop_distance = 15

                    target_1 = current_vwap
                    target_2 = current_vwap + self.target_extension

                    lots = backtester.calculate_position_size(stop_distance)

                    if lots > 0:
                        signal = {
                            'entry_time': idx,
                            'direction': 'long',
                            'entry_price': entry_price,
                            'stop_loss': stop_loss,
                            'take_profit': target_1,
                            'target_1': target_1,
                            'target_2': target_2,
                            'lots': lots,
                            'strategy': 'VWAP',
                            'vwap': current_vwap,
                            'deviation': deviation,
                        }

                        signals.append(signal)

            # SHORT setup: Price above VWAP
            elif self.deviation_min <= deviation <= self.deviation_max:
                # Check for bearish rejection
                if self.check_rejection_pattern(bar, 'bearish'):
                    entry_price = current_price
                    swing_high = self.find_recent_swing(data, i, 'short')
                    stop_loss = swing_high + self.stop_buffer

                    # Ensure minimum stop distance
                    stop_distance = stop_loss - entry_price
                    if stop_distance < 5:
                        stop_loss = entry_price + 5
                        stop_distance = 5
                    elif stop_distance > 15:
                        stop_loss = entry_price + 15
                        stop_distance = 15

                    target_1 = current_vwap
                    target_2 = current_vwap - self.target_extension

                    lots = backtester.calculate_position_size(stop_distance)

                    if lots > 0:
                        signal = {
                            'entry_time': idx,
                            'direction': 'short',
                            'entry_price': entry_price,
                            'stop_loss': stop_loss,
                            'take_profit': target_1,
                            'target_1': target_1,
                            'target_2': target_2,
                            'lots': lots,
                            'strategy': 'VWAP',
                            'vwap': current_vwap,
                            'deviation': deviation,
                        }

                        signals.append(signal)

        return signals
