"""
ML-ENHANCED INSTITUTIONAL STRATEGY

Uses XGBoost predictions combined with institutional order flow patterns
to generate high-probability trade signals.

Risk-based position sizing:
- ML probability >0.80: Trade with 1.5% risk
- ML probability 0.70-0.80: Trade with 1.0% risk
- ML probability 0.60-0.70: Trade with 0.5% risk
- ML probability <0.60: Skip
"""

import pandas as pd
import numpy as np
import pickle
from typing import Dict, List, Tuple, Optional
from datetime import time, datetime, timedelta
from dataclasses import dataclass


@dataclass
class MLTradeSignal:
    """ML-enhanced trade signal"""
    timestamp: datetime
    direction: str  # 'long' or 'short'
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    ml_probability: float
    risk_percent: float
    confidence_tier: str  # 'high', 'medium', 'low'
    features: Dict


class MLInstitutionalStrategy:
    """
    ML-enhanced institutional order flow strategy

    Combines XGBoost predictions with institutional patterns
    """

    def __init__(
        self,
        model_path: str = '/home/user/NEW-LTF-bot-for-mt5/models/xgboost_institutional.pkl',

        # ML thresholds and risk sizing
        high_confidence_threshold: float = 0.80,
        medium_confidence_threshold: float = 0.70,
        low_confidence_threshold: float = 0.60,

        high_confidence_risk: float = 0.015,  # 1.5%
        medium_confidence_risk: float = 0.010,  # 1.0%
        low_confidence_risk: float = 0.005,  # 0.5%

        # Trading parameters
        session_start: time = time(9, 30),
        session_end: time = time(15, 50),

        # Risk management
        max_daily_drawdown: float = 0.02,  # 2%
        target_rr_ratios: Tuple[float, float, float] = (1.5, 2.5, 4.0),
    ):
        # Load trained model
        print(f"Loading ML model from {model_path}...")
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
            self.model = model_data['model']
            self.feature_names = model_data['feature_names']
        print(f"✓ Model loaded successfully")
        print(f"✓ Features: {len(self.feature_names)}")

        # ML parameters
        self.high_confidence_threshold = high_confidence_threshold
        self.medium_confidence_threshold = medium_confidence_threshold
        self.low_confidence_threshold = low_confidence_threshold

        self.high_confidence_risk = high_confidence_risk
        self.medium_confidence_risk = medium_confidence_risk
        self.low_confidence_risk = low_confidence_risk

        # Trading hours
        self.session_start = session_start
        self.session_end = session_end

        # Risk management
        self.max_daily_drawdown = max_daily_drawdown
        self.target_rr_ratios = target_rr_ratios

    def extract_features_for_bar(
        self,
        df_1m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame,
        bar_idx: int
    ) -> Optional[Dict]:
        """
        Extract features for a single bar
        (Simplified version - just uses the current data)
        """
        if bar_idx < 100:  # Need history
            return None

        current_bar = df_1m.iloc[bar_idx]
        timestamp = df_1m.index[bar_idx]
        current_price = current_bar['Close']

        # Basic features
        features = {}

        # Time features
        features['hour'] = timestamp.hour
        features['minute'] = timestamp.minute
        features['minutes_from_open'] = (timestamp.hour - 9) * 60 + (timestamp.minute - 30)
        features['day_of_week'] = timestamp.dayofweek

        # Price action
        body_size = abs(current_bar['Close'] - current_bar['Open'])
        upper_wick = current_bar['High'] - max(current_bar['Open'], current_bar['Close'])
        lower_wick = min(current_bar['Open'], current_bar['Close']) - current_bar['Low']
        bar_range = current_bar['High'] - current_bar['Low']

        features['body_size'] = body_size
        features['body_ratio'] = body_size / bar_range if bar_range > 0 else 0
        features['upper_wick'] = upper_wick
        features['lower_wick'] = lower_wick
        features['range'] = bar_range
        features['is_bullish'] = 1 if current_bar['Close'] > current_bar['Open'] else 0

        # Technical indicators - use pre-calculated from dataframe if available
        for col in ['atr', 'atr_ratio', 'rsi', 'ema_short', 'ema_long', 'volume_ratio']:
            if col in current_bar:
                features[col + '_1m'] = current_bar[col]
            else:
                features[col + '_1m'] = 0

        # EMA distances
        if 'ema_short' in current_bar and 'ema_long' in current_bar:
            features['ema_short_dist_1m'] = (current_price - current_bar['ema_short']) / current_price if current_price > 0 else 0
            features['ema_long_dist_1m'] = (current_price - current_bar['ema_long']) / current_price if current_price > 0 else 0
            features['ema_cross_1m'] = 1 if current_bar['ema_short'] > current_bar['ema_long'] else 0
        else:
            features['ema_short_dist_1m'] = 0
            features['ema_long_dist_1m'] = 0
            features['ema_cross_1m'] = 0

        # Multi-timeframe (simplified)
        features['rsi_5m'] = 50
        features['ema_cross_5m'] = features['ema_cross_1m']
        features['volume_ratio_5m'] = features.get('volume_ratio_1m', 1.0)
        features['atr_5m'] = features.get('atr_1m', 0)

        features['rsi_15m'] = 50
        features['ema_cross_15m'] = features['ema_cross_1m']
        features['above_ema50_15m'] = features['ema_cross_1m']

        # Timeframe alignment
        features['tf_alignment_bullish'] = features['ema_cross_1m']
        features['tf_alignment_bearish'] = 1 - features['ema_cross_1m']

        # Institutional pattern placeholders (simplified - would need full detection)
        features['has_bullish_ob'] = 0
        features['has_bearish_ob'] = 0
        features['num_bullish_obs'] = 0
        features['num_bearish_obs'] = 0
        features['bullish_ob_strength'] = 0
        features['bullish_ob_distance'] = 0
        features['bullish_ob_age'] = 0
        features['bearish_ob_strength'] = 0
        features['bearish_ob_distance'] = 0
        features['bearish_ob_age'] = 0

        features['has_bullish_fvg'] = 0
        features['has_bearish_fvg'] = 0
        features['num_bullish_fvgs'] = 0
        features['num_bearish_fvgs'] = 0
        features['bullish_fvg_size'] = 0
        features['bullish_fvg_distance'] = 0
        features['bearish_fvg_size'] = 0
        features['bearish_fvg_distance'] = 0

        features['has_bullish_sweep'] = 0
        features['has_bearish_sweep'] = 0
        features['num_bullish_sweeps'] = 0
        features['num_bearish_sweeps'] = 0
        features['bullish_sweep_strength'] = 0
        features['bearish_sweep_strength'] = 0

        # Volume profile placeholders
        features['distance_to_vwap'] = 0
        features['distance_to_poc'] = 0
        features['distance_to_vah'] = 0
        features['distance_to_val'] = 0
        features['above_vwap'] = features['ema_cross_1m']
        features['in_value_area'] = 1
        features['value_area_width'] = bar_range * 10

        # Confluence
        features['confluence_long'] = sum([
            features['ema_cross_1m'],
            features['ema_cross_5m'],
            features['ema_cross_15m'],
        ])
        features['confluence_short'] = 3 - features['confluence_long']

        return features

    def predict_probability(self, features: Dict) -> float:
        """Get ML prediction probability"""
        # Create feature vector in correct order
        feature_vector = []
        for fname in self.feature_names:
            feature_vector.append(features.get(fname, 0))

        # Predict probability
        X = np.array(feature_vector).reshape(1, -1)
        proba = self.model.predict_proba(X)[0, 1]

        return proba

    def generate_signal(
        self,
        df_1m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame,
        bar_idx: int
    ) -> Optional[MLTradeSignal]:
        """
        Generate ML-enhanced trade signal for a specific bar
        """
        timestamp = df_1m.index[bar_idx]
        bar_time = timestamp.time()

        # Only trade during session
        if bar_time < self.session_start or bar_time > self.session_end:
            return None

        # Extract features
        features = self.extract_features_for_bar(df_1m, df_5m, df_15m, bar_idx)
        if features is None:
            return None

        # Get ML prediction
        ml_probability = self.predict_probability(features)

        # Filter by minimum confidence
        if ml_probability < self.low_confidence_threshold:
            return None

        # Determine risk and confidence tier
        if ml_probability >= self.high_confidence_threshold:
            risk_percent = self.high_confidence_risk
            confidence_tier = 'high'
        elif ml_probability >= self.medium_confidence_threshold:
            risk_percent = self.medium_confidence_risk
            confidence_tier = 'medium'
        else:
            risk_percent = self.low_confidence_risk
            confidence_tier = 'low'

        # Determine direction (prefer bullish if probability is high and confluence agrees)
        current_bar = df_1m.iloc[bar_idx]
        current_price = current_bar['Close']

        if features['confluence_long'] > features['confluence_short']:
            direction = 'long'
        else:
            direction = 'short'

        # Calculate stops and targets
        atr = features.get('atr_1m', current_price * 0.002)  # Default 0.2%

        if direction == 'long':
            stop_distance = max(atr * 2, current_price * 0.001)  # At least 0.1%
            stop_loss = current_price - stop_distance

            tp1 = current_price + (stop_distance * self.target_rr_ratios[0])
            tp2 = current_price + (stop_distance * self.target_rr_ratios[1])
            tp3 = current_price + (stop_distance * self.target_rr_ratios[2])
        else:
            stop_distance = max(atr * 2, current_price * 0.001)
            stop_loss = current_price + stop_distance

            tp1 = current_price - (stop_distance * self.target_rr_ratios[0])
            tp2 = current_price - (stop_distance * self.target_rr_ratios[1])
            tp3 = current_price - (stop_distance * self.target_rr_ratios[2])

        # Create signal
        signal = MLTradeSignal(
            timestamp=timestamp,
            direction=direction,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            ml_probability=ml_probability,
            risk_percent=risk_percent,
            confidence_tier=confidence_tier,
            features=features
        )

        return signal

    def generate_signals_from_predictions(
        self,
        predictions_csv: str = '/home/user/NEW-LTF-bot-for-mt5/ml_predictions.csv'
    ) -> List[MLTradeSignal]:
        """
        Generate signals from pre-computed predictions (faster for backtesting)
        """
        print("Loading predictions...")
        df = pd.read_csv(predictions_csv)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        print(f"Loaded {len(df)} predictions")

        signals = []

        for _, row in df.iterrows():
            ml_probability = row['ml_probability']

            # Filter by minimum confidence
            if ml_probability < self.low_confidence_threshold:
                continue

            # Determine risk and confidence tier
            if ml_probability >= self.high_confidence_threshold:
                risk_percent = self.high_confidence_risk
                confidence_tier = 'high'
            elif ml_probability >= self.medium_confidence_threshold:
                risk_percent = self.medium_confidence_risk
                confidence_tier = 'medium'
            else:
                risk_percent = self.low_confidence_risk
                confidence_tier = 'low'

            # Get direction
            direction = row['trade_direction']
            if direction == 'none':
                continue

            # Entry and targets (simplified - would need actual calculation)
            entry_price = row['price']
            stop_distance = entry_price * 0.001  # 0.1%

            if direction == 'long':
                stop_loss = entry_price - stop_distance
                tp1 = entry_price + (stop_distance * self.target_rr_ratios[0])
                tp2 = entry_price + (stop_distance * self.target_rr_ratios[1])
                tp3 = entry_price + (stop_distance * self.target_rr_ratios[2])
            else:
                stop_loss = entry_price + stop_distance
                tp1 = entry_price - (stop_distance * self.target_rr_ratios[0])
                tp2 = entry_price - (stop_distance * self.target_rr_ratios[1])
                tp3 = entry_price - (stop_distance * self.target_rr_ratios[2])

            signal = MLTradeSignal(
                timestamp=row['timestamp'],
                direction=direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit_1=tp1,
                take_profit_2=tp2,
                take_profit_3=tp3,
                ml_probability=ml_probability,
                risk_percent=risk_percent,
                confidence_tier=confidence_tier,
                features={}
            )

            signals.append(signal)

        print(f"Generated {len(signals)} trade signals")
        print(f"  High confidence: {sum(1 for s in signals if s.confidence_tier == 'high')}")
        print(f"  Medium confidence: {sum(1 for s in signals if s.confidence_tier == 'medium')}")
        print(f"  Low confidence: {sum(1 for s in signals if s.confidence_tier == 'low')}")

        return signals


def main():
    """Test the strategy"""
    print("=" * 80)
    print("ML INSTITUTIONAL STRATEGY TEST")
    print("=" * 80)

    # Initialize strategy
    strategy = MLInstitutionalStrategy()

    # Generate signals from predictions
    signals = strategy.generate_signals_from_predictions()

    print("\n" + "=" * 80)
    print("SAMPLE SIGNALS")
    print("=" * 80)

    for i, signal in enumerate(signals[:10], 1):
        print(f"\nSignal {i}:")
        print(f"  Timestamp: {signal.timestamp}")
        print(f"  Direction: {signal.direction}")
        print(f"  Entry: {signal.entry_price:.2f}")
        print(f"  Stop: {signal.stop_loss:.2f}")
        print(f"  TP1: {signal.take_profit_1:.2f}")
        print(f"  ML Probability: {signal.ml_probability:.4f}")
        print(f"  Confidence: {signal.confidence_tier}")
        print(f"  Risk: {signal.risk_percent*100:.2f}%")


if __name__ == "__main__":
    main()
