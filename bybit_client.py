"""
Bybit Exchange API Client
Handles authentication, order placement, and account management for Bybit
"""

import hmac
import hashlib
import math
import time
import requests
import json
from typing import Dict, Optional, List, Tuple, Any
from urllib.parse import urlencode
import logging

logger = logging.getLogger(__name__)


class BybitClient:
    """Bybit Exchange API Client"""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://api.bybit.com", 
                 testnet: bool = False, trading_mode: str = "spot", leverage: int = 1,
                 proxy: Optional[str] = None):
        """
        Initialize Bybit API Client
        
        Args:
            api_key: Bybit API Key
            api_secret: Bybit API Secret
            base_url: Bybit API base URL
            testnet: Whether to use testnet (default: False)
            trading_mode: 'spot' or 'futures' (one active mode at a time)
            leverage: Leverage multiplier for futures mode
            proxy: Optional proxy URL (e.g. http://host:port or socks5://host:port)
                   Use when deployment region is blocked by Bybit (403 CloudFront)
        """
        self.api_key = api_key.strip() if api_key else ''
        self.api_secret = api_secret.strip() if api_secret else ''
        
        if testnet:
            self.base_url = "https://api-testnet.bybit.com"
        else:
            self.base_url = base_url.rstrip('/') if base_url else "https://api.bybit.com"
        
        mode = (trading_mode or "spot").lower()
        self.trading_mode = "futures" if mode == "futures" else "spot"
        try:
            lev_val = float(leverage) if leverage is not None and str(leverage).strip() != '' else 1.0
        except (TypeError, ValueError):
            lev_val = 1.0
        self.leverage = max(1, min(100, int(round(lev_val))))
        
        self.testnet = testnet
        self.proxy = (proxy or '').strip() or None
        self.session = requests.Session()
        if self.proxy:
            self.session.proxies = {'http': self.proxy, 'https': self.proxy}
            logger.info(f"   Using proxy for Bybit (bypass geo-restrictions)")
        
        # Log loaded keys (masked) for verification
        if self.api_key:
            masked_key = f"{self.api_key[:6]}...{self.api_key[-4:]}" if len(self.api_key) > 10 else "***"
            logger.info(f"🔑 Loaded Bybit API Key: {masked_key} (length: {len(self.api_key)})")
        if self.api_secret:
            masked_secret = f"{self.api_secret[:6]}...{self.api_secret[-4:]}" if len(self.api_secret) > 10 else "***"
            logger.info(f"🔑 Loaded Bybit API Secret: {masked_secret} (length: {len(self.api_secret)})")
        
        logger.info(f"🌐 Bybit Base URL: {self.base_url} ({'Testnet' if testnet else 'Mainnet'})")
        logger.info(f"   Trading mode: {self.trading_mode.upper()} (leverage={self.leverage}x for futures)")
    
    def _get_server_time(self) -> int:
        """
        Get Bybit server time
        
        Returns:
            Server time in milliseconds
        """
        try:
            response = self.session.get(f"{self.base_url}/v5/market/time", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('retCode') == 0:
                    # timeSecond is returned as STRING - must convert to int before * 1000
                    ts = data.get('result', {}).get('timeSecond', int(time.time()))
                    server_time = int(ts) * 1000
                    logger.debug(f"⏰ Bybit server time: {server_time}")
                    return server_time
        except Exception as e:
            logger.warning(f"Could not get Bybit server time, using local time: {e}")
        
        # Fallback to local time
        return int(time.time() * 1000)
    
    def _generate_signature(self, timestamp: int, recv_window: int, payload: str) -> str:
        """
        Generate HMAC-SHA256 signature for authenticated requests.
        
        Bybit V5 format (matches pybit): param_str = timestamp + api_key + recv_window + payload
        - GET: payload = sorted query string of business params only (no auth in URL)
        - POST: payload = JSON body string
        
        Args:
            timestamp: Request timestamp in milliseconds
            recv_window: Recv window in ms
            payload: Query string (GET) or JSON body (POST)
            
        Returns:
            Signature string
        """
        param_str = f"{timestamp}{self.api_key}{recv_window}{payload}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        logger.debug(f"🔐 Bybit signature payload: {payload[:80]}...")
        return signature
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                     signed: bool = False, category: str = 'spot') -> Dict:
        """
        Make API request to Bybit
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (e.g., '/v5/account/wallet-balance')
            params: Request parameters
            signed: Whether to include authentication signature
            category: API category ('spot', 'linear', 'inverse', 'option')
            
        Returns:
            API response as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        method_upper = method.upper()

        # Log trade write payloads for execution visibility (no auth headers/signature).
        is_trade_write_endpoint = (
            method_upper == 'POST'
            and endpoint in (
                '/v5/order/create',
                '/v5/position/trading-stop',
                '/v5/position/set-leverage',
            )
        )
        if is_trade_write_endpoint:
            logger.info(
                f"Bybit OUTBOUND: endpoint={endpoint} payload={json.dumps(params, default=str)}"
            )
        
        if signed:
            # Get server time
            timestamp = self._get_server_time()
            recv_window = 5000
            
            # Bybit V5: auth in headers only. Sign = timestamp + api_key + recv_window + payload
            # GET: payload = sorted query string of business params
            # POST: payload = JSON body string
            if method.upper() == 'GET':
                payload = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            else:
                payload = json.dumps(params) if params else ""
            signature = self._generate_signature(timestamp, recv_window, payload)
            
            headers = {
                'X-BAPI-API-KEY': self.api_key,
                'X-BAPI-SIGN': signature,
                'X-BAPI-SIGN-TYPE': '2',  # HMAC-SHA256
                'X-BAPI-TIMESTAMP': str(timestamp),
                'X-BAPI-RECV-WINDOW': str(recv_window),
                'Content-Type': 'application/json'
            }
        else:
            headers = {'Content-Type': 'application/json'}
        
        try:
            if method_upper == 'GET':
                if params:
                    qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
                    url = f"{url}?{qs}"
                response = self.session.get(url, headers=headers, timeout=10)
            elif method_upper == 'POST':
                response = self.session.post(url, json=params, headers=headers, timeout=10)
            elif method_upper == 'DELETE':
                response = self.session.delete(url, params=params, headers=headers, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            result = response.json()
            
            # Check Bybit response code
            ret_code = result.get('retCode', 0)
            if ret_code != 0:
                ret_msg = result.get('retMsg', 'Unknown error')
                error_msg = f"Bybit API Error (Code {ret_code}): {ret_msg}"
                if is_trade_write_endpoint:
                    logger.error(
                        f"Bybit INBOUND ERROR: endpoint={endpoint} retCode={ret_code} retMsg={ret_msg} response={json.dumps(result, default=str)}"
                    )
                logger.error(f"❌ {error_msg}")
                logger.error(f"   Response: {json.dumps(result, indent=2)}")
                raise Exception(error_msg)

            if is_trade_write_endpoint:
                logger.info(
                    f"Bybit INBOUND: endpoint={endpoint} retCode={ret_code} retMsg={result.get('retMsg', '')} response={json.dumps(result, default=str)}"
                )
            
            return result
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 'unknown'
            error_msg = f"HTTP {status_code}"
            try:
                error_data = e.response.json()
                ret_msg = (error_data.get('retMsg') or '').strip()
                api_msg = (error_data.get('message') or '').strip()
                error_msg = ret_msg or api_msg or error_msg
                logger.error(f"Bybit API Error Response: {json.dumps(error_data, indent=2)}")
            except:
                error_text = e.response.text if hasattr(e.response, 'text') else str(e)
                clean_text = (error_text or '').strip()
                if clean_text:
                    error_msg = f"{error_msg}: {clean_text}"
                elif status_code == 401:
                    error_msg = (
                        "HTTP 401 Unauthorized (invalid API key/secret, wrong mainnet/testnet "
                        "environment, missing API permissions, or IP whitelist restriction)"
                    )
                logger.error(f"Bybit API Error (non-JSON): {error_text}")
            
            logger.error(f"Bybit API Error: {error_msg}")
            logger.error(f"Request URL: {url}")
            logger.error(f"Request Method: {method}")
            if params:
                logger.error(f"Request Params: {json.dumps(params, indent=2)}")
            
            raise Exception(f"Bybit API Error: {error_msg}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise Exception(f"Request error: {e}")
    
    # Account Methods
    
    def get_account_info(self) -> Dict:
        """
        Get account information
        
        Returns:
            Account information dictionary
        """
        # Bybit V5 wallet-balance only accepts UNIFIED (SPOT deprecated for this endpoint)
        return self._make_request('GET', '/v5/account/wallet-balance', 
                                 params={'accountType': 'UNIFIED'}, signed=True)
    
    def get_balance(self, asset: Optional[str] = None) -> Dict:
        """
        Get account balance
        
        Args:
            asset: Specific asset symbol (e.g., 'USDT'). If None, returns all balances
            
        Returns:
            Balance information
        """
        account = self.get_account_info()
        balances = account.get('result', {}).get('list', [])
        
        if balances:
            spot_account = balances[0].get('coin', [])
            if asset:
                for coin in spot_account:
                    if coin.get('coin') == asset:
                        wallet = float(coin.get('walletBalance', 0))
                        locked = float(coin.get('locked', 0))
                        free = float(coin.get('free', 0) or coin.get('availableToWithdraw', 0) or (wallet - locked))
                        return {
                            'asset': asset,
                            'free': free,
                            'locked': locked,
                            'total': wallet
                        }
                return {'asset': asset, 'free': 0.0, 'locked': 0.0, 'total': 0.0}
        
        return balances if not asset else {'asset': asset, 'free': 0.0, 'locked': 0.0, 'total': 0.0}
    
    def validate_connection(self) -> Dict:
        """
        Validate API connection and get account info
        
        Returns:
            Dictionary with connection status and account info
        """
        try:
            account_info = self.get_account_info()
            ret_code = account_info.get('retCode', 0)
            
            if ret_code == 0:
                return {
                    'connected': True,
                    'account': account_info,
                    'can_trade': True,
                    'balances': account_info.get('result', {}).get('list', [])
                }
            else:
                ret_msg = account_info.get('retMsg', 'Unknown error')
                return {
                    'connected': False,
                    'error': f"Bybit API Error (Code {ret_code}): {ret_msg}",
                    'account': None,
                    'can_trade': False,
                    'balances': []
                }
        except Exception as e:
            logger.error(f"Connection validation failed: {e}")
            return {
                'connected': False,
                'error': str(e),
                'account': None,
                'can_trade': False,
                'balances': []
            }
    
    def get_main_balances(self) -> Dict:
        """
        Get all account balances (all assets with balance > 0)
        
        Returns:
            Dictionary with all asset balances
        """
        try:
            account = self.get_account_info()
            balances = account.get('result', {}).get('list', [])
            
            all_balances = {}
            
            if balances:
                spot_account = balances[0].get('coin', [])
                for coin in spot_account:
                    asset = coin.get('coin', '')
                    wallet = float(coin.get('walletBalance', 0))
                    locked = float(coin.get('locked', 0))
                    free = float(coin.get('free', 0) or coin.get('availableToWithdraw', 0) or (wallet - locked))
                    
                    # Include all assets with balance > 0
                    if wallet > 0:
                        all_balances[asset] = {
                            'free': free,
                            'locked': locked,
                            'total': wallet
                        }
            
            # Log balances for debugging
            if all_balances:
                balance_str = ', '.join([f"{asset}: {bal['total']:.8f}" 
                                       for asset, bal in sorted(all_balances.items())])
                logger.info(f"💰 Account balances: {balance_str}")
            else:
                logger.info("💰 Account balances: No balances found (all zero)")
            
            return all_balances
        except Exception as e:
            logger.error(f"Error getting balances: {e}")
            return {}
    
    # Futures-specific methods
    
    def _category(self) -> str:
        """API category based on trading mode"""
        return 'linear' if self.trading_mode == 'futures' else 'spot'
    
    def set_leverage(self, symbol: str, leverage: Optional[int] = None) -> bool:
        """
        Set leverage for a symbol (futures only). Dynamically uses max supported leverage.

        Args:
            symbol: Trading pair (e.g. BTCUSDT)
            leverage: Desired leverage (uses self.leverage if not provided).
                     Will use min(requested, max_supported) for the symbol.

        Returns:
            True if successful
        """
        if self.trading_mode != 'futures':
            logger.info(f"Skipping set-leverage for {symbol}: trading_mode={self.trading_mode}")
            return True

        # Check for existing open positions
        positions = self.get_positions(symbol)
        if positions:
            for pos in positions:
                pos_size = float(pos.get('size', 0))
                pos_side = pos.get('side', 'N/A')
                pos_entry = float(pos.get('avgPrice', 0))
                if pos_size > 0:
                    logger.warning(
                        f"⚠️  EXISTING POSITION DETECTED on {symbol}: "
                        f"Side={pos_side}, Size={pos_size}, Entry Price={pos_entry:.8f}. "
                        f"Changing leverage on open position may affect margin requirements and risk."
                    )

        requested_lev = int(leverage or self.leverage)

        # Query symbol's max supported leverage
        instrument = self.get_instrument_info(symbol)
        max_leverage = 1
        if instrument:
            leverage_filter = instrument.get('leverageFilter', {})
            max_leverage = int(float(leverage_filter.get('maxLeverage', 1)))
            logger.info(f"Symbol {symbol} supports up to {max_leverage}x leverage")
        else:
            logger.warning(f"Could not fetch leverage info for {symbol}, defaulting to 1x")

        # Use min of requested and max supported
        final_lev = min(requested_lev, max_leverage)

        if final_lev < 1:
            final_lev = 1

        logger.info(f"Requested {requested_lev}x, max supported {max_leverage}x → using {final_lev}x for {symbol}")

        params = {
            'category': 'linear',
            'symbol': symbol,
            'buyLeverage': str(final_lev),
            'sellLeverage': str(final_lev)
        }
        try:
            logger.info(
                f"Attempting set-leverage: symbol={symbol}, leverage={final_lev}x, base_url={self.base_url}, testnet={self.testnet}, mode={self.trading_mode}"
            )
            self._make_request('POST', '/v5/position/set-leverage', params=params, signed=True)
            logger.info(f"✅ Set leverage {final_lev}x for {symbol} (buy/sell)")
            return True
        except Exception as e:
            error_str = str(e)
            # Error 110043 = leverage already set to that value (harmless, continue)
            if '110043' in error_str or 'leverage not modified' in error_str.lower():
                logger.info(f"ℹ️  Leverage already set to {final_lev}x for {symbol}, continuing...")
                return True
            logger.error(f"❌ set-leverage failed for {symbol} at {final_lev}x: {e}")
            return False
    
    def get_instrument_info(self, symbol: str) -> Optional[Dict]:
        """Get instrument info (lot size, tick size) for a symbol"""
        params = {'category': self._category(), 'symbol': symbol}
        try:
            resp = self._make_request('GET', '/v5/market/instruments-info', params=params)
            items = resp.get('result', {}).get('list', [])
            return items[0] if items else None
        except Exception as e:
            logger.warning(f"Could not get instrument info for {symbol}: {e}")
            return None
    
    def _round_qty(self, symbol: str, qty: float) -> str:
        """Round quantity to symbol's lot size precision (round half up)"""
        info = self.get_instrument_info(symbol)
        if info:
            lot_filter = info.get('lotSizeFilter', {})
            qty_step = float(lot_filter.get('qtyStep', 0.001))
            min_qty = float(lot_filter.get('minOrderQty', qty_step))
            if qty_step > 0:
                rounded = round(qty / qty_step) * qty_step
                rounded = max(rounded, min_qty)
                s = f"{rounded:.8f}".rstrip('0').rstrip('.')
                return s if s else str(min_qty)
        return f"{max(qty, 0.001):.6f}"
    
    def _floor_qty_str(self, symbol: str, qty: float) -> Optional[str]:
        """Floor quantity to lot step (for TP slices so sum of TPs does not exceed position)."""
        if qty <= 0:
            return None
        info = self.get_instrument_info(symbol)
        qty_step = 0.001
        min_qty = 0.001
        if info:
            lot_filter = info.get('lotSizeFilter', {})
            qty_step = float(lot_filter.get('qtyStep', 0.001))
            min_qty = float(lot_filter.get('minOrderQty', qty_step))
        if qty_step <= 0:
            qty_step = 0.001
        floored = math.floor(qty / qty_step + 1e-12) * qty_step
        if floored + 1e-12 < min_qty:
            return None
        s = f"{floored:.8f}".rstrip('0').rstrip('.')
        return s if s else None
    
    def _round_price_str(self, symbol: str, price: float) -> str:
        """Round price to tick size (required for Bybit limit orders)."""
        info = self.get_instrument_info(symbol)
        if info:
            pf = info.get('priceFilter', {})
            tick = float(pf.get('tickSize', 0.01))
            if tick > 0:
                rounded = round(price / tick) * tick
                s = f"{rounded:.8f}".rstrip('0').rstrip('.')
                return s if s else str(price)
        return str(round(price, 8))
    
    def set_position_trading_stop(
        self,
        symbol: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        position_idx: int = 0,
        tpsl_mode: str = 'Full',
        sl_trigger_by: str = 'MarkPrice',
        tp_trigger_by: str = 'MarkPrice',
    ) -> Dict:
        """
        Set full/partial TP/SL on an open position (visible in Bybit UI).
        https://bybit-exchange.github.io/docs/v5/position/trading-stop
        """
        if self.trading_mode != 'futures':
            return {}
        params: Dict[str, Any] = {
            'category': 'linear',
            'symbol': symbol,
            'positionIdx': position_idx,
            'tpslMode': tpsl_mode,
        }
        if stop_loss is not None and stop_loss > 0:
            params['stopLoss'] = self._round_price_str(symbol, stop_loss)
            params['slTriggerBy'] = sl_trigger_by
            params['slOrderType'] = 'Market'
        if take_profit is not None and take_profit > 0:
            params['takeProfit'] = self._round_price_str(symbol, take_profit)
            params['tpTriggerBy'] = tp_trigger_by
            params['tpOrderType'] = 'Market'
        if len(params) <= 3:
            return {}
        return self._make_request('POST', '/v5/position/trading-stop', params=params, signed=True)
    
    # Market Methods
    
    def get_ticker_price(self, symbol: str) -> float:
        """
        Get current ticker price
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            
        Returns:
            Current price as float
        """
        params = {'symbol': symbol, 'category': self._category()}
        response = self._make_request('GET', '/v5/market/tickers', params=params)
        
        result = response.get('result', {}).get('list', [])
        if result and len(result) > 0:
            price = float(result[0].get('lastPrice', 0))
            if price > 0:
                return price
        
        raise ValueError(f"Could not get price for {symbol}")
    
    def get_order_book(self, symbol: str, limit: int = 5) -> Dict:
        """
        Get order book
        
        Args:
            symbol: Trading pair symbol
            limit: Number of orders to return (default: 5)
            
        Returns:
            Order book data
        """
        params = {'symbol': symbol, 'category': 'spot', 'limit': limit}
        return self._make_request('GET', '/v5/market/orderbook', params=params)
    
    # Trading Methods
    
    def place_order(self, symbol: str, side: str, order_type: str, 
                   quantity: Optional[float] = None, price: Optional[float] = None,
                   quote_order_qty: Optional[float] = None, reduce_only: bool = False) -> Dict:
        """
        Place a new order (spot or futures based on trading_mode)
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            side: Order side ('Buy' or 'Sell')
            order_type: Order type ('Market', 'Limit', etc.)
            quantity: Order quantity (for MARKET/LIMIT orders)
            price: Order price (for LIMIT orders)
            quote_order_qty: Quote order quantity (for Spot MARKET orders in quote currency)
            reduce_only: For futures - close/reduce position only
            
        Returns:
            Order response dictionary
        """
        category = self._category()
        params = {
            'category': category,
            'symbol': symbol,
            'side': side.capitalize(),
            'orderType': order_type.capitalize(),
        }
        
        if category == 'linear':
            params['positionIdx'] = 0  # One-way mode
            if reduce_only:
                params['reduceOnly'] = True
            if order_type.upper() == 'MARKET':
                params['timeInForce'] = 'IOC'
                if not quantity or quantity <= 0:
                    raise ValueError("Futures MARKET orders require quantity in base currency")
                params['qty'] = self._round_qty(symbol, quantity)
            elif order_type.upper() == 'LIMIT':
                if not quantity or not price:
                    raise ValueError("LIMIT orders require both quantity and price")
                params['qty'] = self._round_qty(symbol, quantity)
                params['price'] = self._round_price_str(symbol, float(price))
                params['timeInForce'] = 'GTC'
        else:
            if order_type.upper() == 'MARKET':
                if quote_order_qty:
                    params['qty'] = str(quote_order_qty)
                    params['marketUnit'] = 'quoteCoin'
                elif quantity:
                    params['qty'] = str(quantity)
                    params['marketUnit'] = 'baseCoin'
            elif order_type.upper() == 'LIMIT':
                if not quantity or not price:
                    raise ValueError("LIMIT orders require both quantity and price")
                params['qty'] = str(quantity)
                params['price'] = self._round_price_str(symbol, float(price))
                params['timeInForce'] = 'GTC'
        
        logger.info(f"Placing {side} order ({category}): symbol={params.get('symbol')} qty={params.get('qty')}")
        logger.info(f"TradingView-to-Bybit order payload: {json.dumps(params, default=str)}")
        return self._make_request('POST', '/v5/order/create', params=params, signed=True)
    
    def place_market_buy(self, symbol: str, quote_quantity: float, price: Optional[float] = None, reduce_only: bool = False) -> Dict:
        """
        Place a market buy order
        
        Args:
            symbol: Trading pair symbol
            quote_quantity: Spot: USDT amount. Futures: position value in USDT (margin * leverage), or qty if reduce_only
            price: Current price (required for futures to compute qty, or when reduce_only with qty in base)
            reduce_only: For futures - close short position only
            
        Returns:
            Order response
        """
        if self.trading_mode == 'futures':
            if reduce_only:
                qty = quote_quantity
            else:
                if price is None or price <= 0:
                    price = self.get_ticker_price(symbol)
                qty = quote_quantity / price
            return self.place_order(symbol=symbol, side='Buy', order_type='Market', quantity=qty, reduce_only=reduce_only)
        return self.place_order(symbol=symbol, side='Buy', order_type='Market', quote_order_qty=quote_quantity)
    
    def place_market_sell(self, symbol: str, quantity: float, reduce_only: bool = False) -> Dict:
        """
        Place a market sell order
        
        Args:
            symbol: Trading pair symbol
            quantity: Quantity in base currency (e.g., BTC amount for BTCUSDT)
            reduce_only: For futures - close position only
            
        Returns:
            Order response
        """
        return self.place_order(
            symbol=symbol,
            side='Sell',
            order_type='Market',
            quantity=quantity,
            reduce_only=reduce_only
        )
    
    def get_order_status(self, symbol: str, order_id: str) -> Dict:
        """
        Get order status for a specific orderId.

        Futures: try /v5/order/realtime first (open + recent closed when filtered by orderId),
        then /v5/order/history. Always narrows the list to the exact orderId so callers
        never read list[0] from another order (which could falsely look FILLED).
        """
        category = self._category()
        oid = (order_id or '').strip()
        if not oid:
            return {'result': {'list': []}}

        def _matching(rows: List[Dict]) -> Optional[Dict]:
            for od in rows or []:
                if str(od.get('orderId', '')).strip() == oid:
                    return od
            return None

        def _wrap(od: Optional[Dict]) -> Dict:
            if od:
                return {'result': {'list': [od]}}
            return {'result': {'list': []}}

        if self.trading_mode == 'futures':
            try:
                realtime = self._make_request(
                    'GET',
                    '/v5/order/realtime',
                    params={'category': category, 'symbol': symbol, 'orderId': oid},
                    signed=True,
                )
                od = _matching((realtime.get('result') or {}).get('list'))
                if od:
                    return _wrap(od)
            except Exception as e:
                logger.debug(f"Bybit realtime order {oid}: {e}")

        try:
            hist = self._make_request(
                'GET',
                '/v5/order/history',
                params={'category': category, 'symbol': symbol, 'orderId': oid},
                signed=True,
            )
            od = _matching((hist.get('result') or {}).get('list'))
            return _wrap(od)
        except Exception as e:
            logger.warning(f"Bybit order history lookup failed for {oid}: {e}")
            return {'result': {'list': []}}
    
    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """Cancel an order"""
        params = {'category': self._category(), 'symbol': symbol, 'orderId': order_id}
        return self._make_request('POST', '/v5/order/cancel', params=params, signed=True)
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open orders"""
        params = {'category': self._category()}
        if symbol:
            params['symbol'] = symbol
        response = self._make_request('GET', '/v5/order/realtime', params=params, signed=True)
        return response.get('result', {}).get('list', [])
    
    def cancel_all_orders(self, symbol: str) -> Dict:
        """Cancel all open orders for a symbol"""
        params = {'category': self._category(), 'symbol': symbol}
        return self._make_request('POST', '/v5/order/cancel-all', params=params, signed=True)
    
    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get open positions (futures only)"""
        if self.trading_mode != 'futures':
            return []
        params = {'category': 'linear', 'settleCoin': 'USDT'}
        if symbol:
            params['symbol'] = symbol
        try:
            resp = self._make_request('GET', '/v5/position/list', params=params, signed=True)
            return resp.get('result', {}).get('list', [])
        except Exception as e:
            logger.warning(f"Could not get positions: {e}")
            return []

    def get_position_for_symbol(self, symbol: str) -> Optional[Dict]:
        """Get open position details for a specific symbol (returns None if no position)"""
        positions = self.get_positions(symbol)
        if positions:
            pos = positions[0]
            if float(pos.get('size', 0)) > 0:
                return {
                    'symbol': symbol,
                    'side': pos.get('side'),
                    'size': float(pos.get('size', 0)),
                    'entry_price': float(pos.get('avgPrice', 0)),
                    'unrealised_pnl': float(pos.get('unrealisedPnl', 0)),
                    'leverage': float(pos.get('leverage', 1)),
                }
        return None
