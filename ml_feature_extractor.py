"""
ML FEATURE EXTRACTOR FOR INSTITUTIONAL ORDER FLOW

Extracts 40-50+ features from SPX500 1-minute data:
- Order Block features (presence, strength, distance, age, volume, direction)
- Fair Value Gap features (size, filled %, direction, age)
- Liquidity Sweep features (recent, type, volume, strength)
- Volume Profile features (POC, VAH, VAL, VWAP distance, nodes)
- Multi-timeframe trends (15m/5m/1m alignment)
- Confluence scores
- Time features (hour, minutes from open, day of week)
- Volatility features (ATR, volume ratios, range)
- Momentum features (RSI, EMA crossovers, price action)

Labels each setup: Was it profitable if traded? (1/0)
"""

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class InstitutionalFeatureExtractor:
    """
    Extract comprehensive institutional order flow features for ML training
    """

    def __init__(
        self,
        # Forward-looking profit labeling
        profit_target_percent: float = 0.005,  # 0.5% profit target
        stop_loss_percent: float = 0.003,      # 0.3% stop loss
        max_bars_forward: int = 30,            # Max 30 minutes to hit target

        # Order Block settings
        ob_lookback: int = 20,
        ob_min_move_percent: float = 0.005,

        # Fair Value Gap settings
        fvg_min_gap_points: float = 3.0,

        # Liquidity Sweep settings
        sweep_lookback: int = 20,
        sweep_min_points: float = 3.0,
        sweep_max_points: float = 10.0,

        # Volume Profile settings
        vp_value_area_percent: float = 0.70,

        # Technical indicators
        atr_period: int = 14,
        rsi_period: int = 14,
        ema_short: int = 9,
        ema_long: int = 21,
    ):
        self.profit_target_percent = profit_target_percent
        self.stop_loss_percent = stop_loss_percent
        self.max_bars_forward = max_bars_forward

        self.ob_lookback = ob_lookback
        self.ob_min_move_percent = ob_min_move_percent
        self.fvg_min_gap_points = fvg_min_gap_points
        self.sweep_lookback = sweep_lookback
        self.sweep_min_points = sweep_min_points
        self.sweep_max_points = sweep_max_points
        self.vp_value_area_percent = vp_value_area_percent

        self.atr_period = atr_period
        self.rsi_period = rsi_period
        self.ema_short = ema_short
        self.ema_long = ema_long

    def load_and_prepare_data(self, csv_path: str) -> pd.DataFrame:
        """Load 1-minute data and prepare timeframes"""
        print(f"Loading data from {csv_path}...")

        # Load 1-minute data
        df_1m = pd.read_csv(csv_path)
        df_1m['Datetime'] = pd.to_datetime(df_1m['Datetime'], utc=True)
        df_1m = df_1m.set_index('Datetime')
        df_1m.sort_index(inplace=True)
        df_1m.index = pd.DatetimeIndex(df_1m.index)

        print(f"Loaded {len(df_1m)} 1-minute bars")
        print(f"Date range: {df_1m.index[0]} to {df_1m.index[-1]}")

        # Create 5-minute and 15-minute resampled data
        df_5m = df_1m.resample('5min').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()

        df_15m = df_1m.resample('15min').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()

        print(f"Created {len(df_5m)} 5-minute bars")
        print(f"Created {len(df_15m)} 15-minute bars")

        return df_1m, df_5m, df_15m

    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate basic technical indicators"""
        df = df.copy()

        # ATR
        df['tr'] = np.maximum(
            df['High'] - df['Low'],
            np.maximum(
                abs(df['High'] - df['Close'].shift(1)),
                abs(df['Low'] - df['Close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(self.atr_period).mean()
        df['atr_ma'] = df['atr'].rolling(20).mean()
        df['atr_ratio'] = df['atr'] / df['atr_ma']

        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # EMAs
        df['ema_short'] = df['Close'].ewm(span=self.ema_short, adjust=False).mean()
        df['ema_long'] = df['Close'].ewm(span=self.ema_long, adjust=False).mean()
        df['ema_50'] = df['Close'].ewm(span=50, adjust=False).mean()

        # Price action
        df['body_size'] = abs(df['Close'] - df['Open'])
        df['upper_wick'] = df['High'] - np.maximum(df['Open'], df['Close'])
        df['lower_wick'] = np.minimum(df['Open'], df['Close']) - df['Low']
        df['range'] = df['High'] - df['Low']
        df['body_ratio'] = df['body_size'] / df['range'].replace(0, np.nan)

        # Volume
        df['volume_ma'] = df['Volume'].rolling(20).mean()
        df['volume_ratio'] = df['Volume'] / df['volume_ma']

        return df

    def detect_order_blocks(self, df: pd.DataFrame) -> List[Dict]:
        """Detect Order Blocks and return as list"""
        order_blocks = []

        for i in range(self.ob_lookback, len(df)):
            current_price = df['Close'].iloc[i]
            lookback_low = df['Low'].iloc[i-self.ob_lookback:i].min()
            lookback_high = df['High'].iloc[i-self.ob_lookback:i].max()

            # Bullish Order Block
            if current_price > lookback_high * (1 + self.ob_min_move_percent):
                for j in range(i-1, max(0, i-self.ob_lookback), -1):
                    if df['Close'].iloc[j] < df['Open'].iloc[j]:
                        move_size = (current_price - lookback_high) / lookback_high
                        volume_ratio = df['Volume'].iloc[i] / df['Volume'].iloc[i-self.ob_lookback:i].mean()
                        strength = min(1.0, (move_size * 100 + volume_ratio) / 3)

                        order_blocks.append({
                            'bar_index': i,
                            'timestamp': df.index[i],
                            'ob_timestamp': df.index[j],
                            'direction': 'bullish',
                            'ob_high': df['Open'].iloc[j],
                            'ob_low': df['Low'].iloc[j],
                            'strength': strength,
                            'distance': current_price - df['Open'].iloc[j],
                            'age_bars': i - j
                        })
                        break

            # Bearish Order Block
            elif current_price < lookback_low * (1 - self.ob_min_move_percent):
                for j in range(i-1, max(0, i-self.ob_lookback), -1):
                    if df['Close'].iloc[j] > df['Open'].iloc[j]:
                        move_size = (lookback_low - current_price) / lookback_low
                        volume_ratio = df['Volume'].iloc[i] / df['Volume'].iloc[i-self.ob_lookback:i].mean()
                        strength = min(1.0, (move_size * 100 + volume_ratio) / 3)

                        order_blocks.append({
                            'bar_index': i,
                            'timestamp': df.index[i],
                            'ob_timestamp': df.index[j],
                            'direction': 'bearish',
                            'ob_high': df['High'].iloc[j],
                            'ob_low': df['Open'].iloc[j],
                            'strength': strength,
                            'distance': df['Open'].iloc[j] - current_price,
                            'age_bars': i - j
                        })
                        break

        return order_blocks

    def detect_fair_value_gaps(self, df: pd.DataFrame) -> List[Dict]:
        """Detect Fair Value Gaps"""
        fvgs = []

        for i in range(2, len(df)):
            # Bullish FVG
            if df['Low'].iloc[i-2] > df['High'].iloc[i]:
                gap_size = df['Low'].iloc[i-2] - df['High'].iloc[i]
                if gap_size >= self.fvg_min_gap_points:
                    fvgs.append({
                        'bar_index': i,
                        'timestamp': df.index[i],
                        'fvg_timestamp': df.index[i-1],
                        'direction': 'bullish',
                        'fvg_high': df['Low'].iloc[i-2],
                        'fvg_low': df['High'].iloc[i],
                        'gap_size': gap_size,
                        'age_bars': 1
                    })

            # Bearish FVG
            elif df['High'].iloc[i-2] < df['Low'].iloc[i]:
                gap_size = df['Low'].iloc[i] - df['High'].iloc[i-2]
                if gap_size >= self.fvg_min_gap_points:
                    fvgs.append({
                        'bar_index': i,
                        'timestamp': df.index[i],
                        'fvg_timestamp': df.index[i-1],
                        'direction': 'bearish',
                        'fvg_high': df['Low'].iloc[i],
                        'fvg_low': df['High'].iloc[i-2],
                        'gap_size': gap_size,
                        'age_bars': 1
                    })

        return fvgs

    def detect_liquidity_sweeps(self, df: pd.DataFrame) -> List[Dict]:
        """Detect Liquidity Sweeps"""
        sweeps = []

        for i in range(self.sweep_lookback, len(df) - 1):
            swing_high = df['High'].iloc[i-self.sweep_lookback:i].max()
            swing_low = df['Low'].iloc[i-self.sweep_lookback:i].min()

            current_high = df['High'].iloc[i]
            current_low = df['Low'].iloc[i]
            current_close = df['Close'].iloc[i]
            next_close = df['Close'].iloc[i+1] if i+1 < len(df) else current_close

            # Bullish Sweep (sweeps lows, reverses up)
            sweep_distance = swing_low - current_low
            if (current_low < swing_low and
                self.sweep_min_points <= sweep_distance <= self.sweep_max_points):
                if current_close > swing_low or next_close > swing_low:
                    rejection_strength = (next_close - current_low) / sweep_distance if sweep_distance > 0 else 0
                    sweeps.append({
                        'bar_index': i,
                        'timestamp': df.index[i],
                        'direction': 'bullish_sweep',
                        'swept_level': swing_low,
                        'strength': min(1.0, rejection_strength),
                        'sweep_distance': sweep_distance
                    })

            # Bearish Sweep (sweeps highs, reverses down)
            sweep_distance = current_high - swing_high
            if (current_high > swing_high and
                self.sweep_min_points <= sweep_distance <= self.sweep_max_points):
                if current_close < swing_high or next_close < swing_high:
                    rejection_strength = (current_high - next_close) / sweep_distance if sweep_distance > 0 else 0
                    sweeps.append({
                        'bar_index': i,
                        'timestamp': df.index[i],
                        'direction': 'bearish_sweep',
                        'swept_level': swing_high,
                        'strength': min(1.0, rejection_strength),
                        'sweep_distance': sweep_distance
                    })

        return sweeps

    def calculate_daily_volume_profile(self, df: pd.DataFrame, date) -> Optional[Dict]:
        """Calculate daily volume profile"""
        day_data = df[df.index.date == date]

        if len(day_data) == 0:
            return None

        # VWAP
        typical_price = (day_data['High'] + day_data['Low'] + day_data['Close']) / 3
        vwap = (typical_price * day_data['Volume']).sum() / day_data['Volume'].sum()

        # Create price-volume distribution
        price_min = day_data['Low'].min()
        price_max = day_data['High'].max()
        num_bins = 50
        bin_size = (price_max - price_min) / num_bins if price_max > price_min else 1

        volume_at_price = {}
        for _, row in day_data.iterrows():
            bar_prices = np.linspace(row['Low'], row['High'], 10)
            volume_per_tick = row['Volume'] / 10

            for price in bar_prices:
                bin_price = round(price / bin_size) * bin_size
                volume_at_price[bin_price] = volume_at_price.get(bin_price, 0) + volume_per_tick

        if not volume_at_price:
            return None

        # POC
        poc = max(volume_at_price.items(), key=lambda x: x[1])[0]

        # Value Area
        total_volume = sum(volume_at_price.values())
        target_volume = total_volume * self.vp_value_area_percent

        sorted_prices = sorted(volume_at_price.keys())
        poc_idx = sorted_prices.index(poc)

        va_volume = volume_at_price[poc]
        va_high_idx = poc_idx
        va_low_idx = poc_idx

        while va_volume < target_volume and (va_high_idx < len(sorted_prices) - 1 or va_low_idx > 0):
            high_vol = volume_at_price.get(sorted_prices[va_high_idx + 1], 0) if va_high_idx < len(sorted_prices) - 1 else 0
            low_vol = volume_at_price.get(sorted_prices[va_low_idx - 1], 0) if va_low_idx > 0 else 0

            if high_vol >= low_vol and va_high_idx < len(sorted_prices) - 1:
                va_high_idx += 1
                va_volume += high_vol
            elif va_low_idx > 0:
                va_low_idx -= 1
                va_volume += low_vol
            else:
                break

        vah = sorted_prices[va_high_idx]
        val = sorted_prices[va_low_idx]

        return {
            'poc': poc,
            'vah': vah,
            'val': val,
            'vwap': vwap,
            'value_area_width': vah - val
        }

    def label_profitability(self, df: pd.DataFrame, bar_idx: int, direction: str) -> Tuple[int, float, int]:
        """
        Label if a trade would have been profitable

        Returns: (is_profitable, max_profit_reached, bars_to_target)
        """
        if bar_idx >= len(df) - 1:
            return 0, 0.0, 0

        entry_price = df['Close'].iloc[bar_idx]

        if direction == 'long':
            profit_target = entry_price * (1 + self.profit_target_percent)
            stop_loss = entry_price * (1 - self.stop_loss_percent)

            max_profit = 0.0
            for i in range(1, min(self.max_bars_forward, len(df) - bar_idx)):
                future_bar = df.iloc[bar_idx + i]

                # Check stop loss
                if future_bar['Low'] <= stop_loss:
                    return 0, max_profit, i

                # Check profit target
                if future_bar['High'] >= profit_target:
                    return 1, self.profit_target_percent, i

                # Track max profit
                max_profit = max(max_profit, (future_bar['High'] - entry_price) / entry_price)

            # Timeout - didn't hit target
            return 0, max_profit, self.max_bars_forward

        else:  # short
            profit_target = entry_price * (1 - self.profit_target_percent)
            stop_loss = entry_price * (1 + self.stop_loss_percent)

            max_profit = 0.0
            for i in range(1, min(self.max_bars_forward, len(df) - bar_idx)):
                future_bar = df.iloc[bar_idx + i]

                # Check stop loss
                if future_bar['High'] >= stop_loss:
                    return 0, max_profit, i

                # Check profit target
                if future_bar['Low'] <= profit_target:
                    return 1, self.profit_target_percent, i

                # Track max profit
                max_profit = max(max_profit, (entry_price - future_bar['Low']) / entry_price)

            # Timeout - didn't hit target
            return 0, max_profit, self.max_bars_forward

    def extract_features(
        self,
        df_1m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Extract all features for each bar

        Returns DataFrame with features and labels
        """
        print("\n=== EXTRACTING FEATURES ===")

        # Calculate technical indicators for all timeframes
        print("Calculating technical indicators...")
        df_1m = self.calculate_technical_indicators(df_1m)
        df_5m = self.calculate_technical_indicators(df_5m)
        df_15m = self.calculate_technical_indicators(df_15m)

        # Detect institutional patterns on 5m
        print("Detecting Order Blocks...")
        order_blocks = self.detect_order_blocks(df_5m)
        print(f"Found {len(order_blocks)} Order Blocks")

        print("Detecting Fair Value Gaps...")
        fvgs = self.detect_fair_value_gaps(df_5m)
        print(f"Found {len(fvgs)} Fair Value Gaps")

        print("Detecting Liquidity Sweeps...")
        sweeps = self.detect_liquidity_sweeps(df_5m)
        print(f"Found {len(sweeps)} Liquidity Sweeps")

        # Calculate daily volume profiles
        print("Calculating Volume Profiles...")
        unique_dates = sorted(set(df_1m.index.date))
        volume_profiles = {}
        for date in unique_dates:
            vp = self.calculate_daily_volume_profile(df_1m, date)
            if vp:
                volume_profiles[date] = vp
        print(f"Calculated {len(volume_profiles)} daily volume profiles")

        # Create feature dataset
        print("\nExtracting features for each bar...")
        features_list = []

        # Only extract features for bars during trading hours
        session_start = time(9, 30)
        session_end = time(15, 50)

        for i in range(100, len(df_1m) - self.max_bars_forward):  # Start at 100 to have enough history
            timestamp = df_1m.index[i]
            bar_time = timestamp.time()

            # Skip outside trading hours
            if bar_time < session_start or bar_time > session_end:
                continue

            # Skip if less than 50 bars on this day (need history)
            day_data = df_1m[df_1m.index.date == timestamp.date()]
            day_bar_idx = len(day_data[day_data.index <= timestamp])
            if day_bar_idx < 50:
                continue

            current_bar = df_1m.iloc[i]
            current_price = current_bar['Close']
            current_date = timestamp.date()

            # Initialize features dictionary
            features = {
                'timestamp': timestamp,
                'price': current_price,
            }

            # === TIME FEATURES ===
            features['hour'] = timestamp.hour
            features['minute'] = timestamp.minute
            features['minutes_from_open'] = (timestamp.hour - 9) * 60 + (timestamp.minute - 30)
            features['day_of_week'] = timestamp.dayofweek

            # === PRICE ACTION FEATURES (1m) ===
            features['body_size'] = current_bar['body_size']
            features['body_ratio'] = current_bar['body_ratio']
            features['upper_wick'] = current_bar['upper_wick']
            features['lower_wick'] = current_bar['lower_wick']
            features['range'] = current_bar['range']
            features['is_bullish'] = 1 if current_bar['Close'] > current_bar['Open'] else 0

            # === TECHNICAL INDICATORS (1m) ===
            features['atr_1m'] = current_bar['atr']
            features['atr_ratio_1m'] = current_bar['atr_ratio']
            features['rsi_1m'] = current_bar['rsi']
            features['ema_short_dist_1m'] = (current_price - current_bar['ema_short']) / current_price
            features['ema_long_dist_1m'] = (current_price - current_bar['ema_long']) / current_price
            features['ema_cross_1m'] = 1 if current_bar['ema_short'] > current_bar['ema_long'] else 0
            features['volume_ratio_1m'] = current_bar['volume_ratio']

            # === MULTI-TIMEFRAME FEATURES (5m, 15m) ===
            # Get corresponding 5m and 15m bars
            idx_5m = df_5m.index.get_indexer([timestamp], method='pad')[0]
            idx_15m = df_15m.index.get_indexer([timestamp], method='pad')[0]

            if idx_5m >= 0 and idx_5m < len(df_5m):
                bar_5m = df_5m.iloc[idx_5m]
                features['atr_5m'] = bar_5m['atr']
                features['rsi_5m'] = bar_5m['rsi']
                features['ema_cross_5m'] = 1 if bar_5m['ema_short'] > bar_5m['ema_long'] else 0
                features['volume_ratio_5m'] = bar_5m['volume_ratio']
            else:
                features['atr_5m'] = 0
                features['rsi_5m'] = 50
                features['ema_cross_5m'] = 0
                features['volume_ratio_5m'] = 1

            if idx_15m >= 0 and idx_15m < len(df_15m):
                bar_15m = df_15m.iloc[idx_15m]
                features['rsi_15m'] = bar_15m['rsi']
                features['ema_cross_15m'] = 1 if bar_15m['ema_short'] > bar_15m['ema_long'] else 0
                features['above_ema50_15m'] = 1 if current_price > bar_15m['ema_50'] else 0
            else:
                features['rsi_15m'] = 50
                features['ema_cross_15m'] = 0
                features['above_ema50_15m'] = 0

            # Timeframe alignment
            features['tf_alignment_bullish'] = (
                features['ema_cross_1m'] and
                features['ema_cross_5m'] and
                features['ema_cross_15m']
            )
            features['tf_alignment_bearish'] = (
                not features['ema_cross_1m'] and
                not features['ema_cross_5m'] and
                not features['ema_cross_15m']
            )

            # === ORDER BLOCK FEATURES ===
            # Find relevant order blocks
            recent_obs = [ob for ob in order_blocks
                         if ob['timestamp'] <= timestamp
                         and (timestamp - ob['timestamp']).total_seconds() <= 3600]  # Within 1 hour

            bullish_obs = [ob for ob in recent_obs if ob['direction'] == 'bullish']
            bearish_obs = [ob for ob in recent_obs if ob['direction'] == 'bearish']

            features['has_bullish_ob'] = 1 if bullish_obs else 0
            features['has_bearish_ob'] = 1 if bearish_obs else 0
            features['num_bullish_obs'] = len(bullish_obs)
            features['num_bearish_obs'] = len(bearish_obs)

            if bullish_obs:
                strongest = max(bullish_obs, key=lambda x: x['strength'])
                features['bullish_ob_strength'] = strongest['strength']
                features['bullish_ob_distance'] = abs(current_price - strongest['ob_high']) / current_price
                features['bullish_ob_age'] = strongest['age_bars']
            else:
                features['bullish_ob_strength'] = 0
                features['bullish_ob_distance'] = 0
                features['bullish_ob_age'] = 0

            if bearish_obs:
                strongest = max(bearish_obs, key=lambda x: x['strength'])
                features['bearish_ob_strength'] = strongest['strength']
                features['bearish_ob_distance'] = abs(current_price - strongest['ob_low']) / current_price
                features['bearish_ob_age'] = strongest['age_bars']
            else:
                features['bearish_ob_strength'] = 0
                features['bearish_ob_distance'] = 0
                features['bearish_ob_age'] = 0

            # === FAIR VALUE GAP FEATURES ===
            recent_fvgs = [fvg for fvg in fvgs
                          if fvg['timestamp'] <= timestamp
                          and (timestamp - fvg['timestamp']).total_seconds() <= 1800]  # Within 30 min

            bullish_fvgs = [fvg for fvg in recent_fvgs if fvg['direction'] == 'bullish']
            bearish_fvgs = [fvg for fvg in recent_fvgs if fvg['direction'] == 'bearish']

            features['has_bullish_fvg'] = 1 if bullish_fvgs else 0
            features['has_bearish_fvg'] = 1 if bearish_fvgs else 0
            features['num_bullish_fvgs'] = len(bullish_fvgs)
            features['num_bearish_fvgs'] = len(bearish_fvgs)

            if bullish_fvgs:
                largest = max(bullish_fvgs, key=lambda x: x['gap_size'])
                features['bullish_fvg_size'] = largest['gap_size']
                features['bullish_fvg_distance'] = min(
                    abs(current_price - largest['fvg_high']),
                    abs(current_price - largest['fvg_low'])
                ) / current_price
            else:
                features['bullish_fvg_size'] = 0
                features['bullish_fvg_distance'] = 0

            if bearish_fvgs:
                largest = max(bearish_fvgs, key=lambda x: x['gap_size'])
                features['bearish_fvg_size'] = largest['gap_size']
                features['bearish_fvg_distance'] = min(
                    abs(current_price - largest['fvg_high']),
                    abs(current_price - largest['fvg_low'])
                ) / current_price
            else:
                features['bearish_fvg_size'] = 0
                features['bearish_fvg_distance'] = 0

            # === LIQUIDITY SWEEP FEATURES ===
            recent_sweeps = [s for s in sweeps
                           if s['timestamp'] <= timestamp
                           and (timestamp - s['timestamp']).total_seconds() <= 1800]  # Within 30 min

            bullish_sweeps = [s for s in recent_sweeps if s['direction'] == 'bullish_sweep']
            bearish_sweeps = [s for s in recent_sweeps if s['direction'] == 'bearish_sweep']

            features['has_bullish_sweep'] = 1 if bullish_sweeps else 0
            features['has_bearish_sweep'] = 1 if bearish_sweeps else 0
            features['num_bullish_sweeps'] = len(bullish_sweeps)
            features['num_bearish_sweeps'] = len(bearish_sweeps)

            if bullish_sweeps:
                strongest = max(bullish_sweeps, key=lambda x: x['strength'])
                features['bullish_sweep_strength'] = strongest['strength']
            else:
                features['bullish_sweep_strength'] = 0

            if bearish_sweeps:
                strongest = max(bearish_sweeps, key=lambda x: x['strength'])
                features['bearish_sweep_strength'] = strongest['strength']
            else:
                features['bearish_sweep_strength'] = 0

            # === VOLUME PROFILE FEATURES ===
            if current_date in volume_profiles:
                vp = volume_profiles[current_date]
                features['vwap'] = vp['vwap']
                features['distance_to_vwap'] = (current_price - vp['vwap']) / current_price
                features['distance_to_poc'] = abs(current_price - vp['poc']) / current_price
                features['distance_to_vah'] = abs(current_price - vp['vah']) / current_price
                features['distance_to_val'] = abs(current_price - vp['val']) / current_price
                features['above_vwap'] = 1 if current_price > vp['vwap'] else 0
                features['in_value_area'] = 1 if vp['val'] <= current_price <= vp['vah'] else 0
                features['value_area_width'] = vp['value_area_width']
            else:
                features['vwap'] = current_price
                features['distance_to_vwap'] = 0
                features['distance_to_poc'] = 0
                features['distance_to_vah'] = 0
                features['distance_to_val'] = 0
                features['above_vwap'] = 0
                features['in_value_area'] = 0
                features['value_area_width'] = 0

            # === CONFLUENCE SCORE ===
            confluence_long = sum([
                features['above_ema50_15m'],
                features['has_bullish_ob'],
                features['has_bullish_fvg'],
                features['has_bullish_sweep'],
                features['in_value_area'],
                not features['above_vwap'],  # Discount
                features['atr_ratio_1m'] >= 0.5 and features['atr_ratio_1m'] <= 1.5
            ])

            confluence_short = sum([
                not features['above_ema50_15m'],
                features['has_bearish_ob'],
                features['has_bearish_fvg'],
                features['has_bearish_sweep'],
                features['in_value_area'],
                features['above_vwap'],  # Premium
                features['atr_ratio_1m'] >= 0.5 and features['atr_ratio_1m'] <= 1.5
            ])

            features['confluence_long'] = confluence_long
            features['confluence_short'] = confluence_short

            # === LABELING ===
            # Label both long and short profitability for ALL bars
            # This gives us maximum data for ML to learn from

            # Try both directions and pick the one with higher confluence
            if confluence_long > confluence_short:
                # Label as potential long
                is_profitable, max_profit, bars_to_target = self.label_profitability(df_1m, i, 'long')
                features['is_profitable'] = is_profitable
                features['max_profit_reached'] = max_profit
                features['bars_to_target'] = bars_to_target
                features['trade_direction'] = 'long'
            elif confluence_short > confluence_long:
                # Label as potential short
                is_profitable, max_profit, bars_to_target = self.label_profitability(df_1m, i, 'short')
                features['is_profitable'] = is_profitable
                features['max_profit_reached'] = max_profit
                features['bars_to_target'] = bars_to_target
                features['trade_direction'] = 'short'
            else:
                # Equal confluence - use candle direction
                direction = 'long' if features['is_bullish'] else 'short'
                is_profitable, max_profit, bars_to_target = self.label_profitability(df_1m, i, direction)
                features['is_profitable'] = is_profitable
                features['max_profit_reached'] = max_profit
                features['bars_to_target'] = bars_to_target
                features['trade_direction'] = direction

            features_list.append(features)

            # Progress update
            if len(features_list) % 1000 == 0:
                print(f"Processed {len(features_list)} bars...")

        print(f"\nTotal features extracted: {len(features_list)} bars")

        # Convert to DataFrame
        df_features = pd.DataFrame(features_list)

        # Print summary statistics
        print("\n=== SUMMARY STATISTICS ===")
        print(f"Total setups: {len(df_features)}")
        print(f"Long setups: {(df_features['trade_direction'] == 'long').sum()}")
        print(f"Short setups: {(df_features['trade_direction'] == 'short').sum()}")
        print(f"Profitable setups: {df_features['is_profitable'].sum()}")
        print(f"Win rate: {df_features['is_profitable'].mean() * 100:.2f}%")

        return df_features


def main():
    """Main execution"""
    print("=" * 80)
    print("ML FEATURE EXTRACTION FOR INSTITUTIONAL ORDER FLOW")
    print("=" * 80)

    # Initialize extractor
    extractor = InstitutionalFeatureExtractor(
        profit_target_percent=0.002,  # 0.2% profit target (~12 pts on SPX500)
        stop_loss_percent=0.001,      # 0.1% stop loss (~6 pts)
        max_bars_forward=90           # 90 minutes max (1.5 hour window)
    )

    # Load data
    data_path = '/home/user/NEW-LTF-bot-for-mt5/data/spx500_stooq_intraday.csv'
    df_1m, df_5m, df_15m = extractor.load_and_prepare_data(data_path)

    # Extract features
    df_features = extractor.extract_features(df_1m, df_5m, df_15m)

    # Save to CSV
    output_path = '/home/user/NEW-LTF-bot-for-mt5/ml_training_data.csv'
    df_features.to_csv(output_path, index=False)
    print(f"\n✓ Features saved to: {output_path}")

    # Print feature names
    feature_cols = [col for col in df_features.columns
                   if col not in ['timestamp', 'price', 'is_profitable', 'max_profit_reached',
                                 'bars_to_target', 'trade_direction']]
    print(f"\n=== {len(feature_cols)} FEATURES EXTRACTED ===")
    for i, col in enumerate(feature_cols, 1):
        print(f"{i}. {col}")

    print("\n" + "=" * 80)
    print("FEATURE EXTRACTION COMPLETE!")
    print("=" * 80)


if __name__ == "__main__":
    main()
