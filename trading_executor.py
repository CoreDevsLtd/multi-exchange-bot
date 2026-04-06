"""
Trading Executor
Handles order execution, position management, and risk management
Supports multiple exchanges (MEXC, Alpaca, etc.)
"""

import logging
import threading
import time
from typing import Dict, Optional, Union
from position_manager import PositionManager
from tp_sl_manager import TPSLManager
from stop_loss_monitor import StopLossMonitor

logger = logging.getLogger(__name__)


class TradingExecutor:
    """Handles trading execution with risk management"""
    
    def __init__(self, exchange_client: Union[object], config: Dict, exchange_name: str = 'mexc'):
        """
        Initialize Trading Executor
        
        Args:
            exchange_client: Exchange API client instance (MEXCClient, AlpacaClient, etc.)
            config: Configuration dictionary
            exchange_name: Name of the exchange ('mexc', 'alpaca', etc.)
        """
        self.client = exchange_client
        self.exchange_name = exchange_name.lower()
        self.config = config
        # Ensure position size is between 5-100%
        position_size = float(config.get('POSITION_SIZE_PERCENT', 20.0))
        self.position_size_percent = max(5.0, min(100.0, position_size))  # Clamp between 5-100%
        self.position_size_fixed = config.get('POSITION_SIZE_FIXED')
        # Handle USE_PERCENTAGE as both boolean and string
        use_percentage_val = config.get('USE_PERCENTAGE', True)
        if isinstance(use_percentage_val, bool):
            self.use_percentage = use_percentage_val
        else:
            self.use_percentage = str(use_percentage_val).lower() == 'true'
        
        # Initialize position and TP/SL managers
        self.position_manager = PositionManager(exchange_client, exchange_name)
        stop_loss_percent = float(config.get('STOP_LOSS_PERCENT', 5.0))
        self.tp_sl_manager = TPSLManager(exchange_client, self.position_manager, stop_loss_percent, exchange_name)
        
        # Initialize stop-loss monitor (exchange-specific)
        self.stop_loss_monitor = StopLossMonitor(exchange_client, self.position_manager, exchange_name)
        self.stop_loss_monitor.start_monitoring()
        
        # Store reference in tp_sl_manager for price updates
        self.tp_sl_manager.stop_loss_monitor = self.stop_loss_monitor
        
        # Start monitoring thread for TP/SL management
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_positions, daemon=True)
        self.monitor_thread.start()
        logger.info(f"Position monitoring thread started for {exchange_name}")
        
        if self.exchange_name == 'mexc':
            logger.warning("⚠️  MEXC Spot API doesn't support stop-loss orders. Using price monitoring system.")
        elif self.exchange_name == 'bybit':
            if hasattr(self.client, 'trading_mode') and self.client.trading_mode == 'futures':
                logger.info("✅ Bybit Futures: Using price monitoring for TP/SL (positions managed via reduce-only orders)")
            else:
                logger.warning("⚠️  Bybit Spot API doesn't support stop-loss orders. Using price monitoring system.")
        elif self.exchange_name == 'alpaca':
            logger.info("✅ Alpaca supports native stop-loss orders via API")
    
    def _symbol_for_exchange(self, symbol: str) -> str:
        """
        Convert symbol to exchange API format.
        TradingView sends BTCUSDT.P (futures); Bybit API expects BTCUSDT.
        """
        s = str(symbol).strip().upper().replace(' ', '')
        if self.exchange_name == 'bybit' and s.endswith('.P'):
            return s[:-2]
        return s
        
    def calculate_position_size(self, symbol: str, signal_price: float) -> float:
        """
        Calculate position size based on configuration
        
        Args:
            symbol: Trading pair symbol
            signal_price: Current price of the asset
            
        Returns:
            Position size in quote currency (e.g., USDT or USD)
        """
        if self.use_percentage:
            # Get account balance
            try:
                if self.exchange_name == 'mexc':
                    account = self.client.get_account_info()
                    balances = account.get('balances', [])
                    
                    # Find USDT balance (or quote currency)
                    quote_currency = symbol.replace('USDT', '').replace('BTC', '').replace('ETH', '')[-4:] or 'USDT'
                    if not quote_currency.endswith('USDT') and 'USDT' in symbol:
                        quote_currency = 'USDT'
                    
                    usdt_balance = 0.0
                    for balance in balances:
                        if balance['asset'] == quote_currency:
                            usdt_balance = float(balance.get('free', 0))
                            break
                    
                    # Calculate position size as percentage
                    position_size = usdt_balance * (self.position_size_percent / 100.0)
                    logger.info(f"Position size: {position_size} {quote_currency} ({self.position_size_percent}% of {usdt_balance})")
                    return position_size
                    
                elif self.exchange_name == 'alpaca':
                    # Alpaca uses USD as quote currency
                    account = self.client.get_account_info()
                    cash = float(account.get('cash', 0))
                    
                    # Calculate position size as percentage
                    position_size = cash * (self.position_size_percent / 100.0)
                    logger.info(f"Position size: {position_size} USD ({self.position_size_percent}% of {cash})")
                    return position_size
                elif self.exchange_name == 'ibkr':
                    # IBKR uses USD as quote currency
                    balances = self.client.get_main_balances()
                    usd_balance = balances.get('USD', {})
                    cash = float(usd_balance.get('free', 0) or usd_balance.get('total', 0))
                    
                    # Calculate position size as percentage
                    position_size = cash * (self.position_size_percent / 100.0)
                    logger.info(f"Position size: {position_size} USD ({self.position_size_percent}% of {cash})")
                    return position_size
                elif self.exchange_name == 'bybit':
                    balances = self.client.get_main_balances()
                    usdt_balance = balances.get('USDT', {})
                    cash = float(usdt_balance.get('free', 0) or usdt_balance.get('total', 0))
                    margin = cash * (self.position_size_percent / 100.0)
                    if hasattr(self.client, 'trading_mode') and self.client.trading_mode == 'futures':
                        leverage = getattr(self.client, 'leverage', 1)
                        position_value = margin * leverage
                        logger.info(f"Position size: {position_value} USDT (margin {margin} x {leverage}x leverage)")
                        return position_value
                    logger.info(f"Position size: {margin} USDT ({self.position_size_percent}% of {cash})")
                    return margin
                else:
                    # Generic fallback
                    balances = self.client.get_main_balances()
                    quote_currency = 'USDT' if 'USDT' in symbol else 'USD'
                    balance = balances.get(quote_currency, {})
                    balance_value = float(balance.get('free', 0) or balance.get('total', 0))
                    position_size = balance_value * (self.position_size_percent / 100.0)
                    logger.info(f"Position size: {position_size} {quote_currency} ({self.position_size_percent}% of {balance_value})")
                    return position_size
                
            except Exception as e:
                logger.error(f"Error calculating position size: {e}")
                # Fallback to fixed size if available
                if self.position_size_fixed:
                    return float(self.position_size_fixed)
                return 0.0
        else:
            # Use fixed position size
            if self.position_size_fixed:
                return float(self.position_size_fixed)
            return 0.0
    
    def check_existing_positions(self, symbol: str) -> bool:
        """
        Check if there are existing open positions for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if positions exist, False otherwise
        """
        symbol = self._symbol_for_exchange(symbol)
        try:
            open_orders = self.client.get_open_orders(symbol)
            if open_orders and len(open_orders) > 0:
                logger.warning(f"Existing open orders found for {symbol}: {len(open_orders)} orders")
                return True
            return False
        except Exception as e:
            logger.warning(f"Could not check existing positions: {e}")
            return False
    
    def execute_buy(self, symbol: str, signal_data: Dict) -> Optional[Dict]:
        """
        Execute a BUY order with TP/SL management
        
        Args:
            symbol: Trading pair symbol (TradingView format e.g. BTCUSDT.P)
            signal_data: Signal data from TradingView
            
        Returns:
            Order response or None if failed
        """
        symbol = self._symbol_for_exchange(symbol)
        try:
            # Check for existing positions if warning is enabled
            warn_existing = self.config.get('warn_existing_positions', True)
            if warn_existing:
                has_positions = self.check_existing_positions(symbol)
                if has_positions:
                    logger.warning(f"⚠️  EXISTING POSITIONS DETECTED for {symbol}. Proceeding with new order.")
            
            # Get current price (this will be our entry price)
            try:
                entry_price = self.client.get_ticker_price(symbol)
                logger.info(f"Current {symbol} price: {entry_price}")
            except ValueError as e:
                # Handle exchange-specific errors (e.g., Alpaca doesn't support crypto)
                error_msg = str(e)
                logger.error(f"❌ {error_msg}")
                return {
                    'error': error_msg,
                    'symbol': symbol,
                    'exchange': self.exchange_name
                }
            
            # Calculate position size (in quote currency, e.g. USDT or USD)
            position_size_usdt = self.calculate_position_size(symbol, entry_price)
            
            if position_size_usdt <= 0:
                logger.error("Invalid position size calculated (balance may be zero or config error)")
                return {'error': 'Invalid position size (balance zero or position_size config)'}
            
            # Bybit futures: set leverage then place order (must succeed or position may open at 1x)
            if self.exchange_name == 'bybit' and hasattr(self.client, 'trading_mode') and self.client.trading_mode == 'futures':
                if hasattr(self.client, 'set_leverage'):
                    lev = int(getattr(self.client, 'leverage', 1) or 1)
                    lev = max(1, min(100, lev))
                    ok = self.client.set_leverage(symbol, lev)
                    if not ok:
                        time.sleep(0.25)
                        ok = self.client.set_leverage(symbol, lev)
                    if not ok:
                        return {
                            'error': f'Failed to set Bybit leverage to {lev}x (check API permissions / margin mode). Trade aborted.',
                            'symbol': symbol,
                            'exchange': self.exchange_name,
                        }
                    logger.info(f"Using leverage {lev}x for {symbol} (set before entry)")
                logger.info(f"Executing BUY order (futures): {symbol}, Position value: {position_size_usdt} USDT notional")
                order_response = self.client.place_market_buy(symbol, position_size_usdt, price=entry_price)
            else:
                quote_currency = 'USD' if self.exchange_name in ['alpaca', 'ibkr'] else 'USDT'
                logger.info(f"Executing BUY order: {symbol}, Size: {position_size_usdt} {quote_currency}")
                order_response = self.client.place_market_buy(symbol, position_size_usdt)
            
            # Handle different exchange order ID formats
            order_id = None
            if 'orderId' in order_response:  # MEXC format
                order_id = str(order_response['orderId'])
            elif 'id' in order_response:  # Alpaca format
                order_id = str(order_response['id'])
            elif 'order_id' in order_response:
                order_id = str(order_response['order_id'])
            elif 'result' in order_response and 'orderId' in order_response['result']:  # Bybit format
                order_id = str(order_response['result']['orderId'])
            elif 'result' in order_response and 'orderLinkId' in order_response['result']:  # Bybit orderLinkId
                order_id = str(order_response['result']['orderLinkId'])
            
            if not order_id:
                logger.error(f"Failed to get order ID from response: {order_response}")
                return {'error': f'Order placed but no order ID in response: {order_response}'}
            
            logger.info(f"BUY order placed successfully: {order_id}")
            
            # Wait a moment for order to fill, then get filled quantity
            time.sleep(1)
            filled_order = self.client.get_order_status(symbol, order_id)
            
            # Handle different exchange status formats
            status = filled_order.get('status', '').upper()
            # Bybit uses 'result' wrapper
            if 'result' in filled_order:
                result = filled_order['result']
                if 'list' in result and len(result['list']) > 0:
                    order_data = result['list'][0]
                    status = order_data.get('orderStatus', '').upper()
            
            if status not in ['FILLED', 'FILL', 'FILLED', 'PARTIALLYFILLED']:
                logger.warning(f"Order {order_id} not yet filled, status: {status}")
            
            # Get executed quantity (different field names per exchange)
            executed_qty = 0.0
            if 'executedQty' in filled_order:  # MEXC
                executed_qty = float(filled_order.get('executedQty', 0))
            elif 'filled_qty' in filled_order:  # Alpaca
                executed_qty = float(filled_order.get('filled_qty', 0))
            elif 'qty' in filled_order and status in ['FILLED', 'FILL']:  # Alpaca filled
                executed_qty = float(filled_order.get('qty', 0))
            elif 'result' in filled_order:  # Bybit format
                result = filled_order['result']
                if 'list' in result and len(result['list']) > 0:
                    order_data = result['list'][0]
                    executed_qty = float(order_data.get('cumExecQty', 0))
                    if executed_qty == 0:
                        executed_qty = float(order_data.get('qty', 0))
            
            if executed_qty <= 0:
                logger.error("No quantity executed (order may be pending)")
                return {'error': 'Order placed but no fill yet (check exchange)', 'order': order_response}
            
            # Calculate actual entry price from filled order
            if 'price' in filled_order and filled_order['price']:
                entry_price = float(filled_order['price'])
            elif 'filled_avg_price' in filled_order:  # Alpaca
                entry_price = float(filled_order.get('filled_avg_price', 0))
            elif 'cummulativeQuoteQty' in filled_order and executed_qty > 0:  # MEXC
                entry_price = float(filled_order['cummulativeQuoteQty']) / executed_qty
            elif 'notional' in filled_order and executed_qty > 0:  # Alpaca notional
                entry_price = float(filled_order.get('notional', 0)) / executed_qty
            elif 'result' in filled_order:  # Bybit format
                result = filled_order['result']
                if 'list' in result and len(result['list']) > 0:
                    order_data = result['list'][0]
                    cum_exec_value = float(order_data.get('cumExecValue', 0))
                    if cum_exec_value > 0 and executed_qty > 0:
                        entry_price = cum_exec_value / executed_qty
                    elif 'avgPrice' in order_data:
                        entry_price = float(order_data.get('avgPrice', 0))
                    elif 'price' in order_data:
                        entry_price = float(order_data.get('price', 0))
            
            # Create position record
            position = self.position_manager.create_position(
                symbol=symbol,
                entry_price=entry_price,
                side='BUY',
                quantity=executed_qty,
                order_id=order_id
            )
            
            # Place initial stop-loss (5% from entry)
            sl_order_id = self.tp_sl_manager.place_initial_stop_loss(
                symbol=symbol,
                entry_price=entry_price,
                side='BUY',
                quantity=executed_qty
            )
            
            if sl_order_id:
                position['stop_loss_order_id'] = sl_order_id
                logger.info(f"Initial stop-loss placed: {sl_order_id}")
            else:
                logger.error("⚠️  WARNING: Failed to place initial stop-loss")
            
            # Place all take-profit orders (TP1-TP5)
            tp_orders = self.tp_sl_manager.place_take_profit_orders(
                symbol=symbol,
                entry_price=entry_price,
                side='BUY',
                initial_quantity=executed_qty
            )
            
            logger.info(f"Take-profit orders placed: {len(tp_orders)} orders")
            
            return {
                'entry_order': order_response,
                'position': position,
                'stop_loss_order_id': sl_order_id,
                'tp_orders': tp_orders
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Error executing BUY order for {symbol} on {self.exchange_name}: {error_msg}", exc_info=True)
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Symbol: {symbol}")
            logger.error(f"   Exchange: {self.exchange_name}")
            # Return error dict so webhook handler can see the actual error
            return {
                'error': error_msg,
                'symbol': symbol,
                'exchange': self.exchange_name,
                'error_type': type(e).__name__
            }
    
    def execute_sell(self, symbol: str, signal_data: Dict) -> Optional[Dict]:
        """
        Execute a SELL order
        
        Args:
            symbol: Trading pair symbol (TradingView format e.g. BTCUSDT.P)
            signal_data: Signal data from TradingView
            
        Returns:
            Order response or None if failed
        """
        symbol = self._symbol_for_exchange(symbol)
        try:
            available_quantity = 0.0
            reduce_only = False
            
            if self.exchange_name == 'alpaca':
                base_currency = symbol.replace('USDT', '').replace('USD', '')
                position = self.client.get_position(symbol)
                if position:
                    available_quantity = float(position.get('qty', 0))
                else:
                    balance = self.client.get_balance(base_currency)
                    available_quantity = float(balance.get('free', 0) or balance.get('total', 0))
            elif self.exchange_name == 'bybit' and hasattr(self.client, 'trading_mode') and self.client.trading_mode == 'futures':
                positions = self.client.get_positions(symbol)
                for pos in positions:
                    if pos.get('symbol') == symbol and float(pos.get('size', 0)) > 0:
                        available_quantity = float(pos.get('size', 0))
                        reduce_only = True
                        break
            else:
                base_currency = symbol.split('USDT')[0] if 'USDT' in symbol else symbol.replace('USDT', '').replace('BTC', '').replace('ETH', '')
                balance = self.client.get_balance(base_currency)
                available_quantity = float(balance.get('free', 0) or balance.get('total', 0))
            
            if available_quantity <= 0:
                logger.warning(f"No position/balance available to sell for {symbol}")
                return {'error': f'No position or balance to sell for {symbol}'}
            
            if self.use_percentage and not reduce_only:
                sell_quantity = available_quantity * (self.position_size_percent / 100.0)
            else:
                sell_quantity = available_quantity
            
            sell_quantity = min(sell_quantity, available_quantity)
            
            logger.info(f"Executing SELL order: {symbol}, Quantity: {sell_quantity}" + (" (reduce-only)" if reduce_only else ""))
            if reduce_only and self.exchange_name == 'bybit':
                order_response = self.client.place_market_sell(symbol, sell_quantity, reduce_only=True)
            else:
                order_response = self.client.place_market_sell(symbol, sell_quantity)
            
            logger.info(f"SELL order placed successfully: {order_response}")
            return order_response
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error executing SELL order: {error_msg}", exc_info=True)
            # Return error dict so webhook handler can see the actual error
            return {
                'error': error_msg,
                'symbol': symbol,
                'exchange': self.exchange_name
            }
    
    def validate_signal(self, signal_data: Dict) -> bool:
        """
        Validate trading signal before execution
        
        Args:
            signal_data: Signal data from TradingView
            
        Returns:
            True if signal is valid, False otherwise
        """
        # Check required fields
        required_fields = ['symbol', 'signal', 'indicators', 'price']
        for field in required_fields:
            if field not in signal_data:
                logger.error(f"Missing required field: {field}")
                return False
        
        # Validate signal type
        signal = signal_data.get('signal', '').upper()
        if signal not in ['BUY', 'SELL']:
            logger.error(f"Invalid signal type: {signal}")
            return False
        
        # Strategy conditions: default True if not present (TradingView may omit)
        strategy = signal_data.get('strategy', {})
        if strategy is not None and 'all_conditions_met' in strategy:
            if not strategy.get('all_conditions_met', False):
                logger.warning("Signal rejected: all_conditions_met=false")
                return False
        
        # TradingView already determines the symbol from the indicator configuration
        # No need to filter by trading pairs - accept any symbol from TradingView
        
        return True
    
    def _monitor_positions(self):
        """Background thread to monitor positions and handle TP/SL"""
        while self.monitoring_active:
            try:
                positions = self.position_manager.get_all_positions()
                
                for symbol, position in positions.items():
                    # Check if TP1 has been hit and move stop-loss to entry (CRITICAL)
                    if not position['tp_hit']['tp1']:
                        try:
                            self.tp_sl_manager.check_and_handle_tp1(symbol)
                        except Exception as e:
                            logger.error(f"CRITICAL ERROR in TP1 handling for {symbol}: {e}")
                            # This is critical - if we can't move SL to entry, we have a problem
                    
                    # Check other TP levels
                    self._check_tp_levels(symbol)
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in position monitoring: {e}")
                time.sleep(10)
    
    def _check_tp_levels(self, symbol: str):
        """Check if TP levels have been hit"""
        position = self.position_manager.get_position(symbol)
        if not position:
            return
        
        for tp_level in ['tp2', 'tp3', 'tp4', 'tp5']:
            if position['tp_hit'][tp_level]:
                continue
            
            tp_order_id = position['tp_orders'].get(tp_level)
            if not tp_order_id:
                continue
            
            try:
                order_status = self.client.get_order_status(symbol, tp_order_id)
                
                # Handle different exchange status formats
                status = order_status.get('status', '').upper()
                if status in ['FILLED', 'FILL']:
                    logger.info(f"✅ {tp_level.upper()} FILLED for {symbol}")
                    self.position_manager.mark_tp_hit(symbol, tp_level)
                    
                    # Update remaining quantity
                    close_qty = self.tp_sl_manager.calculate_close_quantity(
                        position['initial_quantity'],
                        tp_level,
                        position['remaining_quantity']
                    )
                    self.position_manager.update_position_quantity(symbol, close_qty)
                    
            except Exception as e:
                logger.error(f"Error checking {tp_level}: {e}")
    
    def execute_signal(self, signal_data: Dict) -> Optional[Dict]:
        """
        Execute trading signal
        
        Args:
            signal_data: Signal data from TradingView webhook
            
        Returns:
            Order response or None if failed
        """
        # Validate signal
        if not self.validate_signal(signal_data):
            logger.error("Signal validation failed")
            return {'error': 'Signal validation failed (check symbol, signal type, strategy)'}
        
        symbol = signal_data.get('symbol', '')
        signal = signal_data.get('signal', '').upper()
        
        logger.info(f"Executing {signal} signal for {symbol}")
        
        # Execute based on signal type
        if signal == 'BUY':
            return self.execute_buy(symbol, signal_data)
        elif signal == 'SELL':
            return self.execute_sell(symbol, signal_data)
        else:
            logger.error(f"Unknown signal type: {signal}")
            return {'error': f'Unknown signal type: {signal}'}

