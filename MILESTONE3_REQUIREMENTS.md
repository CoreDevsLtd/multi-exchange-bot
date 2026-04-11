# Milestone 3: Portfolio and Trade Detail Dashboard

**Status:** 📋 Planning Phase  
**Priority:** Medium  
**Estimated Timeline:** 1-2 weeks

---

## Overview

Add three new dashboard pages for reviewing trade performance:
1. **Portfolio Page** - List of all trading tickers
2. **Ticker Detail Page** - Statistics and trade history for a single ticker
3. **Trade Detail Page** - Complete breakdown of individual trades

---

## Requirements Breakdown

### REQ-3.1: Portfolio Page ✅

**What it does:**
- Display all tickers that have trading history
- Filter to show only tickers with >= 1 trade from go-live date
- Exclude tickers with zero trades
- Serves as entry point to drill-down views

**Data Source:**
- MongoDB `trades` collection
- Query: Get distinct symbols from trades with `timestamp_open >= go_live_date`

**UI Elements:**
- List/table format with columns:
  - Ticker symbol
  - Number of trades
  - Total P&L (optional)
  - Win rate (optional)
  - Last trade date
  - Click to view details

**Data Query Example:**
```python
db.trades.aggregate([
    {
        '$group': {
            '_id': '$symbol',
            'trade_count': {'$sum': 1},
            'last_trade': {'$max': '$timestamp_close'}
        }
    },
    {'$sort': {'last_trade': -1}}
])
```

---

### REQ-3.2: Ticker Detail Page ✅

**What it does:**
- Show all trades for a single ticker
- Calculate ROI and Win Rate
- List trades chronologically
- Entry point to trade detail view

**Data Source:**
- MongoDB `trades` collection
- Query: Filter by symbol, calculate metrics

**Metrics to Calculate:**

**1. Return on Investment (ROI)**
```
ROI = (Sum of all P&L) / (Average entry price * total quantity) * 100
or simpler:
ROI = (Total P&L) / (Initial capital used) * 100
```

**2. Win Rate**
```
Win Rate = (Trades with positive P&L) / (Total trades) * 100
```

**3. Trade History**
- Chronological list (oldest first or newest first - TBD)
- Show per trade:
  - Date/time
  - Direction (BUY/SELL)
  - Entry price
  - Exit price
  - P&L (dollars and %)
  - Status (Win/Loss)

**UI Elements:**
- Header with ROI and Win Rate stats
- Table of trades with columns:
  - Date
  - Direction (↑ BUY / ↓ SELL)
  - Entry Price
  - Exit Price
  - P&L $
  - P&L %
  - Result (Win/Loss badge)
  - Click row to view full details

**Data Query Example:**
```python
trades = db.trades.find({'symbol': ticker}).sort([('timestamp_open', 1)])
```

---

### REQ-3.3: Trade Detail Page ✅

**What it does:**
- Show complete breakdown of a single trade
- Display all required fields from trade document
- Calculate derived metrics (R-Multiple, Max DD, Max Profit)
- Show trade lifecycle visually (optional)

**Required Fields (from trade document):**

| Field | Source | Example |
|-------|--------|---------|
| Symbol | trades.symbol | BTCUSDT |
| Direction | trades.direction | Long (BUY) / Short (SELL) |
| Entry Price | trades.entry_price | 45000.00 |
| Exit Price | trades.exit_price | 46500.00 |
| Stop Loss | trades.stop_loss | 42750.00 |
| TP1 Hit | trades.tp_hits[0] | Yes/No |
| TP2 Hit | trades.tp_hits[1] | Yes/No |
| TP3 Hit | trades.tp_hits[2] | Yes/No |
| TP4 Hit | trades.tp_hits[3] | Yes/No |
| TP5 Hit | trades.tp_hits[4] | Yes/No (Runner) |
| Result $ | trades.result_usd | 1500.00 |
| Result % | trades.result_percent | 3.33% |
| Exit Reason | trades.exit_reason | TP / SL / Manual / Close |
| Trade Duration | Calculated | 2h 45m |

**Calculated Metrics:**

**1. R-Multiple (REQ-3.4)**
```
R-Multiple = Realized P&L / Initial Risk
Initial Risk = | Entry Price - Stop Loss |

Example:
Entry: 45000, Stop Loss: 42750, Exit: 46500
Initial Risk = |45000 - 42750| = 2250
P&L = 46500 - 45000 = 1500
R-Multiple = 1500 / 2250 = 0.67R
```

**2. Max Drawdown (REQ-3.5)**
- Fetch candle data for trade period (entry to exit)
- For LONG: worst low reached / entry price
- For SHORT: worst high reached / entry price
- Computed on-demand via candle API call

**3. Max Profit (REQ-3.5)**
- Fetch candle data for trade period
- For LONG: best high reached / entry price
- For SHORT: best low reached / entry price
- Computed on-demand via candle API call

**4. Trade Duration**
```
Duration = timestamp_close - timestamp_open
Display as: 2h 45m or 1d 3h 22m
```

**UI Layout:**
```
┌─────────────────────────────────────────┐
│ BTCUSDT - LONG - Entry 45000.00          │
├─────────────────────────────────────────┤
│ Entry Price:      45000.00               │
│ Exit Price:       46500.00               │
│ Stop Loss:        42750.00               │
│                                         │
│ Result:           +$1500.00 (+3.33%)    │
│ R-Multiple:       0.67R                  │
│                                         │
│ Max Profit:       +2.89%                 │
│ Max Drawdown:     -0.89%                 │
│                                         │
│ Exit Reason:      TP2                    │
│ Trade Duration:   2h 45m                 │
│                                         │
│ Take Profit Hits:                        │
│  TP1 (1%):        ✓ Yes                  │
│  TP2 (2%):        ✓ Yes (EXIT HERE)     │
│  TP3 (5%):        ✗ No                   │
│  TP4 (6.5%):      ✗ No                   │
│  TP5 (Runner):    ✗ No                   │
└─────────────────────────────────────────┘
```

---

## Technical Implementation

### Backend Requirements

#### 1. MongoDB Data Queries

**Get all tickers with trades:**
```python
def get_portfolio_tickers(go_live_date=None):
    """Get distinct symbols from trades collection"""
    query = {}
    if go_live_date:
        query['timestamp_open'] = {'$gte': go_live_date}
    
    return db.trades.aggregate([
        {'$match': query},
        {'$group': {'_id': '$symbol'}},
        {'$sort': {'_id': 1}}
    ])
```

**Get ticker metrics:**
```python
def get_ticker_metrics(symbol):
    """Calculate ROI and Win Rate for ticker"""
    trades = list(db.trades.find({'symbol': symbol}))
    
    total_pnl = sum(t.get('result_usd', 0) for t in trades)
    win_count = sum(1 for t in trades if t.get('result_usd', 0) > 0)
    total_trades = len(trades)
    
    roi = (total_pnl / (sum(t.get('entry_price', 0) * t.get('initial_quantity', 1) for t in trades))) * 100
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
    
    return {'roi': roi, 'win_rate': win_rate, 'total_trades': total_trades}
```

**Get trade details:**
```python
def get_trade_details(trade_id):
    """Get single trade document"""
    return db.trades.find_one({'_id': ObjectId(trade_id)})
```

**Calculate Max DD/Profit:**
```python
def calculate_max_dd_profit(trade):
    """Fetch candle data and calculate max DD/profit"""
    symbol = trade['symbol']
    start = trade['timestamp_open']
    end = trade['timestamp_close']
    
    # Fetch candles from exchange API (MEXC, Bybit, etc.)
    candles = fetch_candles(symbol, start, end, timeframe='1h')
    
    if trade['direction'].upper() == 'BUY':
        worst_low = min(c['low'] for c in candles)
        best_high = max(c['high'] for c in candles)
        max_dd = ((worst_low - trade['entry_price']) / trade['entry_price']) * 100
        max_profit = ((best_high - trade['entry_price']) / trade['entry_price']) * 100
    else:  # SELL
        worst_high = max(c['high'] for c in candles)
        best_low = min(c['low'] for c in candles)
        max_dd = ((worst_high - trade['entry_price']) / trade['entry_price']) * 100
        max_profit = ((trade['entry_price'] - best_low) / trade['entry_price']) * 100
    
    return {'max_dd': max_dd, 'max_profit': max_profit}
```

#### 2. Dashboard Routes

**API Endpoints to Add:**

```
GET /api/portfolio
  Returns: List of tickers with trade counts

GET /api/portfolio/<symbol>
  Returns: Ticker metrics (ROI, win rate) + trade history

GET /api/trades/<trade_id>
  Returns: Complete trade details with calculated metrics

GET /api/trades/<trade_id>/candle-analysis
  Returns: Max DD/profit calculated from candle data
```

#### 3. Frontend Pages

**New HTML Templates:**

1. `portfolio.html` - Portfolio page
   - List of tickers
   - Links to ticker detail pages
   
2. `ticker_detail.html` - Ticker detail page
   - ROI and Win Rate stats
   - Trade history table
   - Links to trade detail pages

3. `trade_detail.html` - Trade detail page
   - All trade metrics
   - Calculated R-Multiple
   - Max DD/Profit from candles
   - Visual layout of trade lifecycle

---

## Data Dependencies

### Current MongoDB Collections

**trades collection structure:**
```javascript
{
  _id: ObjectId,
  exchange_account_id: string,
  account_id: string,
  symbol: string,
  direction: string,  // "Long" or "Short"
  entry_price: number,
  exit_price: number,
  stop_loss: number,
  tp_hits: [bool, bool, bool, bool, bool],  // TP1-5
  result_usd: number,
  result_percent: number,
  exit_reason: string,  // "TP", "SL", "Manual", "Close"
  trade_duration_sec: number,
  timestamp_open: ISO8601,
  timestamp_close: ISO8601,
  initial_quantity: number
}
```

**Issues to verify:**
- ✅ `tp_hits` array stored correctly (5 elements)
- ✅ `exit_reason` populated correctly
- ✅ `result_usd` and `result_percent` calculated
- ❓ Need to verify `initial_quantity` is stored
- ❓ Need to verify exchange data is stored

---

## Critical Questions for Client

### Q1: R-Multiple Formula Confirmation (REQ-3.4)

**Proposed Formula:**
```
R-Multiple = Realized P&L / Initial Risk
Initial Risk = | Entry Price - Stop Loss |
```

**Example:**
```
Entry: 45000, SL: 42750, Exit: 46500
Risk = 2250, P&L = 1500
R-Multiple = 1500 / 2250 = 0.67R
```

❓ **Does client approve this formula or prefer alternative?**

### Q2: Go-Live Date for Portfolio Filter

❓ **When is the "go-live date" for filtering trades in portfolio?**
- Default to first trade date?
- Specific date provided by client?
- User-configurable in dashboard?

### Q3: Candle Data Source for Max DD/Profit

❓ **Which exchange API to use for historical candle data?**
- MEXC, Bybit, Alpaca?
- Different per exchange account?
- Fallback strategy if API unavailable?

### Q4: Win Rate Definition

Is Win Rate defined as:
- Trades with positive P&L / Total trades?
- Or specific calculation preferred?

---

## Acceptance Criteria (from CLAUDE.md)

- [ ] Portfolio page shows only tickers with >= 1 trade from go-live date
- [ ] Clicking ticker opens ticker detail page with correct ROI, win rate, trade history
- [ ] Clicking trade opens trade detail page with all specified fields populated
- [ ] Max drawdown and max profit values reflect correct historical candle range
- [ ] R-Multiple calculated using formula agreed upon by client
- [ ] Dashboard continues to work for all existing pages (no regression)

---

## Implementation Plan

### Phase 1: Backend Setup (Day 1-2)
- [ ] Verify trade data in MongoDB
- [ ] Create API endpoints for portfolio data
- [ ] Implement ticker metrics calculation
- [ ] Implement candle data fetching for Max DD/Profit

### Phase 2: Frontend Portfolio & Ticker Pages (Day 3-4)
- [ ] Create portfolio.html page
- [ ] Create ticker_detail.html page
- [ ] Wire up API calls
- [ ] Add navigation links

### Phase 3: Frontend Trade Detail Page (Day 5-6)
- [ ] Create trade_detail.html page
- [ ] Display all required fields
- [ ] Calculate and display R-Multiple
- [ ] Fetch and display Max DD/Profit
- [ ] Format data nicely

### Phase 4: Testing & Polish (Day 7)
- [ ] Test all links and navigation
- [ ] Verify data calculations
- [ ] Check for edge cases
- [ ] No regression on existing pages

---

## Next Steps

**Before Starting Implementation:**

1. ✅ Client confirms R-Multiple formula
2. ✅ Client specifies go-live date
3. ✅ Client confirms candle data sources
4. ✅ Verify current trade data in MongoDB is complete

**Then:**

1. Create backend API endpoints
2. Build frontend pages
3. Test calculations and formulas
4. Deploy and validate

---

## Notes

- All metrics computed on-demand (not pre-calculated)
- Max DD/Profit fetched via API when user opens trade detail
- No new MongoDB collections needed
- Existing data structure supports all requirements
- Dashboard should remain responsive during candle API calls

