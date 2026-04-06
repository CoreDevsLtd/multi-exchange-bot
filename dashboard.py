"""
Trading Bot Dashboard
Web interface for managing API keys, exchanges, and trading settings
"""

import os
import json
import logging
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import secrets

logger = logging.getLogger(__name__)


class Dashboard:
    """Trading Bot Dashboard"""
    
    def __init__(self, config_file: str = 'dashboard_config.json'):
        """
        Initialize Dashboard
        
        Args:
            config_file: Path to configuration file
        """
        self.app = Flask(__name__, 
                        template_folder='templates',
                        static_folder='static')
        self.config_file = config_file
        self.secret_key = os.getenv('DASHBOARD_SECRET_KEY', secrets.token_hex(32))
        self.app.secret_key = self.secret_key
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize demo mode (disabled by default, enable via DEMO_MODE=true env var)
        from demo_mode import DemoMode
        self.demo_mode = DemoMode()
        # Demo mode will be enabled in main_with_dashboard.py only if DEMO_MODE=true
        logger.info("Demo mode instance created (disabled by default)")
        
        # Setup routes
        self._setup_routes()
    
    def _deep_merge(self, default: dict, loaded: dict) -> dict:
        """
        Deep merge loaded config into default config
        
        Args:
            default: Default configuration dictionary
            loaded: Loaded configuration dictionary
            
        Returns:
            Merged configuration dictionary
        """
        result = default.copy()
        
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = self._deep_merge(result[key], value)
            else:
                # Overwrite with loaded value
                result[key] = value
        
        return result
    
    def _load_config(self) -> dict:
        """Load configuration from file with proper deep merge"""
        default_config = {
            'exchanges': {
                'mexc': {
                    'enabled': False,
                    'api_key': '',
                    'api_secret': '',
                    'base_url': 'https://api.mexc.com',
                    'name': 'MEXC',
                    'paper_trading': False,
                    'sub_account_id': '',  # Optional sub-account ID
                    'use_sub_account': False,
                    # List of allowed symbols for this exchange (e.g. ["BTCUSDT", "ETHUSDT"])
                    'symbols': []
                },
                'alpaca': {
                    'enabled': False,
                    'api_key': '',
                    'api_secret': '',
                    'base_url': 'https://paper-api.alpaca.markets',
                    'name': 'Alpaca',
                    'paper_trading': True,
                    'symbols': []
                },
                'ibkr': {
                    'enabled': False,
                    'api_key': '',
                    'api_secret': '',
                    'base_url': 'https://localhost:5000',
                    'name': 'Interactive Brokers',
                    'account_id': '',
                    'use_paper': False,
                    'leverage': 1,
                    'symbols': []
                },
                'bybit': {
                    'enabled': False,
                    'api_key': '',
                    'api_secret': '',
                    'base_url': 'https://api.bybit.com',
                    'name': 'Bybit',
                    'testnet': False,
                    'trading_mode': 'spot',  # 'spot' or 'futures'
                    'leverage': 1,          # Only used for futures mode
                    'proxy': '',            # Optional: http://host:port for geo-blocked regions
                    'symbols': []
                }
            },
            'trading_settings': {
                'position_size_percent': 20.0,  # Configurable 5-100%, default 20%
                'position_size_fixed': '',
                'use_percentage': True,
                'webhook_port': 5000,
                'webhook_host': '0.0.0.0',
                'warn_existing_positions': True
            },
            'risk_management': {
                'stop_loss_percent': 5.0
            }
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # Deep merge to preserve all saved values
                    default_config = self._deep_merge(default_config, loaded_config)
                    logger.info(f"✅ Configuration loaded from {self.config_file}")
                    # Log loaded exchanges for debugging
                    for exchange_name, exchange_config in default_config.get('exchanges', {}).items():
                        has_key = bool(exchange_config.get('api_key'))
                        has_secret = bool(exchange_config.get('api_secret'))
                        enabled = exchange_config.get('enabled', False)
                        logger.info(f"   {exchange_name}: enabled={enabled}, has_key={has_key}, has_secret={has_secret}")
            except Exception as e:
                logger.error(f"Error loading config: {e}", exc_info=True)
        else:
            logger.info(f"Config file {self.config_file} not found, using defaults")
        
        return default_config
    
    def _save_config(self):
        """Save configuration to file"""
        try:
            # Ensure directory exists
            config_dir = os.path.dirname(os.path.abspath(self.config_file))
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            
            # Save with atomic write (write to temp file, then rename)
            temp_file = f"{self.config_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            # Atomic rename
            if os.path.exists(temp_file):
                if os.path.exists(self.config_file):
                    os.replace(temp_file, self.config_file)
                else:
                    os.rename(temp_file, self.config_file)
            
            logger.info(f"✅ Configuration saved successfully to {self.config_file}")
            # Log saved exchanges for verification
            for exchange_name, exchange_config in self.config.get('exchanges', {}).items():
                has_key = bool(exchange_config.get('api_key'))
                has_secret = bool(exchange_config.get('api_secret'))
                enabled = exchange_config.get('enabled', False)
                logger.info(f"   {exchange_name}: enabled={enabled}, has_key={has_key}, has_secret={has_secret}")
            return True
        except Exception as e:
            logger.error(f"❌ Error saving config: {e}", exc_info=True)
            return False

    def _fetch_market_symbols(self, exchange_name: str, exchange: dict, query: str, limit: int = 30) -> list:
        """
        Fetch symbols from exchange market APIs (Bybit, MEXC, Alpaca).
        Returns symbols matching query (empty query = popular/default symbols).
        """
        try:
            if exchange_name == 'bybit':
                return self._fetch_bybit_symbols(exchange, query, limit)
            if exchange_name == 'mexc':
                return self._fetch_mexc_symbols(exchange, query, limit)
            if exchange_name == 'alpaca':
                return self._fetch_alpaca_symbols(exchange, query, limit)
            if exchange_name == 'ibkr':
                return []  # IBKR requires Gateway; no simple public symbol list
        except Exception as e:
            logger.warning(f"Error fetching market symbols for {exchange_name}: {e}")
        return []

    def _fetch_bybit_symbols(self, exchange: dict, query: str, limit: int) -> list:
        base_url = exchange.get('base_url', 'https://api.bybit.com').rstrip('/')
        if exchange.get('testnet'):
            base_url = 'https://api-testnet.bybit.com'
        mode = (exchange.get('trading_mode') or 'spot').lower()
        category = 'linear' if mode == 'futures' else 'spot'
        url = f"{base_url}/v5/market/instruments-info"
        params = {'category': category}
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        if data.get('retCode') != 0:
            return []
        items = data.get('result', {}).get('list', [])
        symbols = []
        for item in items:
            sym = item.get('symbol', '')
            if sym and item.get('status') == 'Trading':
                symbols.append(sym)
        return self._filter_symbols(symbols, query, limit)

    def _fetch_mexc_symbols(self, exchange: dict, query: str, limit: int) -> list:
        base_url = exchange.get('base_url', 'https://api.mexc.com').rstrip('/')
        resp = requests.get(f"{base_url}/api/v3/exchangeInfo", timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        symbols = []
        for s in data.get('symbols', []):
            if s.get('status') == 'ENABLED':
                symbols.append(s.get('symbol', ''))
        return self._filter_symbols([s for s in symbols if s], query, limit)

    def _fetch_alpaca_symbols(self, exchange: dict, query: str, limit: int) -> list:
        base_url = exchange.get('base_url', 'https://paper-api.alpaca.markets').rstrip('/')
        api_key = exchange.get('api_key', '')
        api_secret = exchange.get('api_secret', '')
        if not api_key or not api_secret or api_secret == '***':
            return []
        headers = {
            'APCA-API-KEY-ID': api_key,
            'APCA-API-SECRET-KEY': api_secret,
        }
        symbols = []
        for asset_class in ('us_equity', 'crypto'):
            resp = requests.get(
                f"{base_url}/v2/assets",
                params={'status': 'active', 'asset_class': asset_class},
                headers=headers,
                timeout=10
            )
            if resp.status_code == 200:
                for a in resp.json():
                    if a.get('tradable'):
                        symbols.append(a.get('symbol', ''))
        return self._filter_symbols([s for s in symbols if s], query, limit)

    def _filter_symbols(self, symbols: list, query: str, limit: int) -> list:
        if query:
            q = query.upper()
            symbols = [s for s in symbols if q in s.upper()]
        return symbols[:limit]


    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            """Dashboard home page"""
            return render_template('dashboard.html', config=self.config)
        
        @self.app.route('/api/exchanges', methods=['GET'])
        def get_exchanges():
            """Get all exchange configurations"""
            return jsonify(self.config['exchanges'])
        
        @self.app.route('/api/exchanges/<exchange_name>', methods=['GET'])
        def get_exchange(exchange_name):
            """Get specific exchange configuration"""
            if exchange_name in self.config['exchanges']:
                exchange_config = self.config['exchanges'][exchange_name].copy()
                # Return actual API key (needed for display)
                # Mask API secret for security (show '***' if secret exists)
                exchange_config['api_secret'] = '***' if exchange_config.get('api_secret') else ''
                # Log what we're returning (for debugging)
                logger.debug(f"📤 Returning exchange config for {exchange_name}:")
                logger.debug(f"   API Key present: {bool(exchange_config.get('api_key'))}")
                logger.debug(f"   API Key length: {len(exchange_config.get('api_key', ''))}")
                logger.debug(f"   API Secret present: {bool(exchange_config.get('api_secret') == '***')}")
                return jsonify(exchange_config)
            return jsonify({'error': 'Exchange not found'}), 404
        
        @self.app.route('/api/exchanges/<exchange_name>', methods=['POST'])
        def update_exchange(exchange_name):
            """Update exchange configuration"""
            if exchange_name not in self.config['exchanges']:
                return jsonify({'error': 'Exchange not found'}), 404
            
            data = request.get_json()
            
            # Update exchange configuration
            exchange = self.config['exchanges'][exchange_name]
            
            # Only update if new values provided (don't overwrite with empty strings)
            if 'enabled' in data:
                exchange['enabled'] = bool(data['enabled'])
            
            if 'api_key' in data:
                # Always update if provided (even if empty, to allow clearing)
                if data['api_key']:
                    # Trim whitespace to prevent signature errors
                    old_key = exchange.get('api_key', '')
                    exchange['api_key'] = data['api_key'].strip()
                    # Log saved key (masked) for verification
                    saved_key = exchange['api_key']
                    masked_key = f"{saved_key[:6]}...{saved_key[-4:]}" if len(saved_key) > 10 else "***"
                    logger.info(f"💾 Saved {exchange_name} API Key: {masked_key} (length: {len(saved_key)})")
                    if old_key and old_key != saved_key:
                        logger.info(f"   Previous key: {old_key[:6]}...{old_key[-4:] if len(old_key) > 10 else '***'}")
                else:
                    # Allow clearing the key
                    exchange['api_key'] = ''
                    logger.info(f"💾 Cleared {exchange_name} API Key")
            
            if 'api_secret' in data:
                # Only update if not masked and not empty
                if data['api_secret'] and data['api_secret'] != '***':
                    # Trim whitespace to prevent signature errors
                    old_secret = exchange.get('api_secret', '')
                    exchange['api_secret'] = data['api_secret'].strip()
                    # Log saved secret (masked) for verification
                    saved_secret = exchange['api_secret']
                    masked_secret = f"{saved_secret[:6]}...{saved_secret[-4:]}" if len(saved_secret) > 10 else "***"
                    logger.info(f"💾 Saved {exchange_name} API Secret: {masked_secret} (length: {len(saved_secret)})")
                    if old_secret and old_secret != saved_secret:
                        logger.info(f"   Previous secret: {old_secret[:6]}...{old_secret[-4:] if len(old_secret) > 10 else '***'}")
                elif data['api_secret'] == '':
                    # Allow clearing the secret
                    exchange['api_secret'] = ''
                    logger.info(f"💾 Cleared {exchange_name} API Secret")
                # If '***', do nothing (keep existing secret)
            
            if 'base_url' in data:
                exchange['base_url'] = data['base_url']
            
            if 'paper_trading' in data:
                exchange['paper_trading'] = bool(data['paper_trading'])
            
            if 'sub_account_id' in data:
                exchange['sub_account_id'] = data['sub_account_id']
            
            if 'use_sub_account' in data:
                exchange['use_sub_account'] = bool(data['use_sub_account'])
            
            # Generic leverage setting (IBKR futures / Bybit futures, etc.)
            if 'leverage' in data:
                leverage = int(data['leverage']) if data['leverage'] else 1
                # Ensure leverage is between 1 and 100
                exchange['leverage'] = max(1, min(100, leverage))
            
            if 'account_id' in data:
                exchange['account_id'] = data['account_id']
            
            if 'use_paper' in data:
                exchange['use_paper'] = bool(data['use_paper'])
            
            # Bybit specific settings
            if 'testnet' in data:
                exchange['testnet'] = bool(data['testnet'])

            # Trading mode (for exchanges that support spot/futures, e.g. Bybit)
            if 'trading_mode' in data:
                mode_val = str(data['trading_mode']).lower() if data['trading_mode'] is not None else 'spot'
                if mode_val not in ['spot', 'futures']:
                    mode_val = 'spot'
                exchange['trading_mode'] = mode_val

            # Bybit proxy (for geo-blocked regions)
            if 'proxy' in data and exchange_name == 'bybit':
                exchange['proxy'] = (data['proxy'] or '').strip()

            # Optional: update allowed symbols list if provided (array of strings)
            if 'symbols' in data and isinstance(data['symbols'], list):
                # Normalize symbols: strip whitespace, upper-case, remove empties and duplicates
                normalized_symbols = []
                seen = set()
                for sym in data['symbols']:
                    if not isinstance(sym, str):
                        continue
                    clean = sym.strip().upper()
                    if not clean or clean in seen:
                        continue
                    normalized_symbols.append(clean)
                    seen.add(clean)
                exchange['symbols'] = normalized_symbols
            
            # Save configuration
            if self._save_config():
                return jsonify({'status': 'success', 'message': 'Exchange updated successfully'})
            else:
                return jsonify({'error': 'Failed to save configuration'}), 500
        
        @self.app.route('/api/exchanges/<exchange_name>/toggle', methods=['POST'])
        def toggle_exchange(exchange_name):
            """Enable/disable exchange"""
            if exchange_name not in self.config['exchanges']:
                return jsonify({'error': 'Exchange not found'}), 404
            
            data = request.get_json()
            enabled = data.get('enabled', False)
            
            self.config['exchanges'][exchange_name]['enabled'] = enabled
            
            if self._save_config():
                return jsonify({
                    'status': 'success',
                    'message': f"Exchange {'enabled' if enabled else 'disabled'} successfully",
                    'enabled': enabled
                })
            else:
                return jsonify({'error': 'Failed to save configuration'}), 500

        @self.app.route('/api/exchanges/<exchange_name>/market-symbols', methods=['GET'])
        def search_market_symbols(exchange_name):
            """
            Search symbols from the exchange's market (TradingView-style).
            GET: ?q=btc returns matching symbols from exchange instruments.
            """
            if exchange_name not in self.config['exchanges']:
                return jsonify({'error': 'Exchange not found'}), 404

            exchange = self.config['exchanges'][exchange_name]
            query = (request.args.get('q') or '').strip().upper()
            symbols = self._fetch_market_symbols(exchange_name, exchange, query)
            return jsonify({'symbols': symbols})

        @self.app.route('/api/exchanges/<exchange_name>/symbols', methods=['GET', 'POST'])
        def manage_exchange_symbols(exchange_name):
            """
            Get or update allowed symbols for a specific exchange.
            
            GET: Returns { "symbols": [...] }
            POST: Accepts { "symbols": [...] } and replaces the list.
            """
            if exchange_name not in self.config['exchanges']:
                return jsonify({'error': 'Exchange not found'}), 404

            exchange = self.config['exchanges'][exchange_name]

            if request.method == 'GET':
                symbols = exchange.get('symbols', [])
                # Ensure list of strings
                safe_symbols = [str(s) for s in symbols]
                return jsonify({
                    'exchange': exchange_name,
                    'name': exchange.get('name', exchange_name),
                    'symbols': safe_symbols
                })

            # POST: update symbols list
            data = request.get_json() or {}
            symbols = data.get('symbols', [])

            if not isinstance(symbols, list):
                return jsonify({'error': 'symbols must be a list of strings'}), 400

            normalized_symbols = []
            seen = set()
            for sym in symbols:
                if not isinstance(sym, str):
                    continue
                clean = sym.strip().upper()
                if not clean or clean in seen:
                    continue
                normalized_symbols.append(clean)
                seen.add(clean)

            exchange['symbols'] = normalized_symbols

            if self._save_config():
                logger.info(f"✅ Updated symbols for {exchange_name}: {normalized_symbols}")
                return jsonify({
                    'status': 'success',
                    'message': f"Symbols updated for {exchange_name}",
                    'symbols': normalized_symbols
                })
            else:
                return jsonify({'error': 'Failed to save configuration'}), 500
        
        @self.app.route('/api/trading-settings', methods=['GET'])
        def get_trading_settings():
            """Get trading settings"""
            return jsonify(self.config['trading_settings'])
        
        @self.app.route('/api/trading-settings', methods=['POST'])
        def update_trading_settings():
            """Update trading settings"""
            data = request.get_json()
            allowed_keys = {'position_size_percent', 'position_size_fixed', 'use_percentage', 
                          'warn_existing_positions', 'webhook_port', 'webhook_host'}
            
            for key, value in data.items():
                if key not in allowed_keys:
                    continue
                if key == 'position_size_percent':
                    try:
                        position_size = float(value) if value else 20.0
                        self.config['trading_settings'][key] = max(5.0, min(100.0, position_size))
                    except ValueError:
                        pass
                elif key == 'position_size_fixed':
                    try:
                        self.config['trading_settings'][key] = float(value) if value else ''
                    except ValueError:
                        pass
                elif key == 'use_percentage':
                    self.config['trading_settings'][key] = bool(value)
                else:
                    self.config['trading_settings'][key] = value
            
            if self._save_config():
                return jsonify({'status': 'success', 'message': 'Trading settings updated successfully'})
            else:
                return jsonify({'error': 'Failed to save configuration'}), 500
        
        @self.app.route('/api/risk-management', methods=['GET'])
        def get_risk_management():
            """Get risk management settings"""
            return jsonify(self.config['risk_management'])
        
        @self.app.route('/api/risk-management', methods=['POST'])
        def update_risk_management():
            """Update risk management settings"""
            data = request.get_json()
            
            # Update risk management settings
            for key, value in data.items():
                if key in self.config['risk_management']:
                    try:
                        self.config['risk_management'][key] = float(value)
                    except ValueError:
                        pass
            
            if self._save_config():
                return jsonify({'status': 'success', 'message': 'Risk management settings updated successfully'})
            else:
                return jsonify({'error': 'Failed to save configuration'}), 500
        
        @self.app.route('/api/exchanges/status', methods=['GET'])
        def get_exchanges_status():
            """Get connection status and balances for all exchanges"""
            status = {}
            
            # Check if demo mode is active
            if self.demo_mode.is_active():
                # Return demo data for MEXC
                demo_status = self.demo_mode.get_demo_connection_status()
                demo_balances = self.demo_mode.get_demo_balances()
                
                status['mexc'] = {
                    'name': 'MEXC',
                    'enabled': True,
                    'connected': demo_status['connected'],
                    'can_trade': demo_status['can_trade'],
                    'balances': demo_balances,
                    'demo_mode': True
                }
                return jsonify(status)
            
            # Check all configured exchanges
            for exchange_name, exchange_config in self.config['exchanges'].items():
                exchange_status = {
                    'name': exchange_config.get('name', exchange_name),
                    'enabled': exchange_config.get('enabled', False),
                    'connected': False,
                    'can_trade': False,
                    'balances': {}
                }
                
                # Check if we can validate: API keys, or IBKR (Gateway session — keys optional)
                can_validate = (exchange_config.get('api_key') and exchange_config.get('api_secret')) or exchange_name == 'ibkr'
                if can_validate:
                    try:
                        if exchange_name == 'mexc':
                            from mexc_client import MEXCClient
                            try:
                                # Trim whitespace to prevent signature errors
                                api_key = exchange_config['api_key'].strip()
                                api_secret = exchange_config['api_secret'].strip()
                                client = MEXCClient(
                                    api_key=api_key,
                                    api_secret=api_secret,
                                    base_url=exchange_config.get('base_url', 'https://api.mexc.com'),
                                    sub_account_id=exchange_config.get('sub_account_id', ''),
                                    use_sub_account=exchange_config.get('use_sub_account', False)
                                )
                                validation = client.validate_connection()
                                exchange_status['connected'] = validation['connected']
                                exchange_status['can_trade'] = validation['can_trade']
                                if validation['connected']:
                                    # Always fetch and return balances (even if empty/zero)
                                    balances = client.get_main_balances()
                                    exchange_status['balances'] = balances  # Will be {} if all zero
                                    logger.info(f"✅ {exchange_name} connected - Balances: {len(balances)} assets")
                                else:
                                    # Not connected, set balances to null (not empty object)
                                    exchange_status['balances'] = None
                                # Don't set error message - UI will just show "Not connected"
                            except Exception as e:
                                logger.error(f"Error validating MEXC connection: {e}", exc_info=True)
                                exchange_status['connected'] = False
                                # Don't set error message - UI will just show "Not connected"
                        elif exchange_name == 'alpaca':
                            from alpaca_client import AlpacaClient
                            try:
                                # Trim whitespace to prevent errors
                                api_key = exchange_config['api_key'].strip()
                                api_secret = exchange_config['api_secret'].strip()
                                client = AlpacaClient(
                                    api_key=api_key,
                                    api_secret=api_secret,
                                    base_url=exchange_config.get('base_url', 'https://paper-api.alpaca.markets')
                                )
                                validation = client.validate_connection()
                                exchange_status['connected'] = validation['connected']
                                exchange_status['can_trade'] = validation['can_trade']
                                if validation['connected']:
                                    # Always fetch and return balances (even if empty/zero)
                                    balances = client.get_main_balances()
                                    exchange_status['balances'] = balances  # Will be {} if all zero
                                    logger.info(f"✅ {exchange_name} connected - Balances: {len(balances)} assets")
                                else:
                                    # Not connected, set balances to null (not empty object)
                                    exchange_status['balances'] = None
                                # Don't set error message - UI will just show "Not connected"
                            except Exception as e:
                                logger.error(f"Error validating Alpaca connection: {e}", exc_info=True)
                                exchange_status['connected'] = False
                                # Don't set error message - UI will just show "Not connected"
                        elif exchange_name == 'ibkr':
                            from ibkr_client import IBKRClient
                            try:
                                api_key = (exchange_config.get('api_key') or '').strip()
                                api_secret = (exchange_config.get('api_secret') or '').strip()
                                ibkr_base = (exchange_config.get('base_url') or 'https://localhost:5000').rstrip('/')
                                client = IBKRClient(
                                    api_key=api_key,
                                    api_secret=api_secret,
                                    base_url=ibkr_base,
                                    account_id=exchange_config.get('account_id', ''),
                                    use_paper=exchange_config.get('use_paper', False),
                                    leverage=exchange_config.get('leverage', 1)
                                )
                                validation = client.validate_connection()
                                exchange_status['connected'] = validation['connected']
                                exchange_status['can_trade'] = validation['can_trade']
                                if validation['connected']:
                                    # Always fetch and return balances (even if empty/zero)
                                    balances = client.get_main_balances()
                                    exchange_status['balances'] = balances  # Will be {} if all zero
                                    logger.info(f"✅ {exchange_name} connected - Balances: {len(balances)} assets")
                                else:
                                    # Not connected, set balances to null (not empty object)
                                    exchange_status['balances'] = None
                                # Don't set error message - UI will just show "Not connected"
                            except Exception as e:
                                logger.error(f"Error validating IBKR connection: {e}", exc_info=True)
                                exchange_status['connected'] = False
                                # Don't set error message - UI will just show "Not connected"
                        elif exchange_name == 'bybit':
                            from bybit_client import BybitClient
                            try:
                                # Trim whitespace to prevent errors
                                api_key = exchange_config['api_key'].strip()
                                api_secret = exchange_config['api_secret'].strip()
                                proxy = (exchange_config.get('proxy') or '').strip() or None
                                client = BybitClient(
                                    api_key=api_key,
                                    api_secret=api_secret,
                                    base_url=exchange_config.get('base_url', 'https://api.bybit.com'),
                                    testnet=exchange_config.get('testnet', False),
                                    trading_mode=exchange_config.get('trading_mode', 'spot'),
                                    leverage=exchange_config.get('leverage', 1),
                                    proxy=proxy
                                )
                                validation = client.validate_connection()
                                exchange_status['connected'] = validation['connected']
                                exchange_status['can_trade'] = validation['can_trade']
                                if validation['connected']:
                                    # Always fetch and return balances (even if empty/zero)
                                    balances = client.get_main_balances()
                                    exchange_status['balances'] = balances  # Will be {} if all zero
                                    logger.info(f"✅ {exchange_name} connected - Balances: {len(balances)} assets")
                                else:
                                    # Not connected, set balances to null (not empty object)
                                    exchange_status['balances'] = None
                                # Don't set error message - UI will just show "Not connected"
                            except Exception as e:
                                logger.error(f"Error validating Bybit connection: {e}", exc_info=True)
                                exchange_status['connected'] = False
                                # Don't set error message - UI will just show "Not connected"
                        else:
                            # Don't set error message - UI will just show "Not connected"
                            pass
                    except Exception as e:
                        logger.error(f"Error checking {exchange_name}: {e}")
                        # Don't set error message - UI will just show "Not connected"
                
                status[exchange_name] = exchange_status
            
            return jsonify(status)
        
        @self.app.route('/api/test-connection/<exchange_name>', methods=['POST'])
        def test_connection(exchange_name):
            """Test exchange API connection. Accepts optional JSON body with api_key, api_secret, etc. for testing before save."""
            exchange_name = exchange_name.lower()
            if exchange_name not in self.config['exchanges']:
                return jsonify({'error': 'Exchange not found'}), 404
            
            exchange = self.config['exchanges'][exchange_name]
            data = request.get_json(silent=True) or {}
            
            # Use request body credentials if provided, else saved config
            api_key = (data.get('api_key') or exchange.get('api_key') or '').strip()
            api_secret = (data.get('api_secret') or exchange.get('api_secret') or '').strip()
            if data.get('api_secret') == '***':
                api_secret = (exchange.get('api_secret') or '').strip()  # Keep existing when masked
            base_url = data.get('base_url') or exchange.get('base_url', 'https://api.bybit.com')
            
            # IBKR uses IB Gateway/TWS session auth — no API keys required
            if exchange_name != 'ibkr':
                if not api_key or not api_secret or api_secret == '***':
                    return jsonify({'error': 'API key and secret required. Enter both in the form and save, or re-enter the secret if it shows ***.'}), 400
            
            try:
                if exchange_name == 'mexc':
                    from mexc_client import MEXCClient
                    logger.info(f"🧪 Testing {exchange_name} connection (API Key: {api_key[:6]}...{api_key[-4:]})")
                    client = MEXCClient(
                        api_key=api_key,
                        api_secret=api_secret,
                        base_url=base_url or exchange.get('base_url', 'https://api.mexc.com')
                    )
                    validation = client.validate_connection()
                    if validation['connected']:
                        return jsonify({
                            'status': 'success',
                            'message': 'Connection successful',
                            'can_trade': validation['can_trade'],
                            'balances': client.get_main_balances()
                        })
                    else:
                        return jsonify({
                            'status': 'error',
                            'error': validation.get('error', 'Connection failed')
                        }), 500
                elif exchange_name == 'alpaca':
                    from alpaca_client import AlpacaClient
                    logger.info(f"🧪 Testing {exchange_name} connection (API Key: {api_key[:6]}...{api_key[-4:]})")
                    client = AlpacaClient(
                        api_key=api_key,
                        api_secret=api_secret,
                        base_url=base_url or exchange.get('base_url', 'https://paper-api.alpaca.markets')
                    )
                    validation = client.validate_connection()
                    if validation['connected']:
                        return jsonify({
                            'status': 'success',
                            'message': 'Connection successful',
                            'can_trade': validation['can_trade'],
                            'balances': client.get_main_balances()
                        })
                    else:
                        return jsonify({
                            'status': 'error',
                            'error': validation.get('error', 'Connection failed')
                        }), 500
                elif exchange_name == 'bybit':
                    from bybit_client import BybitClient
                    testnet = data.get('testnet') if 'testnet' in data else exchange.get('testnet', False)
                    trading_mode = data.get('trading_mode') or exchange.get('trading_mode', 'spot')
                    leverage = int(data.get('leverage') or exchange.get('leverage', 1))
                    proxy = (data.get('proxy') or exchange.get('proxy') or '').strip() or None
                    logger.info(f"🧪 Testing Bybit: base_url={base_url or exchange.get('base_url')}, testnet={testnet}, mode={trading_mode}, proxy={'yes' if proxy else 'no'}")
                    client = BybitClient(
                        api_key=api_key,
                        api_secret=api_secret,
                        base_url=(base_url or exchange.get('base_url', 'https://api.bybit.com')).rstrip('/'),
                        testnet=testnet,
                        trading_mode=trading_mode,
                        leverage=leverage,
                        proxy=proxy
                    )
                    validation = client.validate_connection()
                    if validation['connected']:
                        return jsonify({
                            'status': 'success',
                            'message': 'Connection successful',
                            'can_trade': validation['can_trade'],
                            'balances': client.get_main_balances()
                        })
                    else:
                        return jsonify({
                            'status': 'error',
                            'error': validation.get('error', 'Connection failed')
                        }), 500
                elif exchange_name == 'ibkr':
                    from ibkr_client import IBKRClient
                    ibkr_base = (base_url or exchange.get('base_url') or 'https://localhost:5000').rstrip('/')
                    logger.info(f"🧪 Testing IBKR / Gateway at {ibkr_base} (session auth — open Gateway login in browser first)")
                    client = IBKRClient(
                        api_key=api_key or '',
                        api_secret=api_secret or '',
                        base_url=ibkr_base,
                        account_id=data.get('account_id') or exchange.get('account_id', ''),
                        use_paper=data.get('use_paper') if 'use_paper' in data else exchange.get('use_paper', False),
                        leverage=int(data.get('leverage') or exchange.get('leverage', 1))
                    )
                    validation = client.validate_connection()
                    if validation['connected']:
                        return jsonify({
                            'status': 'success',
                            'message': 'Connection successful',
                            'can_trade': validation['can_trade'],
                            'balances': client.get_main_balances()
                        })
                    else:
                        return jsonify({
                            'status': 'error',
                            'error': validation.get('error', 'Connection failed')
                        }), 500
                else:
                    return jsonify({'error': 'Exchange not supported'}), 400
                    
            except Exception as e:
                logger.error(f"Connection test failed: {e}")
                return jsonify({
                    'error': 'Connection failed',
                    'message': str(e)
                }), 500
        
        @self.app.route('/api/status', methods=['GET'])
        def get_status():
            """Get bot status"""
            if self.demo_mode.is_active():
                demo_stats = self.demo_mode.get_demo_stats()
                return jsonify({
                    'exchanges_enabled': ['mexc'],
                    'total_exchanges': 1,
                    'position_size': self.config['trading_settings'].get('position_size_percent', 0),
                    'demo_mode': True,
                    'demo_stats': demo_stats
                })
            
            enabled_exchanges = [
                name for name, config in self.config['exchanges'].items()
                if config.get('enabled', False)
            ]
            
            return jsonify({
                'exchanges_enabled': enabled_exchanges,
                'total_exchanges': len(self.config['exchanges']),
                'position_size': self.config['trading_settings'].get('position_size_percent', 0),
                'demo_mode': False
            })
        
        @self.app.route('/api/demo/trades', methods=['GET'])
        def get_demo_trades():
            """Get demo trades"""
            limit = request.args.get('limit', 10, type=int)
            trades = self.demo_mode.get_demo_trades(limit)
            return jsonify({'trades': trades, 'demo_mode': True})
        
        @self.app.route('/api/demo/positions', methods=['GET'])
        def get_demo_positions():
            """Get demo positions"""
            positions = self.demo_mode.get_demo_positions()
            return jsonify({'positions': positions, 'demo_mode': True})
        
        @self.app.route('/api/demo/stats', methods=['GET'])
        def get_demo_stats():
            """Get demo statistics"""
            stats = self.demo_mode.get_demo_stats()
            return jsonify({'stats': stats, 'demo_mode': True})
        
        @self.app.route('/api/demo/toggle', methods=['POST'])
        def toggle_demo_mode():
            """Toggle demo mode on/off"""
            data = request.get_json() or {}
            enable = data.get('enable', True)
            
            if enable:
                self.demo_mode.enable()
                return jsonify({'status': 'success', 'message': 'Demo mode enabled', 'demo_mode': True})
            else:
                self.demo_mode.disable()
                return jsonify({'status': 'success', 'message': 'Demo mode disabled', 'demo_mode': False})
        
        @self.app.route('/api/signals/status', methods=['GET'])
        def signals_status():
            """Get signal monitoring status (use signal_monitor directly since webhook is integrated)"""
            # Use signal_monitor directly since webhook routes are integrated into this Flask app
            if hasattr(self, 'signal_monitor') and self.signal_monitor:
                status = self.signal_monitor.get_status()
                # If signals have been received, mark as connected
                if status.get('total_signals', 0) > 0 or status.get('webhook_status') == 'connected':
                    status['webhook_status'] = 'connected'
                return jsonify(status), 200
            
            # Fallback if signal_monitor not available
            return jsonify({
                'webhook_status': 'disconnected',
                'total_signals': 0,
                'successful_trades': 0,
                'failed_trades': 0,
                'error': 'Signal monitor not initialized'
            }), 200
        
        @self.app.route('/api/signals/recent', methods=['GET'])
        def recent_signals():
            """Get recent signals from the last 24 hours (use signal_monitor directly since webhook is integrated)"""
            # Use signal_monitor directly since webhook routes are integrated into this Flask app
            if hasattr(self, 'signal_monitor') and self.signal_monitor:
                limit = request.args.get('limit', 100, type=int)  # Increased default limit to show more signals
                hours = request.args.get('hours', 24.0, type=float)  # Default: last 24 hours
                # Get signals from last 24 hours (or specified hours)
                signals = self.signal_monitor.get_recent_signals(limit=limit, hours=hours)
                return jsonify({'signals': signals}), 200
            
            # Fallback if signal_monitor not available
            return jsonify({'signals': []}), 200
    
    def run(self, host: str = '0.0.0.0', port: int = 8080, debug: bool = False):
        """
        Run the dashboard server
        
        Args:
            host: Host to bind to
            port: Port to listen on
            debug: Enable debug mode
        """
        logger.info(f"Starting dashboard on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug)

