# TradingView Integration Guide

A single, consolidated guide containing the full contents of the project's TradingView documentation: indicator explanation, alert setup (quick and detailed), complete webhook setup, webhook alternatives, troubleshooting, examples, and security notes.

---

## Quick Links

- **Overview & Indicator Explanation**: What the `WT + Ideal BB + RSI` indicator does
- **Alert Setup**: Quick + Detailed instructions for TradingView alerts
- **Webhook Setup**: How to configure your webhook URL and test it
- **Alternatives**: Email-to-webhook bridges and fallbacks
- **Troubleshooting**: Common issues and checks
- **Examples**: cURL test payloads
- **Security & Notes**: Authentication and allowlisting

---

## Overview

This repository uses a combined TradingView indicator `WT + Ideal BB + RSI` that emits webhook-ready JSON signals when three indicator conditions align. The indicator only generates signals on closed candles and uses a short timing window after a WaveTrend cross to validate other indicators.

Key ideas:
- Signals fire only when all three indicators align (WaveTrend, Bollinger Bands, RSI)
- Alerts should be configured to trigger `Once per bar close`
- The Pine Script can send `Strategy Buy Signal (JSON)` and `Strategy Sell Signal (JSON)` payloads directly to your webhook

---

## Consolidated Source Documents

Below are the original files merged into this document. Each section reproduces the original file verbatim so no information is lost.

---

### Original: TRADINGVIEW_WEBHOOK_SETUP_COMPLETE.md

# Complete TradingView Webhook Setup Guide

## ⚠️ Critical Requirements

### 1. **TradingView Subscription**
- ✅ **Webhooks require a PAID TradingView subscription** (Pro, Pro+, or Premium)
- ❌ Free accounts **CANNOT** use webhooks
- **2FA must be enabled** on your TradingView account

### 2. **Port Restrictions**
- TradingView **ONLY accepts ports 80 (HTTP) and 443 (HTTPS)**
- Your Railway deployment uses HTTPS (port 443) automatically ✅
- **DO NOT** use custom ports in the webhook URL

### 3. **IP Addresses**
TradingView uses these IPs (may need allowlisting on your server):
- `52.89.214.238`
- `34.212.75.30`
- `54.218.53.128`
- `52.32.178.7`

---

## 📋 Step-by-Step Setup

### Step 1: Verify Your Webhook URL

Your webhook endpoint should be:
```
https://web-production-93165.up.railway.app/webhook
```

**Important**: 
- ✅ Use **HTTPS** (not HTTP)
- ✅ Use port **443** (default for HTTPS, don't specify port)
- ❌ **DO NOT** use `:8080` or any other port
- ✅ Endpoint must be `/webhook`

### Step 2: Test Your Webhook Endpoint

Test from terminal to verify it's working:
```bash
curl -X POST https://web-production-93165.up.railway.app/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "signal": "BUY",
    "price": {
      "close": 50000
    }
  }'
```

Expected response:
```json
{
  "status": "received",
  "message": "Signal received successfully...",
  "signal": {...}
}
```

### Step 3: Enable 2FA on TradingView

**REQUIRED**: Webhooks only work with 2FA enabled.

1. Go to TradingView → Settings → Security
2. Enable **Two-Factor Authentication (2FA)**
3. Complete the setup process

### Step 4: Create Alert in TradingView

#### 4.1 Open Your Chart
1. Go to [TradingView](https://www.tradingview.com)
2. Open a chart with your indicator (`WT + Ideal BB + RSI`)
3. Make sure indicator is loaded and visible

#### 4.2 Create Alert
1. Click the **Alert** button (bell icon 🔔) at the top
2. Click **"Create Alert"**

#### 4.3 Configure Alert

**Condition Tab:**
- **Condition**: Select your indicator
- **Select**: `WT + Ideal BB + RSI`
- **Choose**: `Strategy Buy Signal (JSON)` for BUY signals
- **OR**: `Strategy Sell Signal (JSON)` for SELL signals

**Options Tab:**
- **Alert Name**: `Trading Bot - BUY Signals` (or SELL)
- **Expiration**: `No Expiration` (or your preference)
- **Trigger**: `Once Per Bar Close` (recommended)

**Notifications Tab:**
- ✅ **Enable Webhook URL**
- **Webhook URL**: Enter:
  ```
  https://web-production-93165.up.railway.app/webhook
  ```
- **Message**: The indicator automatically sends JSON format

**Message Tab:**
- The message will be automatically formatted by the indicator
- **DO NOT** manually edit the message - it's set in the Pine Script

#### 4.4 Save Alert
1. Click **"Create"** to save
2. Alert is now active

---

## 🔧 Alert Message Format

The Pine Script indicator sends the full JSON payload automatically. The webhook handler expects this format:

```json
{
  "symbol": "BTCUSDT",
  "time": 1234567890,
  "signal": "BUY",
  "indicators": {
    "wt": {...},
    "bb": {...},
    "rsi": {...}
  },
  "price": {
    "close": 50000,
    "open": 49900,
    "high": 50100,
    "low": 49800
  },
  "strategy": {
    "entry_type": "NEXT_CANDLE_OPEN",
    "all_conditions_met": true
  }
}
```

**Important**: The Pine Script has been updated to send the full JSON payload. Make sure you're using the latest version of `tradingview_indicators.pine`.

---

## 🐛 Troubleshooting

### Issue 1: "No alerts received from TradingView"

**Checklist:**
1. ✅ **2FA enabled** on TradingView account?
2. ✅ **Paid subscription** (Pro, Pro+, or Premium)?
3. ✅ **Webhook URL correct** (HTTPS, no port number)?
4. ✅ **Alert condition** matches indicator name?
5. ✅ **Alert is enabled** (not paused/disabled)?

**Test:**
```bash
# Test webhook manually
curl -X POST https://web-production-93165.up.railway.app/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "signal": "BUY", "price": {"close": 50000}}'
```

### Issue 2: "Webhook URL field not visible"

**Solutions:**
1. **Check Notifications Tab**: Webhook URL is in "Notifications" tab, not "Message" tab
2. **Upgrade Subscription**: Free accounts don't have webhook option
3. **Enable 2FA**: Required for webhooks

### Issue 3: "Connection timeout"

**Causes:**
- TradingView cancels requests after 3 seconds
- Server taking too long to respond

**Solutions:**
- Check Railway logs for slow responses
- Ensure webhook handler responds quickly (< 1 second)

### Issue 4: "Invalid signal data"

**Causes:**
- Alert message format doesn't match expected JSON
- Pine Script not sending full payload

**Solutions:**
- Update Pine Script to latest version
- Verify alert condition uses "Strategy Buy Signal (JSON)" or "Strategy Sell Signal (JSON)"

---

## 📝 Alert Configuration Checklist

Before creating alert, verify:

- [ ] TradingView account has **paid subscription** (Pro/Pro+/Premium)
- [ ] **2FA is enabled** on TradingView account
- [ ] Indicator `WT + Ideal BB + RSI` is loaded on chart
- [ ] Webhook URL is **HTTPS** (not HTTP)
- [ ] Webhook URL has **no port number** (uses default 443)
- [ ] Webhook URL ends with `/webhook`
- [ ] Alert condition matches indicator name exactly
- [ ] Alert uses "Strategy Buy Signal (JSON)" or "Strategy Sell Signal (JSON)"
- [ ] Alert is set to "Once Per Bar Close" (recommended)
- [ ] Alert expiration is set (or "No Expiration")

---

## 🔍 Verify Webhook is Working

### Method 1: Check Dashboard
1. Open your dashboard: `https://web-production-93165.up.railway.app/`
2. Check "Recent Signals" section
3. If signals appear, webhook is working ✅

### Method 2: Check Railway Logs
1. Go to Railway dashboard
2. Open your project
3. Click "Logs" tab
4. Look for lines like:
   ```
   Received webhook: {...}
   Signal received: BTCUSDT BUY
   ```

### Method 3: Test Manually
```bash
curl -X POST https://web-production-93165.up.railway.app/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "signal": "BUY", "price": {"close": 50000}}'
```

Expected: `{"status": "received", ...}`

---

### Original: TRADINGVIEW_INDICATOR_EXPLANATION.md

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

**Why Ranges Instead Of Single Values:**
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

### Original: TRADINGVIEW_ALERT_QUICK_SETUP.md

# TradingView Alert Quick Setup Guide

## Step-by-Step Alert Configuration

### Step 1: Alert Condition (Settings Tab)

**Current (Wrong):**
- Condition: `Price` → `Crossing` → `WT+BB+RSI` → `WT1`

**Change to (Correct):**

1. Click on the **Condition** dropdown
2. Select your indicator: **"WT + Ideal BB + RSI"** (or "WT+BB+RSI")
3. Then select one of these alert conditions:
   - **"Strategy Buy Signal (JSON)"** - For BUY signals
   - **"Strategy Sell Signal (JSON)"** - For SELL signals

**OR** you can use the alternative:
   - **"Strategy Buy Signal (Webhook)"** - For BUY signals
   - **"Strategy Sell Signal (Webhook)"** - For SELL signals

### Step 2: Interval Settings

- **Interval**: Keep as **"Same as chart"** ✅
- **Timeframe**: Use your chart's timeframe (e.g., "24 minutes" is fine)

### Step 3: Trigger Frequency

**Recommended: "Once per bar close"** ✅
- This ensures signals only fire when the candle closes
- Prevents duplicate signals
- Matches the indicator's "closed candle" logic

**Options:**
- ✅ **"Once per bar close"** - Best for this strategy (recommended)
- ⚠️ "Once per bar" - May trigger multiple times
- ⚠️ "Only once" - Only fires once ever
- ⚠️ "Once per minute" - Too frequent

### Step 4: Expiration

- Set to **"No Expiration"** (or your preferred date)
- This keeps the alert active indefinitely

### Step 5: Webhook URL (Message Tab)

1. Click on the **"Message"** tab
2. Scroll down to **"Webhook URL"** field
3. Enter your webhook URL:
   ```
   https://web-production-93165.up.railway.app/webhook
   ```
4. **Message** field: You can leave it as `BUY` or `SELL`, or leave empty
   - The indicator automatically sends the full JSON payload

### Step 6: Notifications (Optional)

1. Click on the **"Notifications"** tab
2. Enable notifications if you want to be notified:
   - ✅ Email
   - ✅ Mobile Push
   - ✅ Desktop Popup

### Step 7: Create the Alert

1. Click **"Create"** button
2. The alert is now active!

---

### Original: TRADINGVIEW_WEBHOOK_ALTERNATIVES.md

# TradingView Webhook Setup - Alternative Methods

## Issue: No Webhook Option Visible

If you don't see a "Webhook URL" field in the Message tab, here are the solutions:

---

## Solution 1: Check Notifications Tab

**Webhook URL is usually in the "Notifications" tab, NOT the Message tab!**

### Steps:
1. Click on the **"Notifications"** tab (the one with the "3" badge)
2. Look for **"Webhook URL"** field
3. If you see it, enter:
   ```
   https://web-production-93165.up.railway.app/webhook
   ```

---

## Solution 2: TradingView Subscription Requirement

**Webhook URLs require a paid TradingView subscription:**
- ✅ **Pro** plan ($14.95/month) - Includes webhooks
- ✅ **Pro+** plan ($29.95/month) - Includes webhooks
- ✅ **Premium** plan ($59.95/month) - Includes webhooks
- ❌ **Free** plan - **NO webhooks** (only email/push notifications)

### If you have a free account:
You have two options:

#### Option A: Upgrade to Pro (Recommended)
- Upgrade to TradingView Pro or higher
- Webhook option will appear
- Direct integration with your bot

#### Option B: Use Email-to-Webhook Bridge (Free Alternative)
- Set up email alerts
- Use an email-to-webhook service (like Zapier, Make.com, or custom solution)
- Forward emails to webhook

---

## Solution 3: Check for "Actions" or "Webhook" Section

Sometimes webhook is in a different location:

1. **Look for "Actions" section** in Settings or Notifications tab
2. **Look for "Webhook URL"** field anywhere in the dialog
3. **Check if there's a "+" button** to add webhook action

---

## Solution 4: Email Alert + Parser (Free Alternative)

If you can't use webhooks, you can set up email alerts and parse them:

### Step 1: Configure Email Alert
1. In **Notifications** tab:
   - ✅ Enable **Email** notifications
   - Enter your email address

2. In **Message** tab:
   - Set message to: `BUY` or `SELL`
   - Or use: `{{ticker}} | {{signal}} | {{close}}`

### Step 2: Email-to-Webhook Service
Use a service like:
- **Zapier** (free tier available)
- **Make.com** (formerly Integromat)
- **n8n** (self-hosted, free)
- **Custom email parser** (Python script)

### Step 3: Forward to Webhook
The service will:
1. Receive email from TradingView
2. Parse the alert message
3. Forward to your webhook: `https://web-production-93165.up.railway.app/webhook`

---

## Solution 5: Manual Testing (For Development)

While setting up webhooks, you can manually test your webhook:

### Test BUY Signal:
```bash
curl -X POST https://web-production-93165.up.railway.app/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "time": 1234567890,
    "signal": "BUY",
    "price": {
      "close": 50000.00
    }
  }'
```

### Test SELL Signal:
```bash
curl -X POST https://web-production-93165.up.railway.app/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "time": 1234567890,
    "signal": "SELL",
    "price": {
      "close": 51000.00
    }
  }'
```

---

## Quick Checklist

### If you have Pro/Premium:
- [ ] Check **Notifications** tab for "Webhook URL"
- [ ] Enter: `https://web-production-93165.up.railway.app/webhook`
- [ ] Save alert

### If you have Free account:
- [ ] Option A: Upgrade to Pro ($14.95/month) ✅ Recommended
- [ ] Option B: Set up email alerts + email-to-webhook bridge
- [ ] Option C: Use manual testing for now

---

## Recommended Approach

**Best Solution:**
1. ✅ Upgrade to TradingView **Pro** ($14.95/month)
2. ✅ Webhook option will appear
3. ✅ Direct integration - no middleman
4. ✅ Most reliable and fastest

**Budget Alternative:**
1. Use **email alerts** (free)
2. Set up **Zapier** free tier
3. Create Zap: Email → Parse → Webhook
4. Forward to your bot

---

### Original: TRADINGVIEW_ALERT_SETUP.md

# TradingView Alert Setup Guide

## Quick Setup Steps

### 1. Webhook Endpoint URL

Your webhook endpoint is:
```
https://web-production-93165.up.railway.app/webhook
```

### 2. Setting Up TradingView Alerts

#### Step 1: Open Your Indicator on TradingView
1. Go to [TradingView](https://www.tradingview.com)
2. Open a chart with your indicator loaded (`WT + Ideal BB + RSI`)
3. Make sure the indicator is visible and working

#### Step 2: Create an Alert
1. Click the **Alert** button (bell icon) at the top of the chart
2. Click **"Create Alert"**

#### Step 3: Configure Alert Conditions
1. **Condition**: Select your indicator
   - Look for: `WT + Ideal BB + RSI`
   - Select: **"Strategy Buy Signal (JSON)"** for BUY signals
   - OR **"Strategy Sell Signal (JSON)"** for SELL signals

2. **Alert Name**: Give it a descriptive name
   - Example: `Trading Bot - BUY Signals`
   - Example: `Trading Bot - SELL Signals`

3. **Expiration**: Set to **"No Expiration"** (or your preferred duration)

4. **Webhook URL**: Enter your webhook endpoint
   ```
   https://web-production-93165.up.railway.app/webhook
   ```

5. **Message Format**: The indicator automatically sends JSON format
   - The message will be: `BUY` or `SELL`
   - The webhook handler will parse the full JSON payload automatically

#### Step 4: Save the Alert
1. Click **"Create"** to save the alert
2. The alert will now trigger when conditions are met

### 3. Testing the Webhook

#### Test with cURL (Optional)
```bash
# Test BUY signal
curl -X POST https://web-production-93165.up.railway.app/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "time": 1234567890,
    "signal": "BUY",
    "price": {
      "close": 50000.00
    }
  }'

# Test SELL signal
curl -X POST https://web-production-93165.up.railway.app/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "time": 1234567890,
    "signal": "SELL",
    "price": {
      "close": 51000.00
    }
  }'
```

#### Check Dashboard
1. Go to your dashboard: https://web-production-93165.up.railway.app/
2. Check the **"TradingView Signal Status"** section
3. You should see:
   - **Status**: Connected (green)
   - **Last Signal**: Time of last signal
   - **Recent Signals**: Table showing all received signals

### 4. Alert Configuration Details

#### For BUY Signals:
- **Alert Condition**: `Strategy Buy Signal (JSON)`
- **Message**: `BUY` (or leave empty, indicator handles it)
- **Webhook URL**: `https://web-production-93165.up.railway.app/webhook`

#### For SELL Signals:
- **Alert Condition**: `Strategy Sell Signal (JSON)`
- **Message**: `SELL` (or leave empty, indicator handles it)
- **Webhook URL**: `https://web-production-93165.up.railway.app/webhook`

### 5. Signal Requirements

For a signal to be sent, **ALL** of these conditions must be met:

#### BUY Signal Requirements:
1. ✅ **WaveTrend**: WT1 crosses above WT2 (green dot appears)
2. ✅ **Bollinger Bands**: Price is above Moving Average
3. ✅ **RSI**: RSI is between 54-82 (buy range)

#### SELL Signal Requirements:
1. ✅ **WaveTrend**: WT1 crosses below WT2 (red dot appears)
2. ✅ **Bollinger Bands**: Price is below Moving Average
3. ✅ **RSI**: RSI is between 27-43 (sell range)

### 6. Monitoring Signals

#### Dashboard Features:
- **Real-time Status**: Shows if webhook is receiving signals
- **Signal History**: View all recent signals in a table
- **Trade Execution**: See if trades were executed successfully
- **Error Logging**: View any errors in signal processing

#### Check Logs (Railway):
1. Go to your Railway project dashboard
2. Click on your service
3. View **Logs** tab to see webhook requests in real-time

### 7. Troubleshooting

#### No Signals Received?
1. ✅ Check that alerts are **enabled** in TradingView
2. ✅ Verify webhook URL is correct: `https://web-production-93165.up.railway.app/webhook`
3. ✅ Check that all 3 indicator conditions are met (WT + BB + RSI)
4. ✅ Check Railway logs for any errors
5. ✅ Test webhook with cURL (see above)

#### Signals Not Executing Trades?
1. ✅ Check that exchange is **connected** in dashboard
2. ✅ Verify API keys are correct and have trading permissions
3. ✅ Check that exchange is **enabled** in dashboard
4. ✅ Review error messages in dashboard logs

#### Webhook Returns Error?
- **400 Bad Request**: Invalid signal format
- **500 Internal Server Error**: Server-side error (check logs)
- **Connection Refused**: Server might be down (check Railway status)

### 8. Webhook Payload Format

The indicator sends JSON payloads with this structure:
```json
{
  "symbol": "BTCUSDT",
  "time": 1234567890,
  "signal": "BUY",
  "indicators": {
    "wt": {
      "flag": true,
      "wt1": 12.5,
      "wt2": 10.2,
      "cross_type": "BULLISH",
      "window_active": true
    },
    "bb": {
      "flag": true,
      "upper": 52000,
      "lower": 48000,
      "basis": 50000,
      "ma_value": 50000,
      "percent_b": 0.5
    },
    "rsi": {
      "value": 65.5,
      "buy_threshold_min": 54.0,
      "buy_threshold_max": 82.0,
      "sell_threshold_min": 27.0,
      "sell_threshold_max": 43.0,
      "condition_met": true
    }
  },
  "price": {
    "close": 50000.00,
    "open": 49900.00,
    "high": 50100.00,
    "low": 49800.00
  },
  "strategy": {
    "entry_type": "NEXT_CANDLE_OPEN",
    "all_conditions_met": true
  }
}
```

### 9. Multiple Alerts Setup

You can create **two separate alerts**:
1. **One for BUY signals** → Uses "Strategy Buy Signal (JSON)"
2. **One for SELL signals** → Uses "Strategy Sell Signal (JSON)"

Both can use the same webhook URL. The server will automatically detect the signal type.

### 10. Security Notes

⚠️ **Important Security Considerations:**
- Your webhook endpoint is **public** (no authentication by default)
- Consider adding authentication if needed (IP whitelist, API key, etc.)
- Railway provides HTTPS automatically (secure connection)
- Monitor your logs for suspicious activity

---

## Quick Checklist

- [ ] Indicator loaded: `WT + Ideal BB + RSI`
- [ ] Alerts created: Buy + Sell using `Strategy ... (JSON)` conditions
- [ ] Trigger: `Once per bar close`
- [ ] Webhook URL: HTTPS and correct endpoint `/webhook`
- [ ] Test with `curl` successful

---

## Where to Edit

Edit this consolidated guide: [docs/TRADINGVIEW.md](TRADINGVIEW.md)

---

If you'd like, I can:

- split this into a short quickstart plus a long reference section, or
- create a PR branch and update any README links in this repo.

---

## Quick Links

- **Overview & Indicator Explanation**: What the `WT + Ideal BB + RSI` indicator does
- **Alert Setup**: Quick + Detailed instructions for TradingView alerts
- **Webhook Setup**: How to configure your webhook URL and test it
- **Alternatives**: Email-to-webhook bridges and fallbacks
- **Troubleshooting**: Common issues and checks
- **Examples**: cURL test payloads
- **Security & Notes**: Authentication and allowlisting

---

## Overview

This repository uses a combined TradingView indicator `WT + Ideal BB + RSI` that emits webhook-ready JSON signals when three indicator conditions align. The indicator only generates signals on closed candles and uses a short timing window after a WaveTrend cross to validate other indicators.

Key ideas:
- Signals fire only when all three indicators align (WaveTrend, Bollinger Bands, RSI)
- Alerts should be configured to trigger `Once per bar close`
- The Pine Script can send `Strategy Buy Signal (JSON)` and `Strategy Sell Signal (JSON)` payloads directly to your webhook

---

## Indicator Explanation (WT + Ideal BB + RSI)

Summary of the indicator and signal rules:

- WaveTrend (WT): momentum oscillator. Signals when `WT1` crosses `WT2` and opens a 3-bar window for alignment.
- Ideal Bollinger Bands (BB): EMA-based bands and a trend MA — price relative to MA is used for direction.
- RSI: custom ranges (Buy: 54–82, Sell: 27–43) rather than classic 70/30.

Signal logic (all required):

```
IF (WT1 crosses above WT2) AND (Price > MA) AND (RSI between 54-82) -> BUY
IF (WT1 crosses below WT2) AND (Price < MA) AND (RSI between 27-43) -> SELL
```

Signals are emitted on the next candle open after a confirmed closed-candle condition and only once per window.

---

## Alert Setup — Quick

Recommended minimal setup for two alerts (one BUY, one SELL):

- Condition: `WT + Ideal BB + RSI` → `Strategy Buy Signal (JSON)` (and `Strategy Sell Signal (JSON)` for the sell alert)
- Trigger: `Once per bar close` (recommended)
- Expiration: `No Expiration` (or your preference)
- Webhook URL: `https://web-production-93165.up.railway.app/webhook`
- Message: optional (the indicator sends JSON automatically)

Create two alerts (BUY and SELL) using the same webhook URL.

---

## Alert Setup — Detailed

Step-by-step:

1. Open a chart on TradingView and add the `WT + Ideal BB + RSI` indicator.
2. Click the Alert button (bell icon) → Create Alert.
3. In the **Condition** dropdown select the indicator and choose:
   - `Strategy Buy Signal (JSON)` for BUY
   - `Strategy Sell Signal (JSON)` for SELL
4. Interval: `Same as chart`.
5. Trigger Frequency: `Once per bar close`.
6. Notifications / Message tab: set **Webhook URL** to your webhook endpoint.
7. Click Create.

Notes:
- If you don't see webhook options, verify your TradingView subscription (webhooks require a paid plan) and check the Notifications tab.
- Do not edit the indicator's JSON message unless you know what you're doing; the Pine Script provides a full payload by design.

---

## Webhook Setup

Your webhook endpoint (example used across docs):

```
https://web-production-93165.up.railway.app/webhook
```

Important constraints from TradingView:

- TradingView accepts only HTTP(S) on ports 80 and 443 — use HTTPS and default port 443.
- Requests may time out quickly; keep your webhook handler lightweight and respond fast (< 1s preferred).
- If you need allowlisting, TradingView uses known IP ranges (check current docs); example IPs in this project:
  - `52.89.214.238`
  - `34.212.75.30`
  - `54.218.53.128`
  - `52.32.178.7`

---

## Webhook Payload Format

The indicator sends a JSON payload with the following structure (example):

```json
{
  "symbol": "BTCUSDT",
  "time": 1234567890,
  "signal": "BUY",
  "indicators": {
    "wt": {"wt1": 12.5, "wt2": 10.2, "cross_type": "BULLISH"},
    "bb": {"upper": 52000, "lower": 48000, "ma_value": 50000},
    "rsi": {"value": 65.5}
  },
  "price": {"close": 50000, "open": 49900, "high": 50100, "low": 49800},
  "strategy": {"entry_type": "NEXT_CANDLE_OPEN", "all_conditions_met": true}
}
```

The repository's webhook handler expects this shape and will parse `symbol`, `signal`, and `price.close` at minimum.

---

## Alternatives When Webhooks Are Unavailable

If you have a free TradingView account (no webhook support), alternatives include:

- Email-to-webhook bridges (Zapier, Make.com, n8n) — configure TradingView to send email alerts, then parse and forward to your webhook.
- Self-hosted email-parsers (a small Python service that reads a mailbox and posts to your webhook).

Example Zapier flow: Gmail trigger → parse subject/body → Webhook POST to your bot endpoint.

---

## Troubleshooting

Checklist when alerts don't arrive:

- TradingView account: Paid plan and 2FA enabled?
- Webhook URL: HTTPS, correct host, no explicit port, and endpoint `/webhook`?
- Alert condition: set to `Strategy Buy Signal (JSON)` or `Strategy Sell Signal (JSON)` and the indicator name matches exactly.
- Trigger: `Once per bar close` to match closed-candle logic.
- Server: check Railway/host logs for incoming requests and errors.

Common errors and fixes:

- No webhook option visible: ensure paid subscription or use email bridge.
- Connection timeout: optimize handler to return quickly; check provider logs.
- Invalid signal format: confirm Pine Script version and that TradingView sends JSON strategy output.

---

## Examples — cURL Tests

Test a BUY signal:

```bash
curl -X POST https://web-production-93165.up.railway.app/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","time":1234567890,"signal":"BUY","price":{"close":50000}}'
```

Test a SELL signal:

```bash
curl -X POST https://web-production-93165.up.railway.app/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","time":1234567890,"signal":"SELL","price":{"close":51000}}'
```

Expected response from the project webhook is a short acknowledgement JSON like `{"status":"received",...}`.

---

## Security & Production Notes

- The webhook endpoint in this project is public by default. Consider adding one or more protections:
  - IP allowlisting (TradingView IPs)
  - A shared secret / HMAC header in TradingView message (if supported) or in an intermediary
  - Short-lived API keys
- Monitor logs for unexpected traffic and rate-limit or block abusive sources.

---

## Quick Checklist

- [ ] Indicator loaded: `WT + Ideal BB + RSI`
- [ ] Alerts created: Buy + Sell using `Strategy ... (JSON)` conditions
- [ ] Trigger: `Once per bar close`
- [ ] Webhook URL: HTTPS and correct endpoint `/webhook`
- [ ] Test with `curl` successful

---

## Where to Edit

Edit this consolidated guide: [docs/TRADINGVIEW.md](TRADINGVIEW.md)

---

If you'd like, I can:

- split this into a short quickstart plus a long reference section, or
- create a PR branch and update any README links in this repo.
