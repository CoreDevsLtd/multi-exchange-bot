#!/usr/bin/env python3
"""
Quick test script for Bybit API connection.
Reads the first Bybit exchange account from MongoDB.
Run: python3 test/test_bybit_connection.py
"""
import os
import sys

# Allow running from project root or test/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()


def main():
    try:
        from mongo_db import get_db
        db = get_db()
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        print("   Set MONGO_URI environment variable and try again.")
        return

    docs = list(db.exchange_accounts.find({'type': 'bybit'}))
    if not docs:
        print("❌ No Bybit exchange accounts found in MongoDB.")
        print("   Add one via the dashboard → Accounts → Add Exchange Account.")
        return

    for bybit in docs:
        ex_id = bybit.get('_id')
        creds = bybit.get('credentials') or {}
        try:
            from secrets_manager import decrypt_credentials_dict
            creds = decrypt_credentials_dict(creds)
        except Exception:
            pass

        api_key = (creds.get('api_key') or '').strip()
        api_secret = (creds.get('api_secret') or '').strip()

        if not api_key or not api_secret:
            print(f"❌ [{ex_id}] Missing API credentials — configure in dashboard.")
            continue

        print(f"Testing Bybit connection: {ex_id}")
        print(f"  API Key: {api_key[:6]}...{api_key[-4:]}")
        print(f"  Base URL: {bybit.get('base_url', 'https://api.bybit.com')}")
        print(f"  Testnet: {bybit.get('testnet', False)}")
        print(f"  Mode: {bybit.get('trading_mode', 'spot')} (leverage={bybit.get('leverage', 1)}x)")
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
                print(f"✅ [{ex_id}] Connected successfully!")
                balances = client.get_main_balances()
                if balances:
                    for asset, bal in balances.items():
                        print(f"   {asset}: {bal['total']:.8f}")
                else:
                    print("   (No balances or all zero)")
            else:
                print(f"❌ [{ex_id}] Connection failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ [{ex_id}] Error: {e}")
            import traceback
            traceback.print_exc()
        print()


if __name__ == '__main__':
    main()
