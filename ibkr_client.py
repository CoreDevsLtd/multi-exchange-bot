"""
Interactive Brokers Client - ibeam Gateway connectivity check
Checks if ibeam container is running and responding on the Gateway port.
"""
import logging
import socket

logger = logging.getLogger(__name__)


class IBKRClient:
    """IBKR Gateway Connection Health Check

    Simple port connectivity check for ibeam container.
    For full trading via ibind or ib-insync, implement additional methods.
    """

    def __init__(self, host='127.0.0.1', port=7497, client_id=1):
        """
        Initialize IBKR Gateway connection checker

        Args:
            host: ibeam/Gateway host (127.0.0.1 for local, VPS IP for remote)
            port: ibeam/Gateway port (7497 for paper, custom per container)
            client_id: Client ID for orders (default: 1)
        """
        self.host = host
        self.port = port
        self.client_id = client_id

    def _check_gateway_port(self, timeout=5):
        """Check if Gateway is listening on the port"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.warning(f"Gateway port check failed: {e}")
            return False

    def test_connection(self):
        """Test ibeam/Gateway connectivity"""
        try:
            logger.info(f"Testing IBKR Gateway connection @ {self.host}:{self.port}...")

            if not self._check_gateway_port():
                return {
                    'connected': False,
                    'error': f'Gateway not responding on {self.host}:{self.port}. Check if ibeam container is running.'
                }

            logger.info(f"✅ Gateway port {self.port} is responding")

            result = {
                'connected': True,
                'account_id': 'pending_auth',
                'gateway_host': self.host,
                'gateway_port': self.port,
                'message': f'Gateway is responding on port {self.port}. Container is running.'
            }

            logger.info("✅ IBKR Gateway Connection Test Successful")
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
