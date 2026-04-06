"""
Signal Monitor
Tracks TradingView webhook signals and connection status
Keeps signals for at least 1 day (24 hours)
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import deque
import threading

class SignalMonitor:
    """Monitors TradingView webhook signals"""
    
    def __init__(self, max_signals: int = 1000, retention_hours: float = 24.0):
        """
        Initialize Signal Monitor
        
        Args:
            max_signals: Maximum number of signals to keep in history (safety limit)
            retention_hours: Number of hours to keep signals (default: 24 hours = 1 day)
        """
        self.max_signals = max_signals
        self.retention_hours = retention_hours
        self.retention_seconds = retention_hours * 3600  # Convert hours to seconds
        self.signals = deque(maxlen=max_signals)
        self.last_signal_time = None
        self.last_signal_data = None
        self.total_signals = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.lock = threading.Lock()
        self.webhook_connected = False
        self.webhook_last_ping = None
        
    def add_signal(self, signal_data: Dict, executed: bool = False, error: Optional[str] = None):
        """
        Add a signal to the monitor
        
        Args:
            signal_data: Signal data from TradingView
            executed: Whether the trade was executed successfully
            error: Error message if execution failed
        """
        with self.lock:
            # Handle price as dict or direct value
            price_value = 0
            if isinstance(signal_data.get('price'), dict):
                price_value = signal_data.get('price', {}).get('close', 0)
            elif signal_data.get('price'):
                price_value = float(signal_data.get('price', 0))
            
            signal_record = {
                'timestamp': time.time(),
                'datetime': datetime.now().isoformat(),
                'symbol': signal_data.get('symbol', ''),
                'signal': signal_data.get('signal', ''),
                'price': price_value,
                'executed': executed,
                'error': error,
                'indicators': signal_data.get('indicators', {})
            }
            
            self.signals.append(signal_record)
            self.last_signal_time = time.time()
            self.last_signal_data = signal_record
            self.total_signals += 1
            
            if executed:
                self.successful_trades += 1
            elif error:
                self.failed_trades += 1
    
    def _cleanup_old_signals(self):
        """Remove signals older than retention period"""
        current_time = time.time()
        cutoff_time = current_time - self.retention_seconds
        
        # Remove signals older than retention period
        while self.signals and self.signals[0]['timestamp'] < cutoff_time:
            self.signals.popleft()
    
    def get_recent_signals(self, limit: int = 10, hours: Optional[float] = None) -> List[Dict]:
        """
        Get recent signals from the last 24 hours (or specified hours)
        
        Args:
            limit: Maximum number of signals to return (default: 10, use None for all)
            hours: Number of hours to look back (default: uses retention_hours, typically 24)
            
        Returns:
            List of recent signal records from the last 24 hours
        """
        with self.lock:
            # Clean up old signals first
            self._cleanup_old_signals()
            
            # Determine time cutoff
            current_time = time.time()
            if hours is not None:
                cutoff_time = current_time - (hours * 3600)
            else:
                # Use retention period (default 24 hours)
                cutoff_time = current_time - self.retention_seconds
            
            # Filter signals from the last 24 hours (or specified period)
            recent_signals = [
                signal for signal in self.signals
                if signal['timestamp'] >= cutoff_time
            ]
            
            # Sort by timestamp (newest first)
            recent_signals.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Apply limit if specified
            if limit is not None and limit > 0:
                return recent_signals[:limit]
            
            return recent_signals
    
    def get_status(self) -> Dict:
        """
        Get current monitoring status
        
        Returns:
            Status dictionary
        """
        with self.lock:
            time_since_last = None
            if self.last_signal_time:
                time_since_last = time.time() - self.last_signal_time
            
            webhook_status = 'connected' if self.webhook_connected else 'disconnected'
            if self.webhook_last_ping:
                ping_age = time.time() - self.webhook_last_ping
                if ping_age > 300:  # 5 minutes
                    webhook_status = 'disconnected'
            
            # Clean up old signals before reporting count
            self._cleanup_old_signals()
            
            # Count signals from last 24 hours
            current_time = time.time()
            cutoff_time = current_time - self.retention_seconds
            recent_count = sum(1 for s in self.signals if s['timestamp'] >= cutoff_time)
            
            return {
                'webhook_status': webhook_status,
                'last_signal_time': self.last_signal_time,
                'last_signal_datetime': self.last_signal_data['datetime'] if self.last_signal_data else None,
                'time_since_last_signal': time_since_last,
                'total_signals': self.total_signals,
                'successful_trades': self.successful_trades,
                'failed_trades': self.failed_trades,
                'recent_signals_count': recent_count,
                'total_stored_signals': len(self.signals),
                'retention_hours': self.retention_hours,
                'last_signal': self.last_signal_data
            }
    
    def ping_webhook(self):
        """Mark webhook as active (called periodically)"""
        with self.lock:
            self.webhook_connected = True
            self.webhook_last_ping = time.time()
    
    def mark_webhook_disconnected(self):
        """Mark webhook as disconnected"""
        with self.lock:
            self.webhook_connected = False

