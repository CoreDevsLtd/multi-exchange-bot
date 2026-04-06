#!/usr/bin/env python3
"""
Test MEXC API Connection
Run this script to diagnose connection issues
"""

import os
import sys
import json
from mexc_client import MEXCClient

def test_connection():
    """Test MEXC API connection"""
    
    # Get API keys from environment or config
    api_key = os.getenv('MEXC_API_KEY')
    api_secret = os.getenv('MEXC_API_SECRET')
    
    if not api_key or not api_secret:
        print("❌ Error: MEXC_API_KEY and MEXC_API_SECRET must be set")
        print("\nSet them with:")
        print("  export MEXC_API_KEY='your_key'")
        print("  export MEXC_API_SECRET='your_secret'")
        return False
    
    print("=" * 60)
    print("MEXC API Connection Test")
    print("=" * 60)
    print(f"API Key: {api_key[:10]}...{api_key[-5:]}")
    print(f"API Secret: {'*' * 20}...{api_secret[-5:]}")
    print()
    
    try:
        # Create client
        print("1. Creating MEXC client...")
        client = MEXCClient(
            api_key=api_key,
            api_secret=api_secret,
            base_url='https://api.mexc.com'
        )
        print("   ✅ Client created")
        print()
        
        # Test connection
        print("2. Testing connection...")
        validation = client.validate_connection()
        print()
        
        if validation['connected']:
            print("✅ Connection successful!")
            print(f"   Permissions: {validation.get('permissions', [])}")
            print(f"   Can Trade: {validation['can_trade']}")
            print()
            
            # Get balances
            print("3. Fetching balances...")
            balances = client.get_main_balances()
            if balances:
                print("   ✅ Balances retrieved:")
                for asset, bal in balances.items():
                    print(f"      {asset}: {bal['total']:.8f} (Free: {bal['free']:.8f})")
            else:
                print("   ⚠️  No significant balances found")
            
            print()
            print("=" * 60)
            print("✅ All tests passed!")
            print("=" * 60)
            return True
        else:
            print("❌ Connection failed!")
            error = validation.get('error', 'Unknown error')
            print(f"   Error: {error}")
            print()
            print("Troubleshooting:")
            print("1. Check API key permissions in MEXC dashboard")
            print("2. Verify IP whitelisting settings")
            print("3. Ensure API key is not expired")
            print("4. Check API key has 'Account' and 'Trade' permissions")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        print("Full error details:")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_connection()
    sys.exit(0 if success else 1)


