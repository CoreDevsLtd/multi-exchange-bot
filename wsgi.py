# WSGI entrypoint for production servers (gunicorn)
from signal_monitor import SignalMonitor
from webhook_handler import WebhookHandler
from dashboard import Dashboard

_signal_monitor = SignalMonitor()
_dashboard = Dashboard()
_dashboard.signal_monitor = _signal_monitor

_webhook_handler = WebhookHandler(signal_monitor=_signal_monitor)
_webhook_handler.dashboard = _dashboard
_webhook_handler._register_routes_to_app(_dashboard.app)

# Expose Flask app for gunicorn: gunicorn wsgi:app
app = _dashboard.app
