"""
Backtesting Engine for SPX500 Trading Strategies
Designed for Blue Guardian prop firm with Guardian Shield simulation
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class GuardianShieldSimulator:
    """Simulates Blue Guardian's Guardian Shield 2% auto-close feature"""

    def __init__(self, account_size: float = 50000, shield_percent: float = 0.02):
        self.account_size = account_size
        self.shield_percent = shield_percent
        self.shield_limit = account_size * shield_percent  # $1,000 for $50K
        self.breaches = 0
        self.max_breaches = 2

    def check_shield(self, unrealized_pnl: float) -> Tuple[bool, str]:
        """
        Check if Guardian Shield should trigger

        Args:
            unrealized_pnl: Current unrealized P&L (negative = loss)

        Returns:
            (should_close, reason)
        """
        if unrealized_pnl <= -self.shield_limit:
            self.breaches += 1

            if self.breaches >= self.max_breaches:
                return True, f"ACCOUNT BLOWN - {self.breaches} Guardian Shield breaches"
            else:
                return True, f"Guardian Shield triggered - Breach #{self.breaches}"

        return False, ""

    def reset_daily(self):
        """Reset for new trading day"""
        pass  # Guardian Shield tracks account-wide, not daily

    def is_account_blown(self) -> bool:
        """Check if account is blown (2 breaches)"""
        return self.breaches >= self.max_breaches


class PerformanceMetrics:
    """Calculate comprehensive performance metrics"""

    @staticmethod
    def calculate_metrics(trades_df: pd.DataFrame, initial_capital: float) -> Dict:
        """Calculate all performance metrics"""

        if len(trades_df) == 0:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'total_return': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'max_drawdown_pct': 0,
            }

        # Basic stats
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # P&L stats
        total_pnl = trades_df['pnl'].sum()
        total_return = (total_pnl / initial_capital) * 100

        wins = trades_df[trades_df['pnl'] > 0]['pnl']
        losses = trades_df[trades_df['pnl'] < 0]['pnl']

        avg_win = wins.mean() if len(wins) > 0 else 0
        avg_loss = abs(losses.mean()) if len(losses) > 0 else 0

        # Profit factor
        gross_profit = wins.sum() if len(wins) > 0 else 0
        gross_loss = abs(losses.sum()) if len(losses) > 0 else 1  # Avoid division by zero
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Drawdown
        trades_df['cumulative_pnl'] = trades_df['pnl'].cumsum()
        trades_df['equity'] = initial_capital + trades_df['cumulative_pnl']
        trades_df['peak_equity'] = trades_df['equity'].cummax()
        trades_df['drawdown'] = trades_df['equity'] - trades_df['peak_equity']
        trades_df['drawdown_pct'] = (trades_df['drawdown'] / trades_df['peak_equity']) * 100

        max_drawdown = trades_df['drawdown'].min()
        max_drawdown_pct = trades_df['drawdown_pct'].min()

        # Sharpe Ratio (simplified - daily returns)
        daily_returns = trades_df.groupby(trades_df['exit_time'].dt.date)['pnl'].sum()
        daily_returns_pct = daily_returns / initial_capital

        sharpe_ratio = 0
        if len(daily_returns_pct) > 1 and daily_returns_pct.std() > 0:
            sharpe_ratio = (daily_returns_pct.mean() / daily_returns_pct.std()) * np.sqrt(252)

        # Consecutive wins/losses
        trades_df['win'] = trades_df['pnl'] > 0
        trades_df['streak'] = (trades_df['win'] != trades_df['win'].shift()).cumsum()

        win_streaks = trades_df[trades_df['win']].groupby('streak').size()
        loss_streaks = trades_df[~trades_df['win']].groupby('streak').size()

        max_win_streak = win_streaks.max() if len(win_streaks) > 0 else 0
        max_loss_streak = loss_streaks.max() if len(loss_streaks) > 0 else 0

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate * 100,
            'total_pnl': total_pnl,
            'total_return': total_return,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': wins.max() if len(wins) > 0 else 0,
            'largest_loss': losses.min() if len(losses) > 0 else 0,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'max_win_streak': max_win_streak,
            'max_loss_streak': max_loss_streak,
            'final_equity': initial_capital + total_pnl,
        }


class SPX500Backtester:
    """
    Backtest SPX500 trading strategies with Blue Guardian constraints
    """

    def __init__(
        self,
        data: pd.DataFrame,
        initial_capital: float = 50000,
        risk_percent: float = 0.006,  # 0.6%
        point_value: float = 50,  # $50 per point for 1.0 lot
        enable_guardian_shield: bool = True,
        daily_loss_limit_pct: float = 0.04,  # 4%
        max_drawdown_pct: float = 0.08,  # 8%
    ):
        """
        Initialize backtester

        Args:
            data: OHLCV dataframe with DatetimeIndex
            initial_capital: Starting account balance
            risk_percent: Risk per trade as decimal (0.006 = 0.6%)
            point_value: Dollar value per point (depends on lot size)
            enable_guardian_shield: Enable 2% auto-close simulation
            daily_loss_limit_pct: Daily loss limit (0.04 = 4%)
            max_drawdown_pct: Maximum drawdown limit (0.08 = 8%)
        """
        self.data = data.copy()
        self.initial_capital = initial_capital
        self.risk_percent = risk_percent
        self.point_value = point_value
        self.enable_guardian_shield = enable_guardian_shield
        self.daily_loss_limit = initial_capital * daily_loss_limit_pct
        self.max_drawdown_limit = initial_capital * max_drawdown_pct

        # Trading state
        self.equity = initial_capital
        self.peak_equity = initial_capital
        self.daily_pnl = 0
        self.current_date = None

        # Position tracking
        self.positions = []  # Open positions
        self.trades = []  # Completed trades

        # Guardian Shield
        self.guardian_shield = GuardianShieldSimulator(
            initial_capital, 0.02
        ) if enable_guardian_shield else None

        # Statistics
        self.guardian_shield_triggers = 0
        self.daily_loss_limit_hits = 0
        self.max_drawdown_hits = 0

    def calculate_position_size(self, stop_loss_points: float) -> float:
        """
        Calculate position size (lot size) based on risk

        Args:
            stop_loss_points: Distance to stop loss in points

        Returns:
            Lot size (e.g., 0.5 lots)
        """
        risk_amount = self.equity * self.risk_percent
        lots = risk_amount / (stop_loss_points * self.point_value)

        # Round down to 2 decimals (typical broker minimum 0.01)
        lots = round(lots, 2)

        # Guardian Shield check - ensure max loss < shield limit
        if self.guardian_shield:
            max_loss = lots * self.point_value * stop_loss_points
            shield_limit = self.guardian_shield.shield_limit * 0.9  # Stay at 90%

            if max_loss > shield_limit:
                lots = shield_limit / (stop_loss_points * self.point_value)
                lots = round(lots, 2)

        return lots

    def check_stop_loss(self, position: Dict, current_bar: pd.Series) -> bool:
        """Check if stop loss is hit"""
        if position['direction'] == 'long':
            return current_bar['Low'] <= position['stop_loss']
        else:  # short
            return current_bar['High'] >= position['stop_loss']

    def check_take_profit(self, position: Dict, current_bar: pd.Series) -> bool:
        """Check if take profit is hit"""
        if position['direction'] == 'long':
            return current_bar['High'] >= position['take_profit']
        else:  # short
            return current_bar['Low'] <= position['take_profit']

    def close_position(self, position: Dict, exit_price: float, exit_time: datetime, reason: str):
        """Close a position and record trade"""
        # Calculate P&L
        if position['direction'] == 'long':
            points = exit_price - position['entry_price']
        else:  # short
            points = position['entry_price'] - exit_price

        pnl = points * self.point_value * position['lots']

        # Update equity
        self.equity += pnl
        self.daily_pnl += pnl

        # Record trade
        trade = {
            'entry_time': position['entry_time'],
            'exit_time': exit_time,
            'direction': position['direction'],
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'stop_loss': position['stop_loss'],
            'take_profit': position['take_profit'],
            'lots': position['lots'],
            'points': points,
            'pnl': pnl,
            'reason': reason,
            'strategy': position['strategy'],
        }

        self.trades.append(trade)

        # Remove from open positions
        self.positions.remove(position)

        return pnl

    def check_guardian_shield(self) -> bool:
        """Check if Guardian Shield should trigger"""
        if not self.guardian_shield:
            return False

        # Calculate unrealized P&L
        unrealized_pnl = sum(pos.get('unrealized_pnl', 0) for pos in self.positions)

        should_close, reason = self.guardian_shield.check_shield(unrealized_pnl)

        if should_close:
            self.guardian_shield_triggers += 1
            print(f"⚠️  GUARDIAN SHIELD TRIGGERED: {reason}")

            # Close all positions
            for pos in self.positions.copy():
                # Use current market price to close
                self.close_position(
                    pos,
                    pos.get('current_price', pos['entry_price']),
                    datetime.now(),
                    f"Guardian Shield: {reason}"
                )

            return self.guardian_shield.is_account_blown()

        return False

    def check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit is hit"""
        if self.daily_pnl < -self.daily_loss_limit:
            self.daily_loss_limit_hits += 1
            print(f"⚠️  DAILY LOSS LIMIT HIT: ${self.daily_pnl:.2f}")

            # Close all positions
            for pos in self.positions.copy():
                self.close_position(
                    pos,
                    pos.get('current_price', pos['entry_price']),
                    datetime.now(),
                    "Daily loss limit"
                )

            return True

        return False

    def check_max_drawdown(self) -> bool:
        """Check if max drawdown limit is hit"""
        self.peak_equity = max(self.peak_equity, self.equity)
        current_drawdown = self.peak_equity - self.equity

        if current_drawdown > self.max_drawdown_limit:
            self.max_drawdown_hits += 1
            print(f"⚠️  MAX DRAWDOWN LIMIT HIT: ${current_drawdown:.2f}")

            # Close all positions and stop trading
            for pos in self.positions.copy():
                self.close_position(
                    pos,
                    pos.get('current_price', pos['entry_price']),
                    datetime.now(),
                    "Max drawdown limit"
                )

            return True

        return False

    def new_day_reset(self):
        """Reset daily tracking"""
        self.daily_pnl = 0

    def get_results(self) -> Dict:
        """Get backtest results"""
        trades_df = pd.DataFrame(self.trades)

        if len(trades_df) == 0:
            return {
                'metrics': PerformanceMetrics.calculate_metrics(trades_df, self.initial_capital),
                'trades': trades_df,
                'guardian_shield_triggers': self.guardian_shield_triggers,
                'daily_loss_limit_hits': self.daily_loss_limit_hits,
                'max_drawdown_hits': self.max_drawdown_hits,
                'account_blown': self.guardian_shield.is_account_blown() if self.guardian_shield else False,
            }

        metrics = PerformanceMetrics.calculate_metrics(trades_df, self.initial_capital)

        return {
            'metrics': metrics,
            'trades': trades_df,
            'guardian_shield_triggers': self.guardian_shield_triggers,
            'daily_loss_limit_hits': self.daily_loss_limit_hits,
            'max_drawdown_hits': self.max_drawdown_hits,
            'account_blown': self.guardian_shield.is_account_blown() if self.guardian_shield else False,
        }

    def print_results(self):
        """Print formatted results"""
        results = self.get_results()
        metrics = results['metrics']

        print("\n" + "="*60)
        print("BACKTEST RESULTS")
        print("="*60)

        print(f"\n📊 TRADE STATISTICS:")
        print(f"Total Trades:        {metrics['total_trades']}")
        print(f"Winning Trades:      {metrics['winning_trades']}")
        print(f"Losing Trades:       {metrics['losing_trades']}")
        print(f"Win Rate:            {metrics['win_rate']:.2f}%")

        print(f"\n💰 PROFIT & LOSS:")
        print(f"Total P&L:           ${metrics['total_pnl']:,.2f}")
        print(f"Total Return:        {metrics['total_return']:.2f}%")
        print(f"Final Equity:        ${metrics['final_equity']:,.2f}")
        print(f"Average Win:         ${metrics['avg_win']:.2f}")
        print(f"Average Loss:        ${metrics['avg_loss']:.2f}")
        print(f"Largest Win:         ${metrics['largest_win']:.2f}")
        print(f"Largest Loss:        ${metrics['largest_loss']:.2f}")

        print(f"\n📈 PERFORMANCE METRICS:")
        print(f"Profit Factor:       {metrics['profit_factor']:.2f}")
        print(f"Sharpe Ratio:        {metrics['sharpe_ratio']:.2f}")
        print(f"Max Drawdown:        ${metrics['max_drawdown']:,.2f} ({metrics['max_drawdown_pct']:.2f}%)")
        print(f"Max Win Streak:      {metrics['max_win_streak']}")
        print(f"Max Loss Streak:     {metrics['max_loss_streak']}")

        print(f"\n⚠️  RISK MANAGEMENT:")
        print(f"Guardian Shield Triggers: {results['guardian_shield_triggers']}")
        print(f"Daily Loss Limit Hits:    {results['daily_loss_limit_hits']}")
        print(f"Max Drawdown Hits:        {results['max_drawdown_hits']}")
        print(f"Account Blown:            {'YES ❌' if results['account_blown'] else 'NO ✅'}")

        print("\n" + "="*60)
