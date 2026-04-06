# MEXC Spot API - Stop Loss Implementation

## ⚠️ Critical Finding

**MEXC Spot API (`/api/v3/order`) does NOT support stop-loss orders.**

According to MEXC's official API documentation:
- Spot V3 order placement only supports `MARKET` and `LIMIT` order types
- `STOP_MARKET_ORDER` is labeled as "(Query only)" - meaning it can only be queried, not placed
- There is no `stopPrice` parameter in the Spot order placement endpoint

## Solution Implemented

Since MEXC Spot doesn't support stop-loss orders, we've implemented a **price monitoring system** that:

1. **Stores stop-loss prices** in the position data
2. **Monitors prices every 2 seconds** via background thread
3. **Executes market orders** when stop-loss price is hit
4. **Updates stop-loss price** to entry after TP1 (critical requirement)

## How It Works

### Initial Stop-Loss (5% from entry)
```python
# Store stop-loss price in position
position['stop_loss_price'] = entry_price * 0.95  # 5% below for BUY
```

### Monitoring System
- Background thread checks current price every 2 seconds
- Compares current price to stop-loss price
- If triggered: Places market SELL order to close position

### After TP1 (Move to Entry)
```python
# Update stop-loss price to entry (breakeven)
position['stop_loss_price'] = entry_price
```

## Files Created/Modified

1. **`stop_loss_monitor.py`** - New file
   - Monitors prices for all active positions
   - Executes stop-loss when price hits trigger
   - Updates stop-loss prices

2. **`tp_sl_manager.py`** - Modified
   - Changed from placing stop-loss orders to storing stop-loss prices
   - Updates monitoring system when SL moves to entry

3. **`trading_executor.py`** - Modified
   - Initializes stop-loss monitor
   - Integrates monitoring with TP/SL management

4. **`position_manager.py`** - Modified
   - Added `stop_loss_price` field to position data

## Trade-offs

### Advantages
- ✅ Works with Spot API (no Futures API needed)
- ✅ Still meets critical requirement (SL moves to entry after TP1)
- ✅ Take-profit orders work normally (LIMIT orders are supported)

### Limitations
- ⚠️ Stop-loss execution depends on monitoring frequency (2 seconds)
- ⚠️ Not as fast as exchange-native stop-loss orders
- ⚠️ Requires bot to be running continuously

## Alternative: Futures API

If you want native stop-loss support, you could:
1. Switch to MEXC Futures API
2. Use endpoint: `POST /api/v1/private/stoporder/place`
3. Requires Futures account and different API endpoints

## Testing Recommendations

1. **Test with small amounts** first
2. **Monitor logs** to verify stop-loss monitoring works
3. **Test TP1 trigger** to verify SL moves to entry
4. **Verify market orders** execute correctly when SL is hit

## Critical Requirement Status

✅ **STILL MET**: Stop-loss moves to entry after TP1
- The monitoring system updates the stop-loss price to entry
- When price hits entry, it will execute market order
- This meets the critical requirement, just via monitoring instead of native orders


