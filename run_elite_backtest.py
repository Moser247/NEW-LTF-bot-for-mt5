"""
Comprehensive Backtest Runner for Elite Institutional Strategy

Multi-timeframe backtesting with detailed analytics
"""

import pandas as pd
import numpy as np
import sys
from datetime import datetime, timedelta
from typing import List, Dict

# Add src to path
sys.path.append('src')

from strategies.elite_institutional_strategy import EliteInstitutionalStrategy, TradeSignal
from backtesting.backtest_engine import SPX500Backtester, GuardianShieldSimulator


class EliteBacktestRunner:
    """
    Backtest runner for Elite Institutional Strategy
    """

    def __init__(
        self,
        initial_capital: float = 50000,
        risk_percent: float = 0.006,
        point_value: float = 50,
        enable_guardian_shield: bool = True
    ):
        self.initial_capital = initial_capital
        self.risk_percent = risk_percent
        self.point_value = point_value
        self.enable_guardian_shield = enable_guardian_shield

        # Initialize strategy
        self.strategy = EliteInstitutionalStrategy(
            risk_percent=risk_percent,
            min_confluence_score=4  # Require at least 4/7 confirmations
        )

        # Backtester will be created when needed (with actual data)
        self.backtester = None

        # Results storage
        self.trades = []
        self.daily_stats = []

    def execute_signal(
        self,
        signal: TradeSignal,
        data_1m: pd.DataFrame
    ) -> Dict:
        """
        Execute a trade signal with multi-target management

        Args:
            signal: TradeSignal to execute
            data_1m: 1-minute data for tracking

        Returns:
            Trade result dictionary
        """
        entry_price = signal.entry_price
        stop_loss = signal.stop_loss
        direction = signal.direction
        entry_time = signal.timestamp

        # Calculate position size
        stop_distance = abs(entry_price - stop_loss)

        risk_amount = self.initial_capital * self.risk_percent
        lot_size = risk_amount / (stop_distance * self.point_value)
        lot_size = round(lot_size, 2)

        # Guardian Shield check - don't risk more than 90% of shield limit
        if self.enable_guardian_shield:
            max_loss = lot_size * stop_distance * self.point_value
            shield_limit = self.initial_capital * 0.02 * 0.9  # 90% of 2% shield
            if max_loss > shield_limit:
                lot_size = shield_limit / (stop_distance * self.point_value)
                lot_size = round(lot_size, 2)

        if lot_size <= 0:
            return None  # Can't trade

        # Track the trade through the data
        # Entry is at signal timestamp
        entry_idx = data_1m.index.get_loc(entry_time)

        # Track multi-target exits
        remaining_lots = lot_size
        partial_exits = []
        total_pnl = 0
        exit_time = None
        exit_reason = "NONE"

        # Maximum holding period: Until 3:50 PM same day
        max_exit_time = entry_time.replace(hour=15, minute=50)

        tp1_hit = False
        tp2_hit = False
        breakeven_moved = False

        # Scan forward from entry
        for i in range(entry_idx + 1, len(data_1m)):
            bar = data_1m.iloc[i]
            bar_time = data_1m.index[i]

            # Check time stop
            if bar_time >= max_exit_time:
                # Close remaining position
                if remaining_lots > 0:
                    exit_price = bar['Close']
                    if direction == 'long':
                        pnl = (exit_price - entry_price) * remaining_lots * self.point_value
                    else:
                        pnl = (entry_price - exit_price) * remaining_lots * self.point_value

                    total_pnl += pnl
                    partial_exits.append({
                        'lots': remaining_lots,
                        'price': exit_price,
                        'pnl': pnl,
                        'reason': 'TIME_STOP'
                    })
                    remaining_lots = 0
                exit_time = bar_time
                exit_reason = "TIME_STOP"
                break

            # LONG trade logic
            if direction == 'long':
                # Check stop loss
                if bar['Low'] <= stop_loss:
                    # Stopped out
                    pnl = (stop_loss - entry_price) * remaining_lots * self.point_value
                    total_pnl += pnl
                    partial_exits.append({
                        'lots': remaining_lots,
                        'price': stop_loss,
                        'pnl': pnl,
                        'reason': 'STOP_LOSS'
                    })
                    remaining_lots = 0
                    exit_time = bar_time
                    exit_reason = "STOP_LOSS"
                    break

                # Check TP1 (40% of position)
                if not tp1_hit and bar['High'] >= signal.take_profit_1:
                    exit_lots = lot_size * 0.4
                    pnl = (signal.take_profit_1 - entry_price) * exit_lots * self.point_value
                    total_pnl += pnl
                    partial_exits.append({
                        'lots': exit_lots,
                        'price': signal.take_profit_1,
                        'pnl': pnl,
                        'reason': 'TP1'
                    })
                    remaining_lots -= exit_lots
                    tp1_hit = True
                    # Move stop to breakeven
                    stop_loss = entry_price
                    breakeven_moved = True

                # Check TP2 (30% of position)
                if tp1_hit and not tp2_hit and bar['High'] >= signal.take_profit_2:
                    exit_lots = lot_size * 0.3
                    pnl = (signal.take_profit_2 - entry_price) * exit_lots * self.point_value
                    total_pnl += pnl
                    partial_exits.append({
                        'lots': exit_lots,
                        'price': signal.take_profit_2,
                        'pnl': pnl,
                        'reason': 'TP2'
                    })
                    remaining_lots -= exit_lots
                    tp2_hit = True
                    # Trail stop to TP1
                    stop_loss = signal.take_profit_1

                # Check TP3 (remaining 30%)
                if tp2_hit and bar['High'] >= signal.take_profit_3:
                    exit_lots = remaining_lots
                    pnl = (signal.take_profit_3 - entry_price) * exit_lots * self.point_value
                    total_pnl += pnl
                    partial_exits.append({
                        'lots': exit_lots,
                        'price': signal.take_profit_3,
                        'pnl': pnl,
                        'reason': 'TP3'
                    })
                    remaining_lots = 0
                    exit_time = bar_time
                    exit_reason = "TP3_FULL_TARGET"
                    break

            # SHORT trade logic
            else:  # direction == 'short'
                # Check stop loss
                if bar['High'] >= stop_loss:
                    # Stopped out
                    pnl = (entry_price - stop_loss) * remaining_lots * self.point_value
                    total_pnl += pnl
                    partial_exits.append({
                        'lots': remaining_lots,
                        'price': stop_loss,
                        'pnl': pnl,
                        'reason': 'STOP_LOSS'
                    })
                    remaining_lots = 0
                    exit_time = bar_time
                    exit_reason = "STOP_LOSS"
                    break

                # Check TP1 (40% of position)
                if not tp1_hit and bar['Low'] <= signal.take_profit_1:
                    exit_lots = lot_size * 0.4
                    pnl = (entry_price - signal.take_profit_1) * exit_lots * self.point_value
                    total_pnl += pnl
                    partial_exits.append({
                        'lots': exit_lots,
                        'price': signal.take_profit_1,
                        'pnl': pnl,
                        'reason': 'TP1'
                    })
                    remaining_lots -= exit_lots
                    tp1_hit = True
                    # Move stop to breakeven
                    stop_loss = entry_price
                    breakeven_moved = True

                # Check TP2 (30% of position)
                if tp1_hit and not tp2_hit and bar['Low'] <= signal.take_profit_2:
                    exit_lots = lot_size * 0.3
                    pnl = (entry_price - signal.take_profit_2) * exit_lots * self.point_value
                    total_pnl += pnl
                    partial_exits.append({
                        'lots': exit_lots,
                        'price': signal.take_profit_2,
                        'pnl': pnl,
                        'reason': 'TP2'
                    })
                    remaining_lots -= exit_lots
                    tp2_hit = True
                    # Trail stop to TP1
                    stop_loss = signal.take_profit_1

                # Check TP3 (remaining 30%)
                if tp2_hit and bar['Low'] <= signal.take_profit_3:
                    exit_lots = remaining_lots
                    pnl = (entry_price - signal.take_profit_3) * exit_lots * self.point_value
                    total_pnl += pnl
                    partial_exits.append({
                        'lots': exit_lots,
                        'price': signal.take_profit_3,
                        'pnl': pnl,
                        'reason': 'TP3'
                    })
                    remaining_lots = 0
                    exit_time = bar_time
                    exit_reason = "TP3_FULL_TARGET"
                    break

        # If still in trade at end of data, close it
        if remaining_lots > 0 and exit_time is None:
            exit_price = data_1m['Close'].iloc[-1]
            if direction == 'long':
                pnl = (exit_price - entry_price) * remaining_lots * self.point_value
            else:
                pnl = (entry_price - exit_price) * remaining_lots * self.point_value

            total_pnl += pnl
            partial_exits.append({
                'lots': remaining_lots,
                'price': exit_price,
                'pnl': pnl,
                'reason': 'END_OF_DATA'
            })
            exit_time = data_1m.index[-1]
            exit_reason = "END_OF_DATA"

        # Determine final exit price (weighted average of partial exits)
        total_lots_exited = sum([e['lots'] for e in partial_exits])
        if total_lots_exited > 0:
            avg_exit_price = sum([e['price'] * e['lots'] for e in partial_exits]) / total_lots_exited
        else:
            avg_exit_price = entry_price

        # Build trade result
        trade_result = {
            'entry_time': entry_time,
            'exit_time': exit_time,
            'direction': direction,
            'entry_price': entry_price,
            'exit_price': avg_exit_price,
            'stop_loss': signal.stop_loss,
            'lot_size': lot_size,
            'pnl': total_pnl,
            'pnl_percent': (total_pnl / self.initial_capital) * 100,
            'exit_reason': exit_reason,
            'confluence_score': signal.confluence_score,
            'confirmations': signal.confirmations,
            'partial_exits': partial_exits,
            'tp1_hit': tp1_hit,
            'tp2_hit': tp2_hit,
            'breakeven_moved': breakeven_moved,
            'r_multiple': total_pnl / (abs(entry_price - signal.stop_loss) * lot_size * self.point_value)
            if abs(entry_price - signal.stop_loss) > 0 else 0
        }

        return trade_result

    def run_backtest(
        self,
        data_15m: pd.DataFrame,
        data_5m: pd.DataFrame,
        data_1m: pd.DataFrame
    ):
        """
        Run full backtest on multi-timeframe data

        Args:
            data_15m: 15-minute data
            data_5m: 5-minute data
            data_1m: 1-minute data
        """
        print("\n" + "="*60)
        print("ELITE INSTITUTIONAL STRATEGY BACKTEST")
        print("="*60)

        print(f"\n📊 Data Summary:")
        print(f"   15-min bars: {len(data_15m)}")
        print(f"   5-min bars: {len(data_5m)}")
        print(f"   1-min bars: {len(data_1m)}")
        print(f"   Date range: {data_1m.index[0].date()} to {data_1m.index[-1].date()}")
        print(f"   Trading days: {len(set([d.date() for d in data_1m.index]))}")

        print(f"\n⚙️  Strategy Configuration:")
        print(f"   Min Confluence Score: {self.strategy.min_confluence_score}/7")
        print(f"   Risk per Trade: {self.risk_percent*100}%")
        print(f"   Target R:R Ratios: {self.strategy.target_rr_ratios}")
        print(f"   Guardian Shield: {'Enabled' if self.enable_guardian_shield else 'Disabled'}")

        # Generate signals
        print(f"\n🔍 Generating trade signals...")
        signals = self.strategy.generate_signals(data_15m, data_5m, data_1m, self.backtester)

        print(f"   Found {len(signals)} high-probability setups")

        if len(signals) == 0:
            print("\n⚠️  No signals generated. Strategy may be too restrictive.")
            return

        # Show signal distribution by confluence score
        confluence_dist = {}
        for sig in signals:
            score = sig.confluence_score
            confluence_dist[score] = confluence_dist.get(score, 0) + 1

        print(f"\n   Confluence Score Distribution:")
        for score in sorted(confluence_dist.keys(), reverse=True):
            print(f"      {score}/7: {confluence_dist[score]} signals")

        # Execute trades
        # Create guardian shield simulator
        guardian_shield = None
        if self.enable_guardian_shield:
            guardian_shield = GuardianShieldSimulator(self.initial_capital, 0.02)

        print(f"\n⚡ Executing trades...")
        equity_curve = [self.initial_capital]
        current_equity = self.initial_capital

        for i, signal in enumerate(signals):
            print(f"   Trade {i+1}/{len(signals)}: {signal.direction.upper()} @ {signal.entry_price:.2f} (score: {signal.confluence_score}/7)", end="")

            trade_result = self.execute_signal(signal, data_1m)

            if trade_result:
                self.trades.append(trade_result)
                current_equity += trade_result['pnl']
                equity_curve.append(current_equity)

                # Check Guardian Shield
                if guardian_shield:
                    unrealized_loss = -trade_result['pnl'] if trade_result['pnl'] < 0 else 0
                    shield_triggered, msg = guardian_shield.check_shield(unrealized_loss)

                    if shield_triggered:
                        print(f" ❌ {msg}")
                        break

                if trade_result['pnl'] > 0:
                    print(f" ✅ +${trade_result['pnl']:.2f} ({trade_result['exit_reason']})")
                else:
                    print(f" ❌ ${trade_result['pnl']:.2f} ({trade_result['exit_reason']})")
            else:
                print(" ⏭️  Skipped (position sizing)")

        # Store guardian shield for statistics
        self.guardian_shield = guardian_shield

        # Calculate statistics
        self.calculate_statistics(equity_curve)

    def calculate_statistics(self, equity_curve: List[float]):
        """Calculate and display comprehensive statistics"""

        if len(self.trades) == 0:
            print("\n⚠️  No trades executed.")
            return

        trades_df = pd.DataFrame(self.trades)

        # Basic stats
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])
        breakeven_trades = len(trades_df[trades_df['pnl'] == 0])

        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0

        total_pnl = trades_df['pnl'].sum()
        total_return = (total_pnl / self.initial_capital) * 100

        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].mean()) if losing_trades > 0 else 0

        largest_win = trades_df['pnl'].max() if len(trades_df) > 0 else 0
        largest_loss = trades_df['pnl'].min() if len(trades_df) > 0 else 0

        # Profit factor
        gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum() if winning_trades > 0 else 0
        gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum()) if losing_trades > 0 else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Sharpe ratio
        returns = trades_df['pnl'] / self.initial_capital
        sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0

        # Max drawdown
        equity_series = pd.Series(equity_curve)
        running_max = equity_series.cummax()
        drawdown = equity_series - running_max
        max_drawdown = drawdown.min()
        max_drawdown_pct = (max_drawdown / self.initial_capital) * 100

        # Average R-multiple
        avg_r = trades_df['r_multiple'].mean()

        # Consecutive stats
        win_streaks = []
        loss_streaks = []
        current_streak = 0
        last_result = None

        for pnl in trades_df['pnl']:
            if pnl > 0:
                if last_result == 'win':
                    current_streak += 1
                else:
                    if last_result == 'loss' and current_streak > 0:
                        loss_streaks.append(current_streak)
                    current_streak = 1
                last_result = 'win'
            else:
                if last_result == 'loss':
                    current_streak += 1
                else:
                    if last_result == 'win' and current_streak > 0:
                        win_streaks.append(current_streak)
                    current_streak = 1
                last_result = 'loss'

        if last_result == 'win' and current_streak > 0:
            win_streaks.append(current_streak)
        elif last_result == 'loss' and current_streak > 0:
            loss_streaks.append(current_streak)

        max_win_streak = max(win_streaks) if win_streaks else 0
        max_loss_streak = max(loss_streaks) if loss_streaks else 0

        # TP hit rates
        tp1_hit_rate = (trades_df['tp1_hit'].sum() / total_trades) * 100
        tp2_hit_rate = (trades_df['tp2_hit'].sum() / total_trades) * 100

        # Display results
        print("\n" + "="*60)
        print("BACKTEST RESULTS")
        print("="*60)

        print(f"\n📊 TRADE STATISTICS:")
        print(f"Total Trades:        {total_trades}")
        print(f"Winning Trades:      {winning_trades}")
        print(f"Losing Trades:       {losing_trades}")
        print(f"Breakeven Trades:    {breakeven_trades}")
        print(f"Win Rate:            {win_rate:.2f}%")

        print(f"\n💰 PROFIT & LOSS:")
        print(f"Total P&L:           ${total_pnl:.2f}")
        print(f"Total Return:        {total_return:.2f}%")
        print(f"Final Equity:        ${self.initial_capital + total_pnl:.2f}")
        print(f"Average Win:         ${avg_win:.2f}")
        print(f"Average Loss:        ${avg_loss:.2f}")
        print(f"Largest Win:         ${largest_win:.2f}")
        print(f"Largest Loss:        ${largest_loss:.2f}")
        print(f"Average R-Multiple:  {avg_r:.2f}R")

        print(f"\n📈 PERFORMANCE METRICS:")
        print(f"Profit Factor:       {profit_factor:.2f}")
        print(f"Sharpe Ratio:        {sharpe_ratio:.2f}")
        print(f"Max Drawdown:        ${max_drawdown:.2f} ({max_drawdown_pct:.2f}%)")
        print(f"Max Win Streak:      {max_win_streak}")
        print(f"Max Loss Streak:     {max_loss_streak}")

        print(f"\n🎯 TARGET ACHIEVEMENT:")
        print(f"TP1 Hit Rate:        {tp1_hit_rate:.1f}%")
        print(f"TP2 Hit Rate:        {tp2_hit_rate:.1f}%")

        # Guardian Shield check
        print(f"\n⚠️  RISK MANAGEMENT:")
        if self.enable_guardian_shield and self.guardian_shield:
            print(f"Guardian Shield Triggers: {self.guardian_shield.breaches}")
            print(f"Daily Loss Limit Hits:    N/A")  # Would need daily tracking
            print(f"Max Drawdown Hits:        {'YES ⚠️' if abs(max_drawdown_pct) > 8 else 'NO ✅'}")
            print(f"Account Blown:            {'YES ❌' if self.guardian_shield.breaches >= 2 else 'NO ✅'}")
        else:
            print("Guardian Shield: DISABLED")

        # Assessment
        print(f"\n🏆 ASSESSMENT:")
        if win_rate >= 70 and profit_factor >= 2.0 and abs(max_drawdown_pct) < 4:
            assessment = "✅ EXCELLENT - Strategy meets all targets"
        elif win_rate >= 65 and profit_factor >= 1.8 and abs(max_drawdown_pct) < 4:
            assessment = "✅ GOOD - Strategy meets minimum requirements"
        elif win_rate >= 60 and profit_factor >= 1.5:
            assessment = "⚠️  ACCEPTABLE - Needs refinement"
        else:
            assessment = "❌ POOR - Significant revision needed"

        print(f"   {assessment}")

        # Weekly projection
        days_tested = len(set([d.date() for d in pd.to_datetime(trades_df['entry_time'])]))
        trades_per_day = total_trades / days_tested if days_tested > 0 else 0
        trades_per_week = trades_per_day * 5

        print(f"\n📅 TRADE FREQUENCY:")
        print(f"   Days Tested: {days_tested}")
        print(f"   Trades per Day: {trades_per_day:.1f}")
        print(f"   Trades per Week: {trades_per_week:.1f}")
        if trades_per_week > 15:
            print(f"   ⚠️  Exceeds 15 trades/week target - consider stricter filtering")
        else:
            print(f"   ✅ Within 15 trades/week target")

        print("\n" + "="*60)


def main():
    """Run elite strategy backtest"""

    print("\n" + "="*60)
    print("LOADING MULTI-TIMEFRAME DATA")
    print("="*60)

    # Load data
    print("\n📂 Loading data files...")
    data_15m = pd.read_csv('data/spx500_15min_data.csv', index_col=0)
    data_15m.index = pd.to_datetime(data_15m.index, utc=True).tz_convert('America/New_York')

    data_5m = pd.read_csv('data/spx500_5min_data.csv', index_col=0)
    data_5m.index = pd.to_datetime(data_5m.index, utc=True).tz_convert('America/New_York')

    data_1m = pd.read_csv('data/spx500_1min_data.csv', index_col=0)
    data_1m.index = pd.to_datetime(data_1m.index, utc=True).tz_convert('America/New_York')

    print(f"✅ Data loaded successfully")

    # Initialize backtester
    runner = EliteBacktestRunner(
        initial_capital=50000,
        risk_percent=0.006,
        point_value=50,
        enable_guardian_shield=True
    )

    # Run backtest
    runner.run_backtest(data_15m, data_5m, data_1m)


if __name__ == "__main__":
    main()
