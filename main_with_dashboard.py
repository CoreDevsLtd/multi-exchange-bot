"""
Main Application with Dashboard
Trading Bot Entry Point with Web Dashboard
"""

import os
import json
import logging
import threading
from dotenv import load_dotenv
from mexc_client import MEXCClient
from trading_executor import TradingExecutor
from webhook_handler import WebhookHandler
from dashboard import Dashboard
from signal_monitor import SignalMonitor

# Load environment variables
load_dotenv()

# Setup logging
def setup_logging(log_level: str = 'INFO', log_file: str = 'trading_bot.log'):
    """Setup logging configuration"""
    import colorlog
    
    # Create formatters
    console_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger


def load_dashboard_config(config_file: str = 'dashboard_config.json') -> dict:
    """Load configuration from dashboard config file"""
    default_config = {
        'exchanges': {
            'mexc': {
                'enabled': False,
                'api_key': '',
                'api_secret': '',
                'base_url': 'https://api.mexc.com',
                'name': 'MEXC'
            },
            'alpaca': {
                'enabled': False,
                'api_key': '',
                'api_secret': '',
                'base_url': 'https://paper-api.alpaca.markets',
                'name': 'Alpaca',
                'paper_trading': True
            },
            'ibkr': {
                'enabled': False,
                'api_key': '',
                'api_secret': '',
                'base_url': 'https://localhost:5000',
                'name': 'Interactive Brokers',
                'account_id': '',
                'use_paper': False,
                'leverage': 1
            },
            'bybit': {
                'enabled': False,
                'api_key': '',
                'api_secret': '',
                'base_url': 'https://api.bybit.com',
                'name': 'Bybit',
                'testnet': False
            }
        },
        'trading_settings': {
            'position_size_percent': 20.0,
            'position_size_fixed': '',
            'use_percentage': True,
            'webhook_port': 5000,
            'webhook_host': '0.0.0.0'
        }
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                loaded_config = json.load(f)
                # Merge with defaults
                default_config.update(loaded_config)
        except Exception as e:
            logging.error(f"Error loading dashboard config: {e}")
    
    return default_config


def _build_executor_config(trading_settings: dict, risk_mgmt: dict) -> dict:
    """Build executor config with correct key mapping from dashboard settings."""
    cfg = trading_settings.copy()
    cfg['STOP_LOSS_PERCENT'] = float(risk_mgmt.get('stop_loss_percent', 5.0))
    cfg['POSITION_SIZE_PERCENT'] = float(trading_settings.get('position_size_percent', 20.0))
    cfg['POSITION_SIZE_FIXED'] = trading_settings.get('position_size_fixed') or None
    use_pct = trading_settings.get('use_percentage', True)
    cfg['USE_PERCENTAGE'] = bool(use_pct) if not isinstance(use_pct, str) else str(use_pct).lower() == 'true'
    cfg['warn_existing_positions'] = trading_settings.get('warn_existing_positions', True)
    return cfg


def create_exchange_clients(config: dict) -> dict:
    """
    Create exchange client instances based on configuration
    Validates connections and logs status
    
    Args:
        config: Dashboard configuration
        
    Returns:
        Dictionary of exchange clients
    """
    clients = {}
    
    for exchange_name, exchange_config in config.get('exchanges', {}).items():
        if not exchange_config.get('enabled', False):
            continue
        
        # Get and trim API credentials (whitespace can cause signature errors)
        api_key = exchange_config.get('api_key', '').strip()
        api_secret = exchange_config.get('api_secret', '').strip()
        base_url = exchange_config.get('base_url', '').strip()
        
        # Log loaded keys (masked) for verification
        if api_key:
            masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "***"
            logging.info(f"📋 Loaded {exchange_name} API Key from config: {masked_key} (length: {len(api_key)})")
        if api_secret:
            masked_secret = f"{api_secret[:6]}...{api_secret[-4:]}" if len(api_secret) > 10 else "***"
            logging.info(f"📋 Loaded {exchange_name} API Secret from config: {masked_secret} (length: {len(api_secret)})")
        
        if exchange_name != 'ibkr' and (not api_key or not api_secret):
            logging.warning(f"{exchange_name} is enabled but missing API credentials")
            continue
        if exchange_name == 'ibkr' and not base_url:
            base_url = 'https://localhost:5000'
        
        try:
            if exchange_name == 'mexc':
                from mexc_client import MEXCClient
                sub_account_id = exchange_config.get('sub_account_id', '')
                use_sub_account = exchange_config.get('use_sub_account', False)
                
                client = MEXCClient(
                    api_key=api_key,
                    api_secret=api_secret,
                    base_url=base_url,
                    sub_account_id=sub_account_id,
                    use_sub_account=use_sub_account
                )
                
                # Validate connection
                logging.info(f"Validating {exchange_name} connection...")
                validation = client.validate_connection()
                
                if validation['connected']:
                    logging.info(f"✅ {exchange_name} connected successfully")
                    if validation['can_trade']:
                        logging.info(f"✅ {exchange_name} has trading permissions")
                    else:
                        logging.warning(f"⚠️  {exchange_name} connected but no trading permissions")
                    
                    # Log main balances
                    balances = client.get_main_balances()
                    if balances:
                        balance_str = ', '.join([f"{asset}: {bal['total']:.2f}" 
                                               for asset, bal in balances.items() if bal['total'] > 0.01])
                        if balance_str:
                            logging.info(f"💰 {exchange_name} balances: {balance_str}")
                    else:
                        logging.info(f"💰 {exchange_name} balances: No significant balances found")
                    
                    clients['mexc'] = client
                    
                    if use_sub_account:
                        logging.info(f"MEXC client initialized with sub-account: {sub_account_id}")
                    else:
                        logging.info(f"MEXC client initialized (main account)")
                else:
                    error_msg = validation.get('error', 'Unknown error')
                    logging.error(f"❌ {exchange_name} connection failed: {error_msg}")
                    logging.warning(f"{exchange_name} will not be available for trading")
                    
            elif exchange_name == 'alpaca':
                from alpaca_client import AlpacaClient
                
                client = AlpacaClient(
                    api_key=api_key,
                    api_secret=api_secret,
                    base_url=base_url
                )
                
                # Validate connection
                logging.info(f"Validating {exchange_name} connection...")
                validation = client.validate_connection()
                
                if validation['connected']:
                    logging.info(f"✅ {exchange_name} connected successfully")
                    if validation['can_trade']:
                        logging.info(f"✅ {exchange_name} has trading permissions")
                    else:
                        logging.warning(f"⚠️  {exchange_name} connected but no trading permissions")
                    
                    # Log main balances
                    balances = client.get_main_balances()
                    if balances:
                        balance_str = ', '.join([f"{asset}: {bal['total']:.2f}" 
                                               for asset, bal in balances.items() if bal['total'] > 0.01])
                        if balance_str:
                            logging.info(f"💰 {exchange_name} balances: {balance_str}")
                    else:
                        logging.info(f"💰 {exchange_name} balances: No significant balances found")
                    
                    clients['alpaca'] = client
                    logging.info(f"Alpaca client initialized ({'Paper' if 'paper' in base_url.lower() else 'Live'} trading)")
                else:
                    error_msg = validation.get('error', 'Unknown error')
                    logging.error(f"❌ {exchange_name} connection failed: {error_msg}")
                    logging.warning(f"{exchange_name} will not be available for trading")
                    
            elif exchange_name == 'ibkr':
                from ibkr_client import IBKRClient
                
                account_id = exchange_config.get('account_id', '')
                use_paper = exchange_config.get('use_paper', False)
                leverage = exchange_config.get('leverage', 1)
                
                client = IBKRClient(
                    api_key=api_key,
                    api_secret=api_secret,
                    base_url=base_url,
                    account_id=account_id,
                    use_paper=use_paper,
                    leverage=leverage
                )
                
                # Validate connection
                logging.info(f"Validating {exchange_name} connection...")
                validation = client.validate_connection()
                
                if validation['connected']:
                    logging.info(f"✅ {exchange_name} connected successfully")
                    if validation['can_trade']:
                        logging.info(f"✅ {exchange_name} has trading permissions")
                    else:
                        logging.warning(f"⚠️  {exchange_name} connected but no trading permissions")
                    
                    # Log main balances
                    balances = client.get_main_balances()
                    if balances:
                        balance_str = ', '.join([f"{asset}: {bal['total']:.2f}" 
                                               for asset, bal in balances.items() if bal['total'] > 0.01])
                        if balance_str:
                            logging.info(f"💰 {exchange_name} balances: {balance_str}")
                    else:
                        logging.info(f"💰 {exchange_name} balances: No significant balances found")
                    
                    clients['ibkr'] = client
                    logging.info(f"IBKR client initialized ({'Paper' if use_paper else 'Live'} trading)")
                    if account_id:
                        logging.info(f"Using account ID: {account_id}")
                else:
                    error_msg = validation.get('error', 'Unknown error')
                    logging.error(f"❌ {exchange_name} connection failed: {error_msg}")
                    logging.warning(f"{exchange_name} will not be available for trading")
                    logging.warning("⚠️  Make sure IB Gateway or TWS is running and API is enabled")
                    
            elif exchange_name == 'bybit':
                from bybit_client import BybitClient
                
                testnet = exchange_config.get('testnet', False)
                trading_mode = exchange_config.get('trading_mode', 'spot')
                leverage = exchange_config.get('leverage', 1)
                proxy = (exchange_config.get('proxy') or '').strip() or None
                
                client = BybitClient(
                    api_key=api_key,
                    api_secret=api_secret,
                    base_url=base_url,
                    testnet=testnet,
                    trading_mode=trading_mode,
                    leverage=leverage,
                    proxy=proxy
                )
                
                # Validate connection
                logging.info(f"Validating {exchange_name} connection...")
                validation = client.validate_connection()
                
                if validation['connected']:
                    logging.info(f"✅ {exchange_name} connected successfully")
                    if validation['can_trade']:
                        logging.info(f"✅ {exchange_name} has trading permissions")
                    else:
                        logging.warning(f"⚠️  {exchange_name} connected but no trading permissions")
                    
                    # Log main balances
                    balances = client.get_main_balances()
                    if balances:
                        balance_str = ', '.join([f"{asset}: {bal['total']:.2f}" 
                                               for asset, bal in balances.items() if bal['total'] > 0.01])
                        if balance_str:
                            logging.info(f"💰 {exchange_name} balances: {balance_str}")
                    else:
                        logging.info(f"💰 {exchange_name} balances: No significant balances found")
                    
                    clients['bybit'] = client
                    logging.info(f"Bybit client initialized ({'Testnet' if testnet else 'Mainnet'})")
                else:
                    error_msg = validation.get('error', 'Unknown error')
                    logging.error(f"❌ {exchange_name} connection failed: {error_msg}")
                    logging.warning(f"{exchange_name} will not be available for trading")
                    
            else:
                logging.warning(f"Unknown exchange: {exchange_name}")
        except Exception as e:
            logging.error(f"Failed to initialize {exchange_name} client: {e}", exc_info=True)
    
    return clients


def main():
    """Main application entry point"""
    
    # Setup logging
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    log_file = os.getenv('LOG_FILE', 'trading_bot.log')
    logger = setup_logging(log_level, log_file)
    
    logger.info("=" * 60)
    logger.info("Multi-Exchange Trading Bot with Dashboard - Starting...")
    logger.info("=" * 60)
    
    # Load dashboard configuration
    dashboard_config = load_dashboard_config()
    
    # Get trading settings from dashboard config
    trading_settings = dashboard_config.get('trading_settings', {})
    
    # Check Railway IP for MEXC whitelist (if on Railway)
    if os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('PORT'):
        try:
            from mexc_ip_manager import MEXCIPManager
            ip_manager = MEXCIPManager()
            current_ip = ip_manager.get_current_ip()
            if current_ip:
                logger.info(f"🌐 Railway IP detected: {current_ip}")
                logger.warning("⚠️  If MEXC connection fails, add this IP to MEXC API whitelist")
                logger.warning("⚠️  Note: Keys without IP whitelist expire in 90 days")
        except Exception as e:
            logger.debug(f"Could not check IP: {e}")
    
    # Create exchange clients
    exchange_clients = create_exchange_clients(dashboard_config)
    
    if not exchange_clients:
        logger.warning("No enabled exchanges found. Please configure exchanges in the dashboard.")
        logger.info("Starting dashboard only...")
    else:
        logger.info(f"Initialized {len(exchange_clients)} exchange client(s)")
        # Log sub-account usage for MEXC
        for name, client in exchange_clients.items():
            if name == 'mexc' and hasattr(client, 'use_sub_account') and client.use_sub_account:
                logger.info(f"MEXC using sub-account: {client.sub_account_id}")
    
    # Initialize signal monitor
    signal_monitor = SignalMonitor()
    logger.info("Signal monitor initialized")
    
    # Webhook creates executors dynamically for all enabled exchanges
    trading_executor = None
    if exchange_clients:
        logger.info(f"Trading executors will be created per-exchange when signals arrive")
        logger.info("⚠️  CRITICAL: Stop-loss will move to entry after TP1 (hard requirement)")
    
    # Initialize webhook handler (always initialize, even without executor for demo mode)
    # Webhook routes will be integrated into dashboard Flask app (single server)
    webhook_handler = WebhookHandler(trading_executor, signal_monitor)
    logger.info("Webhook handler initialized")
    
    # Check if demo mode should be enabled (opt-in via environment variable)
    enable_demo_mode = os.getenv('DEMO_MODE', 'false').lower() == 'true'
    
    if not trading_executor:
        if enable_demo_mode:
            logger.info("🎮 Running in demo mode - Webhook will simulate trades")
        else:
            logger.warning("⚠️  No trading executor available. Please configure exchange API keys in dashboard.")
            logger.warning("⚠️  Set DEMO_MODE=true environment variable to enable demo mode.")
    
    # Initialize and start dashboard
    dashboard = Dashboard()
    
    # Enable demo mode only if explicitly requested via environment variable
    if enable_demo_mode:
        if dashboard.demo_mode and not dashboard.demo_mode.is_active():
            dashboard.demo_mode.enable(signal_monitor)
            logger.info("🎮 Demo mode enabled with demo signals")
    else:
        # Ensure demo mode is disabled
        if dashboard.demo_mode and dashboard.demo_mode.is_active():
            dashboard.demo_mode.disable()
            logger.info("✅ Demo mode disabled - Using real API connections")
    
    # Set signal_monitor reference in dashboard for API endpoints
    dashboard.signal_monitor = signal_monitor
    
    # Store dashboard reference in webhook handler so it can access config
    webhook_handler.dashboard = dashboard
    
    # Integrate webhook route into dashboard Flask app (single server, no port conflict)
    # Register webhook handler's route in dashboard app
    webhook_handler._register_routes_to_app(dashboard.app)
    
    # Use PORT from environment (for Railway/Render) or config default
    # Dashboard and webhook run on same port (single Flask app)
    dashboard_port = int(os.getenv('PORT', os.getenv('DASHBOARD_PORT', 8080)))
    dashboard_host = os.getenv('DASHBOARD_HOST', '0.0.0.0')
    
    logger.info("=" * 60)
    logger.info(f"Dashboard starting on {dashboard_host}:{dashboard_port}")
    logger.info(f"Access dashboard at: http://localhost:{dashboard_port}")
    logger.info(f"Webhook endpoint: http://localhost:{dashboard_port}/webhook")
    logger.info("=" * 60)
    
    try:
        dashboard.run(
            host=dashboard_host,
            port=dashboard_port,
            debug=(log_level.upper() == 'DEBUG')
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == '__main__':
    main()

