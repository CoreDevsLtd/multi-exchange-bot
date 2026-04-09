"""
Webhook Handler
Receives and processes TradingView webhook alerts
"""

import json
import logging
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
        self._setup_routes()
    
    def _get_or_create_executors(self):
        """Create executors for all enabled exchange accounts from MongoDB.

        Returns:
            Dict of exchange_account_id -> TradingExecutor
        """
        executor_config = {}
        self._executor_meta = {}
        try:
            from mongo_db import get_enabled_exchange_accounts, get_central_risk
            risk_mgmt = get_central_risk()
            executor_config['STOP_LOSS_PERCENT'] = float(risk_mgmt.get('stop_loss_percent', 5.0))
            executor_config['POSITION_SIZE_PERCENT'] = float(risk_mgmt.get('position_size_percent', 20.0))
            executor_config['POSITION_SIZE_FIXED'] = risk_mgmt.get('position_size_fixed') or None
            use_pct = risk_mgmt.get('use_percentage', True)
            executor_config['USE_PERCENTAGE'] = bool(use_pct) if not isinstance(use_pct, str) else str(use_pct).lower() == 'true'
            executor_config['warn_existing_positions'] = bool(risk_mgmt.get('warn_existing_positions', True))

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
                        client = AlpacaClient(api_key=api_key, api_secret=api_secret, base_url=base_url)
                    elif ex_type == 'ibkr':
                        from ibkr_client import IBKRClient
                        client = IBKRClient(api_key=api_key, api_secret=api_secret, base_url=base_url,
                                            account_id=ex_acc.get('account_id', ''), use_paper=ex_acc.get('use_paper', False),
                                            leverage=ex_acc.get('leverage', 1))
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

                    executors[ex_id] = TradingExecutor(client, executor_config, ex_type, exchange_account_id=ex_id, account_id=ex_acc.get('account_id'))
                    self._executor_meta[ex_id] = ex_acc
                except Exception as e:
                    logger.error(f"Failed to create client for exchange account {ex_id}: {e}", exc_info=True)

            logger.info(f"✅ Created {len(executors)} executor(s) from MongoDB")
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
                self.signal_monitor.add_signal(data if data else {}, executed=False, error=error_msg)
                return jsonify({'status': 'error', 'message': error_msg}), 400
            
            # Get executors for all enabled exchanges
            executors = self._get_or_create_executors()
            
            if executors:
                symbol = signal_data.get('symbol', '')
                symbol_norm = str(symbol).strip().upper().replace(' ', '') if symbol else ''
                # Base form for matching: BTCUSDT.P and BTCUSDT both map to BTCUSDT
                symbol_base = symbol_norm[:-2] if symbol_norm.endswith('.P') else symbol_norm
                logger.info(f"Signal routing: raw_symbol={symbol}, normalized={symbol_norm}, base={symbol_base}")
                # Find executors that should receive this symbol (keyed by exchange_account_id)
                executors_to_use = []
                for ex_acc_id, executor in executors.items():
                    meta = self._executor_meta.get(ex_acc_id, {})
                    symbol_config = meta.get('symbol')
                    if not symbol_config:
                        logger.info(f"Symbol routing: {ex_acc_id} has no configured symbol — skipping")
                        continue
                    # Normalize configured symbol (e.g., "AAPL" or "AAPL.P" for Alpaca)
                    normalized = str(symbol_config).strip().upper().replace(' ', '')
                    allowed_base = normalized[:-2] if normalized.endswith('.P') else normalized
                    logger.info(f"Symbol routing: {ex_acc_id} configured={normalized} (base={allowed_base}) incoming={symbol_base} match={symbol_base == allowed_base if symbol_base else False}")
                    if symbol_base and symbol_base == allowed_base:
                        executors_to_use.append((ex_acc_id, executor))

                if not executors_to_use:
                    msg = f"Symbol {symbol} not configured for any enabled exchange. Add it in Exchanges → Manage Symbols."
                    logger.info(f"ℹ️  {msg}")
                    self.signal_monitor.add_signal(signal_data, executed=False, error=msg)
                    return jsonify({'status': 'skipped', 'message': msg, 'symbol': symbol}), 200
                
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
                
                self.signal_monitor.add_signal(signal_data, executed=any_success, error=first_error if not any_success else None)
                return jsonify({
                    'status': 'success' if any_success else 'error',
                    'message': f"Executed on {sum(1 for r in results if r.get('success'))} of {len(results)} exchange(s)",
                    'results': results
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
                self.signal_monitor.add_signal(signal_data, executed=False, error='No trading executor configured')
                return jsonify({
                    'status': 'received',
                    'message': 'Signal received successfully. Configure exchange API keys to execute trades.',
                    'signal': signal_data,
                    'note': 'No trading executor available - signal logged only'
                }), 200
                
        except Exception as e:
            logger.error(f"Webhook error: {e}", exc_info=True)
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
            
            # Convert crypto symbols to Alpaca format if needed (BTCUSD -> BTC/USD)
            symbol = data.get('symbol', '')
            if symbol and '/' not in symbol:
                # Check if it's a crypto symbol (ends with USD, USDT, or USDC)
                symbol_upper = symbol.upper()
                if symbol_upper.endswith('USD') or symbol_upper.endswith('USDT') or symbol_upper.endswith('USDC'):
                    # Extract base currency (e.g., BTC from BTCUSD or BTCUSDT)
                    base_currency = symbol_upper
                    for suffix in ['USDT', 'USDC', 'USD']:
                        if base_currency.endswith(suffix):
                            base_currency = base_currency[:-len(suffix)]
                            break
                    
                    # Convert to Alpaca crypto format: BTC/USD
                    if base_currency:
                        data['symbol'] = f"{base_currency}/USD"
                        logger.info(f"Converted crypto symbol {symbol} to Alpaca format: {data['symbol']}")
            
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

