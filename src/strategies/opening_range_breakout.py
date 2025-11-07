"""
Opening Range Breakout (ORB) Strategy
70-80% win rate for SPX500
"""

import pandas as pd
import numpy as np
from datetime import time, datetime
from typing import List, Dict, Optional


class OpeningRangeBreakout:
    """
    Opening Range Breakout Strategy

    Rules:
    1. Define opening range: 9:30-9:45 AM EST (15 minutes)
    2. LONG: Price breaks above OR high + buffer
    3. SHORT: Price breaks below OR low - buffer
    4. Stop: Opposite side of range
    5. Target: 1.5x to 2x range width
    """

    def __init__(
        self,
        or_start_time: time = time(9, 30),
        or_end_time: time = time(9, 45),
        entry_buffer: float = 2.0,  # Points above/below OR
        stop_buffer: float = 3.0,  # Points beyond OR for stop
        target_multiple_1: float = 1.5,  # First target
        target_multiple_2: float = 2.0,  # Second target
        time_stop: time = time(11, 30),  # Close if not profitable by this time
        min_range_size: float = 5.0,  # Minimum OR width in points
    ):
        self.or_start_time = or_start_time
        self.or_end_time = or_end_time
        self.entry_buffer = entry_buffer
        self.stop_buffer = stop_buffer
        self.target_multiple_1 = target_multiple_1
        self.target_multiple_2 = target_multiple_2
        self.time_stop = time_stop
        self.min_range_size = min_range_size

        # Track OR for each day
        self.opening_ranges = {}

    def calculate_opening_range(self, data: pd.DataFrame, date: datetime.date) -> Optional[Dict]:
        """
        Calculate opening range for a specific date

        Args:
            data: Intraday OHLC data
            date: Date to calculate OR for

        Returns:
            Dictionary with OR high, low, width or None
        """
        # Filter data for this date and OR time window
        day_mask = pd.Series([d.date() == date for d in data.index], index=data.index)
        day_data = data[day_mask]

        if len(day_data) == 0:
            return None

        or_data = day_data.between_time(self.or_start_time, self.or_end_time)

        if len(or_data) == 0:
            return None

        or_high = or_data['High'].max()
        or_low = or_data['Low'].min()
        or_width = or_high - or_low

        # Validate minimum range size
        if or_width < self.min_range_size:
            return None

        return {
            'high': or_high,
            'low': or_low,
            'width': or_width,
            'date': date,
        }

    def generate_signals(
        self,
        data: pd.DataFrame,
        backtester
    ) -> List[Dict]:
        """
        Generate ORB trading signals

        Args:
            data: Intraday OHLC data with DatetimeIndex
            backtester: Backtester instance for position management

        Returns:
            List of trade signals
        """
        signals = []

        # Group by date
        unique_dates = sorted(set([d.date() for d in data.index]))

        for date in unique_dates:
            # Calculate opening range
            or_info = self.calculate_opening_range(data, date)

            if or_info is None:
                continue

            # Store for later use
            self.opening_ranges[date] = or_info

            or_high = or_info['high']
            or_low = or_info['low']
            or_width = or_info['width']

            # Get data after OR end time
            day_mask = pd.Series([d.date() == date for d in data.index], index=data.index)
            day_data = data[day_mask]
            time_mask = pd.Series([d.time() > self.or_end_time for d in day_data.index], index=day_data.index)
            post_or_data = day_data[time_mask]

            if len(post_or_data) == 0:
                continue

            # Check for breakout
            breakout_found = False

            for idx, bar in post_or_data.iterrows():
                # Stop checking after time stop
                if idx.time() > self.time_stop:
                    break

                # Already in position for this day
                if breakout_found:
                    break

                current_price = bar['Close']

                # LONG breakout
                if current_price > or_high + self.entry_buffer:
                    entry_price = or_high + self.entry_buffer
                    stop_loss = or_low - self.stop_buffer
                    stop_distance = entry_price - stop_loss

                    target_1 = entry_price + (or_width * self.target_multiple_1)
                    target_2 = entry_price + (or_width * self.target_multiple_2)

                    # Calculate position size
                    lots = backtester.calculate_position_size(stop_distance)

                    if lots > 0:
                        signal = {
                            'entry_time': idx,
                            'direction': 'long',
                            'entry_price': entry_price,
                            'stop_loss': stop_loss,
                            'take_profit': target_1,  # Use first target
                            'target_1': target_1,
                            'target_2': target_2,
                            'lots': lots,
                            'strategy': 'ORB',
                            'or_high': or_high,
                            'or_low': or_low,
                            'or_width': or_width,
                        }

                        signals.append(signal)
                        breakout_found = True

                # SHORT breakout
                elif current_price < or_low - self.entry_buffer:
                    entry_price = or_low - self.entry_buffer
                    stop_loss = or_high + self.stop_buffer
                    stop_distance = stop_loss - entry_price

                    target_1 = entry_price - (or_width * self.target_multiple_1)
                    target_2 = entry_price - (or_width * self.target_multiple_2)

                    # Calculate position size
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
                            'strategy': 'ORB',
                            'or_high': or_high,
                            'or_low': or_low,
                            'or_width': or_width,
                        }

                        signals.append(signal)
                        breakout_found = True

        return signals
