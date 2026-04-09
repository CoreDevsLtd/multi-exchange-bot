"""
Interactive Brokers Client via ibind (ibeam REST API client)
Connects to ibeam Docker container running IBKR Gateway.
Provides trading interface compatible with TradingExecutor.
"""
import logging
import socket
import os

logger = logging.getLogger(__name__)


class IBKRClient:
    """Interactive Brokers Trading Client via ibind

    Connects to ibeam container's REST API for trading and account management.
    Interface compatible with TradingExecutor.
    """

    def __init__(self, host='127.0.0.1', port=7497, client_id=1):
        """
        Initialize IBKR client via ibind

        Args:
            host: ibeam/Gateway host (127.0.0.1 for local, VPS IP for remote)
            port: ibeam/Gateway port (7497 for paper, custom per container)
            client_id: Client ID for orders (default: 1)
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.base_url = f'https://{host}:{port}'
        self.client = None
        self.account_id = None

        # Suppress SSL warnings for self-signed certificates
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _init_client(self):
        """Initialize ibind REST client (lazy loading)"""
        if self.client is None:
            try:
                from ibind import IbkrClient
                # IbkrClient connects to localhost:5000 by default (ibeam port)
                # For custom ports, set IBIND_REST_URL environment variable
                self.client = IbkrClient(host=self.host, port=self.port, cacert=False)
                logger.info(f"✅ ibind client initialized for {self.base_url}")
            except ImportError:
                logger.error("❌ ibind not installed. Install with: pip install ibind==0.1.22")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize ibind client: {e}")
                raise

    def test_connection(self):
        """Test IBKR Gateway connectivity and authentication"""
        try:
            self._init_client()
            logger.info(f"Testing IBKR Gateway connection @ {self.base_url}...")

            # Get accounts to verify authentication
            accounts = self.client.portfolio_accounts()
            if not accounts or not accounts.data:
                return {
                    'connected': False,
                    'error': 'Gateway responding but no accounts found. Check authentication.'
                }

            self.account_id = accounts.data[0]['accountId'] if accounts.data else None
            logger.info(f"✅ Connected to account: {self.account_id}")

            # Get account summary
            summary = self.client.account_summary(account_id=self.account_id)
            balance = 0
            buying_power = 0

            if summary and summary.data:
                for item in summary.data:
                    if item.get('key') == 'TotalCashBalance':
                        balance = float(item.get('value', 0))
                    elif item.get('key') == 'BuyingPower':
                        buying_power = float(item.get('value', 0))

            result = {
                'connected': True,
                'account_id': self.account_id,
                'balance': balance,
                'buying_power': buying_power,
                'open_positions': len(self._get_positions()) if self.account_id else 0
            }

            logger.info(f"✅ IBKR Connection Test Successful: {result}")
            return result

        except Exception as e:
            logger.error(f"Connection test failed: {e}", exc_info=True)
            return {
                'connected': False,
                'error': str(e)
            }

    def get_account_info(self) -> dict:
        """Get account balance and buying power"""
        try:
            self._init_client()
            if not self.account_id:
                # Get first available account
                accounts = self.client.portfolio_accounts()
                if accounts and accounts.data:
                    self.account_id = accounts.data[0]['accountId']

            summary = self.client.account_summary(account_id=self.account_id)

            result = {'balances': {}}
            if summary and summary.data:
                for item in summary.data:
                    key = item.get('key', '')
                    value = item.get('value', 0)
                    if key == 'TotalCashBalance':
                        result['balances']['USD'] = float(value)
                    elif key == 'BuyingPower':
                        result['buying_power'] = float(value)

            logger.debug(f"Account info: {result}")
            return result
        except Exception as e:
            logger.error(f"Error fetching account info: {e}")
            return {'balances': {'USD': 0}}

    def get_ticker_price(self, symbol: str) -> float:
        """Get current market price for symbol"""
        try:
            self._init_client()
            # Format symbol for IBKR (e.g., AAPL for stocks, BTC/USD for crypto)
            formatted_symbol = self._format_symbol(symbol)

            # Get market data snapshot
            snapshot = self.client.live_marketdata_snapshot_by_symbol(symbol=formatted_symbol)

            if snapshot and snapshot.data:
                data = snapshot.data[0] if isinstance(snapshot.data, list) else snapshot.data
                # Try different price fields
                price = data.get('last') or data.get('bid') or data.get('ask')
                if price:
                    logger.debug(f"Current price for {symbol}: ${price}")
                    return float(price)

            logger.warning(f"No price data available for {symbol}")
            raise ValueError(f"Cannot fetch price for {symbol}")

        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            raise ValueError(f"Failed to get price for {symbol}: {e}")

    def _format_symbol(self, symbol: str) -> str:
        """Format symbol for IBKR API"""
        s = str(symbol).strip().upper()
        # IBKR format: AAPL, BTC/USD, etc.
        if s.endswith('USD'):
            if s.endswith('USDT'):
                # BTCUSDT -> BTC/USD
                return s[:-4] + '/USD'
            elif not '/' in s:
                # Handle AAPL, etc.
                return s
        return s

    def _get_positions(self) -> list:
        """Get open positions for account"""
        try:
            if not self.account_id:
                return []

            positions = self.client.positions(account_id=self.account_id)
            return positions.data if positions and positions.data else []
        except Exception as e:
            logger.warning(f"Error fetching positions: {e}")
            return []

    def place_market_buy(self, symbol: str, notional: float, price: float = None) -> dict:
        """
        Place a market buy order

        Args:
            symbol: Trading symbol (e.g., AAPL, BTCUSD)
            notional: Dollar amount to spend
            price: Current price (optional, for logging)

        Returns:
            Order response with 'id' field
        """
        try:
            self._init_client()
            if not self.account_id:
                accounts = self.client.portfolio_accounts()
                if accounts and accounts.data:
                    self.account_id = accounts.data[0]['accountId']

            formatted_symbol = self._format_symbol(symbol)
            current_price = price or self.get_ticker_price(symbol)
            quantity = round(notional / current_price, 2)

            logger.info(f"Placing IBKR market buy: {symbol} (${notional:.2f}, {quantity} units @ ${current_price})")

            # Place order via ibind
            order_response = self.client.place_order(
                account_id=self.account_id,
                symbol=formatted_symbol,
                quantity=quantity,
                order_type='MKT',
                side='BUY'
            )

            # Extract order ID (different response formats)
            if order_response and order_response.data:
                order_id = order_response.data.get('id') or order_response.data.get('orderId')
                result = {
                    'id': str(order_id),
                    'symbol': symbol,
                    'side': 'BUY',
                    'quantity': quantity,
                    'status': 'submitted'
                }
                logger.info(f"✅ Order placed: {result}")
                return result

            logger.error(f"No order ID in response: {order_response}")
            return {'error': 'Order placed but no ID in response'}

        except Exception as e:
            logger.error(f"Error placing market buy for {symbol}: {e}")
            return {'error': str(e)}

    def place_market_sell(self, symbol: str, quantity: float) -> dict:
        """
        Place a market sell order

        Args:
            symbol: Trading symbol
            quantity: Number of units to sell

        Returns:
            Order response with 'id' field
        """
        try:
            self._init_client()
            if not self.account_id:
                accounts = self.client.portfolio_accounts()
                if accounts and accounts.data:
                    self.account_id = accounts.data[0]['accountId']

            formatted_symbol = self._format_symbol(symbol)
            logger.info(f"Placing IBKR market sell: {symbol} ({quantity} units)")

            order_response = self.client.place_order(
                account_id=self.account_id,
                symbol=formatted_symbol,
                quantity=quantity,
                order_type='MKT',
                side='SELL'
            )

            if order_response and order_response.data:
                order_id = order_response.data.get('id') or order_response.data.get('orderId')
                result = {
                    'id': str(order_id),
                    'symbol': symbol,
                    'side': 'SELL',
                    'quantity': quantity,
                    'status': 'submitted'
                }
                logger.info(f"✅ Order placed: {result}")
                return result

            return {'error': 'Order placed but no ID in response'}

        except Exception as e:
            logger.error(f"Error placing market sell for {symbol}: {e}")
            return {'error': str(e)}

    def get_order_status(self, symbol: str, order_id: str) -> dict:
        """
        Get order status

        Args:
            symbol: Trading symbol (for compatibility, not used by IBKR API)
            order_id: Order ID

        Returns:
            Order status dictionary
        """
        try:
            self._init_client()
            if not self.account_id:
                accounts = self.client.portfolio_accounts()
                if accounts and accounts.data:
                    self.account_id = accounts.data[0]['accountId']

            # Get order details
            response = self.client.order_status(account_id=self.account_id, order_id=order_id)

            if response and response.data:
                order_data = response.data
                # Map IBKR fields to executor's expected format
                return {
                    'id': order_data.get('id', order_id),
                    'status': order_data.get('status', 'UNKNOWN').upper(),
                    'filled_qty': float(order_data.get('filledQuantity', 0)),
                    'qty': float(order_data.get('quantity', 0)),
                    'filled_avg_price': float(order_data.get('avgFillPrice', 0)),
                    'notional': float(order_data.get('totalValue', 0))
                }

            return {'id': order_id, 'status': 'UNKNOWN'}

        except Exception as e:
            logger.warning(f"Error fetching order status for {order_id}: {e}")
            return {'id': order_id, 'status': 'UNKNOWN', 'error': str(e)}

    def get_open_orders(self, symbol: str = None) -> list:
        """
        Get list of open orders (optionally filtered by symbol)

        Args:
            symbol: Trading symbol (optional filter)

        Returns:
            List of open orders
        """
        try:
            self._init_client()
            if not self.account_id:
                accounts = self.client.portfolio_accounts()
                if accounts and accounts.data:
                    self.account_id = accounts.data[0]['accountId']

            orders = self.client.live_orders(account_id=self.account_id)

            if not orders or not orders.data:
                return []

            result = []
            formatted_symbol = self._format_symbol(symbol) if symbol else None

            for order in orders.data:
                # Filter by symbol if provided
                if formatted_symbol and order.get('symbol') != formatted_symbol:
                    continue

                status = order.get('status', '').upper()
                # Only include open/pending orders
                if status not in ['SUBMITTED', 'PENDING_SUBMIT', 'OPEN', 'PENDING_CANCEL']:
                    continue

                result.append(order)

            logger.debug(f"Found {len(result)} open orders" + (f" for {symbol}" if symbol else ""))
            return result

        except Exception as e:
            logger.warning(f"Error fetching open orders: {e}")
            return []


# Test script
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test with paper trading (port 7497)
    client = IBKRClient(host='127.0.0.1', port=7497)
    result = client.test_connection()

    print(f"\n{'='*60}")
    print(f"Test Result: {'✅ PASSED' if result.get('connected') else '❌ FAILED'}")
    if result.get('connected'):
        print(f"Account: {result.get('account_id')}")
        print(f"Balance: ${result.get('balance', 0):,.2f}")
        print(f"Buying Power: ${result.get('buying_power', 0):,.2f}")
        print(f"Open Positions: {result.get('open_positions', 0)}")
    else:
        print(f"Error: {result.get('error')}")
    print(f"{'='*60}")
