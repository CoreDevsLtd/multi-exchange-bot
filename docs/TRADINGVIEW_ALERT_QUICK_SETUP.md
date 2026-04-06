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

## Creating Two Separate Alerts (Recommended)

For best results, create **TWO separate alerts**:

### Alert 1: BUY Signals
- **Condition**: `WT + Ideal BB + RSI` → `Strategy Buy Signal (JSON)`
- **Trigger**: `Once per bar close`
- **Webhook URL**: `https://web-production-93165.up.railway.app/webhook`
- **Message**: `BUY` (optional)

### Alert 2: SELL Signals
- **Condition**: `WT + Ideal BB + RSI` → `Strategy Sell Signal (JSON)`
- **Trigger**: `Once per bar close`
- **Webhook URL**: `https://web-production-93165.up.railway.app/webhook`
- **Message**: `SELL` (optional)

---

## Visual Guide

### Settings Tab:
```
Symbols: Markets
Condition: [WT + Ideal BB + RSI] → [Strategy Buy Signal (JSON)]
Interval: Same as chart
Trigger: Once per bar close ✅
Expiration: No Expiration
```

### Message Tab:
```
Webhook URL: https://web-production-93165.up.railway.app/webhook
Message: BUY (or leave empty)
```

---

## Troubleshooting

### Can't find "Strategy Buy Signal (JSON)"?
1. Make sure your indicator is loaded on the chart
2. The indicator must be compiled without errors
3. Try refreshing the page and reloading the indicator
4. Check that the indicator name is exactly: "WT + Ideal BB + RSI"

### Alert not triggering?
1. ✅ Check that all 3 conditions are met (WT + BB + RSI)
2. ✅ Verify the alert is enabled (green toggle)
3. ✅ Check webhook URL is correct
4. ✅ Verify "Once per bar close" is selected
5. ✅ Check Railway logs for incoming requests

### Testing the Alert
1. Wait for a signal to occur naturally, OR
2. Test with a manual webhook:
   ```bash
   curl -X POST https://web-production-93165.up.railway.app/webhook \
     -H "Content-Type: application/json" \
     -d '{"symbol": "BTCUSDT", "signal": "BUY", "price": {"close": 50000}}'
   ```

---

## Quick Checklist

- [ ] Condition set to "Strategy Buy Signal (JSON)" or "Strategy Sell Signal (JSON)"
- [ ] Trigger set to "Once per bar close"
- [ ] Webhook URL entered: `https://web-production-93165.up.railway.app/webhook`
- [ ] Alert enabled (green toggle)
- [ ] Dashboard shows "Connected" status
- [ ] Test signal received in dashboard

---

## Need Help?

1. Check Railway logs: https://railway.app → Your Project → Logs
2. Check dashboard: https://web-production-93165.up.railway.app/
3. Verify indicator is loaded and compiled without errors
4. Test webhook endpoint with cURL


