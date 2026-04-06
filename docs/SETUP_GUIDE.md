# Multi-Exchange Trading Bot - Setup Guide

Complete guide for setting up and running the Multi-Exchange Trading Bot.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the Project](#running-the-project)
5. [Accessing the Dashboard](#accessing-the-dashboard)
6. [Setting Up Exchanges](#setting-up-exchanges)
7. [Testing Webhooks](#testing-webhooks)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Python 3.8+** (Python 3.9 or higher recommended)
- **pip** (Python package manager)
- **Git** (for cloning the repository)

### Python Version Check

```bash
python3 --version
# Should show Python 3.8 or higher
```

### Required Accounts (Optional - depends on which exchanges you want to use)

- **MEXC Account** - For MEXC exchange trading
- **Alpaca Account** - For Alpaca (stocks/crypto) trading
- **Bybit Account** - For Bybit exchange trading
- **IBKR Account** - For Interactive Brokers trading

---

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd MultiExchangeTradingBot
```

### 2. Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Verify Installation

```bash
python3 -c "import flask, requests; print('✅ Dependencies installed successfully')"
```

---

## Configuration

### 1. Environment Variables (Optional)

Create a `.env` file in the project root (optional):

```bash
# .env file (optional)
LOG_LEVEL=INFO
LOG_FILE=trading_bot.log
DEMO_MODE=false
PORT=8080
DASHBOARD_HOST=0.0.0.0
```

### 2. Dashboard Configuration

The dashboard configuration is stored in `dashboard_config.json`. This file is created automatically when you first run the dashboard.

**Important**: This file contains sensitive API keys and is automatically excluded from git (`.gitignore`).

---

## Running the Project

### Quick Start

```bash
python3 main_with_dashboard.py
```

This will start:
- **Dashboard** on `http://localhost:8080` (default)
- **Webhook Server** on `http://localhost:5000` (default)

### Custom Port Configuration

Set environment variables or modify the code:

```bash
# Set port via environment variable
export PORT=8080
python3 main_with_dashboard.py
```

### Running in Background

```bash
# Using nohup (Linux/macOS)
nohup python3 main_with_dashboard.py > bot.log 2>&1 &

# Using screen (Linux/macOS)
screen -S trading_bot
python3 main_with_dashboard.py
# Press Ctrl+A then D to detach

# Using tmux (Linux/macOS)
tmux new -s trading_bot
python3 main_with_dashboard.py
# Press Ctrl+B then D to detach
```

### Running on Production (Using Gunicorn)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 main_with_dashboard:app
```

---

## Accessing the Dashboard

### 1. Open Browser

Navigate to:
```
http://localhost:8080
```

### 2. Dashboard Features

- **Exchange Management**: Configure and enable exchanges
- **Trading Settings**: Set position sizes and trading pairs
- **Risk Management**: Configure stop-loss and take-profit levels
- **Signal Monitor**: View recent trading signals
- **Connection Testing**: Test API connections

---

## Setting Up Exchanges

### MEXC Exchange

1. **Get API Credentials**
   - Log in to MEXC: https://www.mexc.com
   - Go to API Management
   - Create API Key and Secret
   - **Important**: Add your IP to whitelist

2. **Configure in Dashboard**
   - Click gear icon next to MEXC
   - Enter API Key and Secret
   - Base URL: `https://api.mexc.com` (default)
   - Click "Test Connection"
   - Enable exchange toggle
   - Click "Save"

3. **Sub-Account (Optional)**
   - Check "Use Sub-Account" if using sub-account
   - Enter Sub-Account ID

### Alpaca Exchange

1. **Get API Credentials**
   - Sign up at: https://alpaca.markets
   - Go to Paper Trading or Live Trading
   - Navigate to API Keys section
   - Copy API Key ID and Secret Key

2. **Configure in Dashboard**
   - Click gear icon next to Alpaca
   - Enter API Key ID and Secret Key
   - Base URL: 
     - Paper: `https://paper-api.alpaca.markets`
     - Live: `https://api.alpaca.markets`
   - Check "Paper Trading" if using paper account
   - Click "Test Connection"
   - Enable exchange toggle
   - Click "Save"

**Note**: Alpaca stocks only trade during market hours (9:30 AM - 4:00 PM ET). Use crypto symbols (BTC/USD) for 24/7 trading.

### Bybit Exchange

1. **Get API Credentials**
   - Log in to Bybit: https://www.bybit.com
   - Go to API Management
   - Create API Key and Secret
   - Set appropriate permissions (Spot Trading)

2. **Configure in Dashboard**
   - Click gear icon next to Bybit
   - Enter API Key and Secret
   - Base URL: `https://api.bybit.com` (mainnet) or `https://api-testnet.bybit.com` (testnet)
   - Check "Testnet" if using testnet
   - Click "Test Connection"
   - Enable exchange toggle
   - Click "Save"

### IBKR (Interactive Brokers)

1. **Prerequisites**
   - Install **IB Gateway** or **Trader Workstation (TWS)** on the **same machine** where the trading bot runs (or use a VPS with Gateway running there).
   - Enable **API access** in Gateway/TWS and note the port (default **5000** for Client Portal Web API).

2. **No exchange-style API keys**
   - This integration uses the **Client Portal Web API** on `https://localhost:<port>`.
   - You **log in through the Gateway** in a browser; the bot then calls the API on that host after the session is active.

3. **Configure in Dashboard**
   - Click gear icon next to IBKR
   - Set **Base URL** to `https://localhost:5000` (or your Gateway URL/port)
   - Click **Open Gateway login (new tab)**, sign in to IBKR, then return and click **Test Connection**
   - API Key / Secret fields are **not used** for IBKR (hidden in the UI)
   - Set Leverage (1–100x) as needed; Account ID is optional (auto-detected when connected)
   - Enable exchange toggle and **Save**

**Important**: Gateway/TWS must be running and you must complete browser login **on the same host** the bot uses. A remote dashboard cannot log in to Gateway on your home PC unless you use networking/tunneling yourself.

---

## Testing Webhooks

### 1. Get Webhook URL

Your webhook endpoint is:
```
http://your-server-ip:5000/webhook
```

For local testing:
```
http://localhost:5000/webhook
```

### 2. Test Webhook Manually

```bash
# Test BUY signal
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "signal": "BUY",
    "price": {"close": 50000},
    "indicators": {},
    "strategy": {"all_conditions_met": true}
  }'

# Test SELL signal
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "signal": "SELL",
    "price": {"close": 51000},
    "indicators": {},
    "strategy": {"all_conditions_met": true}
  }'
```

### 3. Set Up TradingView Alert

1. Open TradingView chart
2. Add indicator script (`FILTERED_INDICATOR.pine`)
3. Create alert:
   - Condition: "Strategy Buy Signal" or "Strategy Sell Signal"
   - Webhook URL: `http://your-server-ip:5000/webhook`
   - Message: Use JSON format from indicator

### 4. Monitor Signals

- Check dashboard "Recent Signals" section
- View logs: `tail -f trading_bot.log`
- Check webhook status: `http://localhost:5000/health`

---

## Troubleshooting

### Common Issues

#### 1. Port Already in Use

```bash
# Find process using port
lsof -i :8080  # macOS/Linux
netstat -ano | findstr :8080  # Windows

# Kill process or change port
export PORT=8081
python3 main_with_dashboard.py
```

#### 2. Module Not Found

```bash
# Reinstall dependencies
pip install -r requirements.txt

# Check Python version
python3 --version
```

#### 3. API Connection Failed

- **Check API Keys**: Verify keys are correct and not expired
- **Check IP Whitelist**: Ensure your IP is whitelisted (MEXC)
- **Check Base URL**: Verify correct URL for paper/live trading
- **Check Market Hours**: Alpaca stocks only trade during market hours
- **Check Logs**: `tail -f trading_bot.log` for detailed errors

#### 4. Dashboard Not Loading

- Check if Flask is installed: `pip install flask`
- Check port availability
- Check browser console for errors
- Verify `templates/` and `static/` directories exist

#### 5. Webhook Not Receiving Signals

- Verify webhook URL is accessible
- Check firewall settings
- Test webhook manually with curl
- Check TradingView alert configuration
- View webhook logs: `tail -f trading_bot.log | grep webhook`

#### 6. Balance Errors

- Check exchange API connection
- Verify account has balances
- Check API permissions (trading permissions required)
- Review error logs for specific exchange errors

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python3 main_with_dashboard.py
```

### View Logs

```bash
# View all logs
tail -f trading_bot.log

# View only errors
tail -f trading_bot.log | grep ERROR

# View webhook activity
tail -f trading_bot.log | grep webhook

# View exchange activity
tail -f trading_bot.log | grep -E "MEXC|Alpaca|Bybit|IBKR"
```

---

## Project Structure

```
MultiExchangeTradingBot/
├── main_with_dashboard.py      # Main entry point (dashboard + webhook)
├── dashboard.py                 # Dashboard backend
├── webhook_handler.py           # Webhook request handler
├── trading_executor.py          # Trade execution logic
├── position_manager.py          # Position tracking
├── tp_sl_manager.py            # Take-profit/Stop-loss management
├── stop_loss_monitor.py        # Stop-loss monitoring
├── signal_monitor.py           # Signal tracking
│
├── Exchange Clients/
│   ├── mexc_client.py          # MEXC API client
│   ├── alpaca_client.py        # Alpaca API client
│   ├── bybit_client.py         # Bybit API client
│   └── ibkr_client.py          # IBKR API client
│
├── templates/
│   └── dashboard.html          # Dashboard UI
│
├── static/
│   ├── css/
│   │   └── dashboard.css       # Dashboard styles
│   └── js/
│       └── dashboard.js        # Dashboard JavaScript
│
├── requirements.txt            # Python dependencies
├── dashboard_config.json       # Configuration (auto-generated)
├── trading_bot.log             # Application logs
│
└── Documentation/
    ├── README.md               # Project overview
    ├── SETUP_GUIDE.md         # This file
    ├── README_DASHBOARD.md     # Dashboard documentation
    ├── WEBHOOK_README.md       # Webhook documentation
    └── ALPACA_TROUBLESHOOTING.md  # Alpaca-specific troubleshooting
```

---

## Next Steps

1. **Configure Exchanges**: Set up at least one exchange in the dashboard
2. **Test Connections**: Use "Test Connection" button for each exchange
3. **Set Trading Settings**: Configure position size and risk management
4. **Set Up TradingView**: Add indicator and configure alerts
5. **Monitor Signals**: Watch dashboard for incoming signals
6. **Review Logs**: Check `trading_bot.log` for detailed activity

---

## Support

For issues or questions:

1. Check logs: `trading_bot.log`
2. Review troubleshooting section above
3. Check exchange-specific documentation:
   - `ALPACA_TROUBLESHOOTING.md` for Alpaca issues
   - Exchange API documentation for API-specific issues

---

## Security Notes

⚠️ **Important Security Considerations**:

1. **API Keys**: Never commit API keys to git (they're in `.gitignore`)
2. **Dashboard Access**: Add authentication if exposing dashboard publicly
3. **HTTPS**: Use HTTPS in production (consider reverse proxy like nginx)
4. **Firewall**: Restrict access to dashboard and webhook ports
5. **IP Whitelisting**: Use IP whitelisting on exchange APIs when possible
6. **Environment Variables**: Consider using environment variables for sensitive data

---

## License

See repository for license information.

---

**Last Updated**: January 2026
