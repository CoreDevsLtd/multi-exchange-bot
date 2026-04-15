"""
Alpaca Markets API Client
Handles authentication, order placement, and account management for Alpaca
"""

import requests
import json
import re
import time
from typing import Dict, Optional, List
import logging
from datetime import datetime
from urllib.parse import quote

logger = logging.getLogger(__name__)


class AlpacaClient:
    """Alpaca Markets API Client"""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://paper-api.alpaca.markets"):
        """
        Initialize Alpaca API Client
        
        Args:
            api_key: Alpaca API Key ID
            api_secret: Alpaca API Secret Key
            base_url: Alpaca API base URL
                - Paper: https://paper-api.alpaca.markets
                - Live: https://api.alpaca.markets
        """
        # Trim whitespace to prevent errors
        self.api_key = api_key.strip() if api_key else ''
        self.api_secret = api_secret.strip() if api_secret else ''
        self.base_url = base_url.rstrip('/')
        # Market data API base URL (separate from trading API)
        self.data_base_url = "https://data.alpaca.markets"
        self.session = requests.Session()
        
        # Log credentials (masked) for debugging
        if self.api_key:
            masked_key = f"{self.api_key[:6]}...{self.api_key[-4:]}" if len(self.api_key) > 10 else "***"
            logger.info(f"🔑 Initializing Alpaca client with API Key: {masked_key} (length: {len(self.api_key)})")
        else:
            logger.warning("⚠️  Alpaca API Key is empty!")
        
        if self.api_secret:
            masked_secret = f"{self.api_secret[:6]}...{self.api_secret[-4:]}" if len(self.api_secret) > 10 else "***"
            logger.info(f"🔑 Alpaca API Secret: {masked_secret} (length: {len(self.api_secret)})")
        else:
            logger.warning("⚠️  Alpaca API Secret is empty!")
        
        logger.info(f"🌐 Alpaca Base URL: {self.base_url}")
        
        # Validate credentials are not empty
        if not self.api_key or not self.api_secret:
            logger.error("❌ Alpaca API credentials are missing or empty!")
            raise ValueError("Alpaca API Key and Secret are required")
        
        # Set default headers for all requests
        self.session.headers.update({
            'APCA-API-KEY-ID': self.api_key,
            'APCA-API-SECRET-KEY': self.api_secret,
            'Content-Type': 'application/json'
        })
    
    def _is_crypto_symbol(self, symbol: str) -> bool:
        """
        Check if symbol is a crypto symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            True if crypto, False if stock
        """
        # Crypto symbols contain "/" (e.g., BTC/USD)
        if '/' in symbol:
            return True
        
        # Common crypto tickers (without /)
        crypto_tickers = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'MATIC', 'AVAX', 'LINK', 'UNI', 'ATOM', 'BNB', 'XRP', 'DOGE', 'LTC']
        clean_symbol = symbol.replace('USDT', '').replace('USD', '').replace('USDC', '')
        return clean_symbol.upper() in crypto_tickers
    
    def _format_crypto_symbol(self, symbol: str) -> str:
        """
        Format symbol for crypto API (BTC/USD format)
        
        Args:
            symbol: Trading symbol (e.g., BTCUSD, BTC/USD, BTC)
            
        Returns:
            Formatted crypto symbol (e.g., BTC/USD)
        """
        # Alpaca crypto trading uses USD-quoted pairs. Normalize any slash form
        # (e.g. DOGE/USDT, DOGE/USDC) to DOGE/USD for consistent behavior.
        if '/' in symbol:
            base = symbol.split('/')[0].strip().upper()
            return f"{base}/USD"
        
        # Remove common suffixes
        clean = symbol.replace('USDT', '').replace('USD', '').replace('USDC', '')
        
        # Add /USD suffix for crypto
        return f"{clean.upper()}/USD"

    def _format_crypto_position_symbol(self, symbol: str) -> str:
        """
        Format crypto symbol for Alpaca positions endpoints (legacy no-slash form).

        Alpaca trading/data endpoints commonly use pair format (e.g., BTC/USD),
        while positions endpoints are most reliable with legacy symbology
        (e.g., BTCUSD).
        """
        return self._format_crypto_symbol(symbol).replace('/', '')

    @staticmethod
    def _canonical_alpaca_symbol(symbol: str) -> str:
        """Canonical symbol for Alpaca matching: uppercase, no slash, USDT/USDC mapped to USD."""
        s = str(symbol or '').strip().upper().replace(' ', '').replace('/', '')
        if s.endswith('USDT'):
            return f"{s[:-4]}USD"
        if s.endswith('USDC'):
            return f"{s[:-4]}USD"
        return s
    
    def _format_stock_symbol(self, symbol: str) -> str:
        """
        Format symbol for stock API (remove suffixes)
        
        Args:
            symbol: Trading symbol (e.g., AAPLUSD, AAPL)
            
        Returns:
            Clean stock symbol (e.g., AAPL)
        """
        # Remove common suffixes
        return symbol.replace('USDT', '').replace('USD', '').replace('USDC', '').upper()
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                     data: Optional[Dict] = None, use_data_api: bool = False) -> Dict:
        """
        Make authenticated API request
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint (e.g., '/v2/account')
            params: Query parameters
            data: Request body data
            use_data_api: If True, use data API base URL instead of trading API
            
        Returns:
            Response JSON as dictionary
        """
        # Use data API base URL for market data requests
        base_url = self.data_base_url if use_data_api else self.base_url
        url = f"{base_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, timeout=10)
            elif method.upper() == 'POST':
                response = self.session.post(url, params=params, json=data, timeout=10)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, params=params, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP {e.response.status_code}"
            error_details = {}
            try:
                error_data = e.response.json()
                error_msg = error_data.get('message', error_data.get('error', error_msg))
                error_details = error_data
                logger.error(f"Alpaca API Error Response: {json.dumps(error_data, indent=2)}")
            except:
                error_text = e.response.text if hasattr(e.response, 'text') else str(e)
                error_msg = f"{error_msg}: {error_text}"
                logger.error(f"Alpaca API Error (non-JSON): {error_text}")
            
            # Log full error details for debugging
            logger.error(f"Alpaca API Error: {error_msg}")
            logger.error(f"Request URL: {url}")
            logger.error(f"Request Method: {method}")
            
            # Log masked credentials for debugging (don't expose full keys)
            masked_key = f"{self.api_key[:6]}...{self.api_key[-4:]}" if len(self.api_key) > 10 else "***"
            logger.error(f"API Key used: {masked_key} (length: {len(self.api_key)})")
            
            # Provide helpful error message for unauthorized errors
            if 'unauthorized' in error_msg.lower() or e.response.status_code == 401:
                logger.error("=" * 60)
                logger.error("❌ ALPACA AUTHENTICATION FAILED")
                logger.error("=" * 60)
                logger.error("Possible causes:")
                logger.error("1. API Key ID is incorrect")
                logger.error("2. API Secret Key is incorrect")
                logger.error("3. API Key and Secret are swapped")
                logger.error("4. Using paper credentials on live API (or vice versa)")
                logger.error("5. API key doesn't have trading permissions")
                logger.error("")
                logger.error("How to fix:")
                logger.error("1. Go to https://app.alpaca.markets/paper/dashboard/overview")
                logger.error("2. Navigate to 'Your API Keys' section")
                logger.error("3. Copy the 'API Key ID' (not the secret)")
                logger.error("4. Copy the 'Secret Key'")
                logger.error("5. Make sure you're using PAPER keys for paper trading")
                logger.error("6. Update credentials in dashboard")
                logger.error("=" * 60)
            
            if data:
                logger.error(f"Request Data: {json.dumps(data, indent=2)}")
            if params:
                logger.error(f"Request Params: {json.dumps(params, indent=2)}")
            
            raise Exception(f"Alpaca API Error: {error_msg}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise Exception(f"Request error: {e}")
    
    def validate_connection(self) -> Dict:
        """
        Validate API connection and permissions
        
        Returns:
            Dictionary with 'connected' and 'can_trade' status
        """
        try:
            account = self._make_request('GET', '/v2/account')
            
            # Check if account is active and trading is allowed
            trading_blocked = account.get('trading_blocked', False)
            account_blocked = account.get('account_blocked', False)
            pattern_day_trader = account.get('pattern_day_trader', False)
            
            can_trade = not trading_blocked and not account_blocked
            
            return {
                'connected': True,
                'can_trade': can_trade,
                'account_status': {
                    'trading_blocked': trading_blocked,
                    'account_blocked': account_blocked,
                    'pattern_day_trader': pattern_day_trader
                }
            }
        except Exception as e:
            logger.error(f"Connection validation failed: {e}")
            return {
                'connected': False,
                'can_trade': False,
                'error': str(e)
            }
    
    def get_account_info(self) -> Dict:
        """
        Get account information
        
        Returns:
            Account information dictionary
        """
        return self._make_request('GET', '/v2/account')
    
    def get_balance(self, asset: str = 'USD') -> Dict:
        """
        Get balance for a specific asset
        
        Args:
            asset: Asset symbol (default: 'USD' for cash)
            
        Returns:
            Balance information
        """
        account = self.get_account_info()
        
        if asset.upper() == 'USD':
            return {
                'asset': 'USD',
                'free': float(account.get('cash', 0)),
                'locked': float(account.get('cash', 0)) - float(account.get('buying_power', 0)),
                'total': float(account.get('cash', 0))
            }
        else:
            # For positions, get from positions endpoint
            positions = self.get_positions()
            for pos in positions:
                if pos['symbol'] == asset:
                    return {
                        'asset': asset,
                        'free': float(pos.get('qty', 0)),
                        'locked': 0.0,
                        'total': float(pos.get('qty', 0))
                    }
            
            return {
                'asset': asset,
                'free': 0.0,
                'locked': 0.0,
                'total': 0.0
            }
    
    def get_main_balances(self) -> Dict:
        """
        Get main account balances (cash and positions)
        
        Returns:
            Dictionary of asset balances
        """
        balances = {}
        
        try:
            account = self.get_account_info()
            
            # Add cash balance
            cash = float(account.get('cash', 0))
            if cash > 0:
                balances['USD'] = {
                    'free': cash,
                    'locked': cash - float(account.get('buying_power', 0)),
                    'total': cash
                }
            
            # Add position balances
            positions = self.get_positions()
            for pos in positions:
                symbol = pos['symbol']
                qty = float(pos.get('qty', 0))
                if qty > 0:
                    balances[symbol] = {
                        'free': abs(qty),
                        'locked': 0.0,
                        'total': abs(qty)
                    }
            
        except Exception as e:
            logger.error(f"Error getting balances: {e}")
        
        return balances
    
    def get_positions(self) -> List[Dict]:
        """
        Get all open positions
        
        Returns:
            List of position dictionaries
        """
        try:
            return self._make_request('GET', '/v2/positions')
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Get position for a specific symbol (supports both stocks and crypto)
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL' for stocks, 'BTC/USD' for crypto)
            
        Returns:
            Position dictionary or None
        """
        try:
            # Positions endpoint is more reliable with legacy no-slash crypto symbol.
            is_crypto = self._is_crypto_symbol(symbol)
            if is_crypto:
                clean_symbol = self._format_crypto_position_symbol(symbol)
            else:
                clean_symbol = self._format_stock_symbol(symbol)

            encoded_symbol = quote(clean_symbol, safe='')
            return self._make_request('GET', f'/v2/positions/{encoded_symbol}')
        except Exception as e:
            # Position doesn't exist
            return None
    
    def get_ticker_price(self, symbol: str) -> float:
        """
        Get current ticker price (supports both stocks and crypto)
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL' for stocks, 'BTC/USD' or 'BTCUSD' for crypto)
            
        Returns:
            Current price
        """
        try:
            is_crypto = self._is_crypto_symbol(symbol)
            
            if is_crypto:
                # Use crypto market data API
                crypto_symbol = self._format_crypto_symbol(symbol)
                logger.info(f"Fetching crypto price for {crypto_symbol}")
                
                # Use crypto bars endpoint (works 24/7)
                try:
                    # Get latest 1-minute bar (use data API)
                    response = self._make_request(
                        'GET', 
                        '/v1beta3/crypto/us/bars',
                        params={
                            'symbols': crypto_symbol,
                            'timeframe': '1Min',
                            'limit': 1
                        },
                        use_data_api=True
                    )
                    
                    if response and 'bars' in response:
                        bars = response['bars']
                        if crypto_symbol in bars and len(bars[crypto_symbol]) > 0:
                            latest_bar = bars[crypto_symbol][0]
                            price = float(latest_bar.get('c', 0))  # Close price
                            if price > 0:
                                logger.info(f"✅ Got crypto price from bars: {price}")
                                return price
                    
                    raise ValueError(f"No price data available for {crypto_symbol}")
                    
                except Exception as e:
                    logger.error(f"Error getting crypto price: {e}")
                    # Fallback: try position
                    try:
                        position = self.get_position(symbol)
                        if position:
                            price = float(position.get('current_price', 0) or position.get('avg_entry_price', 0))
                            if price > 0:
                                return price
                    except:
                        pass
                    raise ValueError(f"Could not get price for crypto symbol '{symbol}'. Ensure symbol is in format 'BTC/USD' or use MEXC for crypto trading.")
            else:
                # Use stock market data API
                stock_symbol = self._format_stock_symbol(symbol)
                logger.info(f"Fetching stock price for {stock_symbol}")
                
                price = None
                
                # Method 1: Try latest bar (most reliable, works during market hours)
                # Note: /bars/latest endpoint doesn't accept timeframe parameter
                try:
                    latest_bar = self._make_request(
                        'GET', 
                        f'/v2/stocks/{stock_symbol}/bars/latest',
                        params={},  # No params needed for /bars/latest
                        use_data_api=True
                    )
                    if latest_bar and isinstance(latest_bar, dict):
                        if 'bar' in latest_bar:
                            price = float(latest_bar['bar'].get('c', 0))
                        elif 'c' in latest_bar:
                            price = float(latest_bar.get('c', 0))
                    if price and price > 0:
                        logger.info(f"✅ Got stock price from bars: {price}")
                        return price
                except Exception as e:
                    logger.debug(f"Bars endpoint failed: {e}")
                
                # Method 2: Try latest quote (works during market hours)
                try:
                    latest_quote = self._make_request(
                        'GET', 
                        f'/v2/stocks/{stock_symbol}/quotes/latest',
                        use_data_api=True
                    )
                    if latest_quote and isinstance(latest_quote, dict):
                        quote_data = latest_quote.get('quote', latest_quote)
                        bid = float(quote_data.get('bp', 0) or quote_data.get('bid', 0) or 0)
                        ask = float(quote_data.get('ap', 0) or quote_data.get('ask', 0) or 0)
                        if bid > 0 and ask > 0:
                            price = (bid + ask) / 2.0
                        elif bid > 0:
                            price = bid
                        elif ask > 0:
                            price = ask
                    if price and price > 0:
                        logger.info(f"✅ Got stock price from quotes: {price}")
                        return price
                except Exception as e:
                    logger.debug(f"Quotes endpoint failed: {e}")
                
                # Method 3: Try position
                try:
                    position = self.get_position(symbol)
                    if position:
                        price = float(position.get('current_price', 0) or position.get('avg_entry_price', 0))
                        if price > 0:
                            logger.info(f"✅ Got stock price from position: {price}")
                            return price
                except Exception as e:
                    logger.debug(f"Position lookup failed: {e}")
                
                # If all methods failed
                raise ValueError(f"Could not get price for stock '{symbol}' on Alpaca. Market may be closed (9:30 AM - 4:00 PM ET).")
            
        except ValueError:
            # Re-raise ValueError (our custom errors)
            raise
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error getting ticker price for {symbol}: {e}")
            if '404' in error_msg or 'Not Found' in error_msg:
                if self._is_crypto_symbol(symbol):
                    raise ValueError(f"Symbol '{symbol}' not found on Alpaca crypto API. Ensure symbol is in format 'BTC/USD'.")
                else:
                    raise ValueError(f"Symbol '{symbol}' not found on Alpaca or market is closed. Alpaca only supports US stocks during market hours (9:30 AM - 4:00 PM ET).")
            raise
    
    def get_bars(self, symbol: str, start_iso: str, end_iso: str, timeframe: str = None) -> List[Dict]:
        """
        Fetch historical OHLCV bars for a symbol between two ISO-8601 timestamps.

        Args:
            symbol:    Ticker (e.g. 'AAPL' or 'BTC/USD')
            start_iso: Start time as ISO-8601 string (e.g. '2026-04-10T14:00:00Z')
            end_iso:   End time as ISO-8601 string
            timeframe: Alpaca timeframe string ('1Min','5Min','15Min','1Hour','1Day').
                       Auto-selected from duration when omitted.

        Returns:
            List of bar dicts with keys: t, o, h, l, c, v  (oldest → newest)
        """
        try:
            from datetime import datetime as _dt
            t_start = _dt.fromisoformat(start_iso.replace('Z', '+00:00'))
            t_end   = _dt.fromisoformat(end_iso.replace('Z', '+00:00'))
            duration_s = max(0, (t_end - t_start).total_seconds())
        except Exception:
            duration_s = 3600

        if timeframe is None:
            if duration_s <= 3600:
                timeframe = '1Min'
            elif duration_s <= 86400:
                timeframe = '5Min'
            elif duration_s <= 604800:
                timeframe = '1Hour'
            else:
                timeframe = '1Day'

        is_crypto = self._is_crypto_symbol(symbol)
        params = {'timeframe': timeframe, 'start': start_iso, 'end': end_iso, 'limit': 10000}

        try:
            if is_crypto:
                crypto_sym = self._format_crypto_symbol(symbol)
                params['symbols'] = crypto_sym
                resp = self._make_request('GET', '/v1beta3/crypto/us/bars', params=params, use_data_api=True)
                raw = resp.get('bars', {}).get(crypto_sym, []) if resp else []
            else:
                stock_sym = symbol.strip().upper()
                resp = self._make_request('GET', f'/v2/stocks/{stock_sym}/bars', params=params, use_data_api=True)
                raw = resp.get('bars', []) if resp else []
            return raw
        except Exception as e:
            logger.error(f"Failed to fetch bars for {symbol}: {e}")
            return []

    def place_order(self, symbol: str, side: str, order_type: str,
                   quantity: Optional[float] = None,
                   notional: Optional[float] = None,
                   limit_price: Optional[float] = None,
                   stop_price: Optional[float] = None,
                   time_in_force: str = 'day',
                   price: Optional[float] = None,
                   reduce_only: bool = False) -> Dict:
        """
        Place an order (supports both stocks and crypto)
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL' for stocks, 'BTC/USD' for crypto)
            side: 'buy' or 'sell'
            order_type: 'market', 'limit', 'stop', 'stop_limit'
            quantity: Number of shares (for market/limit orders)
            notional: Dollar amount (alternative to quantity for market orders)
            limit_price: Limit price (for limit/stop_limit orders)
            stop_price: Stop price (for stop/stop_limit orders)
            time_in_force: 'day', 'gtc', 'opg', 'cls', 'ioc', 'fok'
            
        Returns:
            Order response
        """
        # Accept 'price' as an alias for limit_price (tp_sl_manager compatibility)
        limit_price = limit_price or price

        # Format symbol based on asset type (crypto or stock)
        is_crypto = self._is_crypto_symbol(symbol)
        if is_crypto:
            # Crypto: use BTC/USD format (keep as-is if already formatted)
            clean_symbol = self._format_crypto_symbol(symbol)
            # Crypto orders only support 'gtc' (Good Till Cancel) or 'ioc' (Immediate Or Cancel)
            # Default to 'gtc' for crypto if 'day' is specified
            if time_in_force.lower() == 'day':
                crypto_time_in_force = 'gtc'
            elif time_in_force.lower() in ['gtc', 'ioc']:
                crypto_time_in_force = time_in_force.lower()
            else:
                crypto_time_in_force = 'gtc'  # Default for crypto
        else:
            # Stock: remove suffixes
            clean_symbol = self._format_stock_symbol(symbol)
            crypto_time_in_force = None  # Not used for stocks
        
        order_data = {
            'symbol': clean_symbol,
            'side': side.lower(),
            'type': order_type.lower(),
            'time_in_force': crypto_time_in_force if is_crypto else time_in_force.lower()
        }
        
        if order_type.lower() == 'market':
            if notional:
                # Alpaca requires notional to be rounded to 2 decimal places
                order_data['notional'] = round(float(notional), 2)
            elif quantity:
                order_data['qty'] = str(quantity)
            else:
                raise ValueError("Market orders require either quantity or notional")
        elif order_type.lower() == 'limit':
            if not quantity or not limit_price:
                raise ValueError("Limit orders require quantity and limit_price")
            order_data['qty'] = str(quantity)
            order_data['limit_price'] = str(limit_price)
        elif order_type.lower() in ['stop', 'stop_limit']:
            if not quantity or not stop_price:
                raise ValueError("Stop orders require quantity and stop_price")
            order_data['qty'] = str(quantity)
            order_data['stop_price'] = str(stop_price)
            if order_type.lower() == 'stop_limit':
                if not limit_price:
                    raise ValueError("Stop-limit orders require limit_price")
                order_data['limit_price'] = str(limit_price)
        
        logger.info(f"Placing {side} order: {order_data}")
        return self._make_request('POST', '/v2/orders', data=order_data)
    
    def place_market_buy(self, symbol: str, notional: float) -> Dict:
        """
        Place a market buy order (supports both stocks and crypto)
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL' for stocks, 'BTC/USD' for crypto)
            notional: Dollar amount to spend (will be rounded to 2 decimal places for Alpaca)
            
        Returns:
            Order response
        """
        # Format symbol correctly
        is_crypto = self._is_crypto_symbol(symbol)
        formatted_symbol = self._format_crypto_symbol(symbol) if is_crypto else self._format_stock_symbol(symbol)
        
        logger.info(f"📤 Placing Alpaca market buy order:")
        logger.info(f"   Original symbol: {symbol}")
        logger.info(f"   Formatted symbol: {formatted_symbol}")
        logger.info(f"   Is crypto: {is_crypto}")
        logger.info(f"   Notional: ${notional}")
        
        # Round notional to 2 decimal places (Alpaca requirement)
        notional_rounded = round(float(notional), 2)
        if notional_rounded != notional:
            logger.info(f"   Rounded notional from ${notional} to ${notional_rounded} (Alpaca requires 2 decimal places)")
        
        # Check minimum order size (Alpaca minimum is typically $1 for stocks, varies for crypto)
        if notional_rounded < 1.0:
            error_msg = f"Order size ${notional_rounded} is below Alpaca minimum of $1.00"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        try:
            return self.place_order(
                symbol=formatted_symbol,
                side='buy',
                order_type='market',
                notional=notional_rounded
            )
        except Exception as e:
            logger.error(f"❌ Failed to place Alpaca market buy order for {formatted_symbol}: {e}")
            raise
    
    def place_market_sell(self, symbol: str, quantity: float) -> Dict:
        """
        Place a market sell order (supports both stocks and crypto)
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL' for stocks, 'BTC/USD' for crypto)
            quantity: Number of shares/coins to sell
            
        Returns:
            Order response
        """
        # Format symbol correctly
        is_crypto = self._is_crypto_symbol(symbol)
        formatted_symbol = self._format_crypto_symbol(symbol) if is_crypto else self._format_stock_symbol(symbol)
        
        return self.place_order(
            symbol=formatted_symbol,
            side='sell',
            order_type='market',
            quantity=quantity
        )
    
    def place_limit_order(self, symbol: str, side: str, quantity: float, 
                         limit_price: float) -> Dict:
        """
        Place a limit order
        
        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell'
            quantity: Number of shares
            limit_price: Limit price
            
        Returns:
            Order response
        """
        return self.place_order(
            symbol=symbol,
            side=side,
            order_type='limit',
            quantity=quantity,
            limit_price=limit_price
        )
    
    def get_order_status(self, symbol: str, order_id: str) -> Dict:
        """
        Get order status
        
        Args:
            symbol: Trading symbol (not used by Alpaca, but kept for compatibility)
            order_id: Order ID
            
        Returns:
            Order status dictionary
        """
        return self._make_request('GET', f'/v2/orders/{order_id}')
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get open orders
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of open orders
        """
        params = {}
        if symbol:
            if self._is_crypto_symbol(symbol):
                clean_symbol = self._format_crypto_position_symbol(symbol)
            else:
                clean_symbol = self._format_stock_symbol(symbol)
            params['symbols'] = clean_symbol
        
        return self._make_request('GET', '/v2/orders', params=params)
    
    def cancel_order(self, symbol_or_order_id: str, order_id: str = None) -> Dict:
        """
        Cancel an order.

        Accepts both single-arg form cancel_order(order_id) and two-arg form
        cancel_order(symbol, order_id) for compatibility with MEXCClient/BybitClient.

        Args:
            symbol_or_order_id: Order ID (single-arg) or symbol (two-arg, ignored)
            order_id: Order ID when called as cancel_order(symbol, order_id)

        Returns:
            Cancellation response
        """
        actual_order_id = order_id if order_id is not None else symbol_or_order_id
        return self._make_request('DELETE', f'/v2/orders/{actual_order_id}')
    
    def get_market_clock(self) -> Dict:
        """
        Get current market clock status (open/closed, next open/close times).

        Use this before placing stock orders to avoid after-hours rejections.
        Crypto is 24/7 and does not need this check.

        Returns:
            Dict with keys: timestamp, is_open, next_open, next_close
        """
        return self._make_request('GET', '/v2/clock')

    def is_market_open(self) -> bool:
        """
        Return True if the US equities market is currently open.

        Returns:
            True if market is open, False otherwise (or on error)
        """
        try:
            clock = self.get_market_clock()
            return bool(clock.get('is_open', False))
        except Exception as e:
            logger.warning(f"Could not check market clock: {e}")
            return False

    def close_position_by_symbol(self, symbol: str,
                                  qty: Optional[float] = None,
                                  percentage: Optional[float] = None) -> Dict:
        """
        Close (or partially close) a position by symbol via DELETE /v2/positions/:symbol.

        More reliable than placing a market sell order because Alpaca handles
        fractional shares, rounding, and lot sizes automatically.

        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'BTC/USD', 'BTCUSD')
            qty: Exact quantity to close (optional, defaults to full position)
            percentage: Percentage of position to close 0-100 (optional)

        Returns:
            Order response dict
        """
        is_crypto = self._is_crypto_symbol(symbol)
        clean_symbol = self._format_crypto_position_symbol(symbol) if is_crypto else self._format_stock_symbol(symbol)

        params: Dict = {}
        if qty is not None:
            params['qty'] = str(qty)
        elif percentage is not None:
            params['percentage'] = str(min(100.0, max(0.0, float(percentage))))

        # Full close only: cancel any open orders for this symbol first so quantity
        # is not reserved (common with staged TP limits).
        if not params:
            try:
                open_orders = self.get_open_orders() or []
                target = self._canonical_alpaca_symbol(clean_symbol)
                terminal = {'filled', 'canceled', 'cancelled', 'expired', 'rejected'}
                matched = []
                for order in open_orders:
                    if str(order.get('status', '')).lower() in terminal:
                        continue
                    if self._canonical_alpaca_symbol(order.get('symbol')) == target:
                        matched.append(order)
                logger.info(
                    f"Alpaca close preflight for {clean_symbol}: "
                    f"open_orders={len(open_orders)}, matched={len(matched)}"
                )
                cancelled = 0
                for order in matched:
                    order_id = order.get('id') or order.get('order_id') or order.get('orderId')
                    if not order_id:
                        continue
                    self.cancel_order(str(order_id))
                    cancelled += 1
                if cancelled > 0:
                    logger.info(f"Cancelled {cancelled} open Alpaca order(s) for {clean_symbol} before close")
                    time.sleep(1.0)
            except Exception as e:
                logger.warning(f"Alpaca close preflight cancel failed for {clean_symbol}: {e}")

        encoded_symbol = quote(clean_symbol, safe='')
        logger.info(f"Closing position via DELETE /v2/positions/{clean_symbol} params={params or 'full'}")
        try:
            return self._make_request('DELETE', f'/v2/positions/{encoded_symbol}', params=params or None)
        except Exception as e:
            # If Alpaca reports only part of the asset is currently available,
            # retry a partial close with the available amount.
            msg = str(e)
            if not params and 'insufficient balance for' in msg.lower():
                m = re.search(r'available:\s*([0-9]*\.?[0-9]+)', msg)
                if m:
                    available_qty = float(m.group(1))
                    if available_qty > 0:
                        retry_params = {'qty': str(available_qty)}
                        logger.warning(
                            f"Retrying close for {clean_symbol} with available qty={available_qty} "
                            f"after insufficient-balance full-close error"
                        )
                        return self._make_request('DELETE', f'/v2/positions/{encoded_symbol}', params=retry_params)
            raise

    def cancel_all_orders(self) -> List[Dict]:
        """
        Cancel all open orders

        Returns:
            List of cancellation responses
        """
        return self._make_request('DELETE', '/v2/orders')
