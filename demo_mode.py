"""
Demo Mode
Simulates trading activity for client demonstration
"""

import time
import random
from typing import Dict, List
from datetime import datetime, timedelta

class DemoMode:
    """Simulates trading activity for demonstration"""
    
    # Singleton instance
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DemoMode, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if DemoMode._initialized:
            return
        DemoMode._initialized = True
        self.demo_active = False
        self.demo_trades = []
        self.demo_positions = []
        self.demo_balances = {
            'USDT': {'free': 10000.0, 'locked': 0.0, 'total': 10000.0},
            'BTC': {'free': 0.5, 'locked': 0.0, 'total': 0.5},
            'ETH': {'free': 10.0, 'locked': 0.0, 'total': 10.0}
        }
        self.start_time = time.time()
    
    def enable(self, signal_monitor=None):
        """Enable demo mode"""
        self.demo_active = True
        self.start_time = time.time()
        # Generate some initial demo trades
        self._generate_demo_trades()
        # Add some demo positions
        self._generate_demo_positions()
        # Generate demo signals if signal monitor is provided
        if signal_monitor:
            self._generate_demo_signals(signal_monitor)
    
    def disable(self):
        """Disable demo mode"""
        self.demo_active = False
    
    def is_active(self) -> bool:
        """Check if demo mode is active"""
        return self.demo_active
    
    def get_demo_balances(self) -> Dict:
        """Get demo account balances"""
        if not self.demo_active:
            return {}
        return self.demo_balances.copy()
    
    def get_demo_connection_status(self) -> Dict:
        """Get demo connection status"""
        if not self.demo_active:
            return {'connected': False, 'can_trade': False}
        return {
            'connected': True,
            'can_trade': True,
            'permissions': ['SPOT'],
            'demo_mode': True
        }
    
    def get_demo_trades(self, limit: int = 10) -> List[Dict]:
        """Get recent demo trades"""
        if not self.demo_active:
            return []
        return self.demo_trades[-limit:]
    
    def get_demo_positions(self) -> List[Dict]:
        """Get demo open positions"""
        if not self.demo_active:
            return []
        return self.demo_positions.copy()
    
    def simulate_trade(self, symbol: str, side: str, price: float, quantity: float) -> Dict:
        """Simulate a trade execution"""
        if not self.demo_active:
            return {}
        
        trade = {
            'id': f"DEMO_{int(time.time() * 1000)}",
            'symbol': symbol,
            'side': side.upper(),
            'price': price,
            'quantity': quantity,
            'amount': price * quantity,
            'status': 'FILLED',
            'timestamp': int(time.time() * 1000),
            'datetime': datetime.now().isoformat(),
            'demo': True
        }
        
        self.demo_trades.append(trade)
        
        # Update balances (simplified)
        if side.upper() == 'BUY':
            # Buying: reduce USDT, increase base currency
            base = symbol.replace('USDT', '')
            if base in self.demo_balances:
                self.demo_balances[base]['total'] += quantity
                self.demo_balances[base]['free'] += quantity
            self.demo_balances['USDT']['total'] -= trade['amount']
            self.demo_balances['USDT']['free'] -= trade['amount']
        else:  # SELL
            # Selling: increase USDT, reduce base currency
            base = symbol.replace('USDT', '')
            if base in self.demo_balances:
                self.demo_balances[base]['total'] -= quantity
                self.demo_balances[base]['free'] -= quantity
            self.demo_balances['USDT']['total'] += trade['amount']
            self.demo_balances['USDT']['free'] += trade['amount']
        
        return trade
    
    def _generate_demo_trades(self):
        """Generate some initial demo trades"""
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
        prices = {'BTCUSDT': 45000, 'ETHUSDT': 2500, 'BNBUSDT': 300}
        
        # Generate 5-8 demo trades
        num_trades = random.randint(5, 8)
        for i in range(num_trades):
            symbol = random.choice(symbols)
            side = random.choice(['BUY', 'SELL'])
            price = prices[symbol] * (1 + random.uniform(-0.02, 0.02))
            quantity = random.uniform(0.001, 0.1) if 'BTC' in symbol else random.uniform(0.01, 1.0)
            
            # Create trade with timestamp in the past
            trade_time = datetime.now() - timedelta(hours=random.randint(1, 24))
            trade = {
                'id': f"DEMO_{int(trade_time.timestamp() * 1000)}",
                'symbol': symbol,
                'side': side,
                'price': round(price, 2),
                'quantity': round(quantity, 6),
                'amount': round(price * quantity, 2),
                'status': 'FILLED',
                'timestamp': int(trade_time.timestamp() * 1000),
                'datetime': trade_time.isoformat(),
                'demo': True
            }
            self.demo_trades.append(trade)
        
        # Sort by timestamp
        self.demo_trades.sort(key=lambda x: x['timestamp'])
    
    def _generate_demo_positions(self):
        """Generate some initial demo positions"""
        symbols = ['BTCUSDT', 'ETHUSDT']
        prices = {'BTCUSDT': 45000, 'ETHUSDT': 2500}
        
        # Generate 1-2 demo positions
        for symbol in symbols[:2]:  # Just BTC and ETH
            entry_price = prices[symbol] * (1 + random.uniform(-0.01, 0.01))
            quantity = random.uniform(0.01, 0.05) if 'BTC' in symbol else random.uniform(0.5, 2.0)
            
            self.add_demo_position(symbol, 'BUY', entry_price, quantity)
    
    def _generate_demo_signals(self, signal_monitor):
        """Generate demo signals for the signal monitor"""
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
        prices = {'BTCUSDT': 45000, 'ETHUSDT': 2500, 'BNBUSDT': 300}
        
        # Generate 8-10 demo signals
        num_signals = random.randint(8, 10)
        signal_times = []
        
        for i in range(num_signals):
            symbol = random.choice(symbols)
            side = random.choice(['BUY', 'SELL'])
            price = prices[symbol] * (1 + random.uniform(-0.02, 0.02))
            
            # Create signal with timestamp in the past (spread over last 2 hours)
            signal_time = datetime.now() - timedelta(minutes=random.randint(5, 120))
            signal_times.append(signal_time.timestamp())
            
            signal_data = {
                'symbol': symbol,
                'signal': side,
                'price': {'close': price},
                'indicators': {
                    'wt': {'value': random.uniform(-0.5, 0.5)},
                    'bb': {'position': random.choice(['upper', 'middle', 'lower'])},
                    'rsi': {'value': random.uniform(30, 70)}
                }
            }
            
            # Add signal to monitor (all executed successfully in demo)
            signal_monitor.add_signal(signal_data, executed=True)
        
        # Update last signal time to most recent
        if signal_times:
            signal_monitor.last_signal_time = max(signal_times)
        else:
            signal_monitor.last_signal_time = time.time()
        
        # Mark webhook as connected
        signal_monitor.ping_webhook()
    
    def add_demo_position(self, symbol: str, side: str, entry_price: float, quantity: float):
        """Add a demo position"""
        if not self.demo_active:
            return
        
        position = {
            'symbol': symbol,
            'side': side.upper(),
            'entry_price': entry_price,
            'quantity': quantity,
            'current_price': entry_price * (1 + random.uniform(-0.01, 0.05)),
            'unrealized_pnl': 0.0,
            'timestamp': int(time.time() * 1000),
            'demo': True
        }
        
        # Calculate PnL
        if side.upper() == 'BUY':
            position['unrealized_pnl'] = (position['current_price'] - entry_price) * quantity
        else:
            position['unrealized_pnl'] = (entry_price - position['current_price']) * quantity
        
        self.demo_positions.append(position)
    
    def get_demo_stats(self) -> Dict:
        """Get demo trading statistics"""
        if not self.demo_active:
            return {}
        
        total_trades = len(self.demo_trades)
        buy_trades = len([t for t in self.demo_trades if t['side'] == 'BUY'])
        sell_trades = len([t for t in self.demo_trades if t['side'] == 'SELL'])
        
        total_volume = sum(t['amount'] for t in self.demo_trades)
        
        return {
            'total_trades': total_trades,
            'buy_trades': buy_trades,
            'sell_trades': sell_trades,
            'total_volume': round(total_volume, 2),
            'open_positions': len(self.demo_positions),
            'uptime_seconds': int(time.time() - self.start_time)
        }

