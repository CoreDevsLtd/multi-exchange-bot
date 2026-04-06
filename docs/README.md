# Multi-Exchange Trading Bot

A comprehensive TradingView Pine Script indicator system combining WaveTrend (WT), Ideal Bollinger Bands (BB), and RSI indicators with webhook integration for automated trading.

## Features

### Core Indicators

1. **WaveTrend (WT) - LazyBear Implementation**
   - LazyBear WaveTrend Cross logic with green/red dot signals
   - WT1 and WT2 lines with crossover detection
   - Configurable channel length and average length
   - Visual dots for bullish/bearish crosses

2. **Ideal Bollinger Bands (BB)**
   - EMA-based Bollinger Bands (smoother than standard BB)
   - Moving Average crossover signals
   - Buy/Sell labels based on price vs MA
   - BB Percent B (%B) and bandwidth calculations

3. **RSI Indicator**
   - Period 12 calculation
   - Custom buy threshold: RSI >= 54
   - Custom sell threshold: RSI <= 43
   - Visual threshold lines and signal labels

### Combined Strategy

- **Three-Indicator Alignment**: Signals fire only when all three indicators align
- **WT Timing Enforcement**: Uses WT cross dots as primary timing signal
- **One Candle Window**: Validates signals within 1 candle on each side of WT dot
- **Closed Candle Logic**: All calculations use confirmed/closed candles only
- **Next Candle Entry**: Entries occur at next candle open (not intrabar)

### Webhook Integration

- **JSON Payload**: Structured JSON output with all indicator data
- **Pipe-Delimited Format**: Alternative format for compatibility
- **Complete Data**: Includes symbol, time, signal, WT flag, BB flag, RSI value, and price data
- **Alert Conditions**: Fires only when all three indicators fully align

## Files

- `tradingview_indicators.pine` - Main indicator script with all features
- `tradingview_bb_labels_overlay.pine` - Overlay script for price chart labels
- `webhook_payload_schema.json` - JSON schema definition
- `webhook_payload_examples.json` - Example payloads
- `WEBHOOK_README.md` - Webhook integration documentation

## Usage

1. Open TradingView Pine Editor
2. Copy `tradingview_indicators.pine` content
3. Add to chart
4. Configure alerts for "Strategy Buy Signal (JSON)" or "Strategy Sell Signal (JSON)"
5. Set up webhook URL in alert settings

## Signal Logic

### BUY Signal Requirements
- WT buy window active (within 1 candle of WT bullish cross)
- BB buy condition: Price > Moving Average
- RSI buy condition: RSI >= 54

### SELL Signal Requirements
- WT sell window active (within 1 candle of WT bearish cross)
- BB sell condition: Price < Moving Average
- RSI sell condition: RSI <= 43

## Alert Types

- **Strategy Buy Signal (JSON)** - JSON format webhook alert
- **Strategy Sell Signal (JSON)** - JSON format webhook alert
- **Strategy Buy Signal (Webhook)** - Pipe-delimited format alert
- **Strategy Sell Signal (Webhook)** - Pipe-delimited format alert

## Technical Details

- **Pine Script Version**: v5
- **Entry Type**: NEXT_CANDLE_OPEN
- **Candle Logic**: Closed candles only (no intrabar values)
- **Window Validation**: 3-candle window (1 before, current, 1 after WT cross)

## License

See repository for license information.
