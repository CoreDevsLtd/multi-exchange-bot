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
    
    def __init__(self, exchange_client: Union[object], exchange_name: str = 'mexc', exchange_account_id: str = None, account_id: str = None):
        """
        Initialize Position Manager
        
        Args:
            exchange_client: Exchange API client instance (MEXCClient, AlpacaClient, etc.)
            exchange_name: Name of the exchange ('mexc', 'alpaca', etc.)
            exchange_account_id: Optional exchange account identifier (for multi-account support)
            account_id: Optional logical account id
        """
        self.client = exchange_client
        self.exchange_name = exchange_name.lower()
        self.exchange_account_id = exchange_account_id
        self.account_id = account_id
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
            'created_at': time.time(),
            'exchange_account_id': self.exchange_account_id,
            'account_id': self.account_id
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
    
    def close_position(self, symbol: str, exit_reason: str = None):
        """Close and remove position. Persists trade to MongoDB when available."""
        logger.info(f"close_position called: symbol={symbol}, active_positions={list(self.active_positions.keys())}")
        if symbol in self.active_positions:
            pos = self.active_positions[symbol]
            try:
                # Attempt to persist trade information to MongoDB if configured
                from mongo_db import insert_trade
                mongo_available = True

                exit_price = None
                try:
                    exit_price = float(self.client.get_ticker_price(symbol))
                except Exception:
                    exit_price = None

                trade_doc = {
                    'exchange_account_id': pos.get('exchange_account_id'),
                    'account_id': pos.get('account_id'),
                    'symbol': pos.get('symbol'),
                    'direction': pos.get('side'),
                    'entry_price': pos.get('entry_price'),
                    'exit_price': exit_price,
                    'stop_loss': pos.get('stop_loss_price'),
                    'tp_hits': [pos['tp_hit'].get('tp1'), pos['tp_hit'].get('tp2'), pos['tp_hit'].get('tp3'), pos['tp_hit'].get('tp4'), pos['tp_hit'].get('tp5')],
                    'r_multiple': None,
                    'result_usd': None,
                    'result_percent': None,
                    'trade_duration_sec': int(time.time() - pos.get('created_at', time.time())),
                    'max_drawdown': None,
                    'max_profit': None,
                    'exit_reason': exit_reason or 'CLOSE',
                    'timestamp_open': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(pos.get('created_at', time.time()))),
                    'timestamp_close': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                }

                # Compute simple P&L if exit_price known
                if exit_price is not None and pos.get('initial_quantity'):
                    qty = float(pos.get('initial_quantity', 0))
                    entry = float(pos.get('entry_price', 0))
                    if pos.get('side', '').upper() == 'BUY':
                        pnl = (exit_price - entry) * qty
                    else:
                        pnl = (entry - exit_price) * qty
                    trade_doc['result_usd'] = pnl
                    try:
                        trade_doc['result_percent'] = (pnl / (entry * qty)) * 100 if (entry * qty) != 0 else None
                    except Exception:
                        trade_doc['result_percent'] = None

                try:
                    insert_trade(trade_doc)
                    logger.info(f"Persisted trade to MongoDB: {pos.get('symbol')}")
                except Exception as e:
                    logger.error(f"Failed to persist trade to MongoDB: {e}")

            except Exception as e:
                logger.error(f"Error while saving trade: {e}")

            del self.active_positions[symbol]
            logger.info(f"Position closed: {symbol}")
    
    def get_all_positions(self) -> Dict:
        """Get all active positions"""
        return self.active_positions.copy()

