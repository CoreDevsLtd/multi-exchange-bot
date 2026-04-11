#!/usr/bin/env python3
"""
IBKR Integration Verification Script
Tests:
1. MongoDB connectivity
2. IBKR exchange account configuration
3. ibeam container spawn from dashboard API
4. IBKRClient connection test
5. Webhook routing to IBKR executor
6. Trade execution simulation
"""

import requests
import json
import time
import os
import sys
from typing import Dict, Tuple

# Configuration
DASHBOARD_BASE_URL = os.getenv('DASHBOARD_URL', 'http://localhost:5000')
MONGO_URI = os.getenv('MONGO_URI')

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def log(level: str, msg: str):
    """Colored log output"""
    colors = {
        'pass': Colors.GREEN,
        'fail': Colors.RED,
        'info': Colors.BLUE,
        'warn': Colors.YELLOW
    }
    color = colors.get(level, Colors.RESET)
    symbol = {'pass': '✅', 'fail': '❌', 'info': 'ℹ️ ', 'warn': '⚠️ '}[level]
    print(f"{color}{symbol} {msg}{Colors.RESET}")

def test_mongodb_connection() -> bool:
    """Test MongoDB connectivity"""
    log('info', "Testing MongoDB connection...")
    if not MONGO_URI:
        log('fail', "MONGO_URI environment variable not set")
        return False

    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        log('pass', "MongoDB connected")

        # Check collections
        db = client[os.getenv('MONGO_DB', 'multi_exchange_bot')]
        collections = db.list_collection_names()
        required = ['accounts', 'exchange_accounts', 'trades', 'central_risk_management']
        found = [c for c in required if c in collections]
        log('info', f"Collections present: {', '.join(found)}")
        return True
    except Exception as e:
        log('fail', f"MongoDB connection failed: {e}")
        return False

def test_ibkr_accounts() -> Tuple[bool, list]:
    """Check if IBKR exchange accounts are configured"""
    log('info', "Checking IBKR exchange accounts in MongoDB...")
    try:
        from mongo_db import get_enabled_exchange_accounts
        accounts = get_enabled_exchange_accounts()
        ibkr_accounts = [a for a in accounts if a.get('type') == 'ibkr']

        if not ibkr_accounts:
            log('warn', "No IBKR exchange accounts configured")
            return False, []

        log('pass', f"Found {len(ibkr_accounts)} IBKR account(s)")
        for acc in ibkr_accounts:
            log('info', f"  - {acc.get('_id')}: symbol={acc.get('symbol')}, enabled={acc.get('enabled')}")

        return True, ibkr_accounts
    except Exception as e:
        log('fail', f"Failed to check IBKR accounts: {e}")
        return False, []

def test_dashboard_health() -> bool:
    """Test dashboard API health"""
    log('info', f"Testing dashboard health at {DASHBOARD_BASE_URL}...")
    try:
        resp = requests.get(f"{DASHBOARD_BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            log('pass', "Dashboard is healthy")
            return True
        else:
            log('fail', f"Dashboard returned {resp.status_code}")
            return False
    except Exception as e:
        log('fail', f"Dashboard unreachable: {e}")
        return False

def test_ibeam_container_spawn(exchange_id: str, ibkr_user: str = None, ibkr_pass: str = None) -> Tuple[bool, str]:
    """Test ibeam container spawning via dashboard API"""
    log('info', f"Testing ibeam container spawn for {exchange_id}...")

    if not ibkr_user or not ibkr_pass:
        log('warn', "IBKR credentials not provided, skipping container spawn test")
        return False, None

    try:
        payload = {
            'exchange_id': exchange_id,
            'ibkr_user': ibkr_user,
            'ibkr_pass': ibkr_pass,
            'paper_trading': True
        }
        resp = requests.post(f"{DASHBOARD_BASE_URL}/api/ibkr/setup", json=payload, timeout=10)

        if resp.status_code in [200, 201]:
            data = resp.json()
            port = data.get('port')
            container_name = data.get('container_name')
            log('pass', f"ibeam container started: {container_name} on port {port}")
            return True, port
        else:
            log('fail', f"Container spawn failed: {resp.status_code} - {resp.text}")
            return False, None
    except Exception as e:
        log('fail', f"Container spawn error: {e}")
        return False, None

def test_ibeam_container_status(exchange_id: str) -> Tuple[bool, str]:
    """Check ibeam container status"""
    log('info', f"Checking ibeam container status for {exchange_id}...")
    try:
        resp = requests.get(f"{DASHBOARD_BASE_URL}/api/ibkr/status/{exchange_id}", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('running'):
                port = data.get('port')
                log('pass', f"ibeam container is running on port {port}")
                return True, port
            else:
                log('warn', "ibeam container is not running")
                return False, None
        else:
            log('fail', f"Status check failed: {resp.status_code}")
            return False, None
    except Exception as e:
        log('fail', f"Status check error: {e}")
        return False, None

def test_ibkr_client_connection(gateway_host: str = '127.0.0.1', gateway_port: int = 7497) -> bool:
    """Test IBKRClient connection"""
    log('info', f"Testing IBKRClient connection to {gateway_host}:{gateway_port}...")
    try:
        from ibkr_client import IBKRClient
        client = IBKRClient(host=gateway_host, port=gateway_port, client_id=1)
        result = client.test_connection()

        if result.get('connected'):
            log('pass', "IBKRClient connected successfully")
            log('info', f"  Account: {result.get('account_id')}")
            log('info', f"  Balance: ${result.get('balance'):,.2f}")
            log('info', f"  Buying Power: ${result.get('buying_power'):,.2f}")
            log('info', f"  Open Positions: {result.get('open_positions')}")
            return True
        else:
            log('fail', f"Connection test failed: {result.get('error')}")
            return False
    except Exception as e:
        log('fail', f"IBKRClient error: {e}")
        return False

def test_webhook_routing(symbol: str = 'BTCUSDT') -> bool:
    """Test webhook can route to IBKR executor"""
    log('info', f"Testing webhook routing for symbol {symbol}...")
    try:
        # Check which executors would handle this symbol
        from mongo_db import get_enabled_exchange_accounts
        accounts = get_enabled_exchange_accounts()
        ibkr_accounts = [a for a in accounts if a.get('type') == 'ibkr' and a.get('enabled')]

        routed = []
        for acc in ibkr_accounts:
            configured_symbol = str(acc.get('symbol', '')).strip().upper()
            if symbol == configured_symbol:
                routed.append(acc.get('_id'))

        if routed:
            log('pass', f"Symbol {symbol} would route to {len(routed)} IBKR account(s): {routed}")
            return True
        else:
            log('warn', f"Symbol {symbol} not configured for any IBKR accounts")
            return False
    except Exception as e:
        log('fail', f"Routing check error: {e}")
        return False

def test_webhook_signal(signal: str = 'BUY', symbol: str = 'BTCUSDT', price: float = 40000.0) -> bool:
    """Send a test webhook signal"""
    log('info', f"Testing webhook signal: {signal} {symbol} @ ${price}")
    try:
        payload = {
            'signal': signal,
            'symbol': symbol,
            'price': price
        }
        resp = requests.post(f"{DASHBOARD_BASE_URL}/webhook", json=payload, timeout=10)

        if resp.status_code in [200, 201]:
            data = resp.json()
            log('info', f"Webhook response: {data.get('message')}")

            # Check if execution succeeded
            if data.get('status') == 'success':
                log('pass', "Webhook signal processed successfully")
                return True
            elif data.get('status') == 'skipped':
                log('warn', f"Signal skipped: {data.get('message')}")
                return False
            else:
                log('fail', f"Signal failed: {data.get('message')}")
                return False
        else:
            log('fail', f"Webhook returned {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        log('fail', f"Webhook signal error: {e}")
        return False

def print_summary(results: Dict[str, bool]):
    """Print test summary"""
    print(f"\n{Colors.BOLD}{'='*60}")
    print("IBKR Integration Test Summary")
    print('='*60 + Colors.RESET)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        symbol = "✅ PASS" if result else "❌ FAIL"
        print(f"{symbol} - {test_name}")

    print(f"\n{Colors.BOLD}Total: {passed}/{total} tests passed{Colors.RESET}")

    if passed == total:
        log('pass', "All tests passed! IBKR integration is ready.")
        return 0
    else:
        log('fail', f"{total - passed} test(s) failed. See details above.")
        return 1

def main():
    print(f"\n{Colors.BOLD}IBKR Integration Verification{Colors.RESET}")
    print(f"Dashboard URL: {DASHBOARD_BASE_URL}")
    print(f"MongoDB: {('configured' if MONGO_URI else 'NOT configured')}\n")

    results = {}

    # Test 1: MongoDB
    results['MongoDB Connection'] = test_mongodb_connection()

    # Test 2: IBKR Accounts
    has_ibkr, ibkr_accounts = test_ibkr_accounts()
    results['IBKR Accounts Configured'] = has_ibkr

    # Test 3: Dashboard Health
    results['Dashboard Health'] = test_dashboard_health()

    # Test 4: ibeam Container Status (without spawning new one)
    if ibkr_accounts:
        exchange_id = ibkr_accounts[0].get('_id')
        running, port = test_ibeam_container_status(exchange_id)
        results['ibeam Container Status'] = running

        if running:
            # Test 5: IBKRClient Connection
            results['IBKRClient Connection'] = test_ibkr_client_connection(
                gateway_host=ibkr_accounts[0].get('gateway_host', '127.0.0.1'),
                gateway_port=int(ibkr_accounts[0].get('gateway_port', 7497))
            )

        # Test 6: Webhook Routing
        symbol = ibkr_accounts[0].get('symbol', 'BTCUSDT')
        results['Webhook Routing'] = test_webhook_routing(symbol)

        # Test 7: Webhook Signal (simulation)
        results['Webhook Signal Processing'] = test_webhook_signal('BUY', symbol, 40000.0)

    return print_summary(results)

if __name__ == '__main__':
    sys.exit(main())
