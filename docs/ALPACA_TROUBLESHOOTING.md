# Alpaca Trading Troubleshooting Guide

## Common Issues and Solutions

### 1. **Market Hours Restriction (Stocks Only)**
**Problem**: Alpaca stocks only trade during market hours (9:30 AM - 4:00 PM ET, Monday-Friday)

**Symptoms**:
- Orders fail with "market closed" or "trading blocked" errors
- Price fetch fails outside market hours

**Solution**:
- Use crypto symbols (BTC/USD, ETH/USD) which trade 24/7
- Or only trade stocks during market hours
- Check current market status before placing orders

### 2. **Symbol Format Issues**
**Problem**: TradingView sends symbols like "BTCUSDT" but Alpaca needs "BTC/USD"

**Symptoms**:
- "Symbol not found" errors
- Price fetch fails

**Solution**:
- The webhook handler automatically converts crypto symbols
- Ensure symbols are properly formatted:
  - Crypto: `BTC/USD`, `ETH/USD` (with `/`)
  - Stocks: `AAPL`, `TSLA` (no suffix)

### 3. **Minimum Order Size**
**Problem**: Alpaca requires minimum order sizes:
- Stocks: $1.00 minimum
- Crypto: Varies by symbol

**Symptoms**:
- Orders rejected with "insufficient buying power" or "order too small"

**Solution**:
- Increase position size percentage in dashboard
- Ensure account has sufficient cash balance
- Check minimum order size for specific symbols

### 4. **Insufficient Buying Power**
**Problem**: Not enough cash in account

**Symptoms**:
- Orders fail with "insufficient buying power" error

**Solution**:
- Check account balance in dashboard
- Reduce position size percentage
- Ensure paper trading account has funds (paper accounts start with $100,000)

### 5. **Price Fetch Failures**
**Problem**: Cannot get current price for symbol

**Symptoms**:
- Trade fails before order placement
- Error: "Could not get price for symbol"

**Common Causes**:
- Market closed (for stocks)
- Symbol not found
- Invalid symbol format
- Market data subscription required (for some symbols)

**Solution**:
- Use crypto symbols for 24/7 trading
- Verify symbol format
- Check if market is open (for stocks)
- Ensure symbol exists on Alpaca

### 6. **Paper Trading Account Issues**
**Problem**: Paper trading account restrictions

**Symptoms**:
- Orders fail unexpectedly
- Different behavior than live account

**Solution**:
- Paper accounts have $100,000 starting balance
- Some features may differ from live accounts
- Verify you're using paper API endpoint: `https://paper-api.alpaca.markets`

## Debugging Steps

1. **Check Logs**: Look for detailed error messages in `trading_bot.log`
   ```bash
   tail -f trading_bot.log | grep -i alpaca
   ```

2. **Test Connection**: Use dashboard "Test Connection" button for Alpaca

3. **Verify Symbol Format**: Check what symbol TradingView is sending
   - Look in webhook logs
   - Check signal monitor in dashboard

4. **Check Account Balance**: Verify sufficient funds
   - Dashboard shows balances
   - Paper account should have $100,000

5. **Test Price Fetch**: Try fetching price manually
   ```python
   from alpaca_client import AlpacaClient
   client = AlpacaClient(api_key, api_secret)
   price = client.get_ticker_price("BTC/USD")  # or "AAPL"
   ```

6. **Check Market Hours**: For stocks, verify market is open
   - Market hours: 9:30 AM - 4:00 PM ET
   - Use crypto for 24/7 trading

## Error Messages Reference

- **"market closed"**: Trading outside market hours (stocks only)
- **"symbol not found"**: Invalid symbol format or symbol doesn't exist
- **"insufficient buying power"**: Not enough cash in account
- **"order too small"**: Order below minimum size ($1 for stocks)
- **"trading blocked"**: Account restrictions or market closed

## Best Practices

1. **Use Crypto Symbols**: BTC/USD, ETH/USD trade 24/7
2. **Check Balances**: Ensure sufficient funds before trading
3. **Monitor Logs**: Watch for detailed error messages
4. **Test First**: Use paper trading to test strategies
5. **Verify Symbols**: Ensure TradingView sends correct symbol format
