# WSGI entrypoint for production servers (gunicorn)
import os
import logging
from signal_monitor import SignalMonitor
from webhook_handler import WebhookHandler
from dashboard import Dashboard

# Setup file logging (stdout logging is handled by gunicorn/Docker)
_log_file = os.getenv('LOG_FILE', 'trading_bot.log')
_log_level = os.getenv('LOG_LEVEL', 'INFO')
_root_logger = logging.getLogger()
_root_logger.setLevel(getattr(logging, _log_level.upper(), logging.INFO))
if not _root_logger.handlers:
    _sh = logging.StreamHandler()
    _sh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    _root_logger.addHandler(_sh)
_fh = logging.FileHandler(_log_file)
_fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
_root_logger.addHandler(_fh)

_signal_monitor = SignalMonitor()
_dashboard = Dashboard()
_dashboard.signal_monitor = _signal_monitor

_webhook_handler = WebhookHandler(signal_monitor=_signal_monitor)
_webhook_handler.dashboard = _dashboard
_dashboard.webhook_handler = _webhook_handler
_webhook_handler._register_routes_to_app(_dashboard.app)

# Expose Flask app for gunicorn: gunicorn wsgi:app
app = _dashboard.app
