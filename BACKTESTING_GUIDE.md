# SPX500 Backtesting Guide

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** If you have issues with ta-lib, you can comment it out in requirements.txt - it's not critical for the core strategies.

### 2. Run Backtest

```bash
python run_backtest.py
```

This will:
- Download last 60 days of SPY 5-minute data (converted to SPX500)
- Run Opening Range Breakout (ORB) strategy backtest
- Run VWAP Mean Reversion strategy backtest
- Display comprehensive results

---

## What Gets Tested

### Blue Guardian Constraints

The backtester simulates ALL Blue Guardian rules:

✅ **Guardian Shield**: 2% unrealized loss = auto-close ($1,000 on $50K)
✅ **Daily Loss Limit**: 4% max per day ($2,000)
✅ **Max Drawdown**: 8% total ($4,000)
✅ **Position Sizing**: 0.6% risk per trade ($300)

### Strategies Tested

**1. Opening Range Breakout (ORB)**
- 15-minute opening range (9:30-9:45 AM)
- Breakout entries with 2-point buffer
- 15-point stops typical
- 1.5:1 to 2:1 risk-reward
- Target win rate: 70-80%

**2. VWAP Mean Reversion**
- 0.3-0.5% deviation from VWAP
- Rejection candle confirmation
- 8-12 point stops
- Target back to VWAP
- Target win rate: 70%+

---

## Output Explanation

### Trade Statistics

```
Total Trades:        50
Winning Trades:      38
Losing Trades:       12
Win Rate:            76.00%
```

**What to look for:**
- Win rate > 70% ✅
- Win rate < 65% ⚠️ (strategy may need adjustment)

### Profit & Loss

```
Total P&L:           $4,523.45
Total Return:        9.05%
Final Equity:        $54,523.45
Average Win:         $245.00
Average Loss:        $285.00
```

**What to look for:**
- Positive total return ✅
- Average win close to or greater than average loss ✅
- On track for 10% target (5-10 weeks) ✅

### Performance Metrics

```
Profit Factor:       2.15
Sharpe Ratio:        1.85
Max Drawdown:        -$1,234.56 (-2.47%)
```

**What to look for:**
- Profit Factor > 1.5 ✅ (2.0+ excellent)
- Sharpe Ratio > 1.5 ✅ (risk-adjusted returns good)
- Max Drawdown < 4% ✅ (CRITICAL for Blue Guardian!)

### Risk Management

```
Guardian Shield Triggers: 0
Daily Loss Limit Hits:    0
Max Drawdown Hits:        0
Account Blown:            NO ✅
```

**What to look for:**
- Zero Guardian Shield triggers ✅ (ideal)
- 1-2 triggers ⚠️ (acceptable but risky)
- Account blown ❌ (strategy needs major adjustment)

---

## Adjusting Parameters

### Change Risk Per Trade

Edit `run_backtest.py`:

```python
config = {
    'initial_capital': 50000,
    'risk_percent': 0.008,  # Change from 0.006 to 0.008 (0.8%)
    'enable_guardian_shield': True,
}
```

**Warning:** Risk > 0.8% will likely trigger Guardian Shield!

### Change Strategy Parameters

#### ORB Strategy

Edit `src/strategies/opening_range_breakout.py`:

```python
orb_strategy = OpeningRangeBreakout(
    entry_buffer=2.0,  # Points above/below OR (default: 2.0)
    stop_buffer=3.0,   # Points for stop loss (default: 3.0)
    target_multiple_1=1.5,  # First target (default: 1.5)
    target_multiple_2=2.0,  # Second target (default: 2.0)
    min_range_size=5.0,  # Minimum OR width (default: 5.0)
)
```

#### VWAP Strategy

Edit `src/strategies/vwap_mean_reversion.py`:

```python
vwap_strategy = VWAPMeanReversion(
    deviation_min=0.003,  # Min 0.3% from VWAP (default: 0.003)
    deviation_max=0.005,  # Max 0.5% from VWAP (default: 0.005)
    stop_buffer=2.0,  # Points beyond swing (default: 2.0)
    target_extension=7.0,  # Points beyond VWAP (default: 7.0)
)
```

### Change Data Period

Edit `run_backtest.py`:

```python
data = downloader.download_sp500(
    start_date='2024-09-01',  # Add specific start date
    end_date='2024-11-01',    # Add specific end date
    interval='5m',
    save_to_file=True,
)
```

**Note:** yfinance limits intraday data to last 60 days for free tier.

---

## Interpreting Results

### ✅ Good Backtest Results

```
Win Rate:            72-78%
Total Return:        6-12% (over test period)
Profit Factor:       1.8-2.5
Max Drawdown:        <3%
Guardian Shield:     0-1 triggers
```

**Action:** Strategy is ready for OctaFX demo testing!

### ⚠️ Marginal Results

```
Win Rate:            65-72%
Total Return:        3-6%
Profit Factor:       1.3-1.8
Max Drawdown:        3-4%
Guardian Shield:     1-2 triggers
```

**Action:** Adjust parameters, test again. May work but risky.

### ❌ Poor Results

```
Win Rate:            <65%
Total Return:        <3% or negative
Profit Factor:       <1.3
Max Drawdown:        >4%
Guardian Shield:     3+ triggers or account blown
```

**Action:** Major strategy revision needed. Do NOT proceed to live trading.

---

## Next Steps After Successful Backtest

### 1. Verify Results (Week 1)

- Run backtest multiple times with different date ranges
- Check consistency across different market conditions
- Document any patterns (e.g., works better in trending vs ranging)

### 2. OctaFX Demo Trading (Weeks 2-4)

- Set up OctaFX Securities demo account ($100K)
- Connect MT5 Python API
- Run bot on demo with SAME parameters
- Track 30-50 trades
- Verify backtest results match real-time execution

### 3. Analyze Slippage & Costs (Week 3-4)

- Backtest assumes perfect fills at stop/target
- Real trading has:
  - Spread (0.5-1.0 points on SPX500)
  - Slippage (0.2-0.5 points)
  - Commission (varies by broker)
- **Total cost: ~1-2 points per round trip**

Adjust backtest to include costs:

```python
# Add to backtest_engine.py close_position()
slippage_points = 1.5  # Conservative estimate
pnl = pnl - (slippage_points * self.point_value * position['lots'])
```

Re-run backtest. If still profitable, proceed!

### 4. Blue Guardian Challenge (Weeks 5+)

- Only after demo proves profitable (>70% win rate, positive P&L)
- Start with same parameters
- Trade EXACTLY as backtested (no improvising!)
- Track every metric
- Adjust only if data clearly shows need

---

## Troubleshooting

### "No signals generated"

**Possible causes:**
- Data doesn't include opening range (check 9:30-9:45 AM bars exist)
- No valid setups in the data period
- Parameters too restrictive

**Solution:**
- Verify data has morning hours: `print(data.between_time('09:30', '10:00').head())`
- Widen parameters (e.g., increase deviation_max for VWAP)
- Try longer data period

### "Import errors"

**Possible causes:**
- Missing dependencies
- Wrong directory structure

**Solution:**
```bash
pip install -r requirements.txt
```

If ta-lib fails:
```bash
# Comment out ta-lib in requirements.txt
# It's not critical for these strategies
```

### "Account blown in backtest"

**Possible causes:**
- Risk too high (>0.8% per trade)
- Strategy having losing streak
- Guardian Shield triggered multiple times

**Solution:**
- Reduce risk_percent to 0.004 (0.4%)
- Adjust strategy parameters (tighter stops, better entries)
- Add additional filters (e.g., only trade on high volume)

### "Data download fails"

**Possible causes:**
- yfinance connection issues
- Invalid date range (>60 days for intraday)

**Solution:**
```python
# Use daily data for longer periods
data = downloader.download_sp500(
    start_date='2024-01-01',
    interval='1d',  # Daily instead of 5m
)
```

Or download manually and load:
```python
data = pd.read_csv('your_data.csv', index_col=0, parse_dates=True)
```

---

## Advanced: Custom Strategies

### Create New Strategy

1. Create file in `src/strategies/`:

```python
# src/strategies/my_strategy.py

class MyStrategy:
    def __init__(self, param1, param2):
        self.param1 = param1
        self.param2 = param2

    def generate_signals(self, data, backtester):
        signals = []

        # Your logic here
        for idx, bar in data.iterrows():
            # Check conditions
            if some_condition:
                signal = {
                    'entry_time': idx,
                    'direction': 'long',  # or 'short'
                    'entry_price': bar['Close'],
                    'stop_loss': bar['Close'] - 10,
                    'take_profit': bar['Close'] + 15,
                    'lots': backtester.calculate_position_size(10),
                    'strategy': 'MyStrategy',
                }
                signals.append(signal)

        return signals
```

2. Add to `run_backtest.py`:

```python
from strategies.my_strategy import MyStrategy

def run_my_backtest(data, config):
    backtester = SPX500Backtester(...)
    my_strategy = MyStrategy(param1=value, param2=value)
    signals = my_strategy.generate_signals(data, backtester)
    # ... execute trades
```

---

## Files Structure

```
NEW-LTF-bot-for-mt5/
├── run_backtest.py                 # Main script (START HERE)
├── requirements.txt                # Dependencies
├── src/
│   ├── backtesting/
│   │   └── backtest_engine.py      # Core backtesting engine
│   ├── strategies/
│   │   ├── opening_range_breakout.py
│   │   └── vwap_mean_reversion.py
│   └── data/
│       └── data_downloader.py      # Download historical data
├── data/                           # Downloaded data stored here
│   └── spx500_5m_latest.csv
└── BACKTESTING_GUIDE.md            # This file
```

---

## Tips for Success

1. **Start conservative**: Use 0.6% risk, don't increase until proven
2. **Be patient**: Good results take time, don't overtrade
3. **Trust the process**: If backtest works, trust it in demo
4. **Document everything**: Track all trades, note observations
5. **Adjust gradually**: Small parameter changes, test thoroughly
6. **Respect Guardian Shield**: It's there for your protection
7. **Focus on process**: Win rate and discipline > individual trades

---

## Questions & Support

**Q: How long should I backtest?**
A: Minimum 30 days (real trading days), ideally 60 days. More data = more confidence.

**Q: What if my results don't match the research (70%+ win rate)?**
A: Check data quality, verify parameters, ensure logic is correct. Markets change, 65%+ is still good.

**Q: Can I backtest on daily data instead of 5-minute?**
A: ORB needs intraday data (opening range). VWAP can work on daily but less accurate. Use 5-minute minimum.

**Q: Should I test both strategies together?**
A: Not in one backtest run (they'll overlap). Test separately, then use best one OR alternate by day.

**Q: When am I ready for Blue Guardian?**
A: After 30+ profitable demo trades on OctaFX with >70% win rate and <3% drawdown.

---

**Ready to backtest? Run:**
```bash
python run_backtest.py
```

Good luck! 🚀
