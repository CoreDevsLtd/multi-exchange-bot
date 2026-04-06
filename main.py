"""
Main Application
Trading Bot Entry Point
"""

import os
import logging
import colorlog
from dotenv import load_dotenv
from mexc_client import MEXCClient
from trading_executor import TradingExecutor
from webhook_handler import WebhookHandler

# Load environment variables
load_dotenv()

# Setup logging
def setup_logging(log_level: str = 'INFO', log_file: str = 'trading_bot.log'):
    """Setup logging configuration"""
    
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
    logger.info("Multi-Exchange Trading Bot - Starting...")
    logger.info("=" * 60)
    
    # Load configuration
    config = {
        'MEXC_API_KEY': os.getenv('MEXC_API_KEY'),
        'MEXC_API_SECRET': os.getenv('MEXC_API_SECRET'),
        'MEXC_BASE_URL': os.getenv('MEXC_BASE_URL', 'https://api.mexc.com'),
        'WEBHOOK_PORT': int(os.getenv('WEBHOOK_PORT', 5000)),
        'WEBHOOK_HOST': os.getenv('WEBHOOK_HOST', '0.0.0.0'),
        'POSITION_SIZE_PERCENT': os.getenv('POSITION_SIZE_PERCENT', '20.0'),
        'POSITION_SIZE_FIXED': os.getenv('POSITION_SIZE_FIXED'),
        'USE_PERCENTAGE': os.getenv('USE_PERCENTAGE', 'true'),
        'LOG_LEVEL': log_level,
        'LOG_FILE': log_file
    }
    
    # Validate required configuration
    if not config['MEXC_API_KEY'] or not config['MEXC_API_SECRET']:
        logger.error("MEXC_API_KEY and MEXC_API_SECRET must be set in environment variables")
        logger.error("Please copy config.example.env to .env and fill in your credentials")
        return
    
    logger.info("Configuration loaded successfully")
    logger.info(f"Position size: {config['POSITION_SIZE_PERCENT']}% (percentage mode)")
    logger.info("Trading pairs: Determined by TradingView indicator configuration")
    
    # Initialize MEXC client
    try:
        mexc_client = MEXCClient(
            api_key=config['MEXC_API_KEY'],
            api_secret=config['MEXC_API_SECRET'],
            base_url=config['MEXC_BASE_URL']
        )
        
        # Test connection
        account_info = mexc_client.get_account_info()
        logger.info("MEXC API connection successful")
        logger.info(f"Account permissions: {account_info.get('permissions', [])}")
        
    except Exception as e:
        logger.error(f"Failed to initialize MEXC client: {e}")
        return
    
    # Initialize trading executor
    trading_executor = TradingExecutor(mexc_client, config)
    logger.info("Trading executor initialized")
    
    # Initialize webhook handler
    webhook_handler = WebhookHandler(trading_executor)
    logger.info("Webhook handler initialized")
    
    # Start webhook server
    logger.info("=" * 60)
    logger.info(f"Webhook server starting on {config['WEBHOOK_HOST']}:{config['WEBHOOK_PORT']}")
    logger.info("Waiting for TradingView alerts...")
    logger.info("=" * 60)
    
    try:
        webhook_handler.run(
            host=config['WEBHOOK_HOST'],
            port=config['WEBHOOK_PORT'],
            debug=(log_level.upper() == 'DEBUG')
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == '__main__':
    main()

