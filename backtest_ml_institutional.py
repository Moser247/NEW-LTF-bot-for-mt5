"""
BACKTEST ML INSTITUTIONAL STRATEGY

Walk-forward backtest of ML-enhanced institutional strategy
Calculates:
- Win rate
- Profit factor
- Weekly returns
- Max drawdown
- Sharpe ratio
- Total trades
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
import json


@dataclass
class Trade:
    """Trade record"""
    entry_time: datetime
    exit_time: datetime
    direction: str
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    pnl: float
    pnl_percent: float
    risk_percent: float
    ml_probability: float
    confidence_tier: str
    exit_reason: str  # 'tp1', 'tp2', 'tp3', 'stop_loss', 'timeout'


class MLBacktester:
    """
    Backtest ML institutional strategy with realistic execution
    """

    def __init__(
        self,
        initial_capital: float = 100000.0,
        max_position_size: float = 0.10,  # 10% of capital max
        max_daily_drawdown: float = 0.02,  # 2%
        max_concurrent_positions: int = 1,
        timeout_bars: int = 60,  # Close after 60 minutes if no TP/SL
    ):
        self.initial_capital = initial_capital
        self.max_position_size = max_position_size
        self.max_daily_drawdown = max_daily_drawdown
        self.max_concurrent_positions = max_concurrent_positions
        self.timeout_bars = timeout_bars

        self.trades: List[Trade] = []
        self.equity_curve = []

    def run_backtest(
        self,
        predictions_csv: str = '/home/user/NEW-LTF-bot-for-mt5/ml_predictions.csv',
        data_csv: str = '/home/user/NEW-LTF-bot-for-mt5/data/spx500_stooq_intraday.csv',
        min_ml_probability: float = 0.60,
        risk_per_trade_pct: float = 0.01,  # 1% base risk
    ):
        """
        Run backtest on historical data using ML predictions
        """
        print("=" * 80)
        print("ML INSTITUTIONAL STRATEGY BACKTEST")
        print("=" * 80)

        # Load predictions
        print(f"\nLoading predictions from {predictions_csv}...")
        df_pred = pd.read_csv(predictions_csv)
        df_pred['timestamp'] = pd.to_datetime(df_pred['timestamp'])
        df_pred = df_pred.sort_values('timestamp')

        # Load price data
        print(f"Loading price data from {data_csv}...")
        df_price = pd.read_csv(data_csv)
        df_price['Datetime'] = pd.to_datetime(df_price['Datetime'], utc=True)
        df_price = df_price.set_index('Datetime')

        print(f"Predictions: {len(df_pred)}")
        print(f"Price bars: {len(df_price)}")

        # Filter predictions by ML probability
        df_signals = df_pred[df_pred['ml_probability'] >= min_ml_probability].copy()
        print(f"\nSignals with probability >= {min_ml_probability}: {len(df_signals)}")

        # Initialize tracking
        capital = self.initial_capital
        peak_capital = capital
        daily_pnl = {}
        current_date = None
        daily_trades = 0
        open_positions = []

        # Process each signal
        print("\nProcessing signals...")

        for idx, signal_row in df_signals.iterrows():
            signal_time = signal_row['timestamp']
            signal_date = signal_time.date()

            # Reset daily counters
            if current_date != signal_date:
                current_date = signal_date
                daily_trades = 0
                daily_pnl[signal_date] = 0

            # Check daily drawdown limit
            if daily_pnl[signal_date] / capital < -self.max_daily_drawdown:
                continue

            # Check max concurrent positions
            if len(open_positions) >= self.max_concurrent_positions:
                continue

            # Skip if no clear direction
            if signal_row['trade_direction'] == 'none':
                continue

            # Get signal details
            direction = signal_row['trade_direction']
            entry_price = signal_row['price']
            ml_probability = signal_row['ml_probability']

            # Determine risk based on ML confidence
            if ml_probability >= 0.80:
                risk_percent = 0.015  # 1.5%
                confidence_tier = 'high'
            elif ml_probability >= 0.70:
                risk_percent = 0.010  # 1.0%
                confidence_tier = 'medium'
            else:
                risk_percent = 0.005  # 0.5%
                confidence_tier = 'low'

            # Calculate position size
            risk_amount = capital * risk_percent
            stop_distance = entry_price * 0.001  # 0.1% stop

            if direction == 'long':
                stop_loss = entry_price - stop_distance
                take_profit_1 = entry_price + (stop_distance * 1.5)
                take_profit_2 = entry_price + (stop_distance * 2.5)
                take_profit_3 = entry_price + (stop_distance * 4.0)
            else:  # short
                stop_loss = entry_price + stop_distance
                take_profit_1 = entry_price - (stop_distance * 1.5)
                take_profit_2 = entry_price - (stop_distance * 2.5)
                take_profit_3 = entry_price - (stop_distance * 4.0)

            # Find entry bar in price data
            try:
                entry_idx = df_price.index.get_indexer([signal_time], method='nearest')[0]
                if entry_idx < 0 or entry_idx >= len(df_price):
                    continue
            except:
                continue

            # Simulate trade execution
            trade = self.execute_trade(
                df_price=df_price,
                entry_idx=entry_idx,
                direction=direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit_1=take_profit_1,
                take_profit_2=take_profit_2,
                take_profit_3=take_profit_3,
                risk_percent=risk_percent,
                ml_probability=ml_probability,
                confidence_tier=confidence_tier
            )

            if trade:
                # Update capital
                capital += trade.pnl
                daily_pnl[signal_date] += trade.pnl
                peak_capital = max(peak_capital, capital)

                # Record equity
                self.equity_curve.append({
                    'timestamp': trade.exit_time,
                    'equity': capital,
                    'drawdown': (capital - peak_capital) / peak_capital
                })

                self.trades.append(trade)
                daily_trades += 1

        print(f"\n✓ Backtest complete")
        print(f"Total trades executed: {len(self.trades)}")

        return self.calculate_performance_metrics(capital)

    def execute_trade(
        self,
        df_price: pd.DataFrame,
        entry_idx: int,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: float,
        take_profit_3: float,
        risk_percent: float,
        ml_probability: float,
        confidence_tier: str
    ) -> Optional[Trade]:
        """
        Simulate trade execution with realistic fills
        """
        entry_time = df_price.index[entry_idx]

        # Look forward for exit
        max_idx = min(entry_idx + self.timeout_bars, len(df_price) - 1)

        for i in range(entry_idx + 1, max_idx + 1):
            bar = df_price.iloc[i]
            exit_time = df_price.index[i]

            if direction == 'long':
                # Check stop loss
                if bar['Low'] <= stop_loss:
                    exit_price = stop_loss
                    pnl_percent = (exit_price - entry_price) / entry_price
                    pnl = self.initial_capital * risk_percent * (pnl_percent / 0.001)

                    return Trade(
                        entry_time=entry_time,
                        exit_time=exit_time,
                        direction=direction,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit_1,
                        pnl=pnl,
                        pnl_percent=pnl_percent,
                        risk_percent=risk_percent,
                        ml_probability=ml_probability,
                        confidence_tier=confidence_tier,
                        exit_reason='stop_loss'
                    )

                # Check take profits
                if bar['High'] >= take_profit_3:
                    exit_price = take_profit_3
                    exit_reason = 'tp3'
                elif bar['High'] >= take_profit_2:
                    exit_price = take_profit_2
                    exit_reason = 'tp2'
                elif bar['High'] >= take_profit_1:
                    exit_price = take_profit_1
                    exit_reason = 'tp1'
                else:
                    continue

                pnl_percent = (exit_price - entry_price) / entry_price
                pnl = self.initial_capital * risk_percent * (pnl_percent / 0.001)

                return Trade(
                    entry_time=entry_time,
                    exit_time=exit_time,
                    direction=direction,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    stop_loss=stop_loss,
                    take_profit=exit_price,
                    pnl=pnl,
                    pnl_percent=pnl_percent,
                    risk_percent=risk_percent,
                    ml_probability=ml_probability,
                    confidence_tier=confidence_tier,
                    exit_reason=exit_reason
                )

            else:  # short
                # Check stop loss
                if bar['High'] >= stop_loss:
                    exit_price = stop_loss
                    pnl_percent = (entry_price - exit_price) / entry_price
                    pnl = self.initial_capital * risk_percent * (pnl_percent / 0.001)

                    return Trade(
                        entry_time=entry_time,
                        exit_time=exit_time,
                        direction=direction,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit_1,
                        pnl=pnl,
                        pnl_percent=pnl_percent,
                        risk_percent=risk_percent,
                        ml_probability=ml_probability,
                        confidence_tier=confidence_tier,
                        exit_reason='stop_loss'
                    )

                # Check take profits
                if bar['Low'] <= take_profit_3:
                    exit_price = take_profit_3
                    exit_reason = 'tp3'
                elif bar['Low'] <= take_profit_2:
                    exit_price = take_profit_2
                    exit_reason = 'tp2'
                elif bar['Low'] <= take_profit_1:
                    exit_price = take_profit_1
                    exit_reason = 'tp1'
                else:
                    continue

                pnl_percent = (entry_price - exit_price) / entry_price
                pnl = self.initial_capital * risk_percent * (pnl_percent / 0.001)

                return Trade(
                    entry_time=entry_time,
                    exit_time=exit_time,
                    direction=direction,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    stop_loss=stop_loss,
                    take_profit=exit_price,
                    pnl=pnl,
                    pnl_percent=pnl_percent,
                    risk_percent=risk_percent,
                    ml_probability=ml_probability,
                    confidence_tier=confidence_tier,
                    exit_reason=exit_reason
                )

        # Timeout - close at market
        final_bar = df_price.iloc[max_idx]
        exit_price = final_bar['Close']

        if direction == 'long':
            pnl_percent = (exit_price - entry_price) / entry_price
        else:
            pnl_percent = (entry_price - exit_price) / entry_price

        pnl = self.initial_capital * risk_percent * (pnl_percent / 0.001)

        return Trade(
            entry_time=entry_time,
            exit_time=df_price.index[max_idx],
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            stop_loss=stop_loss,
            take_profit=take_profit_1,
            pnl=pnl,
            pnl_percent=pnl_percent,
            risk_percent=risk_percent,
            ml_probability=ml_probability,
            confidence_tier=confidence_tier,
            exit_reason='timeout'
        )

    def calculate_performance_metrics(self, final_capital: float) -> Dict:
        """Calculate comprehensive performance metrics"""
        print("\n" + "=" * 80)
        print("PERFORMANCE METRICS")
        print("=" * 80)

        if len(self.trades) == 0:
            print("No trades executed!")
            return {}

        # Basic metrics
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl < 0]

        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0

        total_profit = sum(t.pnl for t in winning_trades)
        total_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

        net_pnl = final_capital - self.initial_capital
        total_return = net_pnl / self.initial_capital

        # Calculate max drawdown
        peak = self.initial_capital
        max_dd = 0
        for point in self.equity_curve:
            equity = point['equity']
            peak = max(peak, equity)
            dd = (equity - peak) / peak
            max_dd = min(max_dd, dd)

        # Calculate weekly returns
        # Group trades by week
        weekly_pnl = {}
        for trade in self.trades:
            week = trade.entry_time.isocalendar()[1]  # Week number
            year = trade.entry_time.year
            key = f"{year}-W{week}"
            if key not in weekly_pnl:
                weekly_pnl[key] = 0
            weekly_pnl[key] += trade.pnl

        weekly_returns = [pnl / self.initial_capital for pnl in weekly_pnl.values()]
        avg_weekly_return = np.mean(weekly_returns) if weekly_returns else 0
        max_weekly_return = max(weekly_returns) if weekly_returns else 0

        # Calculate Sharpe ratio (annualized)
        if len(weekly_returns) > 1:
            weekly_std = np.std(weekly_returns)
            sharpe = (avg_weekly_return / weekly_std * np.sqrt(52)) if weekly_std > 0 else 0
        else:
            sharpe = 0

        # Average trade metrics
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0

        # Exit reason breakdown
        exit_reasons = {}
        for trade in self.trades:
            reason = trade.exit_reason
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

        # Confidence tier breakdown
        tier_performance = {}
        for tier in ['high', 'medium', 'low']:
            tier_trades = [t for t in self.trades if t.confidence_tier == tier]
            if tier_trades:
                tier_wins = [t for t in tier_trades if t.pnl > 0]
                tier_performance[tier] = {
                    'trades': len(tier_trades),
                    'wins': len(tier_wins),
                    'win_rate': len(tier_wins) / len(tier_trades),
                    'total_pnl': sum(t.pnl for t in tier_trades),
                    'avg_pnl': np.mean([t.pnl for t in tier_trades])
                }

        # Print results
        print(f"\nTotal Trades: {total_trades}")
        print(f"Winning Trades: {len(winning_trades)} ({win_rate*100:.2f}%)")
        print(f"Losing Trades: {len(losing_trades)}")
        print(f"\nProfit Factor: {profit_factor:.2f}")
        print(f"Win Rate: {win_rate*100:.2f}%")
        print(f"\nTotal Return: ${net_pnl:,.2f} ({total_return*100:.2f}%)")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Final Capital: ${final_capital:,.2f}")
        print(f"\nMax Drawdown: {max_dd*100:.2f}%")
        print(f"\nWeekly Returns:")
        print(f"  Average: {avg_weekly_return*100:.2f}%")
        print(f"  Maximum: {max_weekly_return*100:.2f}%")
        print(f"  Number of weeks: {len(weekly_returns)}")
        print(f"\nSharpe Ratio: {sharpe:.2f}")
        print(f"\nAverage Win: ${avg_win:.2f}")
        print(f"Average Loss: ${avg_loss:.2f}")

        print(f"\nExit Reasons:")
        for reason, count in sorted(exit_reasons.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count} ({count/total_trades*100:.1f}%)")

        print(f"\nPerformance by Confidence Tier:")
        for tier in ['high', 'medium', 'low']:
            if tier in tier_performance:
                stats = tier_performance[tier]
                print(f"  {tier.upper()}: {stats['trades']} trades, "
                      f"WR: {stats['win_rate']*100:.1f}%, "
                      f"Total P/L: ${stats['total_pnl']:.2f}")

        # Return metrics dictionary
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_return_pct': total_return * 100,
            'max_drawdown_pct': max_dd * 100,
            'avg_weekly_return_pct': avg_weekly_return * 100,
            'max_weekly_return_pct': max_weekly_return * 100,
            'sharpe_ratio': sharpe,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'exit_reasons': exit_reasons,
            'tier_performance': tier_performance,
            'final_capital': final_capital
        }

    def save_results(self, metrics: Dict, filename: str = 'ml_backtest_results.json'):
        """Save backtest results"""
        # Save metrics
        with open(f'/home/user/NEW-LTF-bot-for-mt5/{filename}', 'w') as f:
            json.dump(metrics, f, indent=2)

        # Save trades
        trades_df = pd.DataFrame([asdict(t) for t in self.trades])
        trades_df.to_csv(f'/home/user/NEW-LTF-bot-for-mt5/ml_trades.csv', index=False)

        # Save equity curve
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df.to_csv(f'/home/user/NEW-LTF-bot-for-mt5/ml_equity_curve.csv', index=False)

        print(f"\n✓ Results saved to /home/user/NEW-LTF-bot-for-mt5/{filename}")
        print(f"✓ Trades saved to /home/user/NEW-LTF-bot-for-mt5/ml_trades.csv")
        print(f"✓ Equity curve saved to /home/user/NEW-LTF-bot-for-mt5/ml_equity_curve.csv")


def main():
    """Run backtest"""
    backtester = MLBacktester(
        initial_capital=100000.0,
        max_daily_drawdown=0.02,
        max_concurrent_positions=1
    )

    # Run with different ML probability thresholds
    for min_prob in [0.60, 0.70, 0.80]:
        print("\n" + "=" * 80)
        print(f"BACKTEST WITH ML PROBABILITY >= {min_prob}")
        print("=" * 80)

        metrics = backtester.run_backtest(
            min_ml_probability=min_prob
        )

        backtester.save_results(
            metrics,
            filename=f'ml_backtest_results_prob{int(min_prob*100)}.json'
        )

        # Reset for next run
        backtester.trades = []
        backtester.equity_curve = []


if __name__ == "__main__":
    main()
