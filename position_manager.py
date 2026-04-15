"""
Position Manager
Manages open positions, take-profit levels, and stop-loss orders.

Write-through cache design:
  - active_positions (in-memory dict) is the hot-read path used by monitoring
    loops (StopLossMonitor, _monitor_positions) which poll every 2-5 seconds.
  - Every mutation is written through to MongoDB immediately so all gunicorn
    workers share the same state and positions survive container restarts.
  - get_position() always reads from MongoDB (cross-worker accuracy at
    webhook time), then syncs the result into the local in-memory dict.
  - get_all_positions() reads from the in-memory dict only (fast path for
    tight monitoring loops — stale by at most one DB write, which is fine).
"""

import logging
import time
from typing import Dict, Optional, Union

logger = logging.getLogger(__name__)


class PositionManager:
    """Manages trading positions, TP levels, and stop-loss"""

    def __init__(self, exchange_client: Union[object], exchange_name: str = 'mexc',
                 exchange_account_id: str = None, account_id: str = None):
        self.client = exchange_client
        self.exchange_name = exchange_name.lower()
        self.exchange_account_id = exchange_account_id
        self.account_id = account_id
        self.active_positions = {}  # symbol -> position_data  (in-memory cache)

        # Load any positions that were open before this worker started
        # (handles restarts and multi-worker consistency on startup)
        self._load_from_db()

    # ------------------------------------------------------------------
    # Internal DB helpers
    # ------------------------------------------------------------------

    def _load_from_db(self):
        """Populate in-memory cache from MongoDB on startup."""
        if not self.exchange_account_id:
            return
        try:
            from mongo_db import get_all_active_positions
            docs = get_all_active_positions(self.exchange_account_id)
            for doc in docs:
                self.active_positions[doc['symbol']] = doc
            if docs:
                logger.info(f"Loaded {len(docs)} active position(s) from DB for {self.exchange_account_id}")
        except Exception as e:
            logger.warning(f"Could not load active positions from DB: {e}")

    def _db_upsert(self, position: Dict):
        """Write the full position doc to MongoDB."""
        if not self.exchange_account_id:
            return
        try:
            from mongo_db import upsert_active_position
            upsert_active_position(position)
        except Exception as e:
            logger.warning(f"Failed to persist position to DB: {e}")

    def _db_update(self, symbol: str, fields: Dict):
        """Partial update — only touch the supplied fields in MongoDB."""
        if not self.exchange_account_id:
            return
        try:
            from mongo_db import update_active_position_fields
            update_active_position_fields(self.exchange_account_id, symbol, fields)
        except Exception as e:
            logger.warning(f"Failed to update position fields in DB: {e}")

    def _db_delete(self, symbol: str):
        """Remove the position document from MongoDB."""
        if not self.exchange_account_id:
            return
        try:
            from mongo_db import delete_active_position
            delete_active_position(self.exchange_account_id, symbol)
        except Exception as e:
            logger.warning(f"Failed to delete position from DB: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_position(self, symbol: str, entry_price: float, side: str,
                        quantity: float, order_id: str) -> Dict:
        """Create a new position record in memory and DB."""
        position = {
            'symbol': symbol,
            'entry_price': entry_price,
            'side': side.upper(),
            'initial_quantity': quantity,
            'remaining_quantity': quantity,
            'entry_order_id': order_id,
            'stop_loss_order_id': None,
            'stop_loss_price': None,
            'tp_orders': {},
            'tp_hit': {
                'tp1': False,
                'tp2': False,
                'tp3': False,
                'tp4': False,
                'tp5': False,
            },
            'stop_loss_moved_to_entry': False,
            'exchange_sl_active': False,
            'created_at': time.time(),
            'exchange_account_id': self.exchange_account_id,
            'account_id': self.account_id,
        }
        self.active_positions[symbol] = position
        self._db_upsert(position)
        logger.info(f"Position created: {symbol} {side} @ {entry_price}, Qty: {quantity}")
        return position

    def get_position(self, symbol: str) -> Optional[Dict]:
        """Return the active position for symbol.

        Always reads from MongoDB so that a signal arriving on a different
        gunicorn worker gets the latest state (e.g. TP already hit by worker 1).
        The result is synced back into the local in-memory dict so monitoring
        threads stay current.
        """
        if not self.exchange_account_id:
            return self.active_positions.get(symbol)
        try:
            from mongo_db import get_active_position
            doc = get_active_position(self.exchange_account_id, symbol)
            if doc:
                self.active_positions[symbol] = doc
                return doc
            # Not in DB — remove stale in-memory entry if present
            self.active_positions.pop(symbol, None)
            return None
        except Exception as e:
            logger.warning(f"DB get_position failed, falling back to memory: {e}")
            return self.active_positions.get(symbol)

    def get_all_positions(self) -> Dict:
        """Return all active positions from the in-memory cache.

        This is the fast path used by monitoring loops (every 2-5 seconds).
        It reflects the latest state because every mutation writes through to
        both memory and DB.
        """
        return self.active_positions.copy()

    def save_position(self, symbol: str):
        """Persist the current in-memory state of a position to DB.

        Call this after any direct dict mutation on the position object
        (e.g. position['stop_loss_price'] = x) that bypasses the named
        mutation methods below.
        """
        position = self.active_positions.get(symbol)
        if position:
            self._db_upsert(position)

    def update_position_quantity(self, symbol: str, closed_quantity: float):
        """Update remaining quantity after a partial close."""
        if symbol in self.active_positions:
            self.active_positions[symbol]['remaining_quantity'] -= closed_quantity
            remaining = self.active_positions[symbol]['remaining_quantity']
            self._db_update(symbol, {'remaining_quantity': remaining})
            logger.info(f"Position updated: {symbol}, Remaining: {remaining}")

    def mark_tp_hit(self, symbol: str, tp_level: str):
        """Mark a take-profit level as hit."""
        if symbol in self.active_positions:
            self.active_positions[symbol]['tp_hit'][tp_level] = True
            self._db_update(symbol, {f'tp_hit.{tp_level}': True})
            logger.info(f"TP {tp_level} hit for {symbol}")

    def mark_stop_loss_moved(self, symbol: str):
        """Mark that the stop-loss has been moved to entry."""
        if symbol in self.active_positions:
            self.active_positions[symbol]['stop_loss_moved_to_entry'] = True
            self._db_update(symbol, {'stop_loss_moved_to_entry': True})
            logger.info(f"Stop-loss moved to entry for {symbol}")

    def close_position(self, symbol: str, exit_reason: str = None):
        """Close position: persist trade to trades collection, remove from active_positions."""
        logger.info(f"close_position called: symbol={symbol}, active_positions={list(self.active_positions.keys())}")
        if symbol not in self.active_positions:
            # Try DB in case another worker opened it
            self.get_position(symbol)

        if symbol in self.active_positions:
            pos = self.active_positions[symbol]
            try:
                from mongo_db import insert_trade
                exit_price = None
                try:
                    exit_price = float(self.client.get_ticker_price(symbol))
                except Exception:
                    pass

                trade_doc = {
                    'exchange_account_id': pos.get('exchange_account_id'),
                    'account_id': pos.get('account_id'),
                    'symbol': pos.get('symbol'),
                    'direction': pos.get('side'),
                    'entry_price': pos.get('entry_price'),
                    'exit_price': exit_price,
                    'stop_loss': pos.get('stop_loss_price'),
                    'tp_hits': [
                        pos['tp_hit'].get('tp1'),
                        pos['tp_hit'].get('tp2'),
                        pos['tp_hit'].get('tp3'),
                        pos['tp_hit'].get('tp4'),
                        pos['tp_hit'].get('tp5'),
                    ],
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
            self._db_delete(symbol)
            logger.info(f"Position closed: {symbol}")
