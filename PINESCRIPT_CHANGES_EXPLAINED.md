# Pine Script Changes Explained

## Overview

You have **TWO DIFFERENT STRATEGIES**:

### ❌ OLD (What you're using now)
- **Name:** CUSTOM IDEAL BB + RSI + WT (STRICT LABEL LOCK v3 FINAL)
- **Version:** 4
- **Status:** Currently deployed to TradingView
- **Indicators:** NMA, Kahlman filter, WT, RSI

### ✅ NEW (What we built - ready to deploy)
- **Name:** WT + BB + RSI Trading Strategy
- **Version:** 5
- **Status:** In our codebase, not deployed yet
- **Indicators:** Standard WT, BB, RSI
- **Additions:** RSI directional filter (Milestone 2)

---

## Side-by-Side Comparison

### 1. STRATEGY TYPE

**OLD:**
```pinescript
study("CUSTOM IDEAL BB + RSI + WT (STRICT LABEL LOCK v3 FINAL)", overlay=true)
```
- `study()` = indicator (no position/order management)
- Uses `alertcondition()` only

**NEW:**
```pinescript
strategy("WT + BB + RSI Trading Strategy", overlay=true, 
         initial_capital=10000, default_qty_type=strategy.percent_of_equity, default_qty_value=20)
```
- `strategy()` = full trading strategy (has position/order management)
- Can use `strategy.entry()`, `strategy.exit()`, etc.

---

### 2. INDICATORS USED

#### OLD Uses:
```pinescript
// NMA (Nested Moving Average)
getNMA(s,l1,l2)=>(1+(l1/l2*(l1-1)/(l1-(l1/l2))))*getMA(s,l1)-(l1/l2*(l1-1)/(l1-(l1/l2)))*getMA(getMA(s,l1),l2)

// Kahlman Filter
kahlman(x, g) => ...

// HMA (Hull Moving Average)
hma(_src, _len) => ...
hma3(_src, _len) => ...

// CrossUp/CrossDown Logic
crossup = b>a and b[1]<a[1]
crossdn = a>b and a[1]<b[1]
```

**Purpose:** Complex dual-line crossing with Kahlman smoothing

---

#### NEW Uses:
```pinescript
// Simple WaveTrend (v5 version)
ap = hlc3
esa = ta.ema(ap, wt_channel_length)
d = ta.ema(math.abs(ap - esa), wt_channel_length)
ci = (ap - esa) / (0.015 * d)
tci = ta.ema(ci, wt_average_length)
wt1 = tci
wt2 = ta.ema(tci, wt_average_length)

// WT Cross Detection
wt_cross_up = barstate.isconfirmed and ta.crossover(wt1, wt2)
wt_cross_down = barstate.isconfirmed and ta.crossunder(wt1, wt2)

// Bollinger Bands
ideal_bb_basis = ta.ema(bb_source, bb_length)
ideal_bb_dev = bb_mult * ta.stdev(bb_source, bb_length)
ideal_bb_upper = ideal_bb_basis + ideal_bb_dev
ideal_bb_lower = ideal_bb_basis - ideal_bb_dev

// BB Buy/Sell Conditions
bb_buy_condition = close > ma_value
bb_sell_condition = close < ma_value
```

**Purpose:** Standard technical analysis (WT + BB + RSI)

---

### 3. SIGNAL LOGIC

#### OLD Signal Logic:
```pinescript
buyFinal  = buyStructureValid  and rsiBuyOk
sellFinal = sellStructureValid and rsiSellOk

// Conditions:
rsiBuyOk = rsiValue>53 and rsiValue<83      // RSI between 53-83
rsiSellOk = rsiValue<44 and rsiValue>26     // RSI between 26-44
```

**Logic:**
- Structure (label + WT window) must be valid
- RSI must be in range
- Alert fires when both conditions met

---

#### NEW Signal Logic:

**Step 1: Basic Confirmation (unchanged from requirements)**
```pinescript
// A - WT cross detected
if not na(wt_buy_cross_bar)
    bars_since_cross = bar_index - wt_buy_cross_bar
    
    // Check ±1 candle window
    if bars_since_cross >= -1 and bars_since_cross <= 1
        // B - BB condition valid in entire window
        bb_valid = bb_buy_condition
        
        // C - RSI >= 54 (on cross or after, NOT before)
        if bars_since_cross >= 0
            rsi_valid := rsi_buy_condition  // RSI >= 54
```

**Step 2: RSI Directional Filter (Milestone 2 - NEW)**
```pinescript
// After structure confirmed, apply directional filter
if bb_valid and rsi_valid
    // Milestone 2: Apply RSI directional filter
    if rsi_direction_filter_enabled
        if rsi_bullish  // RSI > 50
            final_buy_signal := true
    else
        final_buy_signal := true  // Can toggle off

// Same for SELL but inverted
if rsi_direction_filter_enabled
    if rsi_bearish  // RSI < 50
        final_sell_signal := true
else
    final_sell_signal := true
```

**Logic:**
- First: Check structure (WT + BB + RSI thresholds) ✅
- Then: Check RSI direction (NEW filter) ✅
- Signal fires only if BOTH conditions met

---

### 4. KEY DIFFERENCE: RSI HANDLING

#### OLD:
```pinescript
rsiValue = rsi(close,12)
rsiBuyOk = rsiValue>53 and rsiValue<83   // Simple range check
rsiSellOk = rsiValue<44 and rsiValue>26
```

- RSI just needs to be in range
- No directional preference
- Can buy when RSI=80 or RSI=55 (both in range)

#### NEW:
```pinescript
// RSI threshold (for entry confirmation)
rsi_buy_condition = rsi >= rsi_buy_threshold   // >= 54
rsi_sell_condition = rsi <= rsi_sell_threshold // <= 44

// RSI direction (NEW - Milestone 2 filter)
rsi_bullish = rsi > rsi_bullish_threshold  // > 50
rsi_bearish = rsi < rsi_bearish_threshold  // < 50

// Buy requires BOTH:
// 1. RSI >= 54 (threshold for entry confirmation)
// 2. RSI > 50 (directional - bullish)
```

**Example:**
```
Scenario 1: RSI = 55
  Old:  ✅ BUY fires (55 is between 53-83)
  New:  ✅ BUY fires (55 >= 54 AND 55 > 50)

Scenario 2: RSI = 52
  Old:  ✅ BUY fires (52 is between 53-83) - FALSE, 52 < 53
  New:  ❌ BUY suppressed (52 >= 54 is FALSE)

Scenario 3: RSI = 45 during crossup
  Old:  ❌ BUY rejected (45 not in range 53-83)
  New:  ❌ BUY rejected (45 < 54, fails first check)

Scenario 4: BUY after structure is valid, RSI=54
  Old:  ✅ BUY fires (54 in range 53-83)
  New:  ✅ BUY fires (54 >= 54 AND 54 > 50)
  
Scenario 5: BUY after structure valid, RSI=60 but bearish context
  Old:  ✅ BUY fires (60 in range)
  New:  ✅ BUY fires (filter is about DIRECTION not magnitude)
```

---

### 5. INPUT PARAMETERS

#### OLD:
```pinescript
length1 = input(120)
length2 = input(12)
maInput = input("EMA", options=["EMA","SMA","VWMA","WMA"])
lengthhull = input(24)
gain = input(10000)
```
- Controls NMA, Kahlman smoothing
- Different algorithm

#### NEW:
```pinescript
// Existing inputs
wt_channel_length = input.int(10, title="WT Channel Length", minval=1)
wt_average_length = input.int(21, title="WT Average Length", minval=1)
rsi_buy_threshold = input.float(54.0, title="RSI Buy Threshold (>=)")
rsi_sell_threshold = input.float(44.0, title="RSI Sell Threshold (<=)")

// NEW Inputs (Milestone 2)
rsi_direction_filter_enabled = input.bool(true, title="Enable RSI Directional Filter (Milestone 2)")
rsi_bullish_threshold = input.float(50.0, title="RSI Bullish Threshold (>)")
rsi_bearish_threshold = input.float(50.0, title="RSI Bearish Threshold (<)")

// Take Profit Levels
tp1_pct = input.float(1.0, title="Take Profit 1 %")
tp2_pct = input.float(2.0, title="Take Profit 2 %")
tp3_pct = input.float(5.0, title="Take Profit 3 %")
tp4_pct = input.float(6.5, title="Take Profit 4 %")

// Stop Loss
stop_loss_pct = input.float(5.0, title="Stop Loss %")
position_size_pct = input.int(20, title="Position Size (% of Account)")
```

**In TradingView, these show up as adjustable inputs** ✅

---

### 6. POSITION MANAGEMENT

#### OLD:
```pinescript
alertcondition(buyFinal, title="BUY", message="BUY")
alertcondition(sellFinal, title="SELL", message="SELL")
```
- Only sends alert
- No position management
- Webhook handler manages orders

#### NEW:
```pinescript
// BUY Entry
if barstate.isconfirmed and final_buy_signal[1] and strategy.position_size == 0
    entry_price := close[1]
    initial_stop_loss := entry_price * (1 - stop_loss_pct / 100)
    
    // Long position
    strategy.entry("BUY", strategy.long, qty_percent=position_size_pct)
    
    // Stop loss at 5% below entry
    strategy.exit("SL", "BUY", stop=initial_stop_loss)
    
    // Take profit levels
    strategy.exit("TP1", "BUY", qty_percent=10, limit=entry_price * (1 + tp1_pct / 100))
    strategy.exit("TP2", "BUY", qty_percent=15, limit=entry_price * (1 + tp2_pct / 100))
    strategy.exit("TP3", "BUY", qty_percent=35, limit=entry_price * (1 + tp3_pct / 100))
    strategy.exit("TP4", "BUY", qty_percent=35, limit=entry_price * (1 + tp4_pct / 100))

// After TP1 hit, move SL to entry
if strategy.position_size != 0 and not na(entry_price) and not tp1_hit
    tp1_price_long = entry_price * (1 + tp1_pct / 100)
    if high >= tp1_price_long
        tp1_hit := true
        strategy.exit("SL", "BUY", stop=entry_price)  // Move SL to entry
```

- Manages entry, SL, TP levels
- Can be used for backtesting
- Still sends alerts via webhook

---

## Summary of Changes

| Aspect | OLD | NEW |
|--------|-----|-----|
| **Version** | 4 | 5 |
| **Type** | study (alert only) | strategy (full management) |
| **Indicators** | NMA + Kahlman + HMA | Standard WT + BB + RSI |
| **Signal Logic** | Label + WT window + RSI range | WT cross + BB + RSI threshold + RSI direction |
| **RSI Filter** | ❌ No | ✅ Yes (Milestone 2) |
| **Take Profits** | ❌ Not in code | ✅ 4 levels (1%, 2%, 5%, 6.5%) |
| **Stop Loss** | ❌ Not in code | ✅ 5%, moves to entry after TP1 |
| **Complexity** | High (Kahlman, HMA) | Medium (standard indicators) |
| **Customization** | Limited | Many inputs adjustable |

---

## What Happens When You Switch

**Before switching (OLD):**
- WT window logic fires
- Label must be on/near WT cross
- RSI must be in range (53-83 or 26-44)
- Alert sent to webhook
- Webhook executes via Bybit/IBKR/Alpaca/MEXC

**After switching (NEW):**
- WT cross detected (green/red dot)
- BB and RSI thresholds confirmed (54 for buy, 44 for sell)
- **NEW:** RSI direction filter applied (>50 for buy, <50 for sell)
- Some signals that would have fired are now suppressed
- Alert sent to webhook
- Webhook executes via Bybit/IBKR/Alpaca/MEXC

---

## Testing Before Deployment

1. **Add NEW strategy to chart alongside OLD**
2. **Monitor both for comparison**
   - OLD: generates X signals
   - NEW: generates fewer signals (some filtered by RSI direction)
3. **Verify NEW signals are more reliable** (RSI confirms momentum)
4. **Then remove OLD and keep only NEW**

---

## Important: Deployment Checklist

```
Before deploying to TradingView:

❓ Are you comfortable with the NEW strategy logic?
❓ Do you want to test it alongside the OLD one first?
❓ What timeframe? (4H recommended)
❓ Which chart/symbol?
```

Once deployed, we can monitor webhook logs to verify the new RSI directional filter is working correctly. 🎯
