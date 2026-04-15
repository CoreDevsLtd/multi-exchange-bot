"""
Take Profit and Stop Loss Manager
Handles TP levels and stop-loss management according to requirements
Supports multiple exchanges

NOTE: MEXC Spot API does NOT support stop-loss orders.
We use a monitoring system to check prices and execute stop-loss manually.
Alpaca supports native stop-loss orders via API.
"""

import logging
import math
import time
from typing import Dict, Optional, Union
from position_manager import PositionManager

logger = logging.getLogger(__name__)


def _bybit_tp_quantities_from_steps(symbol: str, initial_qty: float, client) -> Dict[str, float]:
    """
    TP qtys as % of position using integer qtySteps so sum(T) <= filled position.
    Fixes Bybit rejecting TP4/TP5 when round() on each TP made total reduce-only qty > position.
    """
    info = client.get_instrument_info(symbol) if hasattr(client, 'get_instrument_info') else None
    qty_step = float(info.get('lotSizeFilter', {}).get('qtyStep', 0.001)) if info else 0.001
    min_qty = float(info.get('lotSizeFilter', {}).get('minOrderQty', qty_step)) if info else qty_step
    if qty_step <= 0:
        qty_step = 0.001

    n_steps = int(initial_qty / qty_step + 1e-12)
    while n_steps * qty_step > initial_qty + 1e-9 and n_steps > 0:
        n_steps -= 1
    if n_steps <= 0:
        return {}

    # Step counts: 10%, 15%, 35%, 35% of total steps; TP5 = half of remaining steps
    s1 = int(10 * n_steps / 100)
    s2 = int(15 * n_steps / 100)
    s3 = int(35 * n_steps / 100)
    s4 = int(35 * n_steps / 100)
    used = s1 + s2 + s3 + s4
    rem = max(0, n_steps - used)
    s5 = rem // 2
    steps = [s1, s2, s3, s4, s5]
    total_steps = sum(steps)
    while total_steps > n_steps and any(steps):
        for i in range(4, -1, -1):
            if steps[i] > 0:
                steps[i] -= 1
                break
        total_steps = sum(steps)

    labels = ['tp1', 'tp2', 'tp3', 'tp4', 'tp5']
    out: Dict[str, float] = {}
    for lbl, sc in zip(labels, steps):
        q = sc * qty_step
        if q >= min_qty - 1e-12:
            out[lbl] = q
    return out


class TPSLManager:
    """Manages Take Profit and Stop Loss orders"""
    
    # TP Configuration (from requirements)
    DEFAULT_TP_CONFIG = {
        'tp1': {'percent': 1.0, 'close_percent': 10.0},   # 1% from entry, close 10% (90% remaining)
        'tp2': {'percent': 2.0, 'close_percent': 15.0},   # 2% from entry, close 15% (75% remaining)
        'tp3': {'percent': 5.0, 'close_percent': 35.0},   # 5% from entry, close 35% (40% remaining)
        'tp4': {'percent': 6.5, 'close_percent': 35.0},   # 6.5% from entry, close 35% (5% remaining)
        'tp5': {'percent': 8.0, 'close_percent': 50.0}    # 8% from entry, close 50% of remaining (2.5% runner)
    }
    
    def __init__(self, exchange_client: Union[object], position_manager: PositionManager, 
                 stop_loss_percent: float = 5.0, exchange_name: str = 'mexc',
                 tp_mode: Optional[str] = None, take_profit_percent: float = 5.0,
                 tp_targets: Optional[Dict[str, float]] = None):
        """
        Initialize TP/SL Manager
        
        Args:
            exchange_client: Exchange API client instance (MEXCClient, AlpacaClient, etc.)
            position_manager: Position manager instance
            stop_loss_percent: Initial stop loss percentage (default: 5%)
            exchange_name: Name of the exchange ('mexc', 'alpaca', etc.)
        """
        self.client = exchange_client
        self.position_manager = position_manager
        self.stop_loss_percent = stop_loss_percent
        self.exchange_name = exchange_name.lower()
        self.stop_loss_monitor = None  # Will be set by TradingExecutor
        mode = str(tp_mode or '').strip().lower()
        if mode not in {'ladder', 'single', 'none'}:
            mode = 'single' if self.exchange_name == 'alpaca' else 'ladder'
        self.tp_mode = mode
        self.take_profit_percent = float(take_profit_percent)
        self.tp_config = {k: dict(v) for k, v in self.DEFAULT_TP_CONFIG.items()}
        for tp_key, tp_value in (tp_targets or {}).items():
            if tp_key not in self.tp_config:
                continue
            try:
                self.tp_config[tp_key]['percent'] = float(tp_value)
            except (TypeError, ValueError):
                continue
    
    def calculate_tp_price(self, entry_price: float, tp_level: str, side: str) -> float:
        """
        Calculate take-profit price
        
        Args:
            entry_price: Entry price
            tp_level: TP level (tp1, tp2, etc.)
            side: 'BUY' or 'SELL'
            
        Returns:
            Take-profit price
        """
        tp_config = self.tp_config.get(tp_level, {})
        tp_percent = tp_config.get('percent', 0)
        
        if side.upper() == 'BUY':
            return entry_price * (1 + tp_percent / 100.0)
        else:  # SELL
            return entry_price * (1 - tp_percent / 100.0)
    
    def calculate_sl_price(self, entry_price: float, side: str) -> float:
        """
        Calculate stop-loss price
        
        Args:
            entry_price: Entry price
            side: 'BUY' or 'SELL'
            
        Returns:
            Stop-loss price
        """
        if side.upper() == 'BUY':
            return entry_price * (1 - self.stop_loss_percent / 100.0)
        else:  # SELL
            return entry_price * (1 + self.stop_loss_percent / 100.0)
    
    def calculate_close_quantity(self, initial_quantity: float, tp_level: str, 
                                 remaining_quantity: float) -> float:
        """
        Calculate quantity to close for TP level
        
        Args:
            initial_quantity: Initial position quantity
            tp_level: TP level (tp1, tp2, etc.)
            remaining_quantity: Current remaining quantity
            
        Returns:
            Quantity to close
        """
        tp_config = self.tp_config.get(tp_level, {})
        if self.tp_mode == 'single' and tp_level == 'tp1':
            return remaining_quantity
        
        if tp_level == 'tp5':
            # TP5: Close 50% of remaining
            return remaining_quantity * 0.5
        else:
            # TP1-TP4: Close percentage of initial quantity
            close_percent = tp_config.get('close_percent', 0)
            return initial_quantity * (close_percent / 100.0)
    
    def place_initial_stop_loss(self, symbol: str, entry_price: float, 
                                side: str, quantity: float) -> Optional[str]:
        """
        Set initial stop-loss price (5% from entry)
        
        NOTE: MEXC Spot API does NOT support stop-loss orders.
        We store the stop-loss price and the monitoring system will execute it.
        
        Args:
            symbol: Trading pair symbol
            entry_price: Entry price
            side: 'BUY' or 'SELL'
            quantity: Position quantity
            
        Returns:
            Stop-loss "order ID" (actually just a marker, not a real order)
        """
        try:
            sl_price = self.calculate_sl_price(entry_price, side)
            
            logger.info(f"Setting initial stop-loss: {symbol} @ {sl_price} ({self.stop_loss_percent}% from entry)")
            position = self.position_manager.get_position(symbol)
            if position:
                position['stop_loss_price'] = sl_price

            # Bybit futures: exchange-visible SL via trading-stop (position TP/SL in UI)
            if self.exchange_name == 'bybit' and getattr(self.client, 'trading_mode', '') == 'futures':
                if hasattr(self.client, 'set_position_trading_stop'):
                    try:
                        time.sleep(0.35)  # allow position to sync before trading-stop
                        self.client.set_position_trading_stop(
                            symbol=symbol,
                            stop_loss=sl_price,
                            position_idx=0,
                            tpsl_mode='Full',
                            sl_trigger_by='MarkPrice',
                        )
                        if position:
                            position['stop_loss_order_id'] = 'BYBIT_TPSL'
                            position['exchange_sl_active'] = True
                        self.position_manager.save_position(symbol)
                        logger.info(f"✅ Bybit trading-stop SL set @ {sl_price} (Full, MarkPrice)")
                        return 'BYBIT_TPSL'
                    except Exception as e:
                        logger.error(f"❌ Bybit trading-stop SL failed (fallback to price monitor): {e}")
                if position:
                    position['stop_loss_order_id'] = 'MONITORED'
                    position['exchange_sl_active'] = False
                self.position_manager.save_position(symbol)
                logger.warning("⚠️  Bybit SL not on exchange; using price monitor fallback.")
                return 'MONITORED'

            logger.warning("⚠️  Spot API: no native SL order. Using price monitoring.")
            if position:
                position['stop_loss_order_id'] = 'MONITORED'
                position['exchange_sl_active'] = False
            self.position_manager.save_position(symbol)
            return 'MONITORED'
                
        except Exception as e:
            logger.error(f"Error setting stop-loss: {e}", exc_info=True)
            return None
    
    def move_stop_loss_to_entry(self, symbol: str, entry_price: float, 
                                side: str, current_sl_order_id: Optional[str]) -> Optional[str]:
        """
        Move stop-loss to entry price (CRITICAL: Must happen after TP1)
        
        NOTE: MEXC Spot API doesn't support stop-loss orders.
        We update the stop-loss price in the position, and the monitoring system will execute it.
        
        Args:
            symbol: Trading pair symbol
            entry_price: Entry price
            side: 'BUY' or 'SELL'
            current_sl_order_id: Current stop-loss order ID (ignored for Spot)
            
        Returns:
            Stop-loss marker ID
        """
        try:
            # Get remaining position quantity
            position = self.position_manager.get_position(symbol)
            if not position:
                logger.error(f"No active position found for {symbol}")
                return None
            
            # Update stop-loss price to entry (breakeven)
            logger.info(f"⚠️  CRITICAL: Moving stop-loss to entry price: {symbol} @ {entry_price}")
            position['stop_loss_price'] = entry_price
            self.position_manager.mark_stop_loss_moved(symbol)

            if self.exchange_name == 'bybit' and getattr(self.client, 'trading_mode', '') == 'futures':
                if hasattr(self.client, 'set_position_trading_stop'):
                    try:
                        self.client.set_position_trading_stop(
                            symbol=symbol,
                            stop_loss=entry_price,
                            position_idx=0,
                            tpsl_mode='Full',
                            sl_trigger_by='MarkPrice',
                        )
                        position['stop_loss_order_id'] = 'BYBIT_TPSL'
                        position['exchange_sl_active'] = True
                        logger.info(f"✅ Bybit trading-stop SL moved to entry @ {entry_price}")
                    except Exception as e:
                        logger.error(f"❌ Bybit move SL to entry failed: {e}")
                        position['stop_loss_order_id'] = 'MONITORED'
                        position['exchange_sl_active'] = False
            else:
                position['stop_loss_order_id'] = 'MONITORED'
                position['exchange_sl_active'] = False

            self.position_manager.save_position(symbol)

            if self.stop_loss_monitor:
                self.stop_loss_monitor.update_stop_loss_price(symbol, entry_price)

            logger.info(f"✅ Stop-loss price updated to entry: {entry_price}")
            return position.get('stop_loss_order_id') or 'MONITORED'
                
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR moving stop-loss to entry: {e}", exc_info=True)
            raise Exception("CRITICAL: Cannot move stop-loss to entry - project requirement failed")
    
    def place_take_profit_orders(self, symbol: str, entry_price: float, 
                                 side: str, initial_quantity: float) -> Dict[str, str]:
        """
        Place all take-profit limit orders (TP1-TP5)
        
        Args:
            symbol: Trading pair symbol
            entry_price: Entry price
            side: 'BUY' or 'SELL'
            initial_quantity: Initial position quantity
            
        Returns:
            Dictionary of TP level -> order ID
        """
        tp_orders = {}
        position = self.position_manager.get_position(symbol)
        
        if not position:
            logger.error(f"No position found for {symbol}")
            return tp_orders
        
        if self.tp_mode == 'none':
            logger.info(f"TP mode is 'none' for {self.exchange_name}; skipping TP orders for {symbol}")
            return tp_orders

        bybit_futures = (
            self.exchange_name == 'bybit'
            and getattr(self.client, 'trading_mode', '') == 'futures'
        )
        bybit_tp_qtys: Dict[str, float] = {}
        if bybit_futures:
            bybit_tp_qtys = _bybit_tp_quantities_from_steps(symbol, initial_quantity, self.client)
            if bybit_tp_qtys:
                logger.info(
                    f"Bybit TP allocation (step-based, sum ≤ position): "
                    + ", ".join(f"{k}={v:.8f}" for k, v in bybit_tp_qtys.items())
                )

        tp_levels = ['tp1'] if self.tp_mode == 'single' else ['tp1', 'tp2', 'tp3', 'tp4', 'tp5']
        for tp_level in tp_levels:
            try:
                if self.tp_mode == 'single':
                    if side.upper() == 'BUY':
                        tp_price = entry_price * (1 + self.take_profit_percent / 100.0)
                    else:
                        tp_price = entry_price * (1 - self.take_profit_percent / 100.0)
                else:
                    tp_price = self.calculate_tp_price(entry_price, tp_level, side)

                if bybit_futures and bybit_tp_qtys:
                    close_qty = bybit_tp_qtys.get(tp_level, 0.0)
                    if close_qty <= 0:
                        logger.warning(f"Skip {tp_level}: qty below min step / not enough position")
                        continue
                elif self.tp_mode == 'single':
                    close_qty = initial_quantity
                elif tp_level == 'tp5':
                    remaining_after_tp4 = max(0.0, initial_quantity * (1.0 - 0.10 - 0.15 - 0.35 - 0.35))
                    close_qty = remaining_after_tp4 * 0.5
                else:
                    close_qty = self.calculate_close_quantity(initial_quantity, tp_level, initial_quantity)

                # Place limit order for take-profit
                tp_side = 'SELL' if side.upper() == 'BUY' else 'BUY'

                logger.info(
                    f"Placing {tp_level}: {symbol} @ {tp_price}, Qty: {close_qty} "
                    f"({self.tp_config.get(tp_level, {}).get('close_percent', 0)}% tier vs initial, where applicable)"
                )
                reduce_only = getattr(self.client, 'trading_mode', '') == 'futures'
                order_params = dict(symbol=symbol, side=tp_side, order_type='LIMIT', quantity=close_qty, price=tp_price)
                if reduce_only:
                    order_params['reduce_only'] = True
                response = self.client.place_order(**order_params)
                
                # Handle different exchange response formats (MEXC: orderId, Bybit: result.orderId, Alpaca: id)
                order_id = None
                if response:
                    if 'orderId' in response:
                        order_id = str(response['orderId'])
                    elif 'result' in response and isinstance(response.get('result'), dict) and 'orderId' in response['result']:
                        order_id = str(response['result']['orderId'])
                    elif 'id' in response:
                        order_id = str(response['id'])
                
                if order_id:
                    tp_orders[tp_level] = order_id
                    position['tp_orders'][tp_level] = order_id
                    logger.info(f"{tp_level} order placed: {order_id}")
                else:
                    logger.warning(f"Failed to place {tp_level}: {response}")

            except Exception as e:
                logger.error(f"Error placing {tp_level}: {e}")

        # Persist tp_orders mutations to DB in one shot after the loop
        self.position_manager.save_position(symbol)
        return tp_orders
    
    def check_and_handle_tp1(self, symbol: str) -> bool:
        """
        Check if TP1 has been hit and move stop-loss to entry (CRITICAL)
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if TP1 hit and stop-loss moved, False otherwise
        """
        position = self.position_manager.get_position(symbol)
        if not position:
            return False
        
        # Check if TP1 already hit
        if position['tp_hit']['tp1']:
            return True
        
        # Check if TP1 order has been filled
        tp1_order_id = position['tp_orders'].get('tp1')
        if not tp1_order_id:
            return False
        
        try:
            order_status = self.client.get_order_status(symbol, tp1_order_id)
            
            # Normalize status across exchanges (MEXC: status, Bybit: result.list[0].orderStatus, Alpaca: status)
            status = (order_status.get('status') or '').upper()
            od = None
            if 'result' in order_status and order_status['result'].get('list'):
                od = order_status['result']['list'][0]
                status = (od.get('orderStatus') or od.get('order_status') or '').upper()

            # Bybit: only treat as TP1 when this order is a reduce-only exit in the expected direction.
            # A wrong list row or mis-ID could otherwise mark FILLED and move SL to breakeven early.
            if (
                status == 'FILLED'
                and self.exchange_name == 'bybit'
                and getattr(self.client, 'trading_mode', '') == 'futures'
                and od is not None
            ):
                pos_side = (position.get('side') or 'BUY').upper()
                need_side = 'Sell' if pos_side == 'BUY' else 'Buy'
                if (od.get('side') or '') != need_side:
                    logger.warning(
                        f"TP1 probe order {tp1_order_id} is side={od.get('side')!r} (expected {need_side}) — not moving SL"
                    )
                    return False
                ro = od.get('reduceOnly')
                if ro is False or str(ro).lower() == 'false':
                    logger.warning(
                        f"TP1 probe order {tp1_order_id} is not reduceOnly — not moving SL"
                    )
                    return False
                order_qty = float(od.get('qty') or 0)
                cum = float(od.get('cumExecQty') or 0)
                if order_qty > 0 and cum + 1e-12 < order_qty * 0.85:
                    logger.warning(
                        f"TP1 order {tp1_order_id} cumExecQty={cum} < 85% of order qty {order_qty} — not moving SL"
                    )
                    return False
            
            if status == 'FILLED':
                if self.tp_mode == 'single':
                    logger.info(f"✅ TP1 FILLED for {symbol} - closing position in single-TP mode")
                    self.position_manager.mark_tp_hit(symbol, 'tp1')
                    self.position_manager.update_position_quantity(symbol, position['remaining_quantity'])
                    self.position_manager.close_position(symbol, exit_reason='TP')
                    return True

                logger.info(
                    f"✅ TP1 FILLED for {symbol} - Moving stop-loss to entry @ {position['entry_price']} "
                    f"(breakeven; exits on pullback below entry are expected)"
                )
                
                # CRITICAL: Move stop-loss to entry price
                new_sl_order_id = self.move_stop_loss_to_entry(
                    symbol,
                    position['entry_price'],
                    position['side'],
                    position['stop_loss_order_id']
                )
                
                if new_sl_order_id:
                    position['stop_loss_order_id'] = new_sl_order_id
                    position['tp_hit']['tp1'] = True
                    self.position_manager.mark_tp_hit(symbol, 'tp1')
                    
                    # Update stop-loss price in monitoring system
                    # (Since we're using Spot API, we update the monitored price)
                    from stop_loss_monitor import StopLossMonitor
                    # Note: StopLossMonitor is initialized in TradingExecutor
                    # The price is already updated in move_stop_loss_to_entry
                    
                    # Update remaining quantity
                    tp1_close_qty = self.calculate_close_quantity(
                        position['initial_quantity'],
                        'tp1',
                        position['remaining_quantity']
                    )
                    self.position_manager.update_position_quantity(symbol, tp1_close_qty)
                    
                    return True
                else:
                    raise Exception("CRITICAL: Failed to move stop-loss to entry after TP1")
                    
        except Exception as e:
            logger.error(f"Error checking TP1: {e}")
            raise
        
        return False
