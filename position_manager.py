"""
Position Manager
Manages open positions, take-profit levels, and stop-loss orders
Supports multiple exchanges
"""

import logging
import time
from typing import Dict, Optional, List, Union

logger = logging.getLogger(__name__)


class PositionManager:
    """Manages trading positions, TP levels, and stop-loss"""
    
    def __init__(self, exchange_client: Union[object], exchange_name: str = 'mexc'):
        """
        Initialize Position Manager
        
        Args:
            exchange_client: Exchange API client instance (MEXCClient, AlpacaClient, etc.)
            exchange_name: Name of the exchange ('mexc', 'alpaca', etc.)
        """
        self.client = exchange_client
        self.exchange_name = exchange_name.lower()
        self.active_positions = {}  # symbol -> position_data
        
    def create_position(self, symbol: str, entry_price: float, side: str, 
                       quantity: float, order_id: str) -> Dict:
        """
        Create a new position record
        
        Args:
            symbol: Trading pair symbol
            entry_price: Entry price
            side: 'BUY' or 'SELL'
            quantity: Position quantity
            order_id: Entry order ID
            
        Returns:
            Position data dictionary
        """
        position = {
            'symbol': symbol,
            'entry_price': entry_price,
            'side': side.upper(),
            'initial_quantity': quantity,
            'remaining_quantity': quantity,
            'entry_order_id': order_id,
            'stop_loss_order_id': None,
            'stop_loss_price': None,  # Stop-loss price (for monitoring, since Spot API doesn't support SL orders)
            'tp_orders': {},  # tp_level -> order_id
            'tp_hit': {
                'tp1': False,
                'tp2': False,
                'tp3': False,
                'tp4': False,
                'tp5': False
            },
            'stop_loss_moved_to_entry': False,
            'exchange_sl_active': False,
            'created_at': time.time()
        }
        
        self.active_positions[symbol] = position
        logger.info(f"Position created: {symbol} {side} @ {entry_price}, Qty: {quantity}")
        return position
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get active position for symbol"""
        return self.active_positions.get(symbol)
    
    def update_position_quantity(self, symbol: str, closed_quantity: float):
        """Update remaining quantity after partial close"""
        if symbol in self.active_positions:
            self.active_positions[symbol]['remaining_quantity'] -= closed_quantity
            logger.info(f"Position updated: {symbol}, Remaining: {self.active_positions[symbol]['remaining_quantity']}")
    
    def mark_tp_hit(self, symbol: str, tp_level: str):
        """Mark a take-profit level as hit"""
        if symbol in self.active_positions:
            self.active_positions[symbol]['tp_hit'][tp_level] = True
            logger.info(f"TP {tp_level} hit for {symbol}")
    
    def mark_stop_loss_moved(self, symbol: str):
        """Mark that stop-loss has been moved to entry"""
        if symbol in self.active_positions:
            self.active_positions[symbol]['stop_loss_moved_to_entry'] = True
            logger.info(f"Stop-loss moved to entry for {symbol}")
    
    def close_position(self, symbol: str):
        """Close and remove position"""
        if symbol in self.active_positions:
            del self.active_positions[symbol]
            logger.info(f"Position closed: {symbol}")
    
    def get_all_positions(self) -> Dict:
        """Get all active positions"""
        return self.active_positions.copy()

