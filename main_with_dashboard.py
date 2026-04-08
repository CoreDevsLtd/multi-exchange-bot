"""
Main Application with Dashboard
Trading Bot Entry Point with Web Dashboard
"""

import os
import logging
from dotenv import load_dotenv
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


def main():
    """Main application entry point"""
    
    # Setup logging
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    log_file = os.getenv('LOG_FILE', 'trading_bot.log')
    logger = setup_logging(log_level, log_file)
    
    logger.info("=" * 60)
    logger.info("Multi-Exchange Trading Bot with Dashboard - Starting...")
    logger.info("=" * 60)

    # Validate required environment variables
    if not os.getenv('MONGO_URI') and not os.getenv('MONGODB_URI'):
        logger.critical("MONGO_URI environment variable is required. Set it to your MongoDB connection string.")
        raise SystemExit(1)

    # Ensure MongoDB indexes on startup
    try:
        from mongo_db import ensure_indexes
        ensure_indexes()
        logger.info("✅ MongoDB indexes ensured")
    except Exception as e:
        logger.warning(f"Could not ensure MongoDB indexes: {e}")

    # Check Railway IP for MEXC whitelist (if on Railway)
    if os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('PORT'):
        try:
            from mexc_ip_manager import MEXCIPManager
            ip_manager = MEXCIPManager()
            current_ip = ip_manager.get_current_ip()
            if current_ip:
                logger.info(f"🌐 Railway IP detected: {current_ip}")
                logger.warning("⚠️  If MEXC connection fails, add this IP to MEXC API whitelist")
        except Exception as e:
            logger.debug(f"Could not check IP: {e}")

    # Initialize signal monitor
    signal_monitor = SignalMonitor()
    logger.info("Signal monitor initialized")

    # Initialize webhook handler — executors are created per-signal from MongoDB
    webhook_handler = WebhookHandler(signal_monitor=signal_monitor)
    logger.info("Webhook handler initialized")

    # Check if demo mode should be enabled (opt-in via environment variable)
    enable_demo_mode = os.getenv('DEMO_MODE', 'false').lower() == 'true'
    if enable_demo_mode:
        logger.info("🎮 Running in demo mode - Webhook will simulate trades")

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

