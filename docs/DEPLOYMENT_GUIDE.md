# Deployment Guide

## ⚠️ Important: Vercel Limitations

**Vercel is NOT suitable for this trading bot** because:

1. **Serverless Functions Only** - Vercel runs serverless functions with execution time limits (10 seconds on free tier, 60 seconds on pro)
2. **No Long-Running Processes** - This bot needs continuous monitoring threads that run 24/7
3. **No Background Jobs** - TP/SL monitoring, price checking, and webhook listening require persistent processes
4. **State Management** - The bot maintains position state that needs to persist

## ✅ Recommended Deployment Platforms

### 1. **Railway** (Recommended - Easiest)
- ✅ Free tier available
- ✅ Supports long-running processes
- ✅ Easy GitHub integration
- ✅ Automatic deployments
- ✅ Environment variables management

### 2. **Render**
- ✅ Free tier available
- ✅ Supports background workers
- ✅ Easy setup
- ✅ Auto-deploy from GitHub

### 3. **DigitalOcean App Platform**
- ✅ Good performance
- ✅ Auto-scaling
- ✅ Easy deployment

### 4. **AWS EC2 / Lightsail**
- ✅ Full control
- ✅ Persistent storage
- ✅ More setup required

### 5. **Heroku**
- ✅ Easy deployment
- ✅ Free tier discontinued, but affordable paid plans

---

## 🚀 Deployment on Railway (Recommended)

### Step 1: Prepare for Deployment

1. **Create `Procfile`** (for Railway/Render):
```bash
web: python main_with_dashboard.py
```

2. **Create `runtime.txt`** (specify Python version):
```
python-3.11.0
```

3. **Update `requirements.txt`** (ensure all dependencies are listed):
```
Flask==3.0.0
requests==2.31.0
python-dotenv==1.0.0
colorlog==6.8.0
jsonschema==4.20.0
```

### Step 2: Railway Deployment

1. **Sign up at [railway.app](https://railway.app)**

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect your GitHub account
   - Select your repository

3. **Configure Environment Variables**
   In Railway dashboard, go to Variables tab and add:
   ```
   MEXC_API_KEY=your_key_here
   MEXC_API_SECRET=your_secret_here
   MEXC_BASE_URL=https://api.mexc.com
   WEBHOOK_PORT=5000
   WEBHOOK_HOST=0.0.0.0
   POSITION_SIZE_PERCENT=20.0
   STOP_LOSS_PERCENT=5.0
   LOG_LEVEL=INFO
   ```

4. **Configure Port**
   - Railway provides `PORT` environment variable
   - Update `main_with_dashboard.py` to use `PORT` if available:
   ```python
   webhook_port = int(os.getenv('PORT', os.getenv('WEBHOOK_PORT', 5000)))
   ```

5. **Deploy**
   - Railway will automatically detect Python and deploy
   - Check logs for any errors

### Step 3: Get Your Webhook URL

After deployment, Railway provides a URL like:
```
https://your-app-name.up.railway.app
```

Your webhook endpoint will be:
```
https://your-app-name.up.railway.app/webhook
```

---

## 🚀 Deployment on Render

### Step 1: Prepare Files

Same as Railway - ensure `Procfile` and `requirements.txt` exist.

### Step 2: Render Deployment

1. **Sign up at [render.com](https://render.com)**

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect GitHub repository
   - Select your repo

3. **Configure Service**
   - **Name**: `trading-bot` (or your choice)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main_with_dashboard.py`

4. **Add Environment Variables**
   Same as Railway - add all your API keys and config

5. **Deploy**
   - Click "Create Web Service"
   - Render will build and deploy automatically

### Step 3: Get Webhook URL

Render provides:
```
https://your-app-name.onrender.com
```

Webhook endpoint:
```
https://your-app-name.onrender.com/webhook
```

---

## 🔧 Required Code Changes for Deployment

### Update `main_with_dashboard.py`

```python
import os

def main():
    # ... existing code ...
    
    # Use PORT from environment (for Railway/Render) or default
    webhook_port = int(os.getenv('PORT', os.getenv('WEBHOOK_PORT', 5000)))
    webhook_host = os.getenv('WEBHOOK_HOST', '0.0.0.0')
    
    # Dashboard port (if separate, or use same port)
    dashboard_port = int(os.getenv('DASHBOARD_PORT', os.getenv('PORT', 8080)))
    
    # ... rest of code ...
```

### Update Webhook Handler

Ensure it binds to `0.0.0.0` (already done):
```python
app.run(host='0.0.0.0', port=webhook_port)
```

---

## 📋 Pre-Deployment Checklist

- [ ] All API keys are in environment variables (NOT in code)
- [ ] `.env` file is in `.gitignore`
- [ ] `dashboard_config.json` is in `.gitignore` (contains API keys)
- [ ] `requirements.txt` is up to date
- [ ] `Procfile` exists (for Railway/Render)
- [ ] Port configuration uses environment variables
- [ ] Logging is configured properly
- [ ] Test locally before deploying

---

## 🔒 Security Best Practices

1. **Never commit API keys** - Use environment variables only
2. **Use secrets management** - Platform-provided secrets managers
3. **Enable HTTPS** - All platforms provide this automatically
4. **Restrict API permissions** - Only enable trading permissions needed
5. **Use IP whitelisting** - If exchange supports it
6. **Rotate keys regularly** - Change API keys periodically

---

## 🧪 Testing After Deployment

1. **Check Logs**
   - View deployment logs in platform dashboard
   - Look for connection validation messages
   - Verify exchanges connect successfully

2. **Test Webhook**
   ```bash
   curl -X POST https://your-app.onrender.com/webhook \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}'
   ```

3. **Test Dashboard**
   - Visit: `https://your-app.onrender.com`
   - Verify dashboard loads
   - Check exchange connection status

4. **Test TradingView Integration**
   - Configure TradingView alert to point to your webhook URL
   - Send a test alert
   - Check logs for received signal

---

## 🐛 Troubleshooting

### Issue: App crashes on startup
- **Check logs** for error messages
- **Verify environment variables** are set correctly
- **Check Python version** matches `runtime.txt`

### Issue: Webhook not receiving signals
- **Verify URL** is correct in TradingView
- **Check HTTPS** - TradingView requires HTTPS
- **Check firewall** - Platform should allow inbound connections
- **View logs** for incoming requests

### Issue: Exchange connection fails
- **Verify API keys** are correct
- **Check API permissions** (must have trading enabled)
- **Verify network** - Platform can reach exchange API
- **Check sub-account** configuration if using

### Issue: Port binding errors
- **Use PORT environment variable** from platform
- **Bind to 0.0.0.0** not localhost
- **Check platform documentation** for port requirements

---

## 📊 Monitoring

### Recommended Monitoring Tools

1. **Platform Logs** - Use built-in log viewer
2. **Uptime Monitoring** - Use UptimeRobot or similar
3. **Error Tracking** - Consider Sentry for error tracking
4. **Metrics** - Monitor CPU, memory usage in platform dashboard

---

## 💰 Cost Estimates

### Railway
- **Free tier**: $5 credit/month (usually enough for small bot)
- **Hobby**: $5/month
- **Pro**: $20/month

### Render
- **Free tier**: Available (with limitations)
- **Starter**: $7/month
- **Standard**: $25/month

### DigitalOcean
- **Basic**: $5/month (512MB RAM)
- **Professional**: $12/month (1GB RAM)

---

## 🎯 Quick Start: Railway (5 minutes)

1. Push code to GitHub
2. Sign up at railway.app
3. New Project → Deploy from GitHub
4. Add environment variables
5. Deploy → Get URL
6. Configure TradingView webhook
7. Done!

---

## ⚠️ Important Notes

- **Keep bot running 24/7** - Required for TP/SL monitoring
- **Monitor costs** - Check platform usage regularly
- **Backup config** - Export `dashboard_config.json` regularly
- **Test thoroughly** - Use paper trading first
- **Start small** - Test with small position sizes initially

---

## 📞 Support

If you encounter issues:
1. Check platform logs
2. Review this guide
3. Check platform documentation
4. Verify all environment variables are set


