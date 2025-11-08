"""
ELITE INSTITUTIONAL SPX500 STRATEGY
Multi-Timeframe Order Flow System

Combines:
- Intraday Momentum (19.6% annual academic study)
- Smart Money Concepts (Order Blocks, FVG, Liquidity Sweeps)
- Volume Profile Analysis
- Multi-Timeframe Confluence (15m/5m/1m)
- Volatility Regime Filtering

Target: 70-80% win rate, max 15 trades/week, <4% drawdown
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import time, datetime, timedelta
from dataclasses import dataclass


@dataclass
class OrderBlock:
    """Represents an institutional order block"""
    price_high: float
    price_low: float
    timestamp: datetime
    direction: str  # 'bullish' or 'bearish'
    strength: float  # 0-1, based on volume and move size
    filled: bool = False


@dataclass
class FairValueGap:
    """Represents a Fair Value Gap (price imbalance)"""
    price_high: float
    price_low: float
    timestamp: datetime
    direction: str  # 'bullish' or 'bearish'
    filled_percent: float = 0.0  # 0-100%


@dataclass
class LiquiditySweep:
    """Represents a liquidity sweep (stop hunt)"""
    swept_level: float
    timestamp: datetime
    direction: str  # 'bullish_sweep' (sweeps highs, then down) or 'bearish_sweep'
    strength: float  # How aggressive the rejection was


@dataclass
class VolumeProfile:
    """Daily volume profile data"""
    poc: float  # Point of Control
    vah: float  # Value Area High
    val: float  # Value Area Low
    vwap: float  # Volume Weighted Average Price
    high_volume_nodes: List[float]
    low_volume_nodes: List[float]


@dataclass
class TradeSignal:
    """Complete trade signal with all confluence factors"""
    timestamp: datetime
    direction: str  # 'long' or 'short'
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    confluence_score: int  # 0-7
    confirmations: Dict[str, bool]
    order_block: Optional[OrderBlock] = None
    fair_value_gap: Optional[FairValueGap] = None
    liquidity_sweep: Optional[LiquiditySweep] = None


class EliteInstitutionalStrategy:
    """
    Elite multi-timeframe institutional order flow strategy

    Uses 15m for bias, 5m for signals, 1m for entries
    """

    def __init__(
        self,
        # Trading hours
        session_start: time = time(9, 30),
        session_end: time = time(15, 50),
        optimal_start: time = time(9, 30),
        optimal_end: time = time(14, 0),

        # Risk parameters
        risk_percent: float = 0.006,  # 0.6%
        min_rr_ratio: float = 2.0,
        target_rr_ratios: Tuple[float, float, float] = (1.5, 2.5, 4.0),

        # Confluence requirements
        min_confluence_score: int = 4,  # Out of 7

        # Order Block settings
        ob_lookback: int = 20,
        ob_min_move_percent: float = 0.005,  # 0.5% move to validate OB

        # Fair Value Gap settings
        fvg_min_gap_points: float = 3.0,

        # Liquidity Sweep settings
        sweep_lookback: int = 20,
        sweep_min_points: float = 3.0,
        sweep_max_points: float = 10.0,

        # Volume Profile settings
        vp_value_area_percent: float = 0.70,  # 70% of volume

        # Volatility filter
        atr_period: int = 14,
        atr_ma_period: int = 20,
        atr_min_multiplier: float = 0.5,
        atr_max_multiplier: float = 1.5,

        # Intraday momentum
        momentum_lookback: int = 14,  # days
        momentum_threshold_atr: float = 1.5,
    ):
        # Trading hours
        self.session_start = session_start
        self.session_end = session_end
        self.optimal_start = optimal_start
        self.optimal_end = optimal_end

        # Risk parameters
        self.risk_percent = risk_percent
        self.min_rr_ratio = min_rr_ratio
        self.target_rr_ratios = target_rr_ratios

        # Confluence
        self.min_confluence_score = min_confluence_score

        # Order Blocks
        self.ob_lookback = ob_lookback
        self.ob_min_move_percent = ob_min_move_percent

        # Fair Value Gaps
        self.fvg_min_gap_points = fvg_min_gap_points

        # Liquidity Sweeps
        self.sweep_lookback = sweep_lookback
        self.sweep_min_points = sweep_min_points
        self.sweep_max_points = sweep_max_points

        # Volume Profile
        self.vp_value_area_percent = vp_value_area_percent

        # Volatility filter
        self.atr_period = atr_period
        self.atr_ma_period = atr_ma_period
        self.atr_min_multiplier = atr_min_multiplier
        self.atr_max_multiplier = atr_max_multiplier

        # Momentum
        self.momentum_lookback = momentum_lookback
        self.momentum_threshold_atr = momentum_threshold_atr

        # State
        self.active_order_blocks: List[OrderBlock] = []
        self.active_fvgs: List[FairValueGap] = []
        self.recent_sweeps: List[LiquiditySweep] = []
        self.daily_volume_profile: Optional[VolumeProfile] = None

    def detect_order_blocks(
        self,
        data: pd.DataFrame,
        timeframe: str = '5m'
    ) -> List[OrderBlock]:
        """
        Detect Order Blocks - zones where institutions entered

        Bullish OB: Last bearish candle before strong bullish move
        Bearish OB: Last bullish candle before strong bearish move
        """
        order_blocks = []

        for i in range(self.ob_lookback, len(data)):
            # Look for strong moves
            current_price = data['Close'].iloc[i]
            lookback_low = data['Low'].iloc[i-self.ob_lookback:i].min()
            lookback_high = data['High'].iloc[i-self.ob_lookback:i].max()

            # Bullish Order Block detection
            if current_price > lookback_high * (1 + self.ob_min_move_percent):
                # Find last bearish candle before the move
                for j in range(i-1, i-self.ob_lookback, -1):
                    if data['Close'].iloc[j] < data['Open'].iloc[j]:
                        # This is a bearish candle, potential bullish OB
                        ob_high = data['Open'].iloc[j]
                        ob_low = data['Low'].iloc[j]

                        # Calculate strength based on volume and move size
                        move_size = (current_price - lookback_high) / lookback_high
                        volume_ratio = data['Volume'].iloc[i] / data['Volume'].iloc[i-self.ob_lookback:i].mean()
                        strength = min(1.0, (move_size * 100 + volume_ratio) / 3)

                        ob = OrderBlock(
                            price_high=ob_high,
                            price_low=ob_low,
                            timestamp=data.index[j],
                            direction='bullish',
                            strength=strength
                        )
                        order_blocks.append(ob)
                        break

            # Bearish Order Block detection
            elif current_price < lookback_low * (1 - self.ob_min_move_percent):
                # Find last bullish candle before the move
                for j in range(i-1, i-self.ob_lookback, -1):
                    if data['Close'].iloc[j] > data['Open'].iloc[j]:
                        # This is a bullish candle, potential bearish OB
                        ob_high = data['High'].iloc[j]
                        ob_low = data['Open'].iloc[j]

                        move_size = (lookback_low - current_price) / lookback_low
                        volume_ratio = data['Volume'].iloc[i] / data['Volume'].iloc[i-self.ob_lookback:i].mean()
                        strength = min(1.0, (move_size * 100 + volume_ratio) / 3)

                        ob = OrderBlock(
                            price_high=ob_high,
                            price_low=ob_low,
                            timestamp=data.index[j],
                            direction='bearish',
                            strength=strength
                        )
                        order_blocks.append(ob)
                        break

        return order_blocks

    def detect_fair_value_gaps(
        self,
        data: pd.DataFrame
    ) -> List[FairValueGap]:
        """
        Detect Fair Value Gaps - 3-candle price imbalances

        Bullish FVG: candle[i-2].Low > candle[i].High (gap between them)
        Bearish FVG: candle[i-2].High < candle[i].Low
        """
        fvgs = []

        for i in range(2, len(data)):
            # Bullish FVG
            if data['Low'].iloc[i-2] > data['High'].iloc[i]:
                gap_size = data['Low'].iloc[i-2] - data['High'].iloc[i]
                if gap_size >= self.fvg_min_gap_points:
                    fvg = FairValueGap(
                        price_high=data['Low'].iloc[i-2],
                        price_low=data['High'].iloc[i],
                        timestamp=data.index[i-1],
                        direction='bullish'
                    )
                    fvgs.append(fvg)

            # Bearish FVG
            elif data['High'].iloc[i-2] < data['Low'].iloc[i]:
                gap_size = data['Low'].iloc[i] - data['High'].iloc[i-2]
                if gap_size >= self.fvg_min_gap_points:
                    fvg = FairValueGap(
                        price_high=data['Low'].iloc[i],
                        price_low=data['High'].iloc[i-2],
                        timestamp=data.index[i-1],
                        direction='bearish'
                    )
                    fvgs.append(fvg)

        return fvgs

    def detect_liquidity_sweeps(
        self,
        data: pd.DataFrame
    ) -> List[LiquiditySweep]:
        """
        Detect Liquidity Sweeps - false breakouts that hunt stop losses

        Pattern: Price breaks swing high/low, then strongly rejects
        """
        sweeps = []

        for i in range(self.sweep_lookback, len(data) - 1):
            # Find swing high/low in lookback period
            swing_high = data['High'].iloc[i-self.sweep_lookback:i].max()
            swing_low = data['Low'].iloc[i-self.sweep_lookback:i].min()

            current_high = data['High'].iloc[i]
            current_low = data['Low'].iloc[i]
            current_close = data['Close'].iloc[i]
            next_close = data['Close'].iloc[i+1]

            # Bullish Sweep (sweeps lows, then reverses up)
            sweep_distance = swing_low - current_low
            if (current_low < swing_low and
                self.sweep_min_points <= sweep_distance <= self.sweep_max_points):

                # Check for strong rejection (closes back above swing low)
                if current_close > swing_low or next_close > swing_low:
                    rejection_strength = (next_close - current_low) / sweep_distance

                    sweep = LiquiditySweep(
                        swept_level=swing_low,
                        timestamp=data.index[i],
                        direction='bullish_sweep',
                        strength=min(1.0, rejection_strength)
                    )
                    sweeps.append(sweep)

            # Bearish Sweep (sweeps highs, then reverses down)
            sweep_distance = current_high - swing_high
            if (current_high > swing_high and
                self.sweep_min_points <= sweep_distance <= self.sweep_max_points):

                # Check for strong rejection (closes back below swing high)
                if current_close < swing_high or next_close < swing_high:
                    rejection_strength = (current_high - next_close) / sweep_distance

                    sweep = LiquiditySweep(
                        swept_level=swing_high,
                        timestamp=data.index[i],
                        direction='bearish_sweep',
                        strength=min(1.0, rejection_strength)
                    )
                    sweeps.append(sweep)

        return sweeps

    def calculate_volume_profile(
        self,
        data: pd.DataFrame,
        date: datetime.date
    ) -> VolumeProfile:
        """
        Calculate daily Volume Profile

        Returns POC, Value Area, VWAP, and volume nodes
        """
        # Filter data for this date
        day_mask = pd.Series([d.date() == date for d in data.index], index=data.index)
        day_data = data[day_mask]

        if len(day_data) == 0:
            return None

        # Calculate VWAP
        typical_price = (day_data['High'] + day_data['Low'] + day_data['Close']) / 3
        vwap = (typical_price * day_data['Volume']).sum() / day_data['Volume'].sum()

        # Create price-volume distribution
        price_min = day_data['Low'].min()
        price_max = day_data['High'].max()
        num_bins = 50
        bin_size = (price_max - price_min) / num_bins

        volume_at_price = {}
        for _, row in day_data.iterrows():
            # Distribute volume across price range of the bar
            bar_prices = np.linspace(row['Low'], row['High'], 10)
            volume_per_tick = row['Volume'] / 10

            for price in bar_prices:
                bin_price = round(price / bin_size) * bin_size
                volume_at_price[bin_price] = volume_at_price.get(bin_price, 0) + volume_per_tick

        # Find POC (highest volume price)
        poc = max(volume_at_price.items(), key=lambda x: x[1])[0]

        # Calculate Value Area (70% of volume)
        total_volume = sum(volume_at_price.values())
        target_volume = total_volume * self.vp_value_area_percent

        # Start from POC and expand up/down
        sorted_prices = sorted(volume_at_price.keys())
        poc_idx = sorted_prices.index(poc)

        va_volume = volume_at_price[poc]
        va_high_idx = poc_idx
        va_low_idx = poc_idx

        while va_volume < target_volume and (va_high_idx < len(sorted_prices) - 1 or va_low_idx > 0):
            # Expand to side with more volume
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

        # Identify high and low volume nodes
        avg_volume = np.mean(list(volume_at_price.values()))
        high_volume_nodes = [price for price, vol in volume_at_price.items() if vol > avg_volume * 1.5]
        low_volume_nodes = [price for price, vol in volume_at_price.items() if vol < avg_volume * 0.5]

        return VolumeProfile(
            poc=poc,
            vah=vah,
            val=val,
            vwap=vwap,
            high_volume_nodes=sorted(high_volume_nodes),
            low_volume_nodes=sorted(low_volume_nodes)
        )

    def check_volatility_regime(
        self,
        data: pd.DataFrame
    ) -> Tuple[bool, str]:
        """
        Check if current volatility is in acceptable range

        Returns: (is_acceptable, regime_name)
        """
        # Calculate ATR
        data['tr'] = np.maximum(
            data['High'] - data['Low'],
            np.maximum(
                abs(data['High'] - data['Close'].shift(1)),
                abs(data['Low'] - data['Close'].shift(1))
            )
        )
        data['atr'] = data['tr'].rolling(self.atr_period).mean()
        data['atr_ma'] = data['atr'].rolling(self.atr_ma_period).mean()

        current_atr = data['atr'].iloc[-1]
        atr_ma = data['atr_ma'].iloc[-1]

        if pd.isna(current_atr) or pd.isna(atr_ma):
            return False, "INSUFFICIENT_DATA"

        ratio = current_atr / atr_ma

        if ratio > self.atr_max_multiplier:
            return False, "HIGH_VOLATILITY"
        elif ratio < self.atr_min_multiplier:
            return False, "LOW_VOLATILITY"
        else:
            return True, "NORMAL_VOLATILITY"

    def calculate_confluence_score(
        self,
        data_15m: pd.DataFrame,
        data_5m: pd.DataFrame,
        data_1m: pd.DataFrame,
        current_price: float,
        direction: str
    ) -> Tuple[int, Dict[str, bool]]:
        """
        Calculate confluence score (0-7) based on confirmations

        Returns: (score, confirmations_dict)
        """
        confirmations = {
            '15m_trend': False,
            'order_block': False,
            'fair_value_gap': False,
            'liquidity_sweep': False,
            'volume_confirmation': False,
            'vwap_position': False,
            'volatility_filter': False
        }

        # 1. 15m Trend Alignment
        data_15m['ema50'] = data_15m['Close'].ewm(span=50, adjust=False).mean()
        if direction == 'long' and current_price > data_15m['ema50'].iloc[-1]:
            confirmations['15m_trend'] = True
        elif direction == 'short' and current_price < data_15m['ema50'].iloc[-1]:
            confirmations['15m_trend'] = True

        # 2. Order Block present
        if direction == 'long':
            valid_obs = [ob for ob in self.active_order_blocks
                        if ob.direction == 'bullish' and not ob.filled
                        and ob.price_low <= current_price <= ob.price_high]
            if valid_obs:
                confirmations['order_block'] = True
        else:
            valid_obs = [ob for ob in self.active_order_blocks
                        if ob.direction == 'bearish' and not ob.filled
                        and ob.price_low <= current_price <= ob.price_high]
            if valid_obs:
                confirmations['order_block'] = True

        # 3. Fair Value Gap present
        if direction == 'long':
            valid_fvgs = [fvg for fvg in self.active_fvgs
                         if fvg.direction == 'bullish' and fvg.filled_percent < 80
                         and fvg.price_low <= current_price <= fvg.price_high]
            if valid_fvgs:
                confirmations['fair_value_gap'] = True
        else:
            valid_fvgs = [fvg for fvg in self.active_fvgs
                         if fvg.direction == 'bearish' and fvg.filled_percent < 80
                         and fvg.price_low <= current_price <= fvg.price_high]
            if valid_fvgs:
                confirmations['fair_value_gap'] = True

        # 4. Recent Liquidity Sweep
        recent_time = data_1m.index[-1] - timedelta(minutes=30)
        if direction == 'long':
            recent_sweeps = [s for s in self.recent_sweeps
                           if s.direction == 'bullish_sweep' and s.timestamp >= recent_time]
            if recent_sweeps:
                confirmations['liquidity_sweep'] = True
        else:
            recent_sweeps = [s for s in self.recent_sweeps
                           if s.direction == 'bearish_sweep' and s.timestamp >= recent_time]
            if recent_sweeps:
                confirmations['liquidity_sweep'] = True

        # 5. Volume Confirmation (near POC or VA boundary)
        if self.daily_volume_profile:
            vp = self.daily_volume_profile
            if abs(current_price - vp.poc) < 5 or abs(current_price - vp.vah) < 5 or abs(current_price - vp.val) < 5:
                confirmations['volume_confirmation'] = True

        # 6. VWAP Position
        if self.daily_volume_profile:
            vwap = self.daily_volume_profile.vwap
            if direction == 'long' and current_price < vwap:
                confirmations['vwap_position'] = True  # Buying below VWAP (discount)
            elif direction == 'short' and current_price > vwap:
                confirmations['vwap_position'] = True  # Selling above VWAP (premium)

        # 7. Volatility Filter
        is_acceptable, _ = self.check_volatility_regime(data_5m)
        confirmations['volatility_filter'] = is_acceptable

        score = sum(confirmations.values())
        return score, confirmations

    def generate_signals(
        self,
        data_15m: pd.DataFrame,
        data_5m: pd.DataFrame,
        data_1m: pd.DataFrame,
        backtester=None
    ) -> List[TradeSignal]:
        """
        Generate trade signals with full confluence analysis

        Args:
            data_15m: 15-minute timeframe data
            data_5m: 5-minute timeframe data
            data_1m: 1-minute timeframe data
            backtester: Optional backtester instance for position sizing

        Returns:
            List of high-probability trade signals
        """
        signals = []

        # Get unique dates
        unique_dates = sorted(set([d.date() for d in data_1m.index]))

        for date in unique_dates:
            # Calculate daily volume profile
            self.daily_volume_profile = self.calculate_volume_profile(data_1m, date)

            if self.daily_volume_profile is None:
                continue

            # Detect Order Blocks on 5m
            self.active_order_blocks = self.detect_order_blocks(data_5m)

            # Detect Fair Value Gaps on 5m
            self.active_fvgs = self.detect_fair_value_gaps(data_5m)

            # Detect Liquidity Sweeps on 5m
            self.recent_sweeps = self.detect_liquidity_sweeps(data_5m)

            # Scan 1-minute chart for entries during optimal hours
            day_mask = pd.Series([d.date() == date for d in data_1m.index], index=data_1m.index)
            day_data = data_1m[day_mask]

            for i in range(50, len(day_data)):
                current_time = day_data.index[i].time()

                # Only trade during optimal hours
                if current_time < self.optimal_start or current_time > self.optimal_end:
                    continue

                current_price = day_data['Close'].iloc[i]
                current_bar = day_data.iloc[i]

                # Look for entry triggers
                # Bullish: Strong green candle or engulfing
                bullish_trigger = (
                    (current_bar['Close'] > current_bar['Open']) and
                    (current_bar['Close'] - current_bar['Open']) > (current_bar['High'] - current_bar['Low']) * 0.6
                )

                # Bearish: Strong red candle or engulfing
                bearish_trigger = (
                    (current_bar['Close'] < current_bar['Open']) and
                    (current_bar['Open'] - current_bar['Close']) > (current_bar['High'] - current_bar['Low']) * 0.6
                )

                # Check LONG setup
                if bullish_trigger:
                    score, confirmations = self.calculate_confluence_score(
                        data_15m, data_5m, day_data.iloc[:i+1], current_price, 'long'
                    )

                    if score >= self.min_confluence_score:
                        # Find Order Block for stop placement
                        valid_obs = [ob for ob in self.active_order_blocks
                                    if ob.direction == 'bullish' and not ob.filled
                                    and ob.price_low <= current_price <= ob.price_high]

                        if valid_obs:
                            ob = max(valid_obs, key=lambda x: x.strength)
                            stop_loss = ob.price_low - 3.0
                        else:
                            # Use recent swing low
                            stop_loss = day_data['Low'].iloc[i-20:i].min() - 2.0

                        stop_distance = current_price - stop_loss

                        # Check if R:R is acceptable
                        if stop_distance > 0 and stop_distance < 20:  # Reasonable stop
                            tp1 = current_price + (stop_distance * self.target_rr_ratios[0])
                            tp2 = current_price + (stop_distance * self.target_rr_ratios[1])
                            tp3 = current_price + (stop_distance * self.target_rr_ratios[2])

                            signal = TradeSignal(
                                timestamp=day_data.index[i],
                                direction='long',
                                entry_price=current_price,
                                stop_loss=stop_loss,
                                take_profit_1=tp1,
                                take_profit_2=tp2,
                                take_profit_3=tp3,
                                confluence_score=score,
                                confirmations=confirmations,
                                order_block=ob if valid_obs else None,
                                fair_value_gap=self.active_fvgs[0] if self.active_fvgs else None,
                                liquidity_sweep=self.recent_sweeps[0] if self.recent_sweeps else None
                            )
                            signals.append(signal)

                # Check SHORT setup
                elif bearish_trigger:
                    score, confirmations = self.calculate_confluence_score(
                        data_15m, data_5m, day_data.iloc[:i+1], current_price, 'short'
                    )

                    if score >= self.min_confluence_score:
                        # Find Order Block for stop placement
                        valid_obs = [ob for ob in self.active_order_blocks
                                    if ob.direction == 'bearish' and not ob.filled
                                    and ob.price_low <= current_price <= ob.price_high]

                        if valid_obs:
                            ob = max(valid_obs, key=lambda x: x.strength)
                            stop_loss = ob.price_high + 3.0
                        else:
                            # Use recent swing high
                            stop_loss = day_data['High'].iloc[i-20:i].max() + 2.0

                        stop_distance = stop_loss - current_price

                        # Check if R:R is acceptable
                        if stop_distance > 0 and stop_distance < 20:  # Reasonable stop
                            tp1 = current_price - (stop_distance * self.target_rr_ratios[0])
                            tp2 = current_price - (stop_distance * self.target_rr_ratios[1])
                            tp3 = current_price - (stop_distance * self.target_rr_ratios[2])

                            signal = TradeSignal(
                                timestamp=day_data.index[i],
                                direction='short',
                                entry_price=current_price,
                                stop_loss=stop_loss,
                                take_profit_1=tp1,
                                take_profit_2=tp2,
                                take_profit_3=tp3,
                                confluence_score=score,
                                confirmations=confirmations,
                                order_block=ob if valid_obs else None,
                                fair_value_gap=self.active_fvgs[0] if self.active_fvgs else None,
                                liquidity_sweep=self.recent_sweeps[0] if self.recent_sweeps else None
                            )
                            signals.append(signal)

        return signals
