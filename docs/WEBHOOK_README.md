# TradingView Webhook Alert Payload Documentation

## Overview

This document describes the structured JSON payload format for webhook alerts sent from TradingView to external trading bots. The payload includes all necessary trading signal information: symbol, time, signal direction, and indicator values (WT, BB, RSI).

## Payload Structure

### JSON Schema

The webhook payload follows this structure:

```json
{
  "symbol": "BTCUSDT",
  "time": "2024-01-15T10:30:00Z",
  "timestamp": 1705315800000,
  "signal": "BUY",
  "indicators": {
    "wt": {
      "flag": true,
      "wt1": 45.23,
      "wt2": 42.15,
      "cross_type": "BULLISH",
      "window_active": true
    },
    "bb": {
      "flag": true,
      "upper": 45230.50,
      "lower": 44800.25,
      "basis": 45015.38,
      "ma_value": 45020.00,
      "percent_b": 0.65
    },
    "rsi": {
      "value": 58.5,
      "buy_threshold": 54.0,
      "sell_threshold": 43.0,
      "condition_met": true
    }
  },
  "price": {
    "close": 45025.75,
    "open": 44980.50,
    "high": 45100.00,
    "low": 44950.25
  },
  "strategy": {
    "entry_type": "NEXT_CANDLE_OPEN",
    "all_conditions_met": true
  }
}
```

## Field Descriptions

### Top-Level Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `symbol` | string | Trading pair symbol | "BTCUSDT" |
| `time` | string | Human-readable timestamp (ISO 8601) | "2024-01-15T10:30:00Z" |
| `timestamp` | number | Unix timestamp in milliseconds | 1705315800000 |
| `signal` | string | Trading signal direction ("BUY" or "SELL") | "BUY" |

### Indicators Object

#### WT (WaveTrend) Fields

| Field | Type | Description |
|-------|------|-------------|
| `flag` | boolean | WT buy window active (true) or sell window active (false) |
| `wt1` | number | Current WT1 value |
| `wt2` | number | Current WT2 value |
| `cross_type` | string | Type of WT cross: "BULLISH", "BEARISH", or "NONE" |
| `window_active` | boolean | Whether WT validation window is currently active |

#### BB (Bollinger Bands) Fields

| Field | Type | Description |
|-------|------|-------------|
| `flag` | boolean | BB buy condition (price > MA) = true, sell condition (price < MA) = false |
| `upper` | number | Upper Bollinger Band value |
| `lower` | number | Lower Bollinger Band value |
| `basis` | number | BB basis (middle band) |
| `ma_value` | number | Moving Average value |
| `percent_b` | number | BB Percent B (%B) - position within bands (0-1) |

#### RSI Fields

| Field | Type | Description |
|-------|------|-------------|
| `value` | number | Current RSI value (0-100) |
| `buy_threshold` | number | RSI buy threshold (default: 54.0) |
| `sell_threshold` | number | RSI sell threshold (default: 43.0) |
| `condition_met` | boolean | Whether RSI condition is met (buy: >= threshold, sell: <= threshold) |

### Price Object

| Field | Type | Description |
|-------|------|-------------|
| `close` | number | Close price of the candle |
| `open` | number | Open price of the candle |
| `high` | number | High price of the candle |
| `low` | number | Low price of the candle |

### Strategy Object

| Field | Type | Description |
|-------|------|-------------|
| `entry_type` | string | Type of entry execution (always "NEXT_CANDLE_OPEN") |
| `all_conditions_met` | boolean | Whether all three indicator conditions are met |

## TradingView Alert Message Format

Due to Pine Script limitations, the alert message uses a pipe-delimited format that can be easily parsed into JSON:

```
SYMBOL=BTCUSDT|TIME=1705315800000|SIGNAL=BUY|WT_FLAG=true|WT1=45.23|WT2=42.15|WT_CROSS=BULLISH|WT_WINDOW=BUY|BB_FLAG=true|BB_UPPER=45230.50|BB_LOWER=44800.25|BB_BASIS=45015.38|MA_VALUE=45020.00|BB_PERCENT=0.65|RSI_VALUE=58.5|RSI_BUY_THRESHOLD=54.0|RSI_SELL_THRESHOLD=43.0|RSI_CONDITION=true|PRICE_CLOSE=45025.75|PRICE_OPEN=44980.50|PRICE_HIGH=45100.00|PRICE_LOW=44950.25|ENTRY_TYPE=NEXT_CANDLE_OPEN
```

## Webhook Integration

### TradingView Webhook Setup

1. In TradingView, create an alert for "Strategy Buy Signal (Webhook)" or "Strategy Sell Signal (Webhook)"
2. Configure webhook URL in alert settings
3. TradingView will send POST request with:
   - `{{ticker}}` - Symbol name
   - `{{time}}` - Timestamp
   - `{{message}}` - Alert message with all indicator data

### Example Webhook Handler (Python)

```python
import json
from flask import Flask, request

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    # Parse TradingView alert
    ticker = data.get('ticker', '')
    time = data.get('time', '')
    message = data.get('message', '')
    
    # Parse pipe-delimited message
    fields = {}
    for item in message.split('|'):
        if '=' in item:
            key, value = item.split('=', 1)
            fields[key] = value
    
    # Build JSON payload
    payload = {
        "symbol": ticker,
        "time": time,
        "timestamp": int(fields.get('TIME', 0)),
        "signal": fields.get('SIGNAL', ''),
        "indicators": {
            "wt": {
                "flag": fields.get('WT_FLAG', 'false').lower() == 'true',
                "wt1": float(fields.get('WT1', 0)),
                "wt2": float(fields.get('WT2', 0)),
                "cross_type": fields.get('WT_CROSS', 'NONE'),
                "window_active": fields.get('WT_WINDOW', 'NONE') != 'NONE'
            },
            "bb": {
                "flag": fields.get('BB_FLAG', 'false').lower() == 'true',
                "upper": float(fields.get('BB_UPPER', 0)),
                "lower": float(fields.get('BB_LOWER', 0)),
                "basis": float(fields.get('BB_BASIS', 0)),
                "ma_value": float(fields.get('MA_VALUE', 0)),
                "percent_b": float(fields.get('BB_PERCENT', 0))
            },
            "rsi": {
                "value": float(fields.get('RSI_VALUE', 0)),
                "buy_threshold": float(fields.get('RSI_BUY_THRESHOLD', 54.0)),
                "sell_threshold": float(fields.get('RSI_SELL_THRESHOLD', 43.0)),
                "condition_met": fields.get('RSI_CONDITION', 'false').lower() == 'true'
            }
        },
        "price": {
            "close": float(fields.get('PRICE_CLOSE', 0)),
            "open": float(fields.get('PRICE_OPEN', 0)),
            "high": float(fields.get('PRICE_HIGH', 0)),
            "low": float(fields.get('PRICE_LOW', 0))
        },
        "strategy": {
            "entry_type": fields.get('ENTRY_TYPE', 'NEXT_CANDLE_OPEN'),
            "all_conditions_met": True
        }
    }
    
    # Process trading signal
    if payload['signal'] == 'BUY':
        # Execute buy order logic
        pass
    elif payload['signal'] == 'SELL':
        # Execute sell order logic
        pass
    
    return json.dumps({"status": "success"}), 200

if __name__ == '__main__':
    app.run(port=5000)
```

## Signal Logic

### BUY Signal Conditions

A BUY signal is generated when ALL of the following conditions are met:

1. **WT Flag**: WT buy window is active (within 1 candle of WT bullish cross)
2. **BB Flag**: Price is above Moving Average (`close > ma_value`)
3. **RSI Condition**: RSI value >= buy threshold (default: 54.0)

### SELL Signal Conditions

A SELL signal is generated when ALL of the following conditions are met:

1. **WT Flag**: WT sell window is active (within 1 candle of WT bearish cross)
2. **BB Flag**: Price is below Moving Average (`close < ma_value`)
3. **RSI Condition**: RSI value <= sell threshold (default: 43.0)

## Entry Execution

- **Entry Type**: `NEXT_CANDLE_OPEN`
- Signals are detected on closed candles
- Entry should be executed at the next candle open
- This ensures no intrabar execution and accurate backtesting

## Files

- `webhook_payload_schema.json` - JSON Schema definition
- `webhook_payload_examples.json` - Example payloads for BUY and SELL signals
- `tradingview_indicators.pine` - Pine Script with webhook alert integration










