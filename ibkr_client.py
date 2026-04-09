"""
Interactive Brokers Client using ib-insync (official PyPI package)
Async-ready client for connecting to IBKR TWS/Gateway
"""
import asyncio
import logging
from ib_insync import *

logger = logging.getLogger(__name__)


class IBKRClient:
    def __init__(self, host='127.0.0.1', port=7497, client_id=1):
        """
        Initialize IBKR client

        Args:
            host: Gateway/TWS host (127.0.0.1 for local or VPS IP)
            port: 7497 (paper trading) or 7496 (live trading)
            client_id: Unique client ID for connection
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()
        self.account = None

    async def connect(self):
        """Connect to Interactive Brokers"""
        try:
            await self.ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id
            )

            logger.info(f"✅ Connected to IBKR @ {self.host}:{self.port}")

            # Auto-detect account
            await asyncio.sleep(0.5)
            managed = self.ib.managedAccounts()
            self.account = managed[0] if managed else None

            if self.account:
                logger.info(f"Account auto-detected: {self.account}")

            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from IBKR"""
        try:
            self.ib.disconnect()
            logger.info("✅ Disconnected from IBKR")
        except Exception as e:
            logger.error(f"Disconnect error: {e}")

    async def get_account_summary(self):
        """Get account summary (balance, buying power, etc.)"""
        try:
            if not self.account:
                logger.warning("No account set")
                return None

            summary = self.ib.accountSummary(self.account)
            await asyncio.sleep(0.2)

            return {
                'account_id': self.account,
                'balance': float(summary.TotalCashValue) if summary else 0,
                'buying_power': float(summary.BuyingPower) if summary else 0,
                'portfolio_value': float(summary.NetLiquidation) if summary else 0,
                'currency': 'USD'
            }
        except Exception as e:
            logger.error(f"Error getting account summary: {e}")
            return None

    async def get_positions(self):
        """Get all open positions"""
        try:
            if not self.account:
                return []

            portfolio = self.ib.portfolio(self.account)
            await asyncio.sleep(0.1)

            positions = []
            for pos in portfolio:
                positions.append({
                    'symbol': pos.contract.symbol,
                    'quantity': pos.position,
                    'market_price': float(pos.marketPrice),
                    'market_value': float(pos.marketValue),
                    'avg_cost': float(pos.averageCost) if pos.averageCost else 0
                })
            return positions
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    async def get_market_data(self, symbol):
        """Get real-time market data for a symbol"""
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            ticker = self.ib.ticker(contract)
            await asyncio.sleep(0.2)  # Wait for data to populate

            return {
                'symbol': symbol,
                'last_price': float(ticker.last) if ticker.last else None,
                'bid': float(ticker.bid) if ticker.bid else None,
                'ask': float(ticker.ask) if ticker.ask else None,
                'bid_size': ticker.bidSize,
                'ask_size': ticker.askSize,
                'volume': ticker.volume
            }
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None

    async def place_market_order(self, symbol, qty, action):
        """
        Place a market order (BUY or SELL)

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            qty: Quantity to trade
            action: 'BUY' or 'SELL'
        """
        try:
            if not self.account:
                logger.error("No account set")
                return None

            contract = Stock(symbol, 'SMART', 'USD')
            order = MarketOrder(action, qty)
            trade = self.ib.placeOrder(contract, order)

            logger.info(f"Market order placed: {action} {qty} {symbol}")
            return {
                'order_id': trade.order.orderId,
                'symbol': symbol,
                'action': action,
                'quantity': qty,
                'status': trade.orderStatus.status
            }
        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return None

    async def place_limit_order(self, symbol, qty, action, price):
        """
        Place a limit order

        Args:
            symbol: Stock symbol
            qty: Quantity to trade
            action: 'BUY' or 'SELL'
            price: Limit price
        """
        try:
            if not self.account:
                logger.error("No account set")
                return None

            contract = Stock(symbol, 'SMART', 'USD')
            order = LimitOrder(action, qty, price)
            trade = self.ib.placeOrder(contract, order)

            logger.info(f"Limit order placed: {action} {qty} {symbol} @ ${price}")
            return {
                'order_id': trade.order.orderId,
                'symbol': symbol,
                'action': action,
                'quantity': qty,
                'limit_price': price,
                'status': trade.orderStatus.status
            }
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return None

    async def test_connection(self):
        """Test IBKR connection and return status"""
        try:
            if not await self.connect():
                return False

            await asyncio.sleep(0.5)

            summary = await self.get_account_summary()
            positions = await self.get_positions()

            logger.info("✅ IBKR Connection Test Successful")
            logger.info(f"   Account: {self.account}")
            if summary:
                logger.info(f"   Balance: ${summary['balance']:,.2f}")
                logger.info(f"   Buying Power: ${summary['buying_power']:,.2f}")
            logger.info(f"   Open Positions: {len(positions)}")

            await self.disconnect()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


# Test script
async def main():
    """Test the IBKR client"""
    client = IBKRClient(host='127.0.0.1', port=7497)
    success = await client.test_connection()
    print(f"\n{'='*50}")
    print(f"Test Result: {'✅ PASSED' if success else '❌ FAILED'}")
    print(f"{'='*50}")


if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())
