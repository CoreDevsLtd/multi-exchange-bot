# Quick Deploy Guide: Railway

## ⚡ 5-Minute Deployment

### Step 1: Push to GitHub
```bash
git add .
git commit -m "Ready for deployment"
git push origin main
```

### Step 2: Deploy on Railway

1. **Go to [railway.app](https://railway.app)**
2. **Sign up** (free with GitHub)
3. **Click "New Project"**
4. **Select "Deploy from GitHub repo"**
5. **Select your repository**
6. **Railway auto-detects Python** ✅

### Step 3: Configure MEXC API Key

**⚠️ CRITICAL: Disable IP Whitelisting in MEXC**

Railway uses **dynamic IP addresses** that change with each deployment. You **must disable IP whitelisting** in your MEXC API key settings.

**Steps:**
1. Log into MEXC → API Management
2. Edit your API key
3. **Disable IP Whitelist** (turn it OFF)
4. Save changes

**Why?** Railway IPs change on every deploy - whitelisting is not practical.

See `MEXC_IP_WHITELIST_RAILWAY.md` for detailed instructions.

### Step 4: Add Environment Variables

In Railway dashboard → Variables tab, add:

**Required for Python Installation:**
```
RAILPACK_PYTHON_VERSION=3.11.9
```

**Trading Bot Configuration:**
```
MEXC_API_KEY=your_mexc_api_key
MEXC_API_SECRET=your_mexc_api_secret
MEXC_BASE_URL=https://api.mexc.com
WEBHOOK_PORT=5000
WEBHOOK_HOST=0.0.0.0
POSITION_SIZE_PERCENT=20.0
STOP_LOSS_PERCENT=5.0
LOG_LEVEL=INFO
PORT=8080
```

**Note:** Demo mode is **disabled by default**. The bot will use **real API connections** and execute **real trades**. 
- To enable demo mode (for testing), add: `DEMO_MODE=true`
- **Important:** Configure your exchange API keys in the dashboard after deployment.

### Step 5: Get Your URL

Railway provides a URL like:
```
https://your-app-name.up.railway.app
```

### Step 6: Configure TradingView

In TradingView alert, set webhook URL to:
```
https://your-app-name.up.railway.app/webhook
```

### Step 7: Access Dashboard

Visit:
```
https://your-app-name.up.railway.app
```

### Step 8: Configure Exchange API Keys

1. **Open the dashboard** at your Railway URL
2. **Click "Configure Exchange"** for MEXC
3. **Enter your API credentials:**
   - API Key
   - API Secret
   - Base URL: `https://api.mexc.com`
4. **Click "Test Connection"** to verify
5. **Enable the exchange** and **Save**

**⚠️ Important:** The bot uses **REAL trading** by default. Ensure your API keys have proper permissions and you're ready for live trading.

## ✅ Done!

Your bot is now live and running 24/7!

## 📊 Monitor

- **Logs**: Railway dashboard → Deployments → View Logs
- **Metrics**: Railway dashboard → Metrics tab
- **Status**: Railway dashboard → Settings → Health checks

## 🔧 Troubleshooting

**❌ Mise/Python Installation Error:**
If you see: `mise ERROR Failed to install core:python@3.11.0`
1. **Add environment variable**: `RAILPACK_PYTHON_VERSION=3.11.9` (in Railway Variables tab)
2. **Clear build cache**: Railway dashboard → Settings → Clear Build Cache → Redeploy
3. **Alternative**: If still failing, add `MISE_PYTHON_COMPILE=1` (compiles from source, slower but works)

**Bot not starting?**
- Check logs in Railway dashboard
- Verify all environment variables are set
- Check Python version matches `runtime.txt`
- Ensure `RAILPACK_PYTHON_VERSION` is set

**Webhook not receiving?**
- Verify URL is HTTPS (required by TradingView)
- Check Railway logs for incoming requests
- Test with: `curl -X POST https://your-app.up.railway.app/webhook -d '{"test": "data"}'`

**Exchange connection fails?**
- Verify API keys are correct
- Check API permissions (must have trading enabled)
- View logs for connection errors

## 💰 Cost

- **Free tier**: $5 credit/month (usually enough)
- **Hobby**: $5/month if you exceed free tier

## 🎯 Next Steps

1. Test webhook with TradingView
2. Monitor logs for first trade
3. Check dashboard for connection status
4. Verify balances are showing


