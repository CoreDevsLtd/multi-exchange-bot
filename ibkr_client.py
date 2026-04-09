"""
Interactive Brokers Client using ibind (ibeam connector)
Connects to ibeam Docker container running IBKR Gateway
Synchronous API suitable for Flask integration
"""
import logging
from ibind.server import IBServer

logger = logging.getLogger(__name__)


class IBKRClient:
    """Interactive Brokers Client via ibeam + ibind

    Connects to an ibeam container running IBKR Gateway.
    Each account uses a separate ibeam container on a different port.
    """

    def __init__(self, host='127.0.0.1', port=7497):
        """
        Initialize IBKR client

        Args:
            host: ibeam/Gateway host (127.0.0.1 for local, VPS IP for remote)
            port: ibeam/Gateway port (7497 for paper, 7496 for live, or custom per container)
        """
        self.host = host
        self.port = port
        self.ib = None
        self.account = None

    def connect(self):
        """Connect to ibeam/Gateway via ibind"""
        try:
            self.ib = IBServer(host=self.host, port=self.port)
            # Test connection by requesting accounts
            accounts = self.ib.getPortfolioAccounts()
            if not accounts:
                logger.error(f"❌ No accounts returned from {self.host}:{self.port}")
                return False

            self.account = accounts[0] if accounts else None
            logger.info(f"✅ Connected to ibeam @ {self.host}:{self.port}")
            if self.account:
                logger.info(f"   Account: {self.account}")
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from ibeam"""
        try:
            if self.ib:
                self.ib = None
            logger.info("✅ Disconnected from ibeam")
        except Exception as e:
            logger.error(f"Disconnect error: {e}")

    def get_account_summary(self):
        """Get account summary (balance, buying power, etc.)"""
        try:
            if not self.account or not self.ib:
                logger.warning("No account or connection")
                return None

            # Get account value
            account_value = self.ib.getAccountValue(self.account)

            return {
                'account_id': self.account,
                'balance': float(account_value.get('TotalCashValue', 0)),
                'buying_power': float(account_value.get('BuyingPower', 0)),
                'portfolio_value': float(account_value.get('NetLiquidation', 0)),
                'currency': 'USD'
            }
        except Exception as e:
            logger.error(f"Error getting account summary: {e}")
            return None

    def get_positions(self):
        """Get all open positions"""
        try:
            if not self.account or not self.ib:
                return []

            portfolio = self.ib.getPortfolio(self.account)
            positions = []
            for pos in portfolio:
                positions.append({
                    'symbol': pos.get('symbol', ''),
                    'quantity': float(pos.get('position', 0)),
                    'market_price': float(pos.get('marketPrice', 0)),
                    'market_value': float(pos.get('marketValue', 0)),
                    'avg_cost': float(pos.get('averageCost', 0))
                })
            return positions
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def get_market_data(self, symbol):
        """Get real-time market data for a symbol"""
        try:
            if not self.ib:
                return None

            # ibind can fetch market data
            market_data = self.ib.getMarketData(symbol)

            return {
                'symbol': symbol,
                'last_price': float(market_data.get('last', 0)),
                'bid': float(market_data.get('bid', 0)),
                'ask': float(market_data.get('ask', 0)),
                'bid_size': int(market_data.get('bidSize', 0)),
                'ask_size': int(market_data.get('askSize', 0)),
            }
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None

    def place_market_order(self, symbol, qty, action):
        """
        Place a market order (BUY or SELL)

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            qty: Quantity to trade
            action: 'BUY' or 'SELL'
        """
        try:
            if not self.account or not self.ib:
                logger.error("No account or connection")
                return None

            order_id = self.ib.placeOrder(
                self.account,
                symbol,
                action,
                qty,
                'MKT'  # Market order
            )

            logger.info(f"Market order placed: {action} {qty} {symbol} (Order ID: {order_id})")
            return {
                'order_id': order_id,
                'symbol': symbol,
                'action': action,
                'quantity': qty,
                'status': 'submitted'
            }
        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return None

    def place_limit_order(self, symbol, qty, action, price):
        """
        Place a limit order

        Args:
            symbol: Stock symbol
            qty: Quantity to trade
            action: 'BUY' or 'SELL'
            price: Limit price
        """
        try:
            if not self.account or not self.ib:
                logger.error("No account or connection")
                return None

            order_id = self.ib.placeOrder(
                self.account,
                symbol,
                action,
                qty,
                'LMT',  # Limit order
                limitPrice=price
            )

            logger.info(f"Limit order placed: {action} {qty} {symbol} @ ${price} (Order ID: {order_id})")
            return {
                'order_id': order_id,
                'symbol': symbol,
                'action': action,
                'quantity': qty,
                'limit_price': price,
                'status': 'submitted'
            }
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return None

    def test_connection(self):
        """Test IBKR connection and return status (synchronous)"""
        try:
            if not self.connect():
                return {
                    'connected': False,
                    'error': f'Failed to connect to ibeam @ {self.host}:{self.port}'
                }

            summary = self.get_account_summary()
            positions = self.get_positions()

            logger.info("✅ IBKR Connection Test Successful")
            logger.info(f"   Account: {self.account}")
            if summary:
                logger.info(f"   Balance: ${summary['balance']:,.2f}")
                logger.info(f"   Buying Power: ${summary['buying_power']:,.2f}")
            logger.info(f"   Open Positions: {len(positions)}")

            result = {
                'connected': True,
                'account_id': self.account,
                'balance': summary['balance'] if summary else 0,
                'buying_power': summary['buying_power'] if summary else 0,
                'open_positions': len(positions)
            }

            self.disconnect()
            return result
        except Exception as e:
            logger.error(f"Connection test failed: {e}", exc_info=True)
            return {
                'connected': False,
                'error': str(e)
            }


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
