"""
Stop Loss Monitor
Monitors price and executes stop-loss orders for Spot trading
Since MEXC Spot API doesn't support stop-loss orders, we monitor price and execute market orders
Alpaca supports native stop-loss orders, but we still monitor for safety
"""

import logging
import threading
import time
from typing import Dict, Optional, Union
from position_manager import PositionManager

logger = logging.getLogger(__name__)


class StopLossMonitor:
    """Monitors price and executes stop-loss for Spot trading"""
    
    def __init__(self, exchange_client: Union[object], position_manager: PositionManager, 
                 exchange_name: str = 'mexc'):
        """
        Initialize Stop Loss Monitor
        
        Args:
            exchange_client: Exchange API client instance (MEXCClient, AlpacaClient, etc.)
            position_manager: Position manager instance
            exchange_name: Name of the exchange ('mexc', 'alpaca', etc.)
        """
        self.client = exchange_client
        self.position_manager = position_manager
        self.exchange_name = exchange_name.lower()
        self.monitoring_active = True
        self.monitor_thread = None
        self.check_interval = 2  # Check every 2 seconds
    
    def start_monitoring(self):
        """Start the monitoring thread"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Stop-loss monitor started")
    
    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.monitoring_active = False
        logger.info("Stop-loss monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                positions = self.position_manager.get_all_positions()
                
                for symbol, position in positions.items():
                    self._check_stop_loss(symbol, position)
                    self._check_take_profits(symbol, position)
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in stop-loss monitor: {e}")
                time.sleep(5)
    
    def _check_stop_loss(self, symbol: str, position: Dict):
        """Check if stop-loss should be triggered"""
        try:
            if self.exchange_name == 'bybit' and getattr(self.client, 'trading_mode', '') == 'futures':
                if position.get('exchange_sl_active'):
                    return

            # Get current price
            current_price = self.client.get_ticker_price(symbol)
            
            entry_price = position['entry_price']
            side = position['side']
            remaining_qty = position['remaining_quantity']
            
            # Calculate stop-loss price
            if position.get('stop_loss_price'):
                sl_price = position['stop_loss_price']
            else:
                # Initial stop-loss: 5% below entry for BUY
                sl_percent = 5.0
                if side.upper() == 'BUY':
                    sl_price = entry_price * (1 - sl_percent / 100.0)
                else:  # SELL
                    sl_price = entry_price * (1 + sl_percent / 100.0)
            
            # Check if stop-loss should trigger
            should_trigger = False
            if side.upper() == 'BUY':
                # For long position, trigger if price drops to/below stop-loss
                if current_price <= sl_price:
                    should_trigger = True
            else:  # SELL (short)
                # For short position, trigger if price rises to/above stop-loss
                if current_price >= sl_price:
                    should_trigger = True
            
            if should_trigger and remaining_qty > 0:
                logger.warning(f"⚠️  STOP-LOSS TRIGGERED: {symbol} @ {current_price} (SL: {sl_price})")
                self._execute_stop_loss(symbol, position, current_price)
                
        except Exception as e:
            logger.error(f"Error checking stop-loss for {symbol}: {e}")
    
    def _check_take_profits(self, symbol: str, position: Dict):
        """Check if take-profit levels should be triggered (for monitoring)"""
        try:
            current_price = self.client.get_ticker_price(symbol)
            entry_price = position['entry_price']
            side = position['side']
            
            # Check each TP level
            tp_levels = {
                'tp1': {'percent': 1.0, 'close_percent': 10.0},
                'tp2': {'percent': 2.0, 'close_percent': 15.0},
                'tp3': {'percent': 5.0, 'close_percent': 35.0},
                'tp4': {'percent': 6.5, 'close_percent': 35.0},
                'tp5': {'percent': 8.0, 'close_percent': 50.0}
            }
            
            for tp_level, config in tp_levels.items():
                if position['tp_hit'][tp_level]:
                    continue
                
                # Calculate TP price
                if side.upper() == 'BUY':
                    tp_price = entry_price * (1 + config['percent'] / 100.0)
                    price_hit = current_price >= tp_price
                else:  # SELL
                    tp_price = entry_price * (1 - config['percent'] / 100.0)
                    price_hit = current_price <= tp_price
                
                if price_hit:
                    logger.info(f"✅ {tp_level.upper()} price reached: {symbol} @ {current_price}")
                    # TP orders are already placed as limit orders, so they should fill automatically
                    # But we can verify here if needed
                    
        except Exception as e:
            logger.error(f"Error checking take-profits for {symbol}: {e}")
    
    def _execute_stop_loss(self, symbol: str, position: Dict, current_price: float):
        """Execute stop-loss by placing market sell order"""
        try:
            side = position['side']
            remaining_qty = position['remaining_quantity']
            
            if remaining_qty <= 0:
                logger.warning(f"No remaining quantity to close for {symbol}")
                return
            
            reduce_only = getattr(self.client, 'trading_mode', '') == 'futures'
            if side.upper() == 'BUY':
                logger.info(f"Executing stop-loss: Market SELL {remaining_qty} {symbol}")
                if reduce_only and self.exchange_name == 'bybit':
                    order_response = self.client.place_market_sell(symbol, remaining_qty, reduce_only=True)
                else:
                    order_response = self.client.place_market_sell(symbol, remaining_qty)
            else:
                logger.info(f"Executing stop-loss: Market BUY {remaining_qty} {symbol}")
                if reduce_only and self.exchange_name == 'bybit':
                    order_response = self.client.place_market_buy(symbol, remaining_qty, reduce_only=True)
                else:
                    order_response = self.client.place_market_buy(symbol, remaining_qty * current_price)
            
            # Handle different exchange response formats (MEXC: orderId, Bybit: result.orderId, Alpaca: id)
            executed = False
            if order_response:
                oid = order_response.get('orderId') or (order_response.get('result') or {}).get('orderId') or order_response.get('id')
                if oid:
                    logger.info(f"✅ Stop-loss executed: Order {oid}")
                    executed = True
            if not executed:
                logger.error(f"Failed to execute stop-loss: {order_response}")
            if executed:
                self.position_manager.close_position(symbol)
                
        except Exception as e:
            logger.error(f"Error executing stop-loss: {e}", exc_info=True)
    
    def update_stop_loss_price(self, symbol: str, new_sl_price: float):
        """Update stop-loss price (e.g., move to entry after TP1)"""
        position = self.position_manager.get_position(symbol)
        if position:
            position['stop_loss_price'] = new_sl_price
            logger.info(f"Stop-loss price updated for {symbol}: {new_sl_price}")


