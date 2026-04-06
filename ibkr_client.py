"""
Interactive Brokers (IBKR) API Client
Handles authentication, order placement, and account management for IBKR
Uses IBKR REST API (Client Portal API)
"""

import requests
import json
import time
from typing import Dict, Optional, List
import logging
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class IBKRClient:
    """Interactive Brokers REST API Client"""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://localhost:5000", 
                 account_id: Optional[str] = None, use_paper: bool = False, leverage: int = 1):
        """
        Initialize IBKR API Client
        
        Args:
            api_key: Unused for Client Portal session auth (pass ''); reserved for future OAuth flows
            api_secret: Unused for session auth (pass '')
            base_url: Client Portal Web API base URL
                - Default: https://localhost:5000 (IB Gateway / TWS with API enabled)
            account_id: IBKR account ID (optional, can be auto-detected)
            use_paper: Whether to use paper trading account
            leverage: Leverage multiplier (1 = no leverage, 2 = 2x, etc.)
        """
        # Trim whitespace to prevent errors
        self.api_key = api_key.strip() if api_key else ''
        self.api_secret = api_secret.strip() if api_secret else ''
        self.base_url = base_url.rstrip('/')
        self.account_id = account_id
        self.use_paper = use_paper
        self.leverage = max(1, min(100, int(leverage))) if leverage else 1  # Clamp between 1-100
        self.session = requests.Session()
        
        # IBKR REST API uses OAuth or session-based auth
        # For Client Portal API, authentication is typically done via session
        # Note: IBKR requires IB Gateway or TWS to be running for REST API access
        
        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        # Disable SSL verification for localhost (IB Gateway runs on localhost)
        if 'localhost' in self.base_url or '127.0.0.1' in self.base_url:
            self.session.verify = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                     data: Optional[Dict] = None) -> Dict:
        """
        Make authenticated API request to IBKR
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint (e.g., '/v1/api/portfolio/accounts')
            params: Query parameters
            data: Request body data
            
        Returns:
            Response JSON as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        
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
            
            # IBKR API may return empty response for some endpoints
            if response.text:
                return response.json()
            else:
                return {}
                
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_msg = error_data.get('error', error_data.get('message', error_msg))
            except:
                error_msg = str(e)
            
            logger.error(f"IBKR API Error: {error_msg}")
            raise Exception(f"IBKR API Error: {error_msg}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise Exception(f"Request error: {e}")
    
    def _authenticate(self) -> bool:
        """
        Authenticate with IBKR API
        Note: IBKR Client Portal API requires IB Gateway/TWS to be running
        
        Returns:
            True if authenticated successfully
        """
        try:
            # IBKR Client Portal API uses session-based authentication
            # First, check if we need to authenticate
            response = self._make_request('GET', '/v1/api/iserver/auth/status')
            
            authenticated = response.get('authenticated', False)
            if authenticated:
                logger.info("✅ IBKR session authenticated")
                return True
            else:
                logger.warning("⚠️  IBKR session not authenticated. Ensure IB Gateway/TWS is running.")
                return False
                
        except Exception as e:
            logger.error(f"Authentication check failed: {e}")
            logger.warning("⚠️  Make sure IB Gateway or TWS is running and API is enabled")
            return False
    
    def validate_connection(self) -> Dict:
        """
        Validate API connection and permissions
        
        Returns:
            Dictionary with 'connected' and 'can_trade' status
        """
        try:
            # Check authentication status
            authenticated = self._authenticate()
            
            if not authenticated:
                return {
                    'connected': False,
                    'can_trade': False,
                    'error': 'Not authenticated. Ensure IB Gateway/TWS is running and API is enabled.'
                }
            
            # Get account info to verify connection
            accounts = self._make_request('GET', '/v1/api/portfolio/accounts')
            
            if not accounts or len(accounts) == 0:
                return {
                    'connected': False,
                    'can_trade': False,
                    'error': 'No accounts found'
                }
            
            # Use first account if account_id not specified
            if not self.account_id and accounts:
                self.account_id = accounts[0].get('accountId', '')
                logger.info(f"Using account ID: {self.account_id}")
            
            return {
                'connected': True,
                'can_trade': True,
                'account_id': self.account_id,
                'accounts': accounts
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
        if not self.account_id:
            accounts = self._make_request('GET', '/v1/api/portfolio/accounts')
            if accounts:
                self.account_id = accounts[0].get('accountId', '')
        
        if not self.account_id:
            raise Exception("No account ID available")
        
        return self._make_request('GET', f'/v1/api/portfolio/{self.account_id}/summary')
    
    def get_balance(self, asset: str = 'USD') -> Dict:
        """
        Get balance for a specific asset
        
        Args:
            asset: Asset symbol (default: 'USD' for cash)
            
        Returns:
            Balance information
        """
        try:
            account_info = self.get_account_info()
            
            # IBKR returns account summary with various balance fields
            if asset.upper() == 'USD':
                # Get cash balance
                cash_balance = 0.0
                for item in account_info.get('summary', []):
                    if item.get('tag') == 'CashBalance' or item.get('tag') == 'TotalCashValue':
                        cash_balance = float(item.get('value', 0))
                        break
                
                return {
                    'asset': 'USD',
                    'free': cash_balance,
                    'locked': 0.0,
                    'total': cash_balance
                }
            else:
                # For positions, get from positions endpoint
                positions = self.get_positions()
                for pos in positions:
                    if pos.get('symbol') == asset or pos.get('contractDesc', '').startswith(asset):
                        qty = float(pos.get('position', 0))
                        return {
                            'asset': asset,
                            'free': abs(qty),
                            'locked': 0.0,
                            'total': abs(qty)
                        }
                
                return {
                    'asset': asset,
                    'free': 0.0,
                    'locked': 0.0,
                    'total': 0.0
                }
                
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
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
            account_info = self.get_account_info()
            
            # Get cash balance
            cash_balance = 0.0
            for item in account_info.get('summary', []):
                if item.get('tag') == 'CashBalance' or item.get('tag') == 'TotalCashValue':
                    cash_balance = float(item.get('value', 0))
                    break
            
            if cash_balance > 0:
                balances['USD'] = {
                    'free': cash_balance,
                    'locked': 0.0,
                    'total': cash_balance
                }
            
            # Add position balances
            positions = self.get_positions()
            for pos in positions:
                symbol = pos.get('symbol') or pos.get('contractDesc', '')
                qty = float(pos.get('position', 0))
                if qty != 0:
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
            if not self.account_id:
                accounts = self._make_request('GET', '/v1/api/portfolio/accounts')
                if accounts:
                    self.account_id = accounts[0].get('accountId', '')
            
            if not self.account_id:
                return []
            
            return self._make_request('GET', f'/v1/api/portfolio/{self.account_id}/positions')
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Get position for a specific symbol
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'BTC')
            
        Returns:
            Position dictionary or None
        """
        try:
            positions = self.get_positions()
            for pos in positions:
                pos_symbol = pos.get('symbol') or pos.get('contractDesc', '')
                if symbol.upper() in pos_symbol.upper():
                    return pos
            return None
        except Exception as e:
            logger.error(f"Error getting position: {e}")
            return None
    
    def _format_symbol(self, symbol: str) -> Dict:
        """
        Format symbol for IBKR API (convert to contract format)
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'BTCUSD')
            
        Returns:
            Contract dictionary with conid
        """
        # IBKR uses contract IDs (conid) for trading
        # First, search for the contract to get conid
        try:
            # Search for contract
            search_params = {'symbol': symbol.replace('USDT', '').replace('USD', '')}
            search_result = self._make_request('GET', '/v1/api/trsrv/stocks', params=search_params)
            
            if search_result and len(search_result) > 0:
                # Use first result
                contract = search_result[0]
                return {
                    'conid': contract.get('conid'),
                    'symbol': contract.get('symbol', symbol),
                    'exchange': contract.get('exchange', 'SMART')
                }
            else:
                # Fallback: try to search with full symbol
                search_params = {'symbol': symbol}
                search_result = self._make_request('GET', '/v1/api/trsrv/stocks', params=search_params)
                if search_result and len(search_result) > 0:
                    contract = search_result[0]
                    return {
                        'conid': contract.get('conid'),
                        'symbol': contract.get('symbol', symbol),
                        'exchange': contract.get('exchange', 'SMART')
                    }
                
                raise ValueError(f"Contract not found for symbol: {symbol}")
                
        except Exception as e:
            logger.error(f"Error formatting symbol: {e}")
            # Return basic contract structure (may need manual conid)
            return {
                'conid': None,
                'symbol': symbol,
                'exchange': 'SMART'
            }
    
    def get_ticker_price(self, symbol: str) -> float:
        """
        Get current ticker price
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'BTC')
            
        Returns:
            Current price
        """
        try:
            # Format symbol to get contract
            contract = self._format_symbol(symbol)
            conid = contract.get('conid')
            
            if not conid:
                raise ValueError(f"Could not find contract ID for {symbol}")
            
            # Get market data snapshot
            params = {'conids': conid, 'fields': '31'}  # Field 31 is last price
            market_data = self._make_request('GET', '/v1/api/iserver/marketdata/snapshot', params=params)
            
            if market_data and len(market_data) > 0:
                data = market_data[0]
                # Field 31 is last price
                if '31' in data:
                    return float(data['31'])
                elif 'lastPrice' in data:
                    return float(data['lastPrice'])
                else:
                    raise ValueError(f"No price data available for {symbol}")
            else:
                raise ValueError(f"No market data available for {symbol}")
                
        except Exception as e:
            logger.error(f"Error getting ticker price for {symbol}: {e}")
            raise ValueError(f"Could not get price for {symbol}: {str(e)}")
    
    def place_order(self, symbol: str, side: str, order_type: str,
                   quantity: Optional[float] = None,
                   limit_price: Optional[float] = None,
                   stop_price: Optional[float] = None) -> Dict:
        """
        Place an order
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'BTC')
            side: 'buy' or 'sell'
            order_type: 'market', 'limit', 'stop', 'stop_limit'
            quantity: Number of shares/contracts
            limit_price: Limit price (for limit/stop_limit orders)
            stop_price: Stop price (for stop/stop_limit orders)
            
        Returns:
            Order response
        """
        if not self.account_id:
            accounts = self._make_request('GET', '/v1/api/portfolio/accounts')
            if accounts:
                self.account_id = accounts[0].get('accountId', '')
        
        if not self.account_id:
            raise Exception("No account ID available")
        
        # Format symbol to get contract
        contract = self._format_symbol(symbol)
        conid = contract.get('conid')
        
        if not conid:
            raise ValueError(f"Could not find contract ID for {symbol}")
        
        # Build order data
        order_data = {
            'acctId': self.account_id,
            'conid': conid,
            'orderType': order_type.upper(),
            'side': side.upper(),
            'quantity': quantity
        }
        
        # Add leverage if greater than 1
        if self.leverage > 1:
            # IBKR leverage is typically set via margin type, but we can include it in order data
            # Some IBKR APIs support 'leverage' field directly
            order_data['leverage'] = self.leverage
            logger.info(f"Using leverage: {self.leverage}x")
        
        if order_type.lower() == 'limit':
            if not limit_price:
                raise ValueError("Limit orders require limit_price")
            order_data['price'] = limit_price
        elif order_type.lower() == 'stop':
            if not stop_price:
                raise ValueError("Stop orders require stop_price")
            order_data['auxPrice'] = stop_price
        elif order_type.lower() == 'stop_limit':
            if not limit_price or not stop_price:
                raise ValueError("Stop-limit orders require both limit_price and stop_price")
            order_data['price'] = limit_price
            order_data['auxPrice'] = stop_price
        
        logger.info(f"Placing {side} order: {order_data}")
        
        # Place order
        return self._make_request('POST', '/v1/api/iserver/account/{}/order'.format(self.account_id), data=order_data)
    
    def place_market_buy(self, symbol: str, notional: float) -> Dict:
        """
        Place a market buy order
        
        Args:
            symbol: Trading symbol
            notional: Dollar amount to spend
            
        Returns:
            Order response
        """
        # Get current price to calculate quantity
        try:
            price = self.get_ticker_price(symbol)
            quantity = notional / price
        except:
            # If price fetch fails, use notional directly (IBKR may handle it)
            quantity = notional
        
        return self.place_order(
            symbol=symbol,
            side='buy',
            order_type='market',
            quantity=quantity
        )
    
    def place_market_sell(self, symbol: str, quantity: float) -> Dict:
        """
        Place a market sell order
        
        Args:
            symbol: Trading symbol
            quantity: Number of shares/contracts to sell
            
        Returns:
            Order response
        """
        return self.place_order(
            symbol=symbol,
            side='sell',
            order_type='market',
            quantity=quantity
        )
    
    def get_order_status(self, symbol: str, order_id: str) -> Dict:
        """
        Get order status
        
        Args:
            symbol: Trading symbol (not used by IBKR, but kept for compatibility)
            order_id: Order ID
            
        Returns:
            Order status dictionary
        """
        if not self.account_id:
            accounts = self._make_request('GET', '/v1/api/portfolio/accounts')
            if accounts:
                self.account_id = accounts[0].get('accountId', '')
        
        if not self.account_id:
            raise Exception("No account ID available")
        
        return self._make_request('GET', f'/v1/api/iserver/account/{self.account_id}/order/{order_id}')
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get open orders
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of open orders
        """
        if not self.account_id:
            accounts = self._make_request('GET', '/v1/api/portfolio/accounts')
            if accounts:
                self.account_id = accounts[0].get('accountId', '')
        
        if not self.account_id:
            return []
        
        orders = self._make_request('GET', f'/v1/api/iserver/account/{self.account_id}/orders')
        
        if symbol:
            # Filter by symbol
            filtered = []
            for order in orders:
                order_symbol = order.get('symbol') or order.get('contractDesc', '')
                if symbol.upper() in order_symbol.upper():
                    filtered.append(order)
            return filtered
        
        return orders
    
    def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel an order
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            Cancellation response
        """
        if not self.account_id:
            accounts = self._make_request('GET', '/v1/api/portfolio/accounts')
            if accounts:
                self.account_id = accounts[0].get('accountId', '')
        
        if not self.account_id:
            raise Exception("No account ID available")
        
        return self._make_request('DELETE', f'/v1/api/iserver/account/{self.account_id}/order/{order_id}')
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Cancel all open orders
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of cancellation responses
        """
        open_orders = self.get_open_orders(symbol)
        results = []
        
        for order in open_orders:
            order_id = order.get('orderId') or order.get('id')
            if order_id:
                try:
                    result = self.cancel_order(str(order_id))
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error canceling order {order_id}: {e}")
        
        return results
