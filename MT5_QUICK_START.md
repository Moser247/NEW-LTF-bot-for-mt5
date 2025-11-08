# Quick Start: Test Strategy with MT5 Data

**Goal**: Get real data from YOUR broker and test the strategy

**Why MT5 Data is Best**:
- ✅ Exact prices from your broker (OctaFX, Blue Guardian, etc.)
- ✅ Same spreads you'll get when trading
- ✅ Direct SPX500 data (no conversion needed)
- ✅ Free if you have MT5 account

---

## 10-Minute Setup

### 1. Install MetaTrader 5 (if not already)

**Download**: https://www.metatrader5.com/en/download

**Setup**:
- Install MT5 on your computer
- Login to your account (OctaFX demo, Blue Guardian demo, or any MT5 broker)
- Keep MT5 running (can minimize it)

**Time**: 5 minutes

### 2. Install MT5 Python Package

```bash
pip install MetaTrader5
```

**Important**:
- MT5 Python API only works on **Windows**
- Requires Python 3.8-3.11 (3.12+ may not work)
- If on Mac/Linux, use Alpaca downloader instead

**Time**: 1 minute

### 3. Download Real Data from MT5

```bash
python download_mt5_data.py
```

**What happens**:
- Connects to your running MT5 terminal
- Finds SPX500 symbol (US500, SPX500, etc.)
- Downloads 6 months of 1-minute bars
- Saves to `data/spx500_mt5_real.csv`

**Time**: 2 minutes

### 4. Run Backtest on Real Data

```bash
python run_backtest_on_real_data.py
```

**What happens**:
- Loads the MT5 data
- Runs Elite Institutional Strategy
- Shows win rate, profit factor, drawdown
- Compares to synthetic results (60-75%)
- Gives honest assessment

**Time**: 1 minute

**Done!** You'll see if the strategy actually works on YOUR broker's data.

---

## Example Output

```
MT5 DATA DOWNLOADER
================================================================================
✅ Connected to MT5
   Account: 12345678
   Server: OctaFX-Demo
   Balance: $100,000.00
   Leverage: 1:500

🔍 Searching for SPX500 symbol...
   Found 156 symbols in total
✅ Found SPX500 symbol: US500

📋 Symbol Info:
   Full name: US SPX 500 Index
   Point: 0.01
   Spread: 20
   Contract size: 1.0

📊 Downloading data...
   Symbol: US500
   Timeframe: 1-minute bars
   Period: 6 months
   From: 2024-07-08
   To: 2025-01-08

⬇️  Downloading... (this may take 30-60 seconds)

✅ Downloaded 46,800 bars

🕐 Filtering to regular trading hours (9:30-16:00 ET)...
   Before filter: 46,800 bars
   After filter: 46,800 bars

📈 Data Summary:
   Date range: 2024-07-08 09:30:00 to 2025-01-08 16:00:00
   Trading days: 126
   Total bars: 46,800
   Price range: $4,925.50 to $6,100.25
   Avg volume/bar: 1,250

💾 Saved to: data/spx500_mt5_real.csv

================================================================================
✅ SUCCESS - Real MT5 data downloaded
================================================================================

This is REAL broker data from your MT5 account
Same prices and spreads you'll get when trading live

Next steps:
1. Run backtest: python run_backtest_on_real_data.py
2. Compare to synthetic results
3. See if 60-75% win rate holds on YOUR broker's data
```

---

## Troubleshooting

### "Failed to initialize MT5"

**Causes**:
- MT5 terminal not running
- Not logged into an account
- MT5 not installed

**Solutions**:
1. Open MT5 terminal
2. Login to your account
3. Make sure you see live prices updating
4. Keep MT5 open and run script again

### "Could not find SPX500 symbol"

**Causes**:
- Your broker uses a different symbol name

**Solutions**:
1. The script will show available symbols
2. Look for symbols with "500" or "SPX" in the name
3. Common names:
   - US500, US500.cash, US500m
   - SPX500, SPX500.cash
   - SP500
4. Edit `download_mt5_data.py` and set:
   ```python
   spx_symbol = "YOUR_SYMBOL_NAME"  # Line ~180
   ```

### "pip install MetaTrader5" fails

**Causes**:
- Python version incompatibility
- Not on Windows

**Solutions**:
1. Check Python version: `python --version`
   - Needs 3.8-3.11
   - If 3.12+, install older Python version
2. If on Mac/Linux:
   - MT5 Python API doesn't work
   - Use Alpaca instead: `python download_alpaca_data.py`
   - Or export MT5 data manually (see below)

### "No data returned" / "0 bars downloaded"

**Causes**:
- Symbol doesn't have historical data
- Date range too far back
- Broker limitations

**Solutions**:
1. Try shorter period:
   ```python
   # In download_mt5_data.py, line ~220
   data = download_bars(spx_symbol, months=3)  # Instead of 6
   ```
2. Try 5-minute bars instead of 1-minute:
   ```python
   data = download_bars(spx_symbol, months=6, timeframe=mt5.TIMEFRAME_M5)
   ```

---

## Manual Export (Alternative)

If Python API doesn't work, you can export data manually from MT5:

### Step 1: Export from MT5

1. Open MT5 terminal
2. Press **F2** (or Tools → History Center)
3. Find your SPX500 symbol (US500, etc.)
4. Select **1 Minute (M1)** timeframe
5. Click **Export** button
6. Save as `mt5_export.csv`

### Step 2: Convert the File

Create a script `convert_mt5_export.py`:

```python
import pandas as pd

# Load MT5 export
data = pd.read_csv('mt5_export.csv', sep='\t')

# Rename columns (MT5 uses <DATE>, <TIME>, etc.)
data.rename(columns={
    '<DATE>': 'Date',
    '<TIME>': 'Time',
    '<OPEN>': 'Open',
    '<HIGH>': 'High',
    '<LOW>': 'Low',
    '<CLOSE>': 'Close',
    '<TICKVOL>': 'Volume'
}, inplace=True)

# Combine date and time
data['Datetime'] = pd.to_datetime(data['Date'] + ' ' + data['Time'])
data.set_index('Datetime', inplace=True)

# Keep only OHLCV
data = data[['Open', 'High', 'Low', 'Close', 'Volume']]

# Set timezone
data.index = data.index.tz_localize('America/New_York')

# Save
data.to_csv('data/spx500_mt5_real.csv')
print(f"✅ Converted {len(data):,} bars")
print("   Saved to: data/spx500_mt5_real.csv")
```

Run:
```bash
python convert_mt5_export.py
```

Then:
```bash
python run_backtest_on_real_data.py
```

---

## What Data You Get

### OctaFX Demo Account
- Symbol: Usually **US500** or **US500.cash**
- Historical data: Usually 6-12 months available
- Quality: Good, matches their live servers

### Blue Guardian Demo
- Symbol: Usually **US500**
- Historical data: May be limited (check)
- Quality: Exact data you'll get in challenge

### Other Brokers
- Symbol names vary (SPX500, SP500, USA500, etc.)
- Check MT5 Market Watch for exact name
- Historical data availability varies by broker

---

## Why This is Better Than Alpaca

**MT5 Data (Your Broker)**:
- ✅ Exact prices you'll trade with
- ✅ Realistic spreads included
- ✅ Direct SPX500 (not SPY conversion)
- ✅ Broker-specific characteristics
- ✅ Most accurate for your use case

**Alpaca Data**:
- ✅ More historical data available
- ✅ Works on Mac/Linux
- ✅ Easier to get (just API key)
- ❌ Not exact same as your broker
- ❌ Requires SPY→SPX conversion

**Recommendation**:
- Use MT5 data if you can (most accurate)
- Use Alpaca if MT5 doesn't work

---

## Next Steps After Download

### If Backtest Shows 60-70% Win Rate ✅

**Your broker's data validates the strategy!**

Next:
1. Forward test on same MT5 account (demo)
2. Run strategy in real-time
3. Track 50-100 trades
4. If results match → Blue Guardian challenge

**Timeline**: 3-6 weeks
**Cost**: $0 until challenge

### If Backtest Shows 50-60% Win Rate ⚠️

**Strategy works but needs improvement**

Next:
1. Optimize parameters for YOUR broker's data
2. Test different confluence levels (5/7 instead of 6/7)
3. Adjust time windows
4. Re-test and demo

### If Backtest Shows <50% Win Rate ❌

**Strategy doesn't work on your broker**

Options:
1. Try different broker (maybe data quality issue)
2. Revise strategy
3. Don't proceed to Blue Guardian

---

## The Truth About Your Broker

**Different brokers = Different results**

Why:
- Spreads vary (Blue Guardian vs OctaFX)
- Price feeds differ slightly
- Execution may differ
- Slippage varies

**IMPORTANT**:
- Test on the SAME broker you'll trade on
- If testing on OctaFX, use OctaFX data
- If going to Blue Guardian, use their demo data
- Results may differ between brokers

---

## Bottom Line

**MT5 Data Download**:
- ✅ 10 minutes to set up
- ✅ $0 cost
- ✅ Most accurate for your situation
- ✅ Tests strategy on YOUR broker's data

**Commands**:
```bash
pip install MetaTrader5
python download_mt5_data.py
python run_backtest_on_real_data.py
```

**Result**: Know if strategy works on YOUR broker before risking money.

**Ready?** Make sure MT5 is open and logged in, then run the commands above. 🎯
