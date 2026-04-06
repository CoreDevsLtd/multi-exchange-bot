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

## Quick Reference

**Webhook URL**: `https://web-production-93165.up.railway.app/webhook`

**Dashboard URL**: `https://web-production-93165.up.railway.app/`

**Health Check**: `https://web-production-93165.up.railway.app/health`

---

## Need Help?

1. Check Railway logs for detailed error messages
2. Verify TradingView alert is enabled and configured correctly
3. Test webhook endpoint with cURL
4. Check dashboard for signal status and recent signals


