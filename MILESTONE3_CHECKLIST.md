# Milestone 3: Implementation Checklist

**Status:** 📋 Pre-Implementation Planning  
**Last Updated:** 2026-04-11

---

## Pre-Implementation Phase

### ✅ Phase 0: Client Sign-Off (BEFORE Starting Development)

**Critical Questions Requiring Client Confirmation:**

- [ ] **R-Multiple Formula**
  - Confirm: `R-Multiple = P&L / |Entry - Stop Loss|`
  - Alternative formula if needed
  - Document approval

- [ ] **Go-Live Date**
  - When should portfolio filter start showing trades?
  - Default: First trade execution date?
  - Specific date: _______________?

- [ ] **Candle Data Sources**
  - Which exchange APIs for historical candles?
  - [ ] MEXC
  - [ ] Bybit
  - [ ] Alpaca
  - Fallback strategy if API unavailable?

- [ ] **Win Rate Definition**
  - Confirm: Any trade with `result_usd > 0` is a win?
  - Alternative calculation preferred?

### ✅ Phase 1: Data Verification

**Status:** 🔴 BLOCKED - No trades in database yet

The trading system is operational, but Milestone 3 requires actual trade data to develop and test.

**What's needed:**
- [ ] Wait for trading system to execute trades on live data
- [ ] Verify trades are being persisted to MongoDB `trades` collection
- [ ] Check that all required fields are present:
  - [ ] symbol
  - [ ] direction (Long/Short)
  - [ ] entry_price
  - [ ] exit_price
  - [ ] stop_loss
  - [ ] tp_hits (array of 5 booleans)
  - [ ] result_usd
  - [ ] result_percent
  - [ ] exit_reason
  - [ ] trade_duration_sec
  - [ ] timestamp_open
  - [ ] timestamp_close
  - [ ] initial_quantity

**Verification Command:**
```bash
python3 check_trades_data.py
```

**Once data exists, verify:**
- [ ] At least 5-10 trades in collection
- [ ] Mix of winning and losing trades
- [ ] Different symbols/tickers
- [ ] All required fields populated

---

## Development Phase

### Phase 2: Backend Development

**If proceeding with Milestone 3 development:**

#### API Endpoints

- [ ] `GET /api/portfolio`
  - Returns list of unique symbols with trade counts
  - File: dashboard.py
  - Lines: _____ (to be assigned)

- [ ] `GET /api/portfolio/<symbol>`
  - Returns ticker metrics (ROI, win rate, trade history)
  - File: dashboard.py
  - Lines: _____ (to be assigned)

- [ ] `GET /api/trades/<trade_id>`
  - Returns complete trade document
  - File: dashboard.py
  - Lines: _____ (to be assigned)

- [ ] `GET /api/trades/<trade_id>/max-metrics`
  - Fetches candle data and calculates max DD/profit
  - File: dashboard.py (or new file: trade_metrics.py)
  - Lines: _____ (to be assigned)

#### Helper Functions

- [ ] `calculate_roi(symbol)`
  - Query: Sum all P&L for symbol / initial capital
  - File: dashboard.py or trade_analytics.py
  - Status: ___________

- [ ] `calculate_win_rate(symbol)`
  - Query: Count winning trades / total trades
  - File: dashboard.py or trade_analytics.py
  - Status: ___________

- [ ] `calculate_r_multiple(trade)`
  - Formula: P&L / |Entry - Stop Loss|
  - File: dashboard.py or trade_analytics.py
  - Status: ___________

- [ ] `fetch_max_dd_profit(symbol, entry_time, exit_time, direction)`
  - Calls exchange API for candle data
  - Calculates worst/best price
  - File: trade_metrics.py (new)
  - Status: ___________

### Phase 3: Frontend Development

#### New HTML Pages

- [ ] `templates/portfolio.html`
  - Lists all tickers with trades
  - Shows trade count, win rate, ROI (optional)
  - Links to ticker detail pages
  - Status: ___________

- [ ] `templates/ticker_detail.html`
  - Shows ROI and Win Rate metrics
  - Lists trades chronologically
  - Links to trade detail pages
  - Status: ___________

- [ ] `templates/trade_detail.html`
  - Shows all required trade fields
  - Displays calculated metrics
  - Visual layout (cards or table)
  - Status: ___________

#### JavaScript/Frontend Logic

- [ ] Portfolio page load and list rendering
  - File: static/js/portfolio.js (new)
  - Status: ___________

- [ ] Ticker detail page load and metrics display
  - File: static/js/ticker_detail.js (new)
  - Status: ___________

- [ ] Trade detail page load with candle data fetching
  - File: static/js/trade_detail.js (new)
  - Status: ___________

#### Navigation

- [ ] Add "Portfolio" link to main dashboard navigation
  - File: templates/base.html or templates/dashboard.html
  - Status: ___________

- [ ] Add back links (Portfolio → Ticker → Trade)
  - Status: ___________

### Phase 4: Testing

#### Unit Tests

- [ ] Test ROI calculation
  - File: test_milestone3_calculations.py
  - Status: ___________

- [ ] Test win rate calculation
  - File: test_milestone3_calculations.py
  - Status: ___________

- [ ] Test R-Multiple calculation
  - File: test_milestone3_calculations.py
  - Status: ___________

#### Integration Tests

- [ ] Test portfolio page API endpoint
  - File: test_milestone3_integration.py
  - Status: ___________

- [ ] Test ticker detail page API endpoint
  - File: test_milestone3_integration.py
  - Status: ___________

- [ ] Test trade detail page API endpoint
  - File: test_milestone3_integration.py
  - Status: ___________

- [ ] Test candle data fetching for max metrics
  - File: test_milestone3_integration.py
  - Status: ___________

#### Functional Tests

- [ ] Portfolio page displays all tickers
  - Manual test in browser
  - Status: ___________

- [ ] Clicking ticker opens ticker detail page
  - Manual test in browser
  - Status: ___________

- [ ] Ticker detail shows correct metrics
  - Compare with manual calculations
  - Status: ___________

- [ ] Clicking trade opens trade detail page
  - Manual test in browser
  - Status: ___________

- [ ] Trade detail shows all required fields
  - Verify against data dictionary
  - Status: ___________

- [ ] R-Multiple calculated correctly
  - Verify formula: P&L / |Entry - SL|
  - Status: ___________

- [ ] Max DD/Profit calculated correctly
  - Compare with manual candle analysis
  - Status: ___________

#### Regression Tests

- [ ] Dashboard home page still works
  - Status: ___________

- [ ] Exchange accounts page still works
  - Status: ___________

- [ ] Settings pages still work
  - Status: ___________

- [ ] Risk management page still works
  - Status: ___________

- [ ] No new errors in logs
  - Status: ___________

---

## Data Requirements

### Current Status
```
Total Trades: 0
Ready for M3: ❌ NO (need actual trade data)
```

### Before Development Can Begin

**Need:**
1. At least 5-10 executed trades
2. Mix of symbols (BTC, ETH, etc.)
3. Mix of long/short trades
4. Mix of winning/losing trades
5. All required fields populated

**How to Verify:**
```bash
python3 check_trades_data.py
```

Should show:
```
Total trades: 10+
Required fields: ✅ All present
Ready for Milestone 3: ✅ YES
```

---

## Implementation Order

**Recommended sequence:**

1. **Get Trade Data** (CRITICAL - BLOCKED)
   - Wait for actual trades to execute
   - Verify data completeness

2. **Backend APIs** (5-8 hours)
   - Portfolio endpoint
   - Ticker detail endpoint
   - Trade detail endpoint
   - Max metrics endpoint

3. **Frontend Pages** (8-12 hours)
   - Portfolio page HTML/JS
   - Ticker detail page HTML/JS
   - Trade detail page HTML/JS
   - Navigation wiring

4. **Testing & Validation** (4-6 hours)
   - Unit tests
   - Integration tests
   - Manual browser testing
   - Regression testing

5. **Polish & Deploy** (2-3 hours)
   - Error handling
   - Edge cases
   - Styling/UX
   - Deployment to production

**Total Estimated Effort:** 20-30 hours (3-4 days with breaks)

---

## Risk Mitigation

### Risk: No Trade Data Available
- **Impact:** Cannot develop/test Milestone 3
- **Mitigation:** Use mock/synthetic trade data for development
- **Fallback:** Deploy with synthetic data, update with real data later

### Risk: Missing Fields in Trade Documents
- **Impact:** Cannot display required info
- **Mitigation:** Fix position_manager.py to store all fields
- **Fallback:** Add missing fields retroactively

### Risk: Candle API Rate Limits
- **Impact:** Max DD/Profit calculation fails
- **Mitigation:** Cache candle data, implement rate limiting
- **Fallback:** Show "calculating..." message, compute async

### Risk: Performance Issues
- **Impact:** Dashboard slow with many trades
- **Mitigation:** Pagination, lazy loading, indexing
- **Fallback:** Limit initial display, add search/filter

---

## Success Criteria

✅ **Milestone 3 Complete When:**

- [ ] Portfolio page shows all tickers with trades
- [ ] ROI and Win Rate correctly calculated
- [ ] Clicking ticker opens ticker detail with trade history
- [ ] Clicking trade opens trade detail with all fields
- [ ] R-Multiple calculated per agreed formula
- [ ] Max DD/Profit shown and accurate
- [ ] All calculations verified against manual calculations
- [ ] No regression on existing dashboard pages
- [ ] All tests passing (unit + integration)

---

## Sign-Off

**Client Approval Needed:**
- [ ] R-Multiple formula confirmed
- [ ] Go-live date specified
- [ ] Candle data sources confirmed
- [ ] Ready to proceed with development

**Development Sign-Off:**
- [ ] Requirements document complete
- [ ] Checklist prepared
- [ ] Code review plan established
- [ ] Testing strategy defined

**Deployment Sign-Off:**
- [ ] All tests passing
- [ ] Data integrity verified
- [ ] Performance acceptable
- [ ] Ready for production

---

## Notes

- Dashboard should remain responsive during candle API calls (use async)
- Consider caching candle data to reduce API calls
- Add error messages if data unavailable
- Consider pagination for large trade lists
- Mobile-friendly design recommended

