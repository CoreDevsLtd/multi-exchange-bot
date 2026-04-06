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

## 🎯 Quick Reference

**Webhook URL:**
```
https://web-production-93165.up.railway.app/webhook
```

**Dashboard URL:**
```
https://web-production-93165.up.railway.app/
```

**Health Check:**
```
https://web-production-93165.up.railway.app/health
```

**TradingView IPs (for allowlisting):**
- `52.89.214.238`
- `34.212.75.30`
- `54.218.53.128`
- `52.32.178.7`

---

## ⚡ Common Mistakes

1. ❌ **Using HTTP instead of HTTPS**
   - ✅ Use: `https://web-production-93165.up.railway.app/webhook`
   - ❌ Not: `http://web-production-93165.up.railway.app/webhook`

2. ❌ **Adding port number**
   - ✅ Use: `https://web-production-93165.up.railway.app/webhook`
   - ❌ Not: `https://web-production-93165.up.railway.app:8080/webhook`

3. ❌ **Wrong endpoint path**
   - ✅ Use: `/webhook`
   - ❌ Not: `/api/webhook` or `/webhooks`

4. ❌ **Free TradingView account**
   - ✅ Need: Pro, Pro+, or Premium subscription
   - ❌ Free accounts cannot use webhooks

5. ❌ **2FA not enabled**
   - ✅ Must enable 2FA for webhooks to work

---

## 📞 Still Not Working?

1. **Check Railway logs** for incoming requests
2. **Test webhook manually** with curl (see above)
3. **Verify TradingView subscription** and 2FA status
4. **Check alert configuration** matches this guide exactly
5. **Verify webhook URL** is correct (HTTPS, no port, `/webhook` endpoint)

---

## ✅ Success Indicators

When everything is working, you should see:

1. **Dashboard shows signals**: Recent Signals table updates
2. **Railway logs show**: `Received webhook: {...}`
3. **Trades execute**: If executor is configured, trades will execute
4. **No errors**: Dashboard shows "Connected" status

---

**Last Updated**: Based on TradingView webhook documentation and current bot configuration.

