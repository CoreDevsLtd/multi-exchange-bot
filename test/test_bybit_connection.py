#!/usr/bin/env python3
"""
Quick test script for Bybit API connection.
Run: python3 test/test_bybit_connection.py
"""
import json
import os

def main():
    config_path = 'dashboard_config.json'
    if not os.path.exists(config_path):
        print("❌ dashboard_config.json not found. Configure Bybit in the dashboard first.")
        return
    
    with open(config_path) as f:
        config = json.load(f)
    
    bybit = config.get('exchanges', {}).get('bybit', {})
    api_key = (bybit.get('api_key') or '').strip()
    api_secret = (bybit.get('api_secret') or '').strip()
    
    if not api_key or not api_secret:
        print("❌ Bybit API key or secret not configured in dashboard_config.json")
        return
    
    if api_secret == '***':
        print("❌ API secret is masked. Re-enter the secret in the dashboard and save.")
        return
    
    print("Testing Bybit connection...")
    print(f"  API Key: {api_key[:6]}...{api_key[-4:]}")
    print(f"  Base URL: {bybit.get('base_url', 'https://api.bybit.com')}")
    print(f"  Testnet: {bybit.get('testnet', False)}")
    print()
    
    try:
        from bybit_client import BybitClient
        client = BybitClient(
            api_key=api_key,
            api_secret=api_secret,
            base_url=bybit.get('base_url', 'https://api.bybit.com'),
            testnet=bybit.get('testnet', False),
            trading_mode=bybit.get('trading_mode', 'spot'),
            leverage=int(bybit.get('leverage', 1)),
            proxy=(bybit.get('proxy') or '').strip() or None
        )
        result = client.validate_connection()
        if result['connected']:
            print("✅ Connected successfully!")
            balances = client.get_main_balances()
            if balances:
                for asset, bal in balances.items():
                    print(f"   {asset}: {bal['total']:.8f}")
            else:
                print("   (No balances or all zero)")
        else:
            print(f"❌ Connection failed: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
