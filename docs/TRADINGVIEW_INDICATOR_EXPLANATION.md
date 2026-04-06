# TradingView Indicator Explanation
## WT + Ideal BB + RSI - Multi-Indicator Trading Strategy

---

## Overview

This is a **multi-indicator trading strategy** that combines three powerful technical indicators to generate high-probability buy and sell signals:

1. **WaveTrend (WT)** - Momentum oscillator
2. **Ideal Bollinger Bands (BB)** - Volatility bands with Moving Average
3. **RSI (Relative Strength Index)** - Momentum indicator with custom ranges

**Key Feature**: Signals only fire when **ALL THREE indicators align**, ensuring higher accuracy and reducing false signals.

---

## How It Works

### Signal Generation Logic

A trading signal (BUY or SELL) is generated **ONLY** when all three conditions are met simultaneously:

#### BUY Signal Requirements:
1. ✅ **WaveTrend**: WT1 crosses above WT2 (bullish momentum)
2. ✅ **Bollinger Bands**: Price is above Moving Average (uptrend)
3. ✅ **RSI**: RSI is between 54-82 (buy range)

#### SELL Signal Requirements:
1. ✅ **WaveTrend**: WT1 crosses below WT2 (bearish momentum)
2. ✅ **Bollinger Bands**: Price is below Moving Average (downtrend)
3. ✅ **RSI**: RSI is between 27-43 (sell range)

---

## Component Breakdown

### 1. WaveTrend (WT) Indicator

**What it is:**
- A momentum oscillator developed by LazyBear
- Measures the relationship between price and its moving average
- Identifies trend changes and momentum shifts

**How it works:**
- **WT1**: Primary line (calculated from price momentum)
- **WT2**: Secondary line (EMA of WT1)
- **Cross Signals**:
  - **Green Dot**: WT1 crosses above WT2 = Bullish signal
  - **Red Dot**: WT1 crosses below WT2 = Bearish signal

**Window Logic:**
- When a cross occurs, a **3-bar window** is created
- The window allows time for other indicators to align
- Window includes: 1 bar before, current bar, 1 bar after the cross

**Default Settings:**
- Channel Length: 10
- Average Length: 21

---

### 2. Ideal Bollinger Bands (BB)

**What it is:**
- Modified Bollinger Bands using EMA instead of SMA for smoother bands
- Includes a Moving Average (MA) for trend confirmation
- Shows volatility and price position relative to bands

**How it works:**
- **Upper Band**: EMA + (2 × Standard Deviation)
- **Lower Band**: EMA - (2 × Standard Deviation)
- **Basis**: EMA of price (middle line)
- **Moving Average**: Separate MA line for trend confirmation

**Buy/Sell Conditions:**
- **Buy**: Price > Moving Average (uptrend)
- **Sell**: Price < Moving Average (downtrend)

**Visual Features:**
- Blue bands (upper and lower)
- Yellow basis line
- Purple Moving Average line
- Color-coded fill (green when price near lower band, red when near upper band)

**Default Settings:**
- BB Length: 20
- BB Multiplier: 2.0
- MA Length: 20
- MA Type: EMA

---

### 3. RSI (Relative Strength Index)

**What it is:**
- Momentum oscillator that measures speed and magnitude of price changes
- Ranges from 0 to 100
- Identifies overbought/oversold conditions

**How it works:**
- **Traditional Levels**:
  - Overbought: 70 (red zone)
  - Oversold: 30 (green zone)
- **Custom Buy Range**: 54-82
  - When RSI enters this range, it indicates bullish momentum
- **Custom Sell Range**: 27-43
  - When RSI enters this range, it indicates bearish momentum

**Why Ranges Instead of Single Values:**
- More flexible than fixed thresholds
- Captures momentum zones rather than exact levels
- Reduces false signals from minor fluctuations

**Default Settings:**
- RSI Length: 12
- Buy Range: 54-82
- Sell Range: 27-43

---

## Combined Strategy Logic

### Signal Timing

**Critical Feature: Closed Candle Logic**
- All signals are detected on **closed/confirmed candles only**
- This ensures accurate backtesting and prevents intrabar execution
- Entry occurs on the **NEXT candle open** after conditions are met

**Why This Matters:**
- Prevents false signals from intrabar price movements
- Ensures signals are based on confirmed price action
- Matches real trading execution (can't enter mid-candle)

### Signal Flow

1. **WT Cross Occurs** → Window opens (3 bars)
2. **During Window** → Check BB and RSI conditions
3. **All Conditions Met** → Signal generated on closed candle
4. **Next Candle** → Entry signal fires (for webhook/alert)

### Duplicate Prevention

- Signals only fire **once per window**
- Prevents multiple alerts for the same setup
- Window resets after expiration

---

## Visual Display

### Indicator Panel Shows:

1. **WaveTrend Lines**:
   - WT1 (green when above WT2, red when below)
   - WT2 (orange line)
   - Zero line (dashed gray)
   - Cross dots (green/red circles)

2. **Bollinger Bands**:
   - Upper band (blue)
   - Lower band (blue)
   - Basis line (yellow)
   - Moving Average (purple, dashed)
   - Color-coded fill

3. **RSI**:
   - RSI line (color-coded: red/green/blue)
   - Overbought/oversold levels (dashed)
   - Buy/sell threshold ranges (solid lines)
   - Signal labels (BUY/SELL)

4. **Strategy Signals**:
   - Large "STRATEGY BUY" labels (green)
   - Large "STRATEGY SELL" labels (red)

5. **Info Table** (top-right):
   - Current WT1 value
   - Current RSI value
   - BB %B (position within bands)
   - WT Window status
   - Strategy status

---

## Webhook Integration

### Alert System

The indicator sends signals to your trading bot via webhook when all conditions align.

**Alert Conditions:**
- `Strategy Buy Signal (JSON)` - For BUY signals
- `Strategy Sell Signal (JSON)` - For SELL signals

**Webhook Payload Includes:**
- Symbol (trading pair)
- Signal type (BUY/SELL)
- Timestamp
- All indicator values (WT, BB, RSI)
- Price data (open, high, low, close)
- Strategy metadata

**Payload Format:**
```json
{
  "symbol": "BTCUSDT",
  "signal": "BUY",
  "time": 1234567890,
  "indicators": {
    "wt": { "wt1": 12.5, "wt2": 10.2, "cross_type": "BULLISH" },
    "bb": { "upper": 52000, "lower": 48000, "ma_value": 50000 },
    "rsi": { "value": 65.5, "condition_met": true }
  },
  "price": { "close": 50000, "open": 49900, "high": 50100, "low": 49800 }
}
```

---

## Configuration Options

### Adjustable Parameters

**WaveTrend:**
- Channel Length (default: 10)
- Average Length (default: 21)
- Show cross dots (on/off)

**Bollinger Bands:**
- BB Length (default: 20)
- BB Multiplier (default: 2.0)
- MA Length (default: 20)
- MA Type (SMA, EMA, WMA, RMA)

**RSI:**
- RSI Length (default: 12)
- Buy Threshold Min (default: 54)
- Buy Threshold Max (default: 82)
- Sell Threshold Min (default: 27)
- Sell Threshold Max (default: 43)

**Display:**
- Show/hide individual indicators
- Show/hide labels
- Enable/disable strategy signals

---

## Key Features

### 1. Multi-Indicator Confirmation
- **Not** a single-indicator strategy
- Requires alignment of 3 different indicators
- Reduces false signals significantly

### 2. Closed Candle Logic
- All signals based on confirmed candles
- Prevents intrabar execution issues
- Accurate backtesting

### 3. Window-Based Timing
- WT cross creates a time window
- Allows other indicators to align
- Prevents missed signals

### 4. Custom RSI Ranges
- Not traditional 70/30 levels
- Custom buy (54-82) and sell (27-43) ranges
- More flexible signal generation

### 5. Webhook Ready
- Built-in webhook payload generation
- JSON format for easy parsing
- Includes all indicator data

### 6. Visual Feedback
- Clear visual signals (labels, dots, colors)
- Real-time status table
- Easy to read and understand

---

## How to Use

### Step 1: Load Indicator
1. Open TradingView
2. Add indicator: "WT + Ideal BB + RSI"
3. Configure parameters (or use defaults)

### Step 2: Set Up Alerts
1. Click Alert button (bell icon)
2. Select condition: "Strategy Buy Signal (JSON)" or "Strategy Sell Signal (JSON)"
3. Add webhook URL: `https://your-bot-url.com/webhook`
4. Set trigger: "Once per bar close" (recommended)
5. Create alert

### Step 3: Monitor Signals
- Watch for "STRATEGY BUY" or "STRATEGY SELL" labels
- Check info table for current status
- Verify all 3 indicators are aligned

### Step 4: Execute Trades
- Signals automatically sent to your trading bot
- Bot receives webhook with all data
- Bot executes trades based on your strategy

---

## Strategy Logic Summary

```
IF (WT1 crosses above WT2) AND (Price > MA) AND (RSI between 54-82)
    → BUY Signal

IF (WT1 crosses below WT2) AND (Price < MA) AND (RSI between 27-43)
    → SELL Signal
```

**All conditions must be true simultaneously for a signal to fire.**

---

## Advantages

1. **High Accuracy**: Multiple confirmations reduce false signals
2. **Clear Signals**: Visual indicators make it easy to see setups
3. **Flexible**: Adjustable parameters for different markets
4. **Automated**: Webhook integration for hands-free trading
5. **Backtestable**: Closed candle logic ensures accurate testing
6. **Professional**: Based on proven indicators (WT, BB, RSI)

---

## Technical Details

### WaveTrend Calculation
```
ap = (High + Low + Close) / 3
esa = EMA(ap, channel_length)
d = EMA(|ap - esa|, channel_length)
ci = (ap - esa) / (0.015 * d)
tci = EMA(ci, average_length)
wt1 = tci
wt2 = EMA(tci, average_length)
```

### Bollinger Bands Calculation
```
basis = EMA(price, length)
dev = multiplier × STDEV(price, length)
upper = basis + dev
lower = basis - dev
```

### RSI Calculation
```
RSI = 100 - (100 / (1 + RS))
RS = Average Gain / Average Loss
```

---

## Best Practices

1. **Use on Multiple Timeframes**: Test on 15m, 1h, 4h, daily
2. **Adjust Parameters**: Different markets may need different settings
3. **Combine with Risk Management**: Always use stop-loss and take-profit
4. **Monitor Performance**: Track win rate and adjust thresholds
5. **Paper Trade First**: Test before using real money
6. **Set Proper Alerts**: Use "Once per bar close" to avoid duplicates

---

## Troubleshooting

### No Signals Appearing?
- Check that all 3 indicators are enabled
- Verify parameters are set correctly
- Ensure "Enable Combined Strategy" is ON
- Wait for all conditions to align

### Too Many Signals?
- Increase RSI threshold ranges
- Tighten BB or WT parameters
- Use higher timeframe

### Too Few Signals?
- Decrease RSI threshold ranges
- Loosen BB or WT parameters
- Use lower timeframe

### Signals Not Reaching Bot?
- Verify webhook URL is correct
- Check alert is enabled in TradingView
- Verify bot is running and accessible
- Check Railway/logs for errors

---

## Summary

This indicator combines **WaveTrend**, **Bollinger Bands**, and **RSI** into a single, powerful trading strategy. It only generates signals when all three indicators align, ensuring high-probability setups. The closed-candle logic ensures accurate backtesting and real-world execution, while the webhook integration enables fully automated trading.

**Key Takeaway**: This is not a single-indicator strategy. It requires confirmation from three different technical analysis tools, making it more reliable than strategies using just one indicator.


