"""
Interactive Brokers Client via ibind (ibeam REST API client)
Connects to ibeam Docker container running IBKR Gateway.
Each account uses a separate ibeam container on a different port.
"""
import logging

logger = logging.getLogger(__name__)


class IBKRClient:
    """Interactive Brokers Client via ibind

    Connects to ibeam container's REST API for trading and account management.
    Each account uses a separate ibeam container on a different port.
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
        self.base_url = f'http://{host}:{port}'
        self.client = None

    def _init_client(self):
        """Initialize ibind REST client"""
        if self.client is None:
            try:
                from ibind import IbkrClient
                self.client = IbkrClient(base_url=self.base_url)
                logger.info(f"✅ ibind client initialized for {self.base_url}")
            except Exception as e:
                logger.error(f"Failed to initialize ibind client: {e}")
                raise

    def test_connection(self):
        """Test IBKR Gateway connectivity via ibind"""
        try:
            self._init_client()
            logger.info(f"Testing IBKR Gateway connection @ {self.base_url}...")

            # Try to get auth status
            status = self.client.get('/iserver/auth/status')

            result = {
                'connected': True,
                'account_id': status.get('userId', 'Unknown'),
                'authenticated': status.get('authenticated', False),
                'message': f'Gateway responding. Auth status: {status}'
            }

            logger.info(f"✅ IBKR Gateway Connection Test Successful: {result}")
            return result

        except Exception as e:
            logger.error(f"Connection test failed: {e}", exc_info=True)
            return {
                'connected': False,
                'error': str(e)
            }

    def get_accounts(self):
        """Get list of IBKR accounts"""
        try:
            self._init_client()
            accounts = self.client.get('/portfolio/accounts')
            logger.info(f"Fetched {len(accounts)} accounts")
            return accounts
        except Exception as e:
            logger.error(f"Error fetching accounts: {e}")
            return []

    def get_account_summary(self, account_id):
        """Get account balance and buying power"""
        try:
            self._init_client()
            summary = self.client.get(f'/portfolio/{account_id}/summary')
            logger.info(f"Account summary for {account_id}: {summary}")
            return summary
        except Exception as e:
            logger.error(f"Error fetching account summary: {e}")
            return None

    def get_positions(self, account_id):
        """Get open positions for account"""
        try:
            self._init_client()
            positions = self.client.get(f'/portfolio/{account_id}/positions')
            logger.info(f"Fetched {len(positions)} positions for {account_id}")
            return positions
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

    def place_order(self, account_id, symbol, quantity, action, order_type='MKT', price=None):
        """Place an order (market or limit)"""
        try:
            self._init_client()

            order_data = {
                'orders': [{
                    'acctId': account_id,
                    'conid': self._get_contract_id(symbol),
                    'orderType': order_type,
                    'qty': quantity,
                    'side': action.upper(),  # BUY or SELL
                    'clientId': self.client_id,
                }]
            }

            if order_type == 'LMT' and price:
                order_data['orders'][0]['price'] = price

            result = self.client.post('/iserver/account/orders', json=order_data)
            logger.info(f"Order placed: {result}")
            return result

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    def cancel_order(self, account_id, order_id):
        """Cancel an open order"""
        try:
            self._init_client()
            result = self.client.delete(f'/iserver/account/{account_id}/orders/{order_id}')
            logger.info(f"Order {order_id} cancelled")
            return result
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return None

    def _get_contract_id(self, symbol):
        """Lookup contract ID for symbol (stub - implement as needed)"""
        # TODO: Use ibind contract search API
        # For now, return a placeholder
        return 0


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
