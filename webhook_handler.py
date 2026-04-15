"""
Webhook Handler
Receives and processes TradingView webhook alerts
"""

import json
import logging
import threading
import time
from typing import Dict, Optional
from flask import Flask, request, jsonify
import jsonschema
from trading_executor import TradingExecutor
from signal_monitor import SignalMonitor

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles TradingView webhook requests"""
    
    def __init__(self, signal_monitor: Optional[SignalMonitor] = None):
        """
        Initialize Webhook Handler

        Args:
            signal_monitor: Optional SignalMonitor instance
        """
        self.signal_monitor = signal_monitor or SignalMonitor()
        self.app = Flask(__name__)
        self._executors_cache = None  # Cache executors to maintain position state across webhooks
        self._executor_meta = {}
        self._executor_lock = threading.Lock()
        self._executor_cache_time = 0.0   # monotonic timestamp of last build
        _EXECUTOR_CACHE_TTL = 30          # seconds — config changes propagate within this window
        self._EXECUTOR_CACHE_TTL = _EXECUTOR_CACHE_TTL
        self._setup_routes()
    
    def invalidate_executor_cache(self):
        """Discard cached executors so they are rebuilt from DB on the next webhook."""
        with self._executor_lock:
            self._executors_cache = None
            self._executor_meta = {}
            self._executor_cache_time = 0.0
        logger.info("🔄 Executor cache invalidated — will rebuild on next webhook")

    def _get_or_create_executors(self):
        """Create executors for all enabled exchange accounts from MongoDB.
        Executors are cached to maintain position state across webhooks.

        Returns:
            Dict of exchange_account_id -> TradingExecutor
        """
        now = time.monotonic()
        # Fast path — cache is warm and not expired
        if self._executors_cache is not None and (now - self._executor_cache_time) < self._EXECUTOR_CACHE_TTL:
            return self._executors_cache

        with self._executor_lock:
            # Re-check inside the lock: another thread may have built it while we waited
            now = time.monotonic()
            if self._executors_cache is not None and (now - self._executor_cache_time) < self._EXECUTOR_CACHE_TTL:
                return self._executors_cache

            self._executor_meta = {}
            try:
                from mongo_db import get_enabled_exchange_accounts, get_central_risk, get_exchange_risk
                risk_mgmt = get_central_risk()

                accounts = get_enabled_exchange_accounts()
                executors = {}
                for ex_acc in accounts:
                    ex_type = ex_acc.get('type')
                    ex_id = ex_acc.get('_id')
                    creds = ex_acc.get('credentials', {}) or {}
                    api_key = creds.get('api_key') or ex_acc.get('api_key', '')
                    api_secret = creds.get('api_secret') or ex_acc.get('api_secret', '')
                    base_url = ex_acc.get('base_url', '') or ex_acc.get('connection_info', {}).get('base_url', '')
                    try:
                        if ex_type == 'mexc':
                            from mexc_client import MEXCClient
                            client = MEXCClient(api_key=api_key, api_secret=api_secret, base_url=base_url,
                                                sub_account_id=ex_acc.get('sub_account_id', ''),
                                                use_sub_account=ex_acc.get('use_sub_account', False))
                        elif ex_type == 'alpaca':
                            from alpaca_client import AlpacaClient
                            use_paper = bool(ex_acc.get('use_paper', True))
                            default_base = 'https://paper-api.alpaca.markets' if use_paper else 'https://api.alpaca.markets'
                            client = AlpacaClient(api_key=api_key, api_secret=api_secret, base_url=base_url or default_base)
                        elif ex_type == 'ibkr':
                            from ibkr_client import IBKRClient
                            gateway_host = ex_acc.get('gateway_host', '127.0.0.1')
                            gateway_port = int(ex_acc.get('gateway_port', 7497))
                            client_id = int(ex_acc.get('client_id', 1))
                            client = IBKRClient(host=gateway_host, port=gateway_port, client_id=client_id)
                        elif ex_type == 'bybit':
                            from bybit_client import BybitClient
                            proxy = (ex_acc.get('proxy') or '').strip() or None
                            client = BybitClient(api_key=api_key, api_secret=api_secret, base_url=base_url,
                                                 testnet=ex_acc.get('testnet', False),
                                                 trading_mode=ex_acc.get('trading_mode', 'spot'),
                                                 leverage=int(ex_acc.get('leverage', 1)), proxy=proxy)
                        else:
                            logger.warning(f"Unknown exchange type: {ex_type} ({ex_id}) — skipping")
                            continue

                        ex_risk = get_exchange_risk(ex_type, risk_mgmt)
                        executor_config = {
                            'STOP_LOSS_PERCENT': float(ex_risk.get('stop_loss_percent', 5.0)),
                            'TAKE_PROFIT_PERCENT': float(ex_risk.get('take_profit_percent', 5.0)),
                            'POSITION_SIZE_PERCENT': float(ex_risk.get('position_size_percent', 20.0)),
                            'POSITION_SIZE_FIXED': ex_risk.get('position_size_fixed') or None,
                            'USE_PERCENTAGE': (
                                bool(ex_risk.get('use_percentage', True))
                                if not isinstance(ex_risk.get('use_percentage', True), str)
                                else str(ex_risk.get('use_percentage', True)).lower() == 'true'
                            ),
                            'warn_existing_positions': bool(ex_risk.get('warn_existing_positions', True)),
                            'TP_MODE': str(ex_risk.get('tp_mode') or '').lower() or None,
                            'TP1_TARGET': ex_risk.get('tp1_target'),
                            'TP2_TARGET': ex_risk.get('tp2_target'),
                            'TP3_TARGET': ex_risk.get('tp3_target'),
                            'TP4_TARGET': ex_risk.get('tp4_target'),
                            'TP5_TARGET': ex_risk.get('tp5_target'),
                        }
                        executors[ex_id] = TradingExecutor(client, executor_config, ex_type, exchange_account_id=ex_id, account_id=ex_acc.get('account_id'))
                        self._executor_meta[ex_id] = ex_acc
                    except Exception as e:
                        logger.error(f"Failed to create client for exchange account {ex_id}: {e}", exc_info=True)

                logger.info(f"✅ Created {len(executors)} executor(s) from MongoDB")
                self._executors_cache = executors
                self._executor_cache_time = time.monotonic()
                return executors
            except Exception as e:
                logger.error(f"Failed to create executors from MongoDB: {e}", exc_info=True)
                return {}
    
    def _register_routes_to_app(self, target_app):
        """Register webhook routes to an existing Flask app (for integration)"""
        # Copy webhook route to target app
        @target_app.route('/webhook', methods=['POST'])
        def webhook():
            return self._handle_webhook()
        
        @target_app.route('/health', methods=['GET'])
        def health():
            """Health check endpoint"""
            self.signal_monitor.ping_webhook()
            from flask import jsonify
            return jsonify({'status': 'healthy'}), 200

    def _log_webhook(self, log_doc: dict):
        """Log webhook to MongoDB for audit trail (30-day retention via TTL)"""
        try:
            from mongo_db import get_db
            from datetime import datetime
            db = get_db()
            log_doc['timestamp'] = log_doc.get('timestamp') or datetime.utcnow()
            db.webhook_logs.insert_one(log_doc)
        except Exception as e:
            # Log failures should never break webhook processing
            logger.warning(f"Failed to log webhook to MongoDB: {e}")

    @staticmethod
    def _canonical(sym: str) -> str:
        """Canonical form for symbol comparison: uppercase, no spaces, no slashes.

        This lets TradingView-format symbols (DOGEUSDT) match exchange-stored
        symbols that include a slash (DOGE/USDT), since both canonicalize to
        DOGEUSDT.  Quote-currency differences (DOGEUSDT vs DOGEUSD) are still
        distinguished because we only remove the slash, nothing else.
        """
        return str(sym).strip().upper().replace(' ', '').replace('/', '')

    @staticmethod
    def _alpaca_quote_equivalent(sym: str) -> str:
        """Normalize quote variants for Alpaca symbol matching (USDT/USDC -> USD)."""
        s = str(sym).strip().upper()
        if s.endswith('USDT'):
            return f"{s[:-4]}USD"
        if s.endswith('USDC'):
            return f"{s[:-4]}USD"
        return s

    def _select_executors_for_symbol(self, signal_data: dict, executors: dict):
        """Return list[(exchange_account_id, executor)] matching the incoming symbol.

        TradingView uses the .P suffix to indicate a perpetual/futures symbol
        (e.g. BTCUSDT.P = futures, BTCUSDT = spot).  We use this to route the
        signal only to accounts whose trading_mode matches:
          - incoming .P  → futures accounts only
          - incoming bare → non-futures (spot) accounts only
        This prevents a futures signal from firing on a spot account and vice-versa
        when both accounts share the same base symbol (e.g. BTCUSDT).

        Symbol comparison is done in canonical form (slashes stripped) so that
        TradingView's DOGEUSDT matches an Alpaca account configured as DOGE/USDT.
        """
        symbol = signal_data.get('symbol', '')
        symbol_norm = self._canonical(symbol)
        is_futures_signal = symbol_norm.endswith('.P')
        symbol_base = symbol_norm[:-2] if is_futures_signal else symbol_norm
        if not symbol_base:
            return []

        executors_to_use = []
        for ex_acc_id, executor in executors.items():
            meta = self._executor_meta.get(ex_acc_id, {})
            symbol_config = meta.get('symbol')
            if not symbol_config:
                continue

            # Match trading_mode to signal type
            account_mode = (meta.get('trading_mode') or 'spot').lower()
            account_is_futures = (account_mode == 'futures')
            if is_futures_signal != account_is_futures:
                continue  # futures signal → skip spot accounts, and vice-versa

            configured = self._canonical(symbol_config)
            allowed_base = configured[:-2] if configured.endswith('.P') else configured
            # Alpaca only trades USD-quoted crypto pairs. Treat TradingView
            # USDT/USDC symbols as equivalent to USD for account routing.
            ex_type = (meta.get('type') or '').lower()
            compare_signal = symbol_base
            compare_allowed = allowed_base
            if ex_type == 'alpaca':
                compare_signal = self._alpaca_quote_equivalent(compare_signal)
                compare_allowed = self._alpaca_quote_equivalent(compare_allowed)

            if compare_signal == compare_allowed:
                executors_to_use.append((ex_acc_id, executor))
        return executors_to_use

    def _execute_signal_async(self, signal_data: dict, data: dict, executors_to_use: list):
        """Execute signal in background thread"""
        try:
            symbol = signal_data.get('symbol', '')
            symbol_norm = str(symbol).strip().upper().replace(' ', '') if symbol else ''

            if not executors_to_use:
                msg = f"Symbol {symbol} not configured for any enabled exchange. Add it in Exchanges → Manage Symbols."
                logger.info(f"ℹ️  {msg}")
                self._log_webhook({
                    'raw_payload': data or {},
                    'signal': signal_data.get('signal'),
                    'symbol': symbol,
                    'status': 'skipped',
                    'failure_reason': msg,
                    'matched_exchanges': []
                })
                self.signal_monitor.add_signal(signal_data, executed=False, error=msg)
                return

            results = []
            any_success = False
            first_error = None
            for ex_name, executor in executors_to_use:
                try:
                    logger.info(f"🚀 Executing {signal_data.get('signal')} for {symbol_norm or symbol} on {ex_name}")
                    order_response = executor.execute_signal(signal_data)
                    if order_response and isinstance(order_response, dict) and order_response.get('error'):
                        err = order_response['error']
                        results.append({'exchange': ex_name, 'error': err})
                        logger.error(f"❌ {ex_name}: {err}")
                        if first_error is None:
                            first_error = err
                    elif order_response:
                        results.append({'exchange': ex_name, 'success': True, 'order': order_response})
                        any_success = True
                        logger.info(f"✅ {ex_name}: Order executed")
                    else:
                        err = 'Executor returned None (check logs for validation/position-size errors)'
                        results.append({'exchange': ex_name, 'error': err})
                        if first_error is None:
                            first_error = err
                except ValueError as e:
                    err = str(e)
                    results.append({'exchange': ex_name, 'error': err})
                    logger.error(f"❌ {ex_name}: {e}")
                    if first_error is None:
                        first_error = err
                except Exception as e:
                    err = str(e)
                    results.append({'exchange': ex_name, 'error': err})
                    logger.error(f"❌ {ex_name}: {e}", exc_info=True)
                    if first_error is None:
                        first_error = err

            logger.info(f"Execution summary: symbol={symbol_norm or symbol}, selected_exchanges={len(executors_to_use)}, success={any_success}")

            # Build executions array from results
            executions = []
            for r in results:
                executions.append({
                    'exchange_id': r.get('exchange'),
                    'success': r.get('success', False),
                    'order_id': r.get('order', {}).get('order_id') if r.get('order') else None,
                    'error': r.get('error')
                })

            self._log_webhook({
                'raw_payload': data or {},
                'signal': signal_data.get('signal'),
                'symbol': symbol,
                'status': 'success' if any_success else 'failed',
                'matched_exchanges': [ex for ex, _ in executors_to_use],
                'executions': executions,
                'error': None if any_success else first_error,
                'failure_reason': None if any_success else f"Execution failed: {first_error}"
            })
            self.signal_monitor.add_signal(signal_data, executed=any_success, error=first_error if not any_success else None)
        except Exception as e:
            logger.error(f"Background execution failed: {e}", exc_info=True)
            self.signal_monitor.add_signal(signal_data, executed=False, error=str(e))

    def _handle_webhook(self):
        """Handle webhook request (extracted for reuse)"""
        from flask import request, jsonify
        try:
            # Mark webhook as connected
            self.signal_monitor.ping_webhook()

            # Get request data
            data = request.get_json()

            if not data:
                # Try to parse as form data (TradingView sends form data)
                data = request.form.to_dict()
                if 'message' in data:
                    # Parse pipe-delimited message
                    data = self._parse_pipe_message(data)

            logger.info(f"Received webhook: {json.dumps(data, indent=2)}")

            # Validate and parse signal data
            signal_data = self._parse_signal_data(data)
            if signal_data:
                logger.info(f"Processed signal data: {json.dumps(signal_data, indent=2)}")

            if not signal_data:
                error_msg = 'Invalid signal data'
                self._log_webhook({
                    'raw_payload': data or {},
                    'signal': data.get('signal') if data else None,
                    'symbol': data.get('symbol') if data else None,
                    'status': 'error',
                    'failure_reason': error_msg,
                    'matched_exchanges': []
                })
                self.signal_monitor.add_signal(data if data else {}, executed=False, error=error_msg)
                return jsonify({'status': 'error', 'message': error_msg}), 400

            # Get executors for all enabled exchanges
            executors = self._get_or_create_executors()

            if executors:
                executors_to_use = self._select_executors_for_symbol(signal_data, executors)
                matched_exchange_ids = [ex for ex, _ in executors_to_use]
                # Return immediately and process in background
                thread = threading.Thread(
                    target=self._execute_signal_async,
                    args=(signal_data, data, executors_to_use),
                    daemon=True
                )
                thread.start()

                return jsonify({
                    'status': 'success',
                    'message': 'Signal accepted and queued for processing',
                    'results': [],
                    'matched_exchanges': matched_exchange_ids,
                    'matched_count': len(matched_exchange_ids)
                }), 200
            else:
                # Demo mode: simulate trade execution
                from demo_mode import DemoMode
                demo = DemoMode()
                if demo.is_active():
                    # Simulate trade execution
                    price = float(signal_data.get('price', {}).get('close', 0) if isinstance(signal_data.get('price'), dict) else signal_data.get('price', 0))
                    symbol = signal_data.get('symbol', 'BTCUSDT')
                    side = signal_data.get('signal', 'BUY')
                    # Estimate quantity based on typical position size
                    quantity = (1000 / price) if price > 0 else 0.01  # Simulate $1000 trade
                    
                    trade = demo.simulate_trade(symbol, side, price, quantity)
                    logger.info(f"🎮 Demo trade simulated: {trade}")
                    self._log_webhook({
                        'raw_payload': data or {},
                        'signal': signal_data.get('signal'),
                        'symbol': signal_data.get('symbol'),
                        'status': 'success',
                        'matched_exchanges': ['demo'],
                        'executions': [{
                            'exchange_id': 'demo',
                            'success': True,
                            'order_id': trade.get('id') if isinstance(trade, dict) else None
                        }]
                    })
                    self.signal_monitor.add_signal(signal_data, executed=True)
                    return jsonify({
                        'status': 'success',
                        'message': 'Demo trade executed successfully',
                        'order': trade,
                        'demo': True
                    }), 200
                
                # No executor and demo mode not active: Still accept and log the signal
                # This allows testing webhook connectivity even without trading setup
                logger.info(f"📥 Signal received (no executor): {signal_data.get('symbol')} {signal_data.get('signal')} @ {signal_data.get('price', {}).get('close', 'N/A') if isinstance(signal_data.get('price'), dict) else signal_data.get('price', 'N/A')}")
                self._log_webhook({
                    'raw_payload': data or {},
                    'signal': signal_data.get('signal'),
                    'symbol': signal_data.get('symbol'),
                    'status': 'skipped',
                    'failure_reason': 'No trading executor configured',
                    'matched_exchanges': []
                })
                self.signal_monitor.add_signal(signal_data, executed=False, error='No trading executor configured')
                return jsonify({
                    'status': 'received',
                    'message': 'Signal received successfully. Configure exchange API keys to execute trades.',
                    'signal': signal_data,
                    'note': 'No trading executor available - signal logged only'
                }), 200
                
        except Exception as e:
            logger.error(f"Webhook error: {e}", exc_info=True)
            # Log unexpected error to webhook_logs
            try:
                self._log_webhook({
                    'raw_payload': data if 'data' in locals() else {},
                    'signal': None,
                    'symbol': None,
                    'status': 'error',
                    'failure_reason': str(e),
                    'matched_exchanges': []
                })
            except Exception as log_err:
                logger.warning(f"Failed to log webhook error: {log_err}")
            from flask import jsonify
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    def _setup_routes(self):
        """Setup Flask routes"""

        @self.app.route('/webhook', methods=['POST'])
        def webhook():
            """Handle TradingView webhook POST requests"""
            return self._handle_webhook()
        
        @self.app.route('/health', methods=['GET'])
        def health():
            """Health check endpoint"""
            self.signal_monitor.ping_webhook()
            return jsonify({'status': 'healthy'}), 200
        
        @self.app.route('/api/signals/status', methods=['GET'])
        def signals_status():
            """Get signal monitoring status"""
            status = self.signal_monitor.get_status()
            return jsonify(status), 200
        
        @self.app.route('/api/signals/recent', methods=['GET'])
        def recent_signals():
            """Get recent signals"""
            limit = request.args.get('limit', 10, type=int)
            signals = self.signal_monitor.get_recent_signals(limit)
            return jsonify({'signals': signals}), 200
    
    def _parse_pipe_message(self, data: Dict) -> Dict:
        """
        Parse pipe-delimited message from TradingView
        
        Args:
            data: Request data dictionary
            
        Returns:
            Parsed signal data dictionary
        """
        message = data.get('message', '')
        ticker = data.get('ticker', '')
        time_str = data.get('time', '')
        
        # Parse pipe-delimited fields
        fields = {}
        for item in message.split('|'):
            if '=' in item:
                key, value = item.split('=', 1)
                fields[key] = value
        
        # Build signal data structure
        signal_data = {
            'symbol': ticker or fields.get('SYMBOL', ''),
            'time': time_str,
            'timestamp': int(fields.get('TIME', 0)),
            'signal': fields.get('SIGNAL', ''),
            'indicators': {
                'wt': {
                    'flag': fields.get('WT_FLAG', 'false').lower() == 'true',
                    'wt1': float(fields.get('WT1', 0)),
                    'wt2': float(fields.get('WT2', 0)),
                    'cross_type': fields.get('WT_CROSS', 'NONE'),
                    'window_active': fields.get('WT_WINDOW', 'NONE') != 'NONE'
                },
                'bb': {
                    'flag': fields.get('BB_FLAG', 'false').lower() == 'true',
                    'upper': float(fields.get('BB_UPPER', 0)),
                    'lower': float(fields.get('BB_LOWER', 0)),
                    'basis': float(fields.get('BB_BASIS', 0)),
                    'ma_value': float(fields.get('MA_VALUE', 0)),
                    'percent_b': float(fields.get('BB_PERCENT', 0))
                },
                'rsi': {
                    'value': float(fields.get('RSI_VALUE', 0)),
                    'buy_threshold_min': float(fields.get('RSI_BUY_THRESHOLD_MIN', 54.0)),
                    'buy_threshold_max': float(fields.get('RSI_BUY_THRESHOLD_MAX', 82.0)),
                    'sell_threshold_min': float(fields.get('RSI_SELL_THRESHOLD_MIN', 27.0)),
                    'sell_threshold_max': float(fields.get('RSI_SELL_THRESHOLD_MAX', 43.0)),
                    'condition_met': fields.get('RSI_CONDITION', 'false').lower() == 'true'
                }
            },
            'price': {
                'close': float(fields.get('PRICE_CLOSE', 0)),
                'open': float(fields.get('PRICE_OPEN', 0)),
                'high': float(fields.get('PRICE_HIGH', 0)),
                'low': float(fields.get('PRICE_LOW', 0))
            },
            'strategy': {
                'entry_type': fields.get('ENTRY_TYPE', 'NEXT_CANDLE_OPEN'),
                'all_conditions_met': True
            }
        }
        
        return signal_data
    
    def _parse_signal_data(self, data: Dict) -> Optional[Dict]:
        """
        Parse and validate signal data from webhook
        
        Args:
            data: Raw webhook data
            
        Returns:
            Parsed signal data or None if invalid
        """
        # If data is already in JSON format, use it directly
        if 'symbol' in data and 'signal' in data:
            # Ensure required fields are present for validation
            if 'indicators' not in data:
                data['indicators'] = {}
            if 'strategy' not in data:
                data['strategy'] = {'all_conditions_met': True}
            if 'price' not in data:
                # Try to get price from close if available
                close_price = data.get('close') or (data.get('price', {}).get('close') if isinstance(data.get('price'), dict) else 0)
                data['price'] = {'close': close_price}
            
            # Keep symbol as-is - symbol routing handles exchange-specific formats
            # (Bybit uses DOGEUSDT, Alpaca uses DOGE/USD)
            # Symbol conversion is handled per-exchange in their client adapters
            symbol = data.get('symbol', '')
            
            return data
        
        # Otherwise, try to parse from TradingView format
        return self._parse_pipe_message(data)
    
    def run(self, host: str = '0.0.0.0', port: int = 5000, debug: bool = False):
        """
        Run the webhook server
        
        Args:
            host: Host to bind to
            port: Port to listen on
            debug: Enable debug mode
        """
        logger.info(f"Starting webhook server on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug)
