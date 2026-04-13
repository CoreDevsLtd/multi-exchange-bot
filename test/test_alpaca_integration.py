"""
Alpaca Integration Test Suite

Tests AlpacaClient using mocked HTTP requests (no credentials required).
Set ALPACA_API_KEY and ALPACA_API_SECRET environment variables to also run live
tests against the Alpaca paper API.

Usage:
    # Mocked tests only (no credentials needed):
    python3 test/test_alpaca_integration.py

    # Include live paper API tests:
    ALPACA_API_KEY=PKxxxxxxx ALPACA_API_SECRET=xxxxxxx python3 test/test_alpaca_integration.py
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch, call

# Ensure project root is on path so alpaca_client can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from alpaca_client import AlpacaClient

PAPER_BASE = 'https://paper-api.alpaca.markets'
LIVE_BASE = 'https://api.alpaca.markets'


def make_mock_response(json_data, status_code=200):
    """Build a mock requests.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    if status_code >= 400:
        from requests.exceptions import HTTPError
        http_err = HTTPError(response=resp)
        resp.raise_for_status.side_effect = http_err
        resp.text = json.dumps(json_data)
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Mocked test class — no real credentials needed
# ---------------------------------------------------------------------------

class TestAlpacaClientMocked(unittest.TestCase):
    """All tests run with a mocked requests.Session — no Alpaca credentials required."""

    def setUp(self):
        """Create a client with a fully mocked HTTP session."""
        self.session_patcher = patch('alpaca_client.requests.Session')
        MockSessionClass = self.session_patcher.start()
        self.mock_session = MagicMock()
        MockSessionClass.return_value = self.mock_session
        # headers.update is called in __init__; allow it silently
        self.mock_session.headers = MagicMock()
        self.client = AlpacaClient('TESTKEY123456', 'TESTSECRET123456', PAPER_BASE)

    def tearDown(self):
        self.session_patcher.stop()

    # ------------------------------------------------------------------
    # 1. Initialisation
    # ------------------------------------------------------------------

    def test_init_paper_and_live_urls(self):
        """Client stores base_url correctly for paper and live environments."""
        self.assertEqual(self.client.base_url, PAPER_BASE)
        self.assertEqual(self.client.api_key, 'TESTKEY123456')
        self.assertEqual(self.client.api_secret, 'TESTSECRET123456')

        # Live client
        with patch('alpaca_client.requests.Session') as MockLive:
            mock_live_session = MagicMock()
            mock_live_session.headers = MagicMock()
            MockLive.return_value = mock_live_session
            live_client = AlpacaClient('KEY', 'SEC', LIVE_BASE)
        self.assertEqual(live_client.base_url, LIVE_BASE)
        self.assertNotEqual(live_client.base_url, self.client.base_url)

    # ------------------------------------------------------------------
    # 2. validate_connection
    # ------------------------------------------------------------------

    def test_validate_connection(self):
        """validate_connection returns connected=True and can_trade=True for a healthy account."""
        account_data = {
            'id': 'acct-123',
            'status': 'ACTIVE',
            'trading_blocked': False,
            'account_blocked': False,
            'pattern_day_trader': False,
            'cash': '50000.00',
            'buying_power': '100000.00',
        }
        self.mock_session.get.return_value = make_mock_response(account_data)

        result = self.client.validate_connection()

        self.assertTrue(result['connected'])
        self.assertTrue(result['can_trade'])
        self.assertFalse(result['account_status']['trading_blocked'])

    def test_validate_connection_blocked(self):
        """validate_connection returns can_trade=False when trading is blocked."""
        account_data = {
            'status': 'ACTIVE',
            'trading_blocked': True,
            'account_blocked': False,
            'pattern_day_trader': False,
        }
        self.mock_session.get.return_value = make_mock_response(account_data)

        result = self.client.validate_connection()

        self.assertTrue(result['connected'])
        self.assertFalse(result['can_trade'])

    # ------------------------------------------------------------------
    # 3. get_account_info and get_balance
    # ------------------------------------------------------------------

    def test_get_account_info_and_balance(self):
        """get_account_info returns raw account dict; get_balance extracts USD cash."""
        account_data = {
            'cash': '50000.00',
            'buying_power': '100000.00',
            'equity': '55000.00',
            'status': 'ACTIVE',
        }
        self.mock_session.get.return_value = make_mock_response(account_data)

        info = self.client.get_account_info()
        self.assertEqual(info['cash'], '50000.00')

        # get_balance calls get_account_info again
        self.mock_session.get.return_value = make_mock_response(account_data)
        balance = self.client.get_balance('USD')
        self.assertEqual(balance['free'], 50000.0)
        self.assertEqual(balance['asset'], 'USD')

    # ------------------------------------------------------------------
    # 4. get_ticker_price — stock
    # ------------------------------------------------------------------

    def test_get_ticker_price_stock(self):
        """get_ticker_price returns close price for a US equity from bars/latest."""
        bars_response = {'bar': {'o': 173.0, 'h': 175.5, 'l': 172.0, 'c': 174.25, 'v': 12000}}
        self.mock_session.get.return_value = make_mock_response(bars_response)

        price = self.client.get_ticker_price('AAPL')

        self.assertEqual(price, 174.25)
        # Verify the correct data API base URL was used
        called_url = self.mock_session.get.call_args[0][0]
        self.assertIn('data.alpaca.markets', called_url)
        self.assertIn('AAPL', called_url)

    # ------------------------------------------------------------------
    # 5. get_ticker_price — crypto
    # ------------------------------------------------------------------

    def test_get_ticker_price_crypto(self):
        """get_ticker_price returns close price for a crypto pair from bars endpoint."""
        crypto_response = {
            'bars': {
                'BTC/USD': [{'o': 68000.0, 'h': 69000.0, 'l': 67500.0, 'c': 68500.0, 'v': 5.0}]
            }
        }
        self.mock_session.get.return_value = make_mock_response(crypto_response)

        price = self.client.get_ticker_price('BTC/USD')

        self.assertEqual(price, 68500.0)

    def test_get_ticker_price_crypto_btcusd_format(self):
        """get_ticker_price handles BTCUSD input and converts to BTC/USD format."""
        crypto_response = {
            'bars': {
                'BTC/USD': [{'c': 68500.0}]
            }
        }
        self.mock_session.get.return_value = make_mock_response(crypto_response)

        price = self.client.get_ticker_price('BTCUSD')
        self.assertEqual(price, 68500.0)

    # ------------------------------------------------------------------
    # 6. place_market_buy
    # ------------------------------------------------------------------

    def test_place_market_buy_notional(self):
        """place_market_buy sends correct notional and side in POST body."""
        order_response = {
            'id': 'order-001',
            'status': 'accepted',
            'symbol': 'AAPL',
            'side': 'buy',
            'type': 'market',
            'notional': '1000.00',
        }
        self.mock_session.post.return_value = make_mock_response(order_response)

        result = self.client.place_market_buy('AAPL', 1000.00)

        self.assertEqual(result['id'], 'order-001')
        post_body = self.mock_session.post.call_args[1]['json']
        self.assertEqual(post_body['notional'], 1000.0)
        self.assertEqual(post_body['side'], 'buy')
        self.assertEqual(post_body['type'], 'market')

    def test_place_market_buy_crypto_notional(self):
        """place_market_buy works for crypto symbols (BTC/USD format)."""
        order_response = {'id': 'order-crypto-001', 'status': 'accepted', 'symbol': 'BTC/USD'}
        self.mock_session.post.return_value = make_mock_response(order_response)

        result = self.client.place_market_buy('BTCUSD', 500.0)

        self.assertEqual(result['id'], 'order-crypto-001')
        post_body = self.mock_session.post.call_args[1]['json']
        self.assertEqual(post_body['symbol'], 'BTC/USD')
        # Crypto orders use 'gtc', not 'day'
        self.assertEqual(post_body['time_in_force'], 'gtc')

    # ------------------------------------------------------------------
    # 7. place_market_sell
    # ------------------------------------------------------------------

    def test_place_market_sell_quantity(self):
        """place_market_sell sends correct qty and side in POST body."""
        order_response = {
            'id': 'order-002',
            'status': 'accepted',
            'symbol': 'AAPL',
            'side': 'sell',
            'type': 'market',
            'qty': '5.0',
        }
        self.mock_session.post.return_value = make_mock_response(order_response)

        result = self.client.place_market_sell('AAPL', 5.0)

        self.assertEqual(result['id'], 'order-002')
        post_body = self.mock_session.post.call_args[1]['json']
        self.assertEqual(post_body['qty'], '5.0')
        self.assertEqual(post_body['side'], 'sell')

    # ------------------------------------------------------------------
    # 8. place_order with price alias (Bug 1 regression test)
    # ------------------------------------------------------------------

    def test_place_order_price_alias(self):
        """
        REGRESSION: place_order must accept 'price=' kwarg as alias for limit_price.

        tp_sl_manager.py calls:
            client.place_order(symbol=..., side=..., order_type='LIMIT', quantity=..., price=tp_price)

        Before the fix this raised TypeError because AlpacaClient had no 'price' param.
        After the fix, 'price' maps to 'limit_price' in the POST body.
        """
        order_response = {
            'id': 'tp-order-001',
            'status': 'accepted',
            'symbol': 'AAPL',
            'side': 'sell',
            'type': 'limit',
            'limit_price': '180.0',
            'qty': '10.0',
        }
        self.mock_session.post.return_value = make_mock_response(order_response)

        # Call exactly as tp_sl_manager does — using price= not limit_price=
        result = self.client.place_order(
            symbol='AAPL',
            side='SELL',
            order_type='LIMIT',
            quantity=10.0,
            price=180.0
        )

        self.assertEqual(result['id'], 'tp-order-001')
        post_body = self.mock_session.post.call_args[1]['json']
        # The body must contain limit_price, NOT be missing it
        self.assertEqual(post_body['limit_price'], '180.0')
        self.assertEqual(post_body['qty'], '10.0')
        self.assertEqual(post_body['side'], 'sell')
        self.assertEqual(post_body['type'], 'limit')

    def test_place_order_limit_price_still_works(self):
        """limit_price= kwarg continues to work after adding price= alias."""
        order_response = {'id': 'tp-order-002', 'status': 'accepted'}
        self.mock_session.post.return_value = make_mock_response(order_response)

        self.client.place_order(
            symbol='AAPL',
            side='BUY',
            order_type='LIMIT',
            quantity=5.0,
            limit_price=170.0
        )

        post_body = self.mock_session.post.call_args[1]['json']
        self.assertEqual(post_body['limit_price'], '170.0')

    # ------------------------------------------------------------------
    # 9. get_order_status
    # ------------------------------------------------------------------

    def test_get_order_status(self):
        """get_order_status fetches order by ID and returns fill data."""
        order_data = {
            'id': 'order-001',
            'status': 'filled',
            'filled_qty': '5.0',
            'filled_avg_price': '175.00',
            'symbol': 'AAPL',
            'side': 'buy',
        }
        self.mock_session.get.return_value = make_mock_response(order_data)

        result = self.client.get_order_status('AAPL', 'order-001')

        self.assertEqual(result['status'], 'filled')
        self.assertEqual(result['filled_qty'], '5.0')
        self.assertEqual(result['filled_avg_price'], '175.00')

        called_url = self.mock_session.get.call_args[0][0]
        self.assertTrue(called_url.endswith('/v2/orders/order-001'))

    # ------------------------------------------------------------------
    # 10. cancel_order compatibility (Bug 2 regression test)
    # ------------------------------------------------------------------

    def test_cancel_order_compat(self):
        """
        REGRESSION: cancel_order must accept both (order_id,) and (symbol, order_id).

        MEXCClient and BybitClient both use cancel_order(symbol, order_id).
        Before the fix, AlpacaClient.cancel_order only accepted (order_id,)
        and would silently DELETE /v2/orders/<symbol> instead of the real order.
        After the fix, the two-arg call correctly targets the order ID.
        """
        self.mock_session.delete.return_value = make_mock_response({}, status_code=204)

        # Two-arg call: cancel_order(symbol, order_id) — as called by uniform exchange interface
        self.client.cancel_order('AAPL', 'order-001')
        called_url = self.mock_session.delete.call_args[0][0]
        # Must target the ORDER ID, not the symbol
        self.assertTrue(
            called_url.endswith('/v2/orders/order-001'),
            f"Expected URL to end with /v2/orders/order-001, got: {called_url}"
        )
        self.assertNotIn('AAPL', called_url.split('/v2/orders/')[-1],
                         "Symbol must NOT appear as the order ID in the URL")

        # Single-arg call: cancel_order(order_id) — legacy form
        self.client.cancel_order('order-002')
        called_url_2 = self.mock_session.delete.call_args[0][0]
        self.assertTrue(
            called_url_2.endswith('/v2/orders/order-002'),
            f"Expected URL to end with /v2/orders/order-002, got: {called_url_2}"
        )

    # ------------------------------------------------------------------
    # 11. get_market_clock / is_market_open
    # ------------------------------------------------------------------

    def test_get_market_clock_open(self):
        """get_market_clock returns clock data; is_market_open returns True when open."""
        clock_data = {
            'timestamp': '2026-04-13T14:30:00-04:00',
            'is_open': True,
            'next_open': '2026-04-14T09:30:00-04:00',
            'next_close': '2026-04-13T16:00:00-04:00',
        }
        self.mock_session.get.return_value = make_mock_response(clock_data)

        clock = self.client.get_market_clock()
        self.assertTrue(clock['is_open'])

        self.mock_session.get.return_value = make_mock_response(clock_data)
        self.assertTrue(self.client.is_market_open())

    def test_is_market_open_closed(self):
        """is_market_open returns False when market is closed."""
        clock_data = {'is_open': False, 'next_open': '2026-04-14T09:30:00-04:00'}
        self.mock_session.get.return_value = make_mock_response(clock_data)

        self.assertFalse(self.client.is_market_open())

    # ------------------------------------------------------------------
    # 12. close_position_by_symbol
    # ------------------------------------------------------------------

    def test_close_position_by_symbol_full(self):
        """close_position_by_symbol issues DELETE /v2/positions/<symbol> with no params."""
        order_response = {'id': 'close-001', 'status': 'accepted', 'symbol': 'AAPL', 'side': 'sell'}
        self.mock_session.delete.return_value = make_mock_response(order_response)

        result = self.client.close_position_by_symbol('AAPL')

        self.assertEqual(result['id'], 'close-001')
        called_url = self.mock_session.delete.call_args[0][0]
        self.assertTrue(called_url.endswith('/v2/positions/AAPL'), f"Unexpected URL: {called_url}")

    def test_close_position_by_symbol_partial_qty(self):
        """close_position_by_symbol passes qty param for partial close."""
        order_response = {'id': 'close-002', 'status': 'accepted'}
        self.mock_session.delete.return_value = make_mock_response(order_response)

        self.client.close_position_by_symbol('AAPL', qty=2.5)

        call_kwargs = self.mock_session.delete.call_args
        params = call_kwargs[1].get('params') or {}
        self.assertEqual(params.get('qty'), '2.5')

    def test_close_position_by_symbol_crypto(self):
        """close_position_by_symbol formats crypto symbol correctly."""
        order_response = {'id': 'close-crypto', 'status': 'accepted'}
        self.mock_session.delete.return_value = make_mock_response(order_response)

        self.client.close_position_by_symbol('BTCUSD')

        called_url = self.mock_session.delete.call_args[0][0]
        self.assertIn('BTC/USD', called_url, f"Crypto symbol not formatted: {called_url}")

    # ------------------------------------------------------------------
    # Full buy → status → sell flow
    # ------------------------------------------------------------------

    def test_buy_sell_flow(self):
        """Integration flow: place buy → check fill → place sell."""
        buy_response = {'id': 'buy-001', 'status': 'accepted', 'symbol': 'AAPL', 'side': 'buy'}
        fill_response = {
            'id': 'buy-001',
            'status': 'filled',
            'filled_qty': '5.714',
            'filled_avg_price': '175.00',
            'symbol': 'AAPL',
        }
        sell_response = {'id': 'sell-001', 'status': 'accepted', 'symbol': 'AAPL', 'side': 'sell'}

        # Sequence: POST(buy), GET(status), POST(sell)
        self.mock_session.post.side_effect = [
            make_mock_response(buy_response),
            make_mock_response(sell_response),
        ]
        self.mock_session.get.return_value = make_mock_response(fill_response)

        # Buy
        buy = self.client.place_market_buy('AAPL', 1000.0)
        self.assertEqual(buy['id'], 'buy-001')

        # Check fill
        status = self.client.get_order_status('AAPL', buy['id'])
        self.assertEqual(status['status'], 'filled')
        filled_qty = float(status['filled_qty'])
        self.assertGreater(filled_qty, 0)

        # Sell using filled quantity
        sell = self.client.place_market_sell('AAPL', filled_qty)
        self.assertEqual(sell['id'], 'sell-001')

        # Verify POST was called twice
        self.assertEqual(self.mock_session.post.call_count, 2)


# ---------------------------------------------------------------------------
# Live test class — skipped unless ALPACA_API_KEY/ALPACA_API_SECRET are set
# ---------------------------------------------------------------------------

class TestAlpacaClientLive(unittest.TestCase):
    """
    Optional live tests against Alpaca paper API.
    Skipped automatically when credentials are not set.
    """

    @classmethod
    def setUpClass(cls):
        cls.api_key = os.environ.get('ALPACA_API_KEY')
        cls.api_secret = os.environ.get('ALPACA_API_SECRET')
        cls.base_url = os.environ.get('ALPACA_BASE_URL', PAPER_BASE)
        if not cls.api_key or not cls.api_secret:
            raise unittest.SkipTest(
                'Skipping live tests: set ALPACA_API_KEY and ALPACA_API_SECRET to run'
            )
        cls.client = AlpacaClient(cls.api_key, cls.api_secret, cls.base_url)

    def test_live_validate_connection(self):
        """Live: validate_connection returns connected=True for valid paper credentials."""
        result = self.client.validate_connection()
        self.assertTrue(result.get('connected'), f"Connection failed: {result.get('error')}")
        self.assertIn('account_status', result)

    def test_live_get_balance(self):
        """Live: get_balance returns a positive USD cash value on the paper account."""
        balance = self.client.get_balance('USD')
        self.assertEqual(balance['asset'], 'USD')
        self.assertGreaterEqual(balance['free'], 0.0)

    def test_live_ticker_price_stock(self):
        """Live: get_ticker_price returns a positive price for AAPL."""
        try:
            price = self.client.get_ticker_price('AAPL')
            self.assertGreater(price, 0.0, "AAPL price should be positive")
        except ValueError as e:
            # Market may be closed; acceptable outcome for live test
            self.skipTest(f"Market data unavailable (market may be closed): {e}")

    def test_live_ticker_price_crypto(self):
        """Live: get_ticker_price returns a positive price for BTC/USD (24/7)."""
        price = self.client.get_ticker_price('BTC/USD')
        self.assertGreater(price, 0.0, "BTC/USD price should be positive")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main(verbosity=2)
