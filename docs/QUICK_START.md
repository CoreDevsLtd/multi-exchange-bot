# Quick Start Guide

Get the trading bot running in 5 minutes!

## 1. Install Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 2. Run the Bot

```bash
python3 main_with_dashboard.py
```

## 3. Access Dashboard

Open browser: `http://localhost:8080`

## 4. Configure Exchange

1. Click gear icon next to an exchange (MEXC, Alpaca, Bybit, or IBKR)
2. Enter API Key and Secret
3. Click "Test Connection"
4. Enable exchange toggle
5. Click "Save"

## 5. Set Trading Settings

1. Set position size (20-100%)
2. Configure stop-loss percentage
3. Click "Save"

## 6. Test Webhook

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "signal": "BUY", "price": {"close": 50000}, "indicators": {}, "strategy": {"all_conditions_met": true}}'
```

## That's It! 🎉

Your bot is now running and ready to receive TradingView signals.

**Webhook URL**: `http://your-server-ip:5000/webhook`

For detailed setup instructions, see [SETUP_GUIDE.md](SETUP_GUIDE.md)
