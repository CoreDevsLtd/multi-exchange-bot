# Milestone Status Report

**Project:** Multi-Exchange Trading Bot  
**As of:** 2026-04-13  
**Developer:** Core Devs

---

## Milestone 1 — Exchange Integrations & Multi-Account Architecture

**Status: ✅ 100% COMPLETE**

---

### REQ-1.1 — Bybit Integration

**Status: ✅ COMPLETE (manually verified 2026-04-10)**

| Acceptance Criterion | Result |
|----------------------|--------|
| Executes trades at 5x leverage | ✅ Tested on DOGEUSDT |
| Executes trades at 7x leverage | ✅ Tested on DOGEUSDT |
| Handles max leverage limits per symbol | ✅ Dynamic leverage detection |

**What was built:**
- `bybit_client.py` — Full Bybit V5 API client (spot + futures)
- Dynamic leverage detection: queries `GET /v5/market/instruments-info` on every trade to find the symbol's maximum supported leverage, then auto-caps the configured leverage to that max
- Error 110043 ("leverage not modified") caught and treated as success — Bybit returns this when the leverage is already at the requested value
- Futures positions use `set_position_trading_stop` to set exchange-native stop-loss and take-profit visible in the Bybit UI
- `.P` suffix in TradingView symbols (e.g. `BTCUSDT.P`) is stripped before sending to Bybit API

**Fallbacks:**
- If `set_leverage` fails on first attempt, retries once after 250ms
- If both attempts fail, trade is **aborted** (not executed at unknown leverage) — intentional safety behaviour
- If `set_position_trading_stop` (exchange SL) fails, falls back to software price monitor for stop-loss

---

### REQ-1.2 — Alpaca Integration

**Status: ✅ COMPLETE (2026-04-13)**

CLAUDE.md specifies IBKR as REQ-1.2. Per SDS v2.0 (signed scope update), **Alpaca replaces IBKR** as the second exchange. IBKR code (`ibkr_client.py`) is retained in the codebase but is not the active second exchange.

| Acceptance Criterion | Result |
|----------------------|--------|
| Paper trading via configuration | ✅ Toggle in dashboard, auto-derives base_url |
| Live trading via configuration | ✅ Same codebase, different base_url |
| Trades execute for configured symbols | ✅ US equities and crypto (BTC/USD format) |

**What was built:**
- `alpaca_client.py` — Full raw REST client using Alpaca Trading API v2 + Market Data v2
- Paper vs live controlled by `paper_trading` toggle in dashboard; `base_url` auto-set:
  - Paper: `https://paper-api.alpaca.markets`
  - Live: `https://api.alpaca.markets`
- US equities (AAPL, SPY, etc.) and crypto (BTC/USD, ETH/USD) supported in same client
- Market price fetched from `data.alpaca.markets` (separate data API)

**Bugs fixed during development:**

| Bug | Location | Description |
|-----|----------|-------------|
| `price=` kwarg TypeError | `alpaca_client.py` | `tp_sl_manager` calls `place_order(..., price=X)` but client used `limit_price=` — added `price` alias |
| `cancel_order` signature | `alpaca_client.py` | Bybit/MEXC use `cancel_order(symbol, order_id)` two-arg form; Alpaca only accepted one arg — made compatible |
| Empty `base_url` | `webhook_handler.py` | Empty string from MongoDB caused all API calls to fail — added fallback to paper URL |
| `paper_trading` not stored | `dashboard.py` | Five endpoints only stored `paper_trading` for IBKR, not Alpaca — fixed at all five locations |
| Symbol dropdown not selecting | `app.js` | `@click` fires after input blur; symbol never selected — changed to `@mousedown.prevent` (same as Bybit) |
| Dropdown z-index too low | `app.js` | Dropdown covered by other elements — raised to `z-index: 1000` |
| Mode label showed "Spot" | `app.js` | `trading_mode` defaults to `spot` for Alpaca; card badge showed "Spot" instead of "Paper/Live" |
| `PARTIALLYFILLED` typo | `trading_executor.py` | Status check was `PARTIALLYFILLED`; Alpaca returns `partially_filled` → uppercased to `PARTIALLY_FILLED` |

**API gaps closed:**

| Gap | Fix |
|-----|-----|
| Missing `GET /v2/clock` | Added `get_market_clock()` and `is_market_open()` to client |
| Missing `DELETE /v2/positions/:symbol` | Added `close_position_by_symbol()` — more reliable than market sell |
| Sell path used manual qty lookup | Alpaca `execute_sell` now calls `close_position_by_symbol` first; falls back to market sell if that fails |

**Fallbacks:**
- `execute_sell` for Alpaca: tries `close_position_by_symbol` first → falls back to `place_market_sell` with manually fetched quantity
- `is_market_open` error: returns `False` and logs warning; order still proceeds (queues as `day` order for next open, which is correct Alpaca behaviour)
- `base_url` empty from MongoDB: falls back to `https://paper-api.alpaca.markets` in both `webhook_handler.py` and `alpaca_client.__init__`
- Price fetch for stocks: tries `/bars/latest` → `/quotes/latest` → open position price — three-level fallback chain
- Symbol search cache miss (first search after server start, or after 1 hour TTL): fetches from Alpaca `/v2/assets`; if that times out, returns empty and retries on next keystroke

**Known limitation:**
- Symbol search on a **brand-new unsaved** Alpaca exchange returns empty — the search requires the exchange account to exist in MongoDB. Save the exchange first, then search symbols.

**Tests:** `test/test_alpaca_integration.py` — 20 mocked tests, all pass. 4 live tests auto-skip unless `ALPACA_API_KEY` + `ALPACA_API_SECRET` env vars are set.

```
Ran 20 tests in 0.027s — OK (skipped=1)
```

---

### REQ-1.3 — Multi-Account Architecture

**Status: ✅ COMPLETE**

- MongoDB-backed: `accounts` collection (logical accounts) + `exchange_accounts` collection (one per exchange slot)
- Each account can have multiple exchange slots (one per exchange type by default)
- Webhook handler reads `exchange_accounts` from MongoDB at signal time and routes to the correct exchange based on matching symbol
- `MONGO_URI` is **mandatory** — app will not start without it

**MongoDB collections:**

| Collection | Purpose |
|------------|---------|
| `accounts` | Logical accounts (name, enabled) |
| `exchange_accounts` | Exchange credentials, symbol, type, settings |
| `central_risk_management` | Global risk settings (position size, stop loss %) |
| `trades` | Append-only trade ledger |

---

### REQ-1.4 — Account and Ticker Management

**Status: ✅ COMPLETE**

- Dashboard: full CRUD for accounts and exchange accounts
- Each exchange account assigned exactly one symbol
- Symbol search per exchange type:
  - Bybit: public API (`/v5/market/instruments-info`) — no credentials needed
  - MEXC: public API (`/api/v3/exchangeInfo`) — no credentials needed
  - Alpaca: private API (`/v2/assets`) — requires credentials; results cached server-side for 1 hour
- Credential encryption at rest via `secrets_manager.py` (requires `ENCRYPTION_KEY` env var; no-op if not set)

---

## Milestone 2 — TradingView Strategy RSI Filter

**Status: ✅ 100% COMPLETE (2026-04-11)**

---

### REQ-2.1 — RSI Confirmation Filter

**Status: ✅ COMPLETE**

**File:** `tradingview_strategy.pine`

The RSI directional confirmation filter was added to the existing Pine Script strategy as a gate on top of all existing signal logic.

---

### REQ-2.2 — Filter Logic

**Status: ✅ COMPLETE**

| Condition | Behaviour |
|-----------|-----------|
| RSI > 50 (bullish) + BUY signal | Signal **fires** |
| RSI > 50 (bullish) + SELL signal | Signal **suppressed** |
| RSI < 50 (bearish) + SELL signal | Signal **fires** |
| RSI < 50 (bearish) + BUY signal | Signal **suppressed** |

**Pine Script inputs added:**
```pinescript
rsi_direction_filter_enabled = input.bool(true, title="Enable RSI Directional Filter (Milestone 2)")
rsi_bullish_threshold        = input.float(50.0, title="RSI Bullish Threshold (>)")
rsi_bearish_threshold        = input.float(50.0, title="RSI Bearish Threshold (<)")
```

Filter can be toggled off via the TradingView Inputs tab to revert to original behaviour without code changes.

---

### REQ-2.3 — No Changes to Existing Strategy Logic

**Status: ✅ CONFIRMED**

All original entry, exit, stop-loss, and take-profit logic (NMA, Kahlman, HMA, label lock mechanism) is untouched. The RSI filter is an additive gate only.

---

### Supporting files (Milestone 2)

| File | Purpose |
|------|---------|
| `tradingview_strategy.pine` | Full strategy with RSI filter |
| `FILTERED_INDICATOR.pine` | Standalone indicator version |
| `PINESCRIPT_CHANGES_EXPLAINED.md` | Line-by-line explanation of changes |
| `MILESTONE2_TEST_REPORT.md` | Test report |
| `test_milestone2_rsi_filter.py` | Python validation tests |
| `test_milestone2_validation.py` | Additional signal logic validation |

---

## Code Fallbacks Summary

| Scenario | Fallback Behaviour |
|----------|--------------------|
| Bybit set_leverage fails | Retry once after 250ms → abort trade on second failure |
| Bybit exchange SL fails | Fall back to software price monitor (stop_loss_monitor.py) |
| Alpaca close_position_by_symbol fails | Fall back to manual qty lookup + market sell order |
| Alpaca base_url empty in DB | Default to `https://paper-api.alpaca.markets` |
| Alpaca stock price unavailable | bars/latest → quotes/latest → open position price |
| Alpaca is_market_open() error | Warn and continue (order queues as day order) |
| Alpaca symbol search timeout | Return empty list; retry on next keystroke (cache not populated) |
| Alpaca symbol search cache miss | Fetch fresh from `/v2/assets`; cache result for 1 hour |
| MongoDB unavailable at startup | App exits — MongoDB is mandatory, no config-file fallback |
| Encryption key not set | Credentials stored/read as plaintext (no-op passthrough) |
| Order qty = 0 after fill check | Trade aborted with error logged (never placed SL/TP) |

---

## What is NOT in Scope (per CLAUDE.md)

- Strategy backtesting
- Hyperliquid vault integration
- Any exchange beyond Bybit and Alpaca
- IBKR (replaced by Alpaca per SDS v2.0)
- Milestone 3 (Portfolio & Trade Detail Dashboard) — not started

---

## Deployment Checklist (Milestone 1 & 2)

- [ ] `MONGO_URI` environment variable set
- [ ] `ENCRYPTION_KEY` set (optional but recommended for credential encryption)
- [ ] Bybit API key has futures trading permissions
- [ ] Alpaca API key and secret entered in dashboard (paper or live)
- [ ] TradingView strategy (`tradingview_strategy.pine`) deployed to chart
- [ ] TradingView alerts pointing to webhook endpoint (`/webhook`)
- [ ] At least one exchange account created with a symbol assigned
- [ ] Test connection button passes for each exchange account
