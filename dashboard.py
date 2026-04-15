"""
Trading Bot Dashboard
Web interface for managing API keys, exchanges, and trading settings
"""

import os
import logging
import time
import requests
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, jsonify
import secrets

logger = logging.getLogger(__name__)

# Module-level cache for Alpaca assets to avoid fetching thousands of records on every keystroke.
# Key: exchange_account_id, Value: {'symbols': [...], 'ts': epoch_seconds}
_alpaca_symbol_cache: dict = {}
_ALPACA_CACHE_TTL = 3600  # 1 hour


def _portfolio_date_range_from_request(req) -> tuple[str, str]:
    """
    Build ISO date-time bounds for portfolio queries.
    Defaults to last 30 days if no explicit date range is provided.
    """
    start_raw = (req.args.get('start_date') or '').strip()
    end_raw = (req.args.get('end_date') or '').strip()

    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=30)
    end_dt = now

    try:
        if start_raw:
            start_dt = datetime.strptime(start_raw, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except Exception:
        pass

    try:
        if end_raw:
            end_dt = datetime.strptime(end_raw, '%Y-%m-%d').replace(
                tzinfo=timezone.utc, hour=23, minute=59, second=59
            )
    except Exception:
        pass

    if end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt

    return (
        start_dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
        end_dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
    )


def _exchange_label(db, exchange_account_id: str) -> str:
    """Return a human-readable label for an exchange account."""
    if not exchange_account_id:
        return 'Unknown'
    try:
        ea = db.exchange_accounts.find_one(
            {'_id': exchange_account_id},
            {'type': 1, 'trading_mode': 1, 'account_id': 1}
        )
        if not ea:
            return exchange_account_id
        ex_type = (ea.get('type') or 'exchange').upper()
        account_name = None
        account_id = ea.get('account_id')
        if account_id:
            acc = db.accounts.find_one({'_id': account_id}, {'name': 1})
            if acc:
                account_name = acc.get('name')
        left = str(account_name or account_id or 'Unknown Account').strip()
        return f'{left} - {ex_type} - {exchange_account_id}'
    except Exception:
        return exchange_account_id


def _compute_drawdown_profit(trade: dict, db) -> tuple:
    """
    Compute max drawdown % and max profit % for a closed trade on demand (REQ-3.5).

    Fetches OHLCV candles from the exchange that executed the trade, covering the
    trade's open-to-close window, then calculates:
      - For LONG  (BUY):  max_profit = (peak_high - entry) / entry * 100
                          max_drawdown = (entry - trough_low) / entry * 100
      - For SHORT (SELL): max_profit = (entry - trough_low) / entry * 100
                          max_drawdown = (peak_high - entry) / entry * 100

    Returns (max_drawdown_pct, max_profit_pct) both rounded to 2dp, or (None, None)
    on any failure.
    """
    entry = float(trade.get('entry_price') or 0)
    if entry <= 0:
        return None, None

    symbol = trade.get('symbol', '')
    direction = (trade.get('direction') or '').upper()
    ts_open = trade.get('timestamp_open')
    ts_close = trade.get('timestamp_close')
    exchange_account_id = trade.get('exchange_account_id')

    if not (symbol and ts_open and ts_close):
        return None, None

    # Look up exchange account to get credentials and type
    ex_acc = db.exchange_accounts.find_one({'_id': exchange_account_id}) if exchange_account_id else None
    if not ex_acc:
        # Try to find any account that trades this symbol
        ex_acc = db.exchange_accounts.find_one({'symbol': symbol, 'enabled': True})
    if not ex_acc:
        return None, None

    ex_type = (ex_acc.get('type') or '').lower()

    try:
        from datetime import datetime as _dt
        t_open  = _dt.fromisoformat(ts_open.replace('Z', '+00:00'))
        t_close = _dt.fromisoformat(ts_close.replace('Z', '+00:00'))
        # Add small buffer around trade window
        start_iso = t_open.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_iso   = t_close.strftime('%Y-%m-%dT%H:%M:%SZ')
        start_ms  = int(t_open.timestamp() * 1000)
        end_ms    = int(t_close.timestamp() * 1000)
    except Exception:
        return None, None

    highs = []
    lows  = []

    try:
        from secrets_manager import decrypt_credentials_dict
        creds = decrypt_credentials_dict((ex_acc.get('credentials') or {}))
    except Exception:
        creds = ex_acc.get('credentials') or {}

    api_key    = creds.get('api_key') or ex_acc.get('api_key', '')
    api_secret = creds.get('api_secret') or ex_acc.get('api_secret', '')

    if ex_type == 'bybit':
        try:
            from bybit_client import BybitClient
            client = BybitClient(
                api_key=api_key, api_secret=api_secret,
                base_url=(ex_acc.get('base_url') or 'https://api.bybit.com').rstrip('/'),
                testnet=ex_acc.get('testnet', False),
                trading_mode=ex_acc.get('trading_mode', 'spot'),
            )
            candles = client.get_klines(symbol, start_ms, end_ms)
            # candle format: [startTime, open, high, low, close, volume, turnover]
            highs = [float(c[2]) for c in candles if len(c) >= 5]
            lows  = [float(c[3]) for c in candles if len(c) >= 5]
        except Exception as e:
            logger.warning(f"Bybit candle fetch failed: {e}")
            return None, None

    elif ex_type == 'alpaca':
        try:
            from alpaca_client import AlpacaClient
            client = AlpacaClient(
                api_key=api_key, api_secret=api_secret,
                base_url=ex_acc.get('base_url') or 'https://paper-api.alpaca.markets',
            )
            bars = client.get_bars(symbol, start_iso, end_iso)
            highs = [float(b['h']) for b in bars if 'h' in b]
            lows  = [float(b['l']) for b in bars if 'l' in b]
        except Exception as e:
            logger.warning(f"Alpaca bars fetch failed: {e}")
            return None, None
    else:
        return None, None

    if not highs or not lows:
        return None, None

    peak_high   = max(highs)
    trough_low  = min(lows)

    if direction == 'BUY':
        max_profit_pct   = round((peak_high - entry) / entry * 100, 2)
        max_drawdown_pct = round((entry - trough_low) / entry * 100, 2)
    else:  # SELL / SHORT
        max_profit_pct   = round((entry - trough_low) / entry * 100, 2)
        max_drawdown_pct = round((peak_high - entry) / entry * 100, 2)

    # Clamp drawdown to 0 minimum (price never went against us)
    max_drawdown_pct = max(0.0, max_drawdown_pct)
    max_profit_pct   = max(0.0, max_profit_pct)

    return max_drawdown_pct, max_profit_pct


class Dashboard:
    """Trading Bot Dashboard"""

    def __init__(self):
        self.app = Flask(__name__,
                         template_folder='templates',
                         static_folder='static')
        self.secret_key = os.getenv('DASHBOARD_SECRET_KEY', secrets.token_hex(32))
        self.app.secret_key = self.secret_key

        # Load trading settings from MongoDB central_risk_management
        self.config = self._load_config_from_mongo()

        # Ensure MongoDB indexes
        try:
            from mongo_db import ensure_indexes
            ensure_indexes()
        except Exception as e:
            logger.warning(f"Could not ensure MongoDB indexes: {e}")

        # Initialize demo mode (opt-in via DEMO_MODE=true env var)
        from demo_mode import DemoMode
        self.demo_mode = DemoMode()
        self.webhook_handler = None  # set by wsgi.py after WebhookHandler is created

        self._setup_routes()

    def _invalidate_executors(self):
        """Invalidate WebhookHandler executor cache after any exchange account change."""
        if self.webhook_handler and hasattr(self.webhook_handler, 'invalidate_executor_cache'):
            self.webhook_handler.invalidate_executor_cache()
    
    def _load_config_from_mongo(self) -> dict:
        """Load trading settings from MongoDB central_risk_management collection."""
        defaults = {
            'trading_settings': {
                'webhook_port': 5000,
                'webhook_host': '0.0.0.0',
                'warn_existing_positions': True
            },
            'risk_management': {
                'stop_loss_percent': 5.0
            }
        }
        try:
            from mongo_db import get_central_risk, get_exchange_risk
            risk = get_central_risk()
            bybit = get_exchange_risk('bybit', risk)
            defaults['trading_settings']['warn_existing_positions'] = bool(bybit.get('warn_existing_positions', True))
            defaults['risk_management']['stop_loss_percent'] = float(bybit.get('stop_loss_percent', 5.0))
            logger.info("✅ Configuration loaded from MongoDB central_risk_management")
        except Exception as e:
            logger.warning(f"Could not load config from MongoDB, using defaults: {e}")
        return defaults

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
            logger.warning(f"Unknown exchange type: {exchange_name}")
        except Exception as e:
            logger.error(f"Error fetching market symbols for {exchange_name}: {e}", exc_info=True)
        return []

    def _fetch_bybit_symbols(self, exchange: dict, query: str, limit: int) -> list:
        base_url = exchange.get('base_url') or 'https://api.bybit.com'
        base_url = base_url.rstrip('/')
        if exchange.get('testnet'):
            base_url = 'https://api-testnet.bybit.com'
        mode = (exchange.get('trading_mode') or 'spot').lower()
        category = 'linear' if mode == 'futures' else 'spot'
        url = f"{base_url}/v5/market/instruments-info"
        symbols = []
        seen = set()

        logger.debug(f"_fetch_bybit_symbols: base_url={base_url}, mode={mode}, category={category}")

        # Spot does not support pagination parameters (cursor/limit) on this endpoint.
        if category == 'spot':
            try:
                resp = requests.get(url, params={'category': category}, timeout=10)
                logger.debug(f"Bybit API status: {resp.status_code}")
                if resp.status_code != 200:
                    logger.warning(f"❌ Bybit market API returned {resp.status_code}: {resp.text[:200]}")
                    return []
                data = resp.json()
                if data.get('retCode') != 0:
                    logger.warning(f"❌ Bybit API error: {data.get('retMsg', 'unknown error')}")
                    return []
                items = data.get('result', {}).get('list', [])
                logger.debug(f"✅ Bybit API returned {len(items)} total symbols (spot category)")
                for item in items:
                    sym = item.get('symbol', '')
                    if sym and item.get('status') == 'Trading' and sym not in seen:
                        symbols.append(sym)
                        seen.add(sym)
                logger.debug(f"Collected {len(symbols)} trading symbols, applying query filter")
                return self._filter_symbols(symbols, query, limit)
            except Exception as e:
                logger.error(f"❌ Error fetching Bybit symbols: {e}", exc_info=True)
                return []

        # Linear/Inverse/Option can exceed 500 symbols; paginate to avoid missing pairs.
        cursor = None
        max_pages = 20
        pages = 0
        while pages < max_pages:
            params = {'category': category, 'limit': 1000}
            if cursor:
                params['cursor'] = cursor

            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                break

            data = resp.json()
            if data.get('retCode') != 0:
                break

            result = data.get('result', {})
            items = result.get('list', [])
            for item in items:
                sym = item.get('symbol', '')
                if sym and item.get('status') == 'Trading' and sym not in seen:
                    symbols.append(sym)
                    seen.add(sym)

            # Early exit when we already have enough query matches for autocomplete.
            if query and len(self._filter_symbols(symbols, query, limit)) >= limit:
                break

            cursor = result.get('nextPageCursor')
            pages += 1
            if not cursor:
                break

        return self._filter_symbols(symbols, query, limit)

    def _fetch_mexc_symbols(self, exchange: dict, query: str, limit: int) -> list:
        base_url = exchange.get('base_url') or 'https://api.mexc.com'
        base_url = base_url.rstrip('/')
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
        use_paper = bool(exchange.get('use_paper', True))
        default_base = 'https://paper-api.alpaca.markets' if use_paper else 'https://api.alpaca.markets'
        base_url = (exchange.get('base_url') or default_base).rstrip('/')
        api_key = (exchange.get('api_key') or '').strip()
        api_secret = (exchange.get('api_secret') or '').strip()
        if not api_key or not api_secret or api_secret == '***':
            logger.warning('Alpaca symbol search: missing credentials, returning empty list')
            return []

        # Use a cache key based on the API key so paper/live accounts are separate
        cache_key = f'alpaca_{api_key[:12]}'
        cached = _alpaca_symbol_cache.get(cache_key)
        if cached and (time.time() - cached['ts']) < _ALPACA_CACHE_TTL:
            logger.debug(f'Alpaca symbol cache hit for {cache_key} ({len(cached["symbols"])} symbols)')
            return self._filter_symbols(cached['symbols'], query, limit)

        # Cache miss — fetch from Alpaca (runs once per hour per account)
        headers = {
            'APCA-API-KEY-ID': api_key,
            'APCA-API-SECRET-KEY': api_secret,
        }
        all_symbols = []
        for asset_class in ('us_equity', 'crypto'):
            try:
                resp = requests.get(
                    f"{base_url}/v2/assets",
                    params={'status': 'active', 'asset_class': asset_class},
                    headers=headers,
                    timeout=30,  # large response — give it room to breathe
                )
                raw_body = resp.text or ''
                preview_len = 2000
                logger.info(
                    f"Alpaca /v2/assets raw response ({asset_class}): "
                    f"status={resp.status_code}, bytes={len(raw_body)}, preview={raw_body[:preview_len]}"
                )
                if resp.status_code == 200:
                    assets = resp.json()
                    logger.info(f'Alpaca /v2/assets parsed count ({asset_class}): {len(assets)}')
                    for a in assets:
                        sym = (a.get('symbol') or '').strip()
                        if sym and a.get('tradable'):
                            all_symbols.append(sym)
                    logger.info(f'Alpaca assets fetched: {asset_class} → {len(all_symbols)} total so far')
                else:
                    logger.warning(f'Alpaca /v2/assets {asset_class} returned {resp.status_code}: {resp.text[:200]}')
            except requests.exceptions.Timeout:
                logger.error(f'Timeout fetching Alpaca {asset_class} assets — will retry next search')
            except Exception as e:
                logger.error(f'Error fetching Alpaca {asset_class} assets: {e}')

        if all_symbols:
            _alpaca_symbol_cache[cache_key] = {'symbols': all_symbols, 'ts': time.time()}
            logger.info(f'Alpaca symbol cache populated: {len(all_symbols)} symbols for {cache_key}')

        return self._filter_symbols(all_symbols, query, limit)

    def _filter_symbols(self, symbols: list, query: str, limit: int) -> list:
        logger.debug(f"_filter_symbols: input={len(symbols)} symbols, query='{query}', limit={limit}")
        if query:
            q = query.upper()
            before = len(symbols)
            symbols = [s for s in symbols if q in s.upper()]
            logger.debug(f"  After query filter: {len(symbols)} symbols (was {before})")
        result = symbols[:limit]
        logger.debug(f"  Final result: {len(result)} symbols (after limit)")
        return result


    def _check_mongo_exchanges_status(self, mongo_accounts: list) -> dict:
        """Check connection status for Mongo-backed exchange accounts. Returns status dict keyed by exchange account _id."""
        status = {}
        for ex_acc in mongo_accounts:
            ex_type = (ex_acc.get('type') or '').lower()
            ex_id = ex_acc.get('_id', ex_type)
            creds = ex_acc.get('credentials', {}) or {}
            try:
                from secrets_manager import decrypt_credentials_dict
                creds = decrypt_credentials_dict(creds)
            except Exception:
                pass
            api_key = creds.get('api_key', '').strip()
            api_secret = creds.get('api_secret', '').strip()
            base_url = ex_acc.get('base_url') or (ex_acc.get('connection_info') or {}).get('base_url', '')
            exchange_status = {
                'name': f"{ex_type.upper()} ({ex_id})",
                'enabled': ex_acc.get('enabled', True),
                'connected': False,
                'can_trade': False,
                'balances': {}
            }
            can_validate = (api_key and api_secret) or ex_type == 'ibkr'
            if can_validate:
                try:
                    client = None
                    if ex_type == 'mexc':
                        from mexc_client import MEXCClient
                        client = MEXCClient(api_key=api_key, api_secret=api_secret, base_url=base_url or 'https://api.mexc.com')
                    elif ex_type == 'alpaca':
                        from alpaca_client import AlpacaClient
                        client = AlpacaClient(api_key=api_key, api_secret=api_secret, base_url=base_url or 'https://paper-api.alpaca.markets')
                    elif ex_type == 'bybit':
                        from bybit_client import BybitClient
                        proxy = (ex_acc.get('proxy') or '').strip() or None
                        client = BybitClient(api_key=api_key, api_secret=api_secret,
                                             base_url=(base_url or 'https://api.bybit.com').rstrip('/'),
                                             testnet=ex_acc.get('testnet', False),
                                             trading_mode=ex_acc.get('trading_mode', 'spot'),
                                             leverage=int(ex_acc.get('leverage') or 1), proxy=proxy)
                    elif ex_type == 'ibkr':
                        from ibkr_client import IBKRClient
                        client = IBKRClient(api_key=api_key or '', api_secret=api_secret or '',
                                            base_url=(base_url or 'https://localhost:5000').rstrip('/'),
                                            account_id=ex_acc.get('account_id', ''),
                                            use_paper=ex_acc.get('use_paper', False),
                                            leverage=int(ex_acc.get('leverage') or 1))
                    if client:
                        validation = client.validate_connection()
                        exchange_status['connected'] = validation.get('connected', False)
                        exchange_status['can_trade'] = validation.get('can_trade', False)
                        if exchange_status['connected']:
                            try:
                                exchange_status['balances'] = client.get_main_balances()
                            except Exception:
                                exchange_status['balances'] = {}
                        else:
                            exchange_status['balances'] = None
                except Exception as e:
                    logger.error(f"Status check failed for {ex_id}: {e}", exc_info=True)
            status[ex_id] = exchange_status
        return status

    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            """Dashboard home page"""
            return render_template('dashboard.html', config=self.config)

        # Catch-all for SPA routing: /accounts, /symbols-routing, /trading-settings, /risk-management, /activity, /exchanges/<account_id>
        @self.app.route('/<path:path>')
        def spa_route(path):
            """Serve dashboard.html for all non-API routes (SPA routing)"""
            # Allow paths like: accounts, symbols-routing, trading-settings, risk-management, activity, exchanges/account_123
            if not path.startswith('api/') and not path.startswith('static/'):
                return render_template('dashboard.html', config=self.config)
            # Fallback to 404 for other paths
            return {'error': 'Not found'}, 404

        @self.app.route('/api/exchanges', methods=['GET'])
        def get_exchanges():
            """Get all exchange account configurations (enabled and disabled)."""
            try:
                from mongo_db import get_db
                try:
                    from secrets_manager import decrypt_credentials_dict
                except Exception:
                    decrypt_credentials_dict = lambda d: d
                db = get_db()
                exs = list(db.exchange_accounts.find({}))
                mapped = {}
                for e in exs:
                    creds = decrypt_credentials_dict(e.get('credentials') or {})
                    mapped[e['_id']] = {
                        'enabled': e.get('enabled', False),
                        'type': e.get('type', e['_id']),
                        'api_key': creds.get('api_key', ''),
                        'api_secret': '***' if creds.get('api_secret') else '',
                        'base_url': e.get('base_url') or (e.get('connection_info') or {}).get('base_url', ''),
                        'name': e.get('type', e['_id']),
                        'testnet': e.get('testnet', False),
                        'trading_mode': e.get('trading_mode', 'spot'),
                        'leverage': e.get('leverage', 1),
                        'proxy': e.get('proxy', ''),
                        'symbol': e.get('symbol'),
                        'account_id': e.get('account_id'),
                        'gateway_host': e.get('gateway_host', '127.0.0.1'),
                        'gateway_port': e.get('gateway_port', 7497),
                        'client_id': e.get('client_id', 1),
                        'paper_trading': (
                            e.get('paper_trading', True) if e.get('type') == 'ibkr'
                            else e.get('use_paper', True) if e.get('type') == 'alpaca'
                            else None
                        ),
                    }
                return jsonify(mapped)
            except Exception as ex:
                logger.error(f"Error reading exchanges from MongoDB: {ex}", exc_info=True)
                return jsonify({'error': 'Failed to read exchanges from DB'}), 500
        
        @self.app.route('/api/exchanges/<exchange_name>', methods=['GET'])
        def get_exchange(exchange_name):
            """Get specific exchange configuration"""
            try:
                from mongo_db import get_db
                db = get_db()
                doc = db.exchange_accounts.find_one({'_id': exchange_name})
                if not doc:
                    return jsonify({'error': 'Exchange account not found'}), 404
                try:
                    from secrets_manager import decrypt_credentials_dict
                    creds = decrypt_credentials_dict(doc.get('credentials') or {})
                except Exception:
                    creds = doc.get('credentials') or {}
                exchange_config = {
                    'enabled': doc.get('enabled', False),
                    'api_key': creds.get('api_key', ''),
                    'api_secret': '***' if creds.get('api_secret') else '',
                    'base_url': doc.get('base_url') or doc.get('connection_info', {}).get('base_url', ''),
                    'name': doc.get('type', exchange_name),
                    'testnet': doc.get('testnet', False),
                    'trading_mode': doc.get('trading_mode', 'spot'),
                    'leverage': doc.get('leverage', 1),
                    'proxy': doc.get('proxy', ''),
                    'symbol': doc.get('symbol'),
                    'account_id': doc.get('account_id'),
                    'type': doc.get('type', exchange_name),
                    'gateway_host': doc.get('gateway_host', '127.0.0.1'),
                    'gateway_port': doc.get('gateway_port', 7497),
                    'client_id': doc.get('client_id', 1),
                    'paper_trading': (
                        doc.get('paper_trading', True) if doc.get('type') == 'ibkr'
                        else doc.get('use_paper', True) if doc.get('type') == 'alpaca'
                        else None
                    ),
                }
                return jsonify(exchange_config)
            except Exception as ex:
                logger.error(f"Error fetching exchange from MongoDB: {ex}", exc_info=True)
                return jsonify({'error': 'Failed to fetch exchange from DB'}), 500
        
        @self.app.route('/api/exchanges/<exchange_name>', methods=['POST'])
        def update_exchange(exchange_name):
            """Update exchange configuration"""
            data = request.get_json()
            try:
                from mongo_db import get_db
                db = get_db()
                # Fetch existing document to get exchange type
                doc = db.exchange_accounts.find_one({'_id': exchange_name})
                exchange_type = (doc.get('type') or '').lower() if doc else ''
                update = {}
                if 'enabled' in data:
                    update['enabled'] = bool(data['enabled'])
                creds = {}
                try:
                    from secrets_manager import decrypt_credentials_dict
                    creds = decrypt_credentials_dict((doc or {}).get('credentials') or {})
                except Exception:
                    creds = (doc or {}).get('credentials') or {}
                if 'api_key' in data:
                    api_key_val = (data.get('api_key') or '').strip()
                    if api_key_val == '***':
                        pass
                    else:
                        creds['api_key'] = api_key_val
                if 'api_secret' in data:
                    api_secret_val = (data.get('api_secret') or '').strip()
                    if api_secret_val == '***':
                        pass
                    else:
                        creds['api_secret'] = api_secret_val
                if 'api_key' in data or 'api_secret' in data:
                    try:
                        from secrets_manager import encrypt_credentials_dict
                        creds = encrypt_credentials_dict(creds)
                    except Exception:
                        pass
                    update['credentials'] = creds
                if 'base_url' in data:
                    update['base_url'] = data['base_url']
                if 'paper_trading' in data:
                    update['use_paper'] = bool(data['paper_trading'])
                if 'sub_account_id' in data:
                    update['sub_account_id'] = data['sub_account_id']
                if 'use_sub_account' in data:
                    update['use_sub_account'] = bool(data['use_sub_account'])
                if 'leverage' in data:
                    try:
                        update['leverage'] = int(data['leverage'])
                    except Exception:
                        pass
                if 'account_id' in data:
                    update['account_id'] = data['account_id']
                if 'use_paper' in data:
                    update['use_paper'] = bool(data['use_paper'])
                if 'testnet' in data:
                    update['testnet'] = bool(data['testnet'])
                if 'trading_mode' in data:
                    tm = data['trading_mode'] if data['trading_mode'] in ['spot', 'futures'] else 'spot'
                    update['trading_mode'] = tm
                if 'proxy' in data:
                    update['proxy'] = data['proxy']
                if 'symbol' in data:
                    symbol = data['symbol']
                    if symbol and isinstance(symbol, str):
                        update['symbol'] = symbol.strip().upper()
                    elif symbol is None or symbol == '':
                        update['symbol'] = None
                # IBKR Gateway connection settings
                if 'gateway_host' in data:
                    update['gateway_host'] = data['gateway_host'].strip() if data['gateway_host'] else '127.0.0.1'
                if 'gateway_port' in data:
                    try:
                        update['gateway_port'] = int(data['gateway_port'])
                    except (ValueError, TypeError):
                        update['gateway_port'] = 7497
                if 'client_id' in data:
                    try:
                        update['client_id'] = int(data['client_id'])
                    except (ValueError, TypeError):
                        update['client_id'] = 1
                if 'paper_trading' in data and exchange_type == 'ibkr':
                    update['paper_trading'] = bool(data['paper_trading'])
                if update:
                    db.exchange_accounts.update_one({'_id': exchange_name}, {'$set': update}, upsert=False)
                    self._invalidate_executors()
                    return jsonify({'status': 'success', 'message': 'Exchange updated in DB'})
                return jsonify({'error': 'No valid fields to update'}), 400
            except Exception as ex:
                logger.error(f"Error updating exchange in MongoDB: {ex}", exc_info=True)
                return jsonify({'error': 'Failed to update exchange in DB'}), 500

        @self.app.route('/api/exchanges/<exchange_name>', methods=['DELETE'])
        def delete_exchange(exchange_name):
            try:
                from mongo_db import get_db
                db = get_db()
                res = db.exchange_accounts.delete_one({'_id': exchange_name})
                if res.deleted_count == 0:
                    return jsonify({'error': 'Exchange account not found'}), 404
                self._invalidate_executors()
                return jsonify({'status': 'success', 'message': 'Exchange deleted'}), 200
            except Exception as ex:
                logger.error(f"Error deleting exchange in MongoDB: {ex}", exc_info=True)
                return jsonify({'error': 'Failed to delete exchange in DB'}), 500

        @self.app.route('/api/exchanges/<exchange_name>/toggle', methods=['POST'])
        def toggle_exchange(exchange_name):
            """Enable/disable exchange"""
            data = request.get_json() or {}
            enabled = bool(data.get('enabled', False))
            try:
                from mongo_db import get_db
                db = get_db()
                res = db.exchange_accounts.update_one({'_id': exchange_name}, {'$set': {'enabled': enabled}})
                if res.matched_count == 0:
                    return jsonify({'error': 'Exchange account not found'}), 404
                self._invalidate_executors()
                return jsonify({'status': 'success', 'message': f"Exchange {'enabled' if enabled else 'disabled'} successfully", 'enabled': enabled})
            except Exception as ex:
                logger.error(f"Error toggling exchange in MongoDB: {ex}", exc_info=True)
                return jsonify({'error': 'Failed to update exchange in DB'}), 500

        @self.app.route('/api/exchanges/<exchange_name>/market-symbols', methods=['GET', 'POST'])
        def search_market_symbols(exchange_name):
            """Search symbols from the exchange's market. Looks up exchange_accounts by _id."""
            query = (request.args.get('q') or '').strip().upper()
            try:
                from mongo_db import get_db
                db = get_db()
                doc = db.exchange_accounts.find_one({'_id': exchange_name})
                if not doc:
                    logger.warning(f"❌ Exchange account not found in MongoDB: {exchange_name}")
                    return jsonify({'error': 'Exchange not found'}), 404
                logger.info(f"✅ Found exchange account {exchange_name}: {list(doc.keys())}")
                ex_type = doc.get('type', '').lower()
                logger.info(f"Exchange type field value: '{ex_type}' (raw type field: {repr(doc.get('type'))})")
                if not ex_type:
                    logger.warning(f"❌ Exchange {exchange_name} has no 'type' field or it's empty")
                    logger.warning(f"Document keys: {list(doc.keys())}")
                    return jsonify({'error': 'Exchange type not configured'}), 400
                req_data = request.get_json(silent=True) or {}
                creds = doc.get('credentials') or {}
                try:
                    from secrets_manager import decrypt_credentials_dict
                    creds = decrypt_credentials_dict(creds)
                except Exception:
                    pass
                req_api_key = (req_data.get('api_key') or '').strip()
                if req_api_key == '***':
                    req_api_key = ''
                req_api_secret = (req_data.get('api_secret') or '').strip()
                if req_api_secret == '***':
                    req_api_secret = ''
                exchange = {
                    'base_url': req_data.get('base_url') or doc.get('base_url') or (doc.get('connection_info') or {}).get('base_url') or '',
                    'testnet': req_data.get('testnet') if 'testnet' in req_data else doc.get('testnet', False),
                    'trading_mode': req_data.get('trading_mode') or doc.get('trading_mode', 'spot'),
                    'api_key': req_api_key or (creds.get('api_key') or '').strip(),
                    'api_secret': '',
                }
                if req_api_secret:
                    exchange['api_secret'] = req_api_secret
                else:
                    exchange['api_secret'] = (creds.get('api_secret') or '').strip()
                logger.info(f"Fetching symbols: exchange_type={ex_type}, trading_mode={exchange.get('trading_mode')}, query={query}")
                symbols = self._fetch_market_symbols(ex_type, exchange, query)
                logger.info(f"✅ market-symbols returned {len(symbols)} results for {ex_type} with query '{query}'")
                return jsonify({'symbols': symbols})
            except Exception as e:
                logger.error(f"❌ market-symbols lookup failed: {e}", exc_info=True)
                return jsonify({'error': 'Failed to fetch symbols'}), 500

        @self.app.route('/api/exchanges/<exchange_name>/symbols', methods=['GET', 'POST'])
        def manage_exchange_symbols(exchange_name):
            """Get or update symbol for a specific exchange.
            Each exchange can have max 1 symbol.
            GET: Returns { "symbol": "BTC" } or { "symbol": null }
            POST: Accepts { "symbol": "BTC" } and replaces it.
            """
            try:
                from mongo_db import get_db
                db = get_db()
                doc = db.exchange_accounts.find_one({'_id': exchange_name})
                if not doc:
                    return jsonify({'error': 'Exchange not found'}), 404
                if request.method == 'GET':
                    symbol = doc.get('symbol') or None
                    return jsonify({
                        'exchange': exchange_name,
                        'name': doc.get('type', exchange_name),
                        'symbol': str(symbol).upper() if symbol else None
                    })
                data = request.get_json() or {}
                raw = data.get('symbol')
                if raw is None:
                    # Clear symbol
                    db.exchange_accounts.update_one({'_id': exchange_name}, {'$set': {'symbol': None}})
                    logger.info(f"✅ Cleared symbol for {exchange_name}")
                    return jsonify({'status': 'success', 'symbol': None})
                if not isinstance(raw, str):
                    return jsonify({'error': 'symbol must be a string'}), 400
                clean = raw.strip().upper()
                if not clean:
                    db.exchange_accounts.update_one({'_id': exchange_name}, {'$set': {'symbol': None}})
                    return jsonify({'status': 'success', 'symbol': None})
                db.exchange_accounts.update_one({'_id': exchange_name}, {'$set': {'symbol': clean}})
                logger.info(f"✅ Updated symbol for {exchange_name}: {clean}")
                return jsonify({'status': 'success', 'symbol': clean})
            except Exception as e:
                logger.warning(f"symbols operation failed: {e}")
                return jsonify({'error': 'Failed to manage symbols'}), 500
        
        @self.app.route('/api/trading-settings', methods=['GET'])
        def get_trading_settings():
            """Get trading settings"""
            return jsonify(self.config['trading_settings'])
        
        @self.app.route('/api/trading-settings', methods=['POST'])
        def update_trading_settings():
            """Update trading settings — writes to MongoDB central_risk_management."""
            data = request.get_json() or {}
            allowed_keys = {'warn_existing_positions', 'webhook_port', 'webhook_host'}
            update = {}
            for key, value in data.items():
                if key not in allowed_keys:
                    continue
                if key == 'warn_existing_positions':
                    update[key] = bool(value)
                else:
                    update[key] = value
            if not update:
                return jsonify({'error': 'No valid fields to update'}), 400
            try:
                from mongo_db import get_db
                db = get_db()
                if 'warn_existing_positions' in update:
                    db.central_risk_management.update_one(
                        {'_id': 'default'},
                        {'$set': {'bybit.warn_existing_positions': update['warn_existing_positions']}},
                        upsert=True
                    )
                self.config['trading_settings'].update(update)
                return jsonify({'status': 'success', 'message': 'Trading settings updated successfully'})
            except Exception as e:
                logger.error(f"Error saving trading settings to MongoDB: {e}", exc_info=True)
                return jsonify({'error': 'Failed to save trading settings'}), 500
        
        @self.app.route('/api/risk-management', methods=['GET'])
        def get_risk_management():
            """Get risk management settings from MongoDB."""
            try:
                from mongo_db import get_central_risk
                return jsonify(get_central_risk())
            except Exception as e:
                logger.error(f"Error fetching central risk from MongoDB: {e}", exc_info=True)
                return jsonify({'error': 'Failed to fetch risk management settings'}), 500
        
        @self.app.route('/api/risk-management', methods=['POST'])
        def update_risk_management():
            """Update risk management settings in MongoDB central_risk_management."""
            data = request.get_json() or {}
            try:
                from mongo_db import get_db, get_central_risk
                db = get_db()
                if not isinstance(data, dict):
                    return jsonify({'error': 'Invalid payload'}), 400

                numeric_fields = {
                    'stop_loss_percent', 'take_profit_percent', 'position_size_percent',
                    'tp1_target', 'tp2_target', 'tp3_target', 'tp4_target', 'tp5_target',
                }
                bool_fields = {'use_percentage', 'warn_existing_positions'}
                mode_fields = {'tp_mode'}

                def _parse_exchange_profile(payload: dict):
                    parsed = {}
                    for key, value in payload.items():
                        if key in numeric_fields:
                            try:
                                parsed[key] = float(value)
                            except Exception:
                                continue
                        elif key in bool_fields:
                            parsed[key] = bool(value) if not isinstance(value, str) else str(value).lower() == 'true'
                        elif key in mode_fields:
                            mode = str(value or '').strip().lower()
                            if mode in {'ladder', 'single', 'none'}:
                                parsed[key] = mode
                        elif key == 'position_size_fixed':
                            try:
                                parsed[key] = float(value) if value not in (None, '') else None
                            except Exception:
                                continue
                    # Enforce mutual exclusion at API level as well.
                    # Percentage mode ignores fixed size; fixed mode can keep percentage as fallback.
                    use_pct = parsed.get('use_percentage')
                    if use_pct is True:
                        parsed['position_size_fixed'] = None
                    return parsed

                update = {}
                bybit_payload = data.get('bybit')
                if isinstance(bybit_payload, dict):
                    parsed_bybit = _parse_exchange_profile(bybit_payload)
                    for key, value in parsed_bybit.items():
                        update[f'bybit.{key}'] = value

                alpaca_payload = data.get('alpaca')
                if isinstance(alpaca_payload, dict):
                    parsed_alpaca = _parse_exchange_profile(alpaca_payload)
                    for key, value in parsed_alpaca.items():
                        update[f'alpaca.{key}'] = value

                if update:
                    db.central_risk_management.update_one({'_id': 'default'}, {'$set': update}, upsert=True)
                    refreshed = get_central_risk()
                    bybit = refreshed.get('bybit', {})
                    self.config['trading_settings']['warn_existing_positions'] = bool(bybit.get('warn_existing_positions', True))
                    self.config['risk_management']['stop_loss_percent'] = float(bybit.get('stop_loss_percent', 5.0))
                    return jsonify({'status': 'success', 'message': 'Central risk management updated in DB', 'risk': refreshed})
                return jsonify({'error': 'No valid fields to update'}), 400
            except Exception as e:
                logger.error(f'Error updating central risk in MongoDB: {e}', exc_info=True)
                return jsonify({'error': 'Failed to update central risk in DB'}), 500

        @self.app.route('/api/portfolio', methods=['GET'])
        def get_portfolio():
            """Get all ticker+account combinations with trades in selected date range."""
            try:
                from mongo_db import get_db
                db = get_db()

                start_iso, end_iso = _portfolio_date_range_from_request(request)
                match_stage = {
                    'timestamp_open': {
                        '$gte': start_iso,
                        '$lte': end_iso,
                    }
                }

                pipeline = []
                if match_stage:
                    pipeline.append({'$match': match_stage})
                # Group by (symbol, exchange_account_id) so futures and spot show separately
                pipeline += [
                    {'$group': {
                        '_id': {
                            'symbol': '$symbol',
                            'exchange_account_id': '$exchange_account_id',
                        },
                        'trade_count': {'$sum': 1},
                        'last_trade': {'$max': '$timestamp_close'},
                    }},
                    {'$sort': {'last_trade': -1}},
                ]

                rows = list(db.trades.aggregate(pipeline))

                # Enrich each row with exchange type/mode label
                tickers = []
                for row in rows:
                    symbol = row['_id']['symbol']
                    ea_id  = row['_id'].get('exchange_account_id')
                    label  = _exchange_label(db, ea_id)
                    tickers.append({
                        'symbol':              symbol,
                        'exchange_account_id': ea_id,
                        'exchange_label':      label,
                        'trade_count':         row['trade_count'],
                        'last_trade':          row['last_trade'],
                    })

                return jsonify({
                    'tickers': tickers,
                    'count': len(tickers),
                    'start_date': start_iso[:10],
                    'end_date': end_iso[:10],
                })
            except Exception as e:
                logger.error(f'Error fetching portfolio: {e}', exc_info=True)
                return jsonify({'error': 'Failed to fetch portfolio'}), 500

        @self.app.route('/api/portfolio/<symbol>/<exchange_account_id>', methods=['GET'])
        def get_ticker_detail(symbol, exchange_account_id):
            """Get ticker detail with trades, ROI, and win rate (Milestone 3 - Ticker Detail Page)"""
            try:
                from mongo_db import get_db
                db = get_db()

                query = {'symbol': symbol, 'exchange_account_id': exchange_account_id}
                start_iso, end_iso = _portfolio_date_range_from_request(request)
                query['timestamp_open'] = {'$gte': start_iso, '$lte': end_iso}

                # Fetch trades for this symbol+account in selected date range, sorted by open time descending
                trades = list(db.trades.find(query).sort('timestamp_open', -1))

                # Serialize ObjectId to string
                for t in trades:
                    if '_id' in t and hasattr(t['_id'], '__class__') and t['_id'].__class__.__name__ == 'ObjectId':
                        t['_id'] = str(t['_id'])

                # Calculate ROI and win rate
                total_pnl = sum(float(t.get('result_usd') or 0) for t in trades)
                winning_trades = sum(1 for t in trades if float(t.get('result_usd') or 0) > 0)
                total_trades = len(trades)
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

                # Calculate total invested (entry_price * quantity for first trade, approximation)
                total_invested = 0
                for t in trades:
                    entry = float(t.get('entry_price') or 0)
                    if entry > 0 and t.get('direction'):
                        # Rough estimate: assume 1 unit traded
                        total_invested += entry

                roi = (total_pnl / total_invested * 100) if total_invested > 0 else 0
                exchange_label = _exchange_label(db, exchange_account_id)

                return jsonify({
                    'symbol': symbol,
                    'exchange_label': exchange_label,
                    'roi_percent': round(roi, 2),
                    'win_rate_percent': round(win_rate, 2),
                    'total_pnl': round(total_pnl, 2),
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'trades': trades,
                    'start_date': start_iso[:10],
                    'end_date': end_iso[:10],
                })
            except Exception as e:
                logger.error(f'Error fetching ticker detail for {symbol}: {e}', exc_info=True)
                return jsonify({'error': 'Failed to fetch ticker detail'}), 500

        @self.app.route('/api/portfolio/<symbol>/<exchange_account_id>/trade/<trade_id>', methods=['GET'])
        def get_trade_detail(symbol, exchange_account_id, trade_id):
            """Get detailed breakdown of a single trade (Milestone 3 - Trade Detail Page)"""
            try:
                from mongo_db import get_db
                from bson import ObjectId
                db = get_db()

                # Fetch the trade by ID
                try:
                    trade = db.trades.find_one({'_id': ObjectId(trade_id)})
                except Exception:
                    trade = db.trades.find_one({'_id': trade_id})

                if not trade:
                    return jsonify({'error': 'Trade not found'}), 404

                # Serialize ObjectId to string
                if '_id' in trade and hasattr(trade['_id'], '__class__') and trade['_id'].__class__.__name__ == 'ObjectId':
                    trade['_id'] = str(trade['_id'])

                # Calculate R-Multiple: P&L / |Entry Price - Stop Loss|
                entry = float(trade.get('entry_price') or 0)
                stop_loss = float(trade.get('stop_loss') or 0)
                pnl = float(trade.get('result_usd') or 0)

                r_multiple = None
                if entry > 0 and stop_loss > 0:
                    initial_risk = abs(entry - stop_loss)
                    if initial_risk > 0:
                        r_multiple = round(pnl / initial_risk, 2)

                # Calculate trade duration in readable format
                from datetime import datetime
                try:
                    open_time = datetime.fromisoformat(trade['timestamp_open'].replace('Z', '+00:00'))
                    close_time = datetime.fromisoformat(trade['timestamp_close'].replace('Z', '+00:00'))
                    duration_seconds = int((close_time - open_time).total_seconds())

                    hours = duration_seconds // 3600
                    minutes = (duration_seconds % 3600) // 60
                    seconds = duration_seconds % 60

                    if hours > 0:
                        duration_str = f"{hours}h {minutes}m"
                    elif minutes > 0:
                        duration_str = f"{minutes}m {seconds}s"
                    else:
                        duration_str = f"{seconds}s"
                except Exception:
                    duration_str = f"{trade.get('trade_duration_sec', 0)}s"

                # Compute max drawdown and max profit on demand from candle data (REQ-3.5)
                max_drawdown_pct = None
                max_profit_pct = None
                try:
                    max_drawdown_pct, max_profit_pct = _compute_drawdown_profit(trade, db)
                except Exception as e:
                    logger.warning(f"Could not compute drawdown/profit for trade {trade_id}: {e}")

                return jsonify({
                    'symbol': trade.get('symbol'),
                    'direction': trade.get('direction'),
                    'entry_price': round(float(trade.get('entry_price') or 0), 8),
                    'exit_price': round(float(trade.get('exit_price') or 0), 8),
                    'stop_loss': round(float(trade.get('stop_loss') or 0), 8),
                    'tp_hits': trade.get('tp_hits', [False, False, False, False, False]),
                    'result_usd': round(float(trade.get('result_usd') or 0), 2),
                    'result_percent': round(float(trade.get('result_percent') or 0), 2),
                    'r_multiple': r_multiple,
                    'trade_duration': duration_str,
                    'trade_duration_sec': trade.get('trade_duration_sec', 0),
                    'max_drawdown_pct': max_drawdown_pct,
                    'max_profit_pct': max_profit_pct,
                    'exit_reason': trade.get('exit_reason', 'UNKNOWN'),
                    'timestamp_open': trade.get('timestamp_open'),
                    'timestamp_close': trade.get('timestamp_close'),
                })
            except Exception as e:
                logger.error(f'Error fetching trade detail {trade_id}: {e}', exc_info=True)
                return jsonify({'error': 'Failed to fetch trade detail'}), 500

        @self.app.route('/api/accounts', methods=['GET', 'POST'])
        def list_accounts():
            """List logical accounts (GET) or create/update an account (POST)."""
            from uuid import uuid4
            try:
                from mongo_db import list_accounts as _list_accounts, get_db
                if request.method == 'GET':
                    accounts = _list_accounts()
                    for a in accounts:
                        a.pop('metadata', None)
                    return jsonify({'accounts': accounts})
                data = request.get_json() or {}
                account_id = data.get('_id') or f"account_{str(uuid4())[:8]}"
                db = get_db()
                existing = db.accounts.find_one({'_id': account_id})
                if existing:
                    update_fields = {}
                    if 'name' in data and data['name']:
                        update_fields['name'] = data['name']
                    if 'enabled' in data:
                        update_fields['enabled'] = bool(data['enabled'])
                    if update_fields:
                        db.accounts.update_one({'_id': account_id}, {'$set': update_fields})
                    doc = {**existing, **update_fields, '_id': account_id}
                    return jsonify({'status': 'success', 'account': doc}), 200
                name = data.get('name') or f"Account {str(uuid4())[:8]}"
                enabled = bool(data.get('enabled', True))
                doc = {'_id': account_id, 'name': name, 'enabled': enabled}
                db.accounts.insert_one(doc)

                # Auto-create 4 disabled exchange account slots
                EXCHANGE_TYPES = ['bybit', 'mexc', 'alpaca', 'ibkr']
                for ex_type in EXCHANGE_TYPES:
                    ex_id = f"{account_id}_{ex_type}"
                    db.exchange_accounts.update_one(
                        {'_id': ex_id},
                        {'$setOnInsert': {
                            '_id': ex_id,
                            'account_id': account_id,
                            'type': ex_type,
                            'enabled': False,
                            'credentials': {},
                            'symbols': [],
                            'leverage': None,
                            'trading_mode': 'spot',
                            'testnet': False,
                            'base_url': '',
                            'proxy': '',
                            'use_paper': False,
                        }},
                        upsert=True
                    )

                return jsonify({'status': 'success', 'account': doc}), 201
            except Exception as e:
                logger.error(f"Error listing/creating accounts from MongoDB: {e}")
                return jsonify({'error': 'Failed to list/create accounts from DB'}), 500

        @self.app.route('/api/accounts/<account_id>/exchanges', methods=['GET', 'POST'])
        def get_account_exchanges(account_id):
            """Return ExchangeAccounts for a logical account (GET) or create an ExchangeAccount (POST)."""
            try:
                from mongo_db import get_exchange_accounts_for_account, get_db
                if request.method == 'GET':
                    exs = get_exchange_accounts_for_account(account_id)
                    for e in exs:
                        if 'credentials' in e and isinstance(e['credentials'], dict):
                            api_key = (e['credentials'].get('api_key') or '').strip()
                            api_secret = (e['credentials'].get('api_secret') or '').strip()
                            e['credentials'] = {}
                            if api_key:
                                e['credentials']['api_key'] = api_key
                            if api_secret:
                                e['credentials']['api_secret'] = '***'
                    return jsonify({'exchanges': exs})
                data = request.get_json() or {}
                from uuid import uuid4
                ex_type = data.get('type', 'mexc')
                ex_id = data.get('_id') or f"{account_id}_{ex_type}"
                credentials = data.get('credentials') or {}
                if not credentials:
                    flat_key = (data.get('api_key') or '').strip()
                    flat_secret = (data.get('api_secret') or '').strip()
                    if flat_key or flat_secret:
                        credentials = {}
                        if flat_key:
                            credentials['api_key'] = flat_key
                        if flat_secret and flat_secret != '***':
                            credentials['api_secret'] = flat_secret
                try:
                    from secrets_manager import encrypt_credentials_dict
                    credentials = encrypt_credentials_dict(credentials)
                except Exception:
                    pass
                doc = {
                    '_id': ex_id,
                    'account_id': account_id,
                    'type': ex_type,
                    'enabled': bool(data.get('enabled', False)),
                    'credentials': credentials,
                    'symbol': data.get('symbol'),
                    'leverage': data.get('leverage'),
                    'trading_mode': data.get('trading_mode'),
                    'testnet': bool(data.get('testnet', False)),
                    'base_url': data.get('base_url') or '',
                    'proxy': data.get('proxy', ''),
                    'use_paper': bool(data.get('use_paper', False)),
                    'gateway_host': (data.get('gateway_host') or '127.0.0.1').strip(),
                    'gateway_port': int(data.get('gateway_port') or 7497),
                    'client_id': int(data.get('client_id') or 1),
                    'paper_trading': bool(data.get('paper_trading', True)) if ex_type == 'ibkr' else None,
                }
                db = get_db()
                db.exchange_accounts.update_one({'_id': ex_id}, {'$set': doc}, upsert=True)
                self._invalidate_executors()
                resp_doc = dict(doc)
                resp_doc['credentials'] = {'api_key': '***'} if credentials.get('api_key') else {}
                return jsonify({'status': 'success', 'exchange': resp_doc}), 201
            except Exception as e:
                logger.error(f"Error fetching/creating exchange accounts: {e}")
                return jsonify({'error': 'Failed to fetch/create exchange accounts'}), 500

        @self.app.route('/api/accounts/<account_id>', methods=['DELETE'])
        def delete_account(account_id):
            """Delete a logical account and all its exchange accounts from MongoDB."""
            try:
                from mongo_db import get_db
                db = get_db()
                db.exchange_accounts.delete_many({'account_id': account_id})
                res = db.accounts.delete_one({'_id': account_id})
                if res.deleted_count == 0:
                    return jsonify({'error': 'Account not found'}), 404
                self._invalidate_executors()
                return jsonify({'status': 'success', 'message': 'Account and its exchange accounts deleted'})
            except Exception as e:
                logger.error(f"Error deleting account: {e}")
                return jsonify({'error': 'Failed to delete account'}), 500

        @self.app.route('/api/trades', methods=['GET'])
        def query_trades():
            """Query trades. Supports account_id, exchange_account_id, symbol, limit, page"""
            params = request.args
            account_id = params.get('account_id')
            exchange_account_id = params.get('exchange_account_id')
            symbol = params.get('symbol')
            try:
                limit = int(params.get('limit', 100))
                page = int(params.get('page', 0))
            except Exception:
                limit = 100
                page = 0
            skip = page * limit
            try:
                from mongo_db import get_trades
                filters = {}
                if account_id:
                    filters['account_id'] = account_id
                if exchange_account_id:
                    filters['exchange_account_id'] = exchange_account_id
                if symbol:
                    filters['symbol'] = symbol
                trades = get_trades(filters, limit=limit, skip=skip)
                return jsonify({'trades': trades, 'page': page, 'limit': limit})
            except Exception as e:
                logger.error(f"Error querying trades: {e}")
                return jsonify({'error': 'Failed to query trades'}), 500

        @self.app.route('/api/exchanges/status', methods=['GET'])
        def get_exchanges_status():
            """Get connection status and balances for all exchange accounts."""
            if self.demo_mode.is_active():
                demo_status = self.demo_mode.get_demo_connection_status()
                demo_balances = self.demo_mode.get_demo_balances()
                return jsonify({'mexc': {
                    'name': 'MEXC',
                    'enabled': True,
                    'connected': demo_status['connected'],
                    'can_trade': demo_status['can_trade'],
                    'balances': demo_balances,
                    'demo_mode': True
                }})
            try:
                from mongo_db import get_enabled_exchange_accounts
                mongo_accounts = get_enabled_exchange_accounts()
                return jsonify(self._check_mongo_exchanges_status(mongo_accounts))
            except Exception as e:
                logger.error(f"Exchange status check failed: {e}", exc_info=True)
                return jsonify({'error': 'Failed to check exchange status'}), 500
        
        @self.app.route('/api/test-connection/<exchange_name>', methods=['POST'])
        def test_connection(exchange_name):
            """Test exchange API connection. Looks up exchange_accounts by _id to get saved credentials."""
            data = request.get_json(silent=True) or {}
            exchange_type = exchange_name.lower()
            exchange = {}

            try:
                from mongo_db import get_db
                db = get_db()
                doc = db.exchange_accounts.find_one({'_id': exchange_name})
                if doc:
                    exchange_type = (doc.get('type') or exchange_name).lower()
                    creds = doc.get('credentials') or {}
                    try:
                        from secrets_manager import decrypt_credentials_dict
                        creds = decrypt_credentials_dict(creds)
                    except Exception:
                        pass
                    exchange = {
                        'api_key': creds.get('api_key', ''),
                        'api_secret': creds.get('api_secret', ''),
                        'base_url': doc.get('base_url') or (doc.get('connection_info') or {}).get('base_url', ''),
                        'testnet': doc.get('testnet', False),
                        'trading_mode': doc.get('trading_mode', 'spot'),
                        'leverage': doc.get('leverage', 1),
                        'account_id': doc.get('account_id', ''),
                        'use_paper': doc.get('use_paper', False),
                        'proxy': doc.get('proxy', ''),
                    }
            except Exception as e:
                logger.warning(f"test-connection Mongo lookup failed: {e}")

            if not exchange:
                return jsonify({'error': 'Exchange account not found'}), 404

            # Merge request-provided credentials/settings over saved values
            api_key = (data.get('api_key') or exchange.get('api_key') or '').strip()
            api_secret = (data.get('api_secret') or exchange.get('api_secret') or '').strip()
            if data.get('api_secret') == '***':
                api_secret = (exchange.get('api_secret') or '').strip()
            base_url = data.get('base_url') or exchange.get('base_url', '')

            if exchange_type != 'ibkr':
                if not api_key or not api_secret or api_secret == '***':
                    return jsonify({'error': 'API key and secret required. Enter both and save, or re-enter the secret if it shows ***.'}), 400

            try:
                if exchange_type == 'mexc':
                    from mexc_client import MEXCClient
                    client = MEXCClient(api_key=api_key, api_secret=api_secret,
                                        base_url=base_url or 'https://api.mexc.com')
                    validation = client.validate_connection()
                elif exchange_type == 'alpaca':
                    from alpaca_client import AlpacaClient
                    client = AlpacaClient(api_key=api_key, api_secret=api_secret,
                                          base_url=base_url or 'https://paper-api.alpaca.markets')
                    validation = client.validate_connection()
                elif exchange_type == 'bybit':
                    from bybit_client import BybitClient
                    testnet = data.get('testnet') if 'testnet' in data else exchange.get('testnet', False)
                    trading_mode = data.get('trading_mode') or exchange.get('trading_mode', 'spot')
                    leverage = int(data.get('leverage') or exchange.get('leverage', 1))
                    proxy = (data.get('proxy') or exchange.get('proxy') or '').strip() or None
                    client = BybitClient(api_key=api_key, api_secret=api_secret,
                                         base_url=(base_url or 'https://api.bybit.com').rstrip('/'),
                                         testnet=testnet, trading_mode=trading_mode,
                                         leverage=leverage, proxy=proxy)
                    validation = client.validate_connection()
                elif exchange_type == 'ibkr':
                    from ibkr_client import IBKRClient
                    # For IBKR, we use Gateway/TWS connection instead of REST API
                    gateway_host = data.get('gateway_host') or exchange.get('gateway_host') or '127.0.0.1'
                    gateway_port = int(data.get('gateway_port') or exchange.get('gateway_port') or 7497)
                    client_id = int(data.get('client_id') or exchange.get('client_id') or 1)
                    client = IBKRClient(host=gateway_host, port=gateway_port, client_id=client_id)
                    validation = client.test_connection()
                else:
                    return jsonify({'error': 'Exchange not supported'}), 400

                if validation.get('connected'):
                    result = {
                        'status': 'success',
                        'message': 'Connection successful'
                    }
                    # Include IBKR-specific data
                    if exchange_type == 'ibkr':
                        result['account_id'] = validation.get('account_id', 'Unknown')
                        result['balance'] = validation.get('balance', 0)
                        result['buying_power'] = validation.get('buying_power', 0)
                        result['open_positions'] = validation.get('open_positions', 0)
                    # Include balances for other exchanges
                    elif hasattr(client, 'get_main_balances'):
                        result['balances'] = client.get_main_balances()
                    return jsonify(result)
                else:
                    return jsonify({'status': 'error', 'error': validation.get('error', 'Connection failed')}), 500

            except Exception as e:
                logger.error(f"Connection test failed: {e}")
                return jsonify({'error': 'Connection failed', 'message': str(e)}), 500

        @self.app.route('/api/exchanges/<exchange_name>/check-position/<symbol>', methods=['GET'])
        def check_position_before_leverage(exchange_name, symbol):
            """Check if a position exists for a symbol before changing leverage (Bybit only)"""
            try:
                from mongo_db import get_db
                db = get_db()
                doc = db.exchange_accounts.find_one({'_id': exchange_name})

                if not doc:
                    return jsonify({'error': 'Exchange account not found'}), 404

                exchange_type = (doc.get('type') or exchange_name).lower()
                if exchange_type != 'bybit':
                    return jsonify({'error': 'Position checking only supported for Bybit', 'has_position': False}), 400

                # Get credentials
                creds = doc.get('credentials') or {}
                try:
                    from secrets_manager import decrypt_credentials_dict
                    creds = decrypt_credentials_dict(creds)
                except Exception:
                    pass

                api_key = creds.get('api_key', '')
                api_secret = creds.get('api_secret', '')

                if not api_key or not api_secret:
                    return jsonify({'error': 'Exchange credentials not configured'}), 400

                # Create Bybit client and check position
                from bybit_client import BybitClient
                client = BybitClient(api_key=api_key, api_secret=api_secret,
                                    base_url=(doc.get('base_url') or 'https://api.bybit.com').rstrip('/'),
                                    testnet=doc.get('testnet', False),
                                    trading_mode=doc.get('trading_mode', 'spot'),
                                    leverage=int(doc.get('leverage') or 1))

                # Get position for symbol
                position = client.get_position_for_symbol(symbol)

                if position:
                    return jsonify({
                        'has_position': True,
                        'warning': f"⚠️ EXISTING POSITION: {position['side']} {position['size']} @ {position['entry_price']:.8f} (Leverage: {position['leverage']}x, Unrealised P&L: ${position['unrealised_pnl']:.2f})",
                        'position': position
                    })
                else:
                    return jsonify({'has_position': False, 'message': f'No open position for {symbol}'})

            except Exception as e:
                logger.error(f"Position check failed for {exchange_name}/{symbol}: {e}", exc_info=True)
                return jsonify({'error': 'Failed to check position', 'message': str(e)}), 500

        @self.app.route('/api/status', methods=['GET'])
        def get_status():
            """Get bot status"""
            if self.demo_mode.is_active():
                demo_stats = self.demo_mode.get_demo_stats()
                return jsonify({
                    'exchanges_enabled': ['mexc'],
                    'total_exchanges': 1,
                    'position_size': None,
                    'demo_mode': True,
                    'demo_stats': demo_stats
                })
            try:
                from mongo_db import get_db
                db = get_db()
                all_accs = list(db.exchange_accounts.find({}, {'_id': 1, 'type': 1, 'enabled': 1}))
                enabled = [a['_id'] for a in all_accs if a.get('enabled', True)]
                return jsonify({
                    'exchanges_enabled': enabled,
                    'total_exchanges': len(all_accs),
                    'position_size': None,
                    'demo_mode': False,
                })
            except Exception as e:
                logger.warning(f"Status Mongo lookup failed: {e}")
                return jsonify({'error': 'Failed to get status'}), 500
        
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
            """Get signal monitoring status, augmented with persisted webhook logs."""
            # Use signal_monitor directly since webhook routes are integrated into this Flask app
            if hasattr(self, 'signal_monitor') and self.signal_monitor:
                status = self.signal_monitor.get_status()
                # If signals have been received, mark as connected
                if status.get('total_signals', 0) > 0 or status.get('webhook_status') == 'connected':
                    status['webhook_status'] = 'connected'
                # Augment in-memory counters with persisted webhook logs so UI survives restarts
                try:
                    from mongo_db import get_db
                    from datetime import datetime, timedelta
                    db = get_db()
                    recent_cutoff = datetime.utcnow() - timedelta(hours=24)
                    recent_logs_count = db.webhook_logs.count_documents({'timestamp': {'$gte': recent_cutoff}})
                    total_logs_count = db.webhook_logs.count_documents({})
                    success_logs_count = db.webhook_logs.count_documents({'status': 'success'})
                    failed_logs_count = max(0, int(total_logs_count) - int(success_logs_count))
                    latest = db.webhook_logs.find_one({}, sort=[('timestamp', -1)])
                    status['recent_signals_count'] = max(int(status.get('recent_signals_count', 0)), int(recent_logs_count))
                    status['total_signals'] = max(int(status.get('total_signals', 0)), int(total_logs_count))
                    status['successful_trades'] = max(int(status.get('successful_trades', 0)), int(success_logs_count))
                    status['failed_trades'] = max(int(status.get('failed_trades', 0)), int(failed_logs_count))
                    if latest and latest.get('timestamp') and not status.get('last_signal_datetime'):
                        status['last_signal_datetime'] = latest['timestamp'].isoformat()
                except Exception as e:
                    logger.debug(f"signals_status webhook_logs augmentation skipped: {e}")
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
            """Get recent signals from persisted webhook logs, with signal_monitor fallback."""
            limit = request.args.get('limit', 100, type=int)
            hours = request.args.get('hours', 24.0, type=float)
            try:
                from datetime import datetime, timedelta
                from mongo_db import get_db

                db = get_db()
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                logs = list(
                    db.webhook_logs.find({'timestamp': {'$gte': cutoff}})
                    .sort('timestamp', -1)
                    .limit(limit)
                )

                signals = []
                for log in logs:
                    raw = log.get('raw_payload') or {}
                    raw_price = raw.get('price')
                    executions = log.get('executions') if isinstance(log.get('executions'), list) else []
                    price = None
                    if isinstance(raw_price, dict):
                        try:
                            price = float(raw_price.get('close')) if raw_price.get('close') is not None else None
                        except Exception:
                            price = None
                    elif raw_price is not None:
                        try:
                            price = float(raw_price)
                        except Exception:
                            price = None

                    ts = log.get('timestamp')
                    dt_iso = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts) if ts else None
                    status = (log.get('status') or '').lower()
                    error_msg = log.get('error') or log.get('failure_reason')
                    if status not in {'success', 'failed', 'error', 'skipped'}:
                        if any(bool(e.get('success')) for e in executions):
                            status = 'success'
                        else:
                            status = 'failed'
                            if not error_msg:
                                error_msg = 'Execution status unavailable (treated as failed)'
                    signals.append({
                        'id': str(log.get('_id')) if log.get('_id') is not None else None,
                        'timestamp': dt_iso,
                        'datetime': dt_iso,
                        'symbol': log.get('symbol') or raw.get('symbol') or '',
                        'signal': log.get('signal') or raw.get('signal') or '',
                        'price': price,
                        'executed': status == 'success',
                        'status': status,
                        'error': error_msg if status in ['failed', 'error'] else None,
                        'matched_exchanges': log.get('matched_exchanges') or [],
                        'executions': executions,
                    })

                return jsonify({'signals': signals}), 200
            except Exception as e:
                logger.warning(f"recent_signals webhook_logs query failed, falling back to signal_monitor: {e}")

            # Fallback to in-memory signal monitor
            if hasattr(self, 'signal_monitor') and self.signal_monitor:
                signals = self.signal_monitor.get_recent_signals(limit=limit, hours=hours)
                return jsonify({'signals': signals}), 200
            return jsonify({'signals': []}), 200

        @self.app.route('/api/webhook-logs', methods=['GET'])
        def get_webhook_logs():
            """Get webhook audit logs with filtering"""
            try:
                from mongo_db import get_db
                db = get_db()

                limit = request.args.get('limit', 100, type=int)
                status = request.args.get('status')  # filter: success/failed/skipped/error
                symbol = request.args.get('symbol')  # filter by symbol

                query = {}
                if status:
                    query['status'] = status
                if symbol:
                    query['symbol'] = {'$regex': symbol, '$options': 'i'}

                logs = list(db.webhook_logs.find(query).sort('timestamp', -1).limit(limit))

                # Convert ObjectId and datetime to JSON-safe strings
                for log in logs:
                    log['_id'] = str(log['_id']) if log.get('_id') else None
                    if log.get('timestamp'):
                        log['timestamp'] = log['timestamp'].isoformat()

                return jsonify({'logs': logs}), 200
            except Exception as e:
                logger.error(f"Error fetching webhook logs: {e}")
                return jsonify({'error': 'Failed to fetch webhook logs'}), 500

        @self.app.route('/api/ibkr/setup', methods=['POST'])
        def ibkr_setup():
            """Start an ibeam Docker container for an IBKR account"""
            import docker
            from datetime import datetime

            data = request.get_json() or {}
            exchange_id = data.get('exchange_id')
            ibkr_user = data.get('ibkr_user', '').strip()
            ibkr_pass = data.get('ibkr_pass', '').strip()
            paper_trading = bool(data.get('paper_trading', True))

            if not exchange_id or not ibkr_user or not ibkr_pass:
                return jsonify({'error': 'Missing exchange_id, ibkr_user, or ibkr_pass'}), 400

            try:
                from mongo_db import get_db
                db = get_db()

                # Check if container already exists for this exchange
                existing = db.ibkr_containers.find_one({'exchange_id': exchange_id})
                if existing and existing.get('status') == 'running':
                    return jsonify({'port': existing['port'], 'container_name': existing['container_name'], 'status': 'running'}), 200

                # Find next available port
                IBKR_PORT_START = 7497
                used_ports = {doc['port'] for doc in db.ibkr_containers.find({}, {'port': 1})}
                port = IBKR_PORT_START
                while port in used_ports:
                    port += 1

                # Build container name: ibeam-{exchange_id}-{paper/live}
                container_name = f"ibeam-{exchange_id.replace('_', '-')}"

                # Start Docker container
                client = docker.from_env()
                try:
                    container = client.containers.run(
                        'voyz/ibeam:latest',
                        detach=True,
                        name=container_name,
                        ports={7497: port},
                        environment={
                            'IBKR_USER': ibkr_user,
                            'IBKR_PASS': ibkr_pass
                        },
                        restart_policy={'Name': 'unless-stopped'},
                        remove=False
                    )
                    logger.info(f"Started ibeam container {container_name} on port {port}")
                except docker.errors.APIError as e:
                    if 'already exists' in str(e):
                        # Container exists but stopped, start it
                        container = client.containers.get(container_name)
                        container.start()
                    else:
                        raise

                # Store in MongoDB
                doc_id = f"ibeam-{exchange_id}"
                db.ibkr_containers.update_one(
                    {'_id': doc_id},
                    {'$set': {
                        '_id': doc_id,
                        'exchange_id': exchange_id,
                        'container_name': container_name,
                        'port': port,
                        'paper_trading': paper_trading,
                        'status': 'running',
                        'created_at': datetime.utcnow().isoformat()
                    }},
                    upsert=True
                )

                return jsonify({'port': port, 'container_name': container_name, 'status': 'running'}), 201
            except Exception as e:
                logger.error(f"Error setting up ibeam container: {e}", exc_info=True)
                return jsonify({'error': f'Failed to start ibeam container: {str(e)}'}), 500

        @self.app.route('/api/ibkr/status/<exchange_id>', methods=['GET'])
        def ibkr_status(exchange_id):
            """Check if ibeam container is running for an IBKR exchange"""
            import docker

            try:
                from mongo_db import get_db
                db = get_db()

                container_doc = db.ibkr_containers.find_one({'exchange_id': exchange_id})
                if not container_doc:
                    return jsonify({'running': False, 'port': None, 'container_name': None}), 200

                container_name = container_doc.get('container_name')
                port = container_doc.get('port')

                # Check actual Docker status
                try:
                    client = docker.from_env()
                    container = client.containers.get(container_name)
                    is_running = container.status == 'running'

                    if is_running:
                        db.ibkr_containers.update_one(
                            {'_id': container_doc['_id']},
                            {'$set': {'status': 'running'}}
                        )
                    return jsonify({'running': is_running, 'port': port, 'container_name': container_name}), 200
                except docker.errors.NotFound:
                    db.ibkr_containers.update_one(
                        {'_id': container_doc['_id']},
                        {'$set': {'status': 'stopped'}}
                    )
                    return jsonify({'running': False, 'port': None, 'container_name': container_name}), 200
            except Exception as e:
                logger.error(f"Error checking ibeam status: {e}")
                return jsonify({'error': 'Failed to check container status'}), 500

        @self.app.route('/api/ibkr/stop/<exchange_id>', methods=['DELETE'])
        def ibkr_stop(exchange_id):
            """Stop and remove ibeam Docker container for an IBKR exchange"""
            import docker

            try:
                from mongo_db import get_db
                db = get_db()

                container_doc = db.ibkr_containers.find_one({'exchange_id': exchange_id})
                if not container_doc:
                    return jsonify({'error': 'Container not found in database'}), 404

                container_name = container_doc.get('container_name')

                # Stop and remove container
                try:
                    client = docker.from_env()
                    container = client.containers.get(container_name)
                    container.stop(timeout=10)
                    container.remove()
                    logger.info(f"Stopped and removed ibeam container {container_name}")
                except docker.errors.NotFound:
                    logger.warning(f"Container {container_name} not found in Docker")

                # Remove from MongoDB
                db.ibkr_containers.delete_one({'_id': container_doc['_id']})

                return jsonify({'status': 'stopped'}), 200
            except Exception as e:
                logger.error(f"Error stopping ibeam container: {e}", exc_info=True)
                return jsonify({'error': f'Failed to stop container: {str(e)}'}), 500

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
