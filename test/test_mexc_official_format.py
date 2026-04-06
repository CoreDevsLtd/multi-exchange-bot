#!/usr/bin/env python3
"""
Test MEXC API using official format from their documentation/examples
"""

import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode, quote

def test_official_format_1(api_key, api_secret):
    """Test based on official MEXC documentation format"""
    print("=" * 60)
    print("Test: Official Format - Manual string construction")
    print("=" * 60)
    
    timestamp = int(time.time() * 1000)
    recv_window = 5000
    
    # Build query string manually (sorted alphabetically)
    # recvWindow comes before timestamp alphabetically
    query_string = f"recvWindow={recv_window}&timestamp={timestamp}"
    
    print(f"Query string: {query_string}")
    
    # Generate signature
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    print(f"Signature: {signature}")
    
    # Build full URL with params
    params = {
        'recvWindow': recv_window,
        'timestamp': timestamp,
        'signature': signature
    }
    
    headers = {
        'X-MEXC-APIKEY': api_key,
        'Content-Type': 'application/json'
    }
    
    url = f"https://api.mexc.com/api/v3/account?{urlencode(params)}"
    print(f"Full URL: {url[:100]}...")
    
    response = requests.get('https://api.mexc.com/api/v3/account', params=params, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    return response.status_code == 200

def test_with_debug_info(api_key, api_secret):
    """Test with maximum debug information"""
    print("=" * 60)
    print("Test: Maximum Debug Information")
    print("=" * 60)
    
    import json
    
    timestamp = int(time.time() * 1000)
    recv_window = 5000
    
    print(f"API Key: {api_key}")
    print(f"API Key Length: {len(api_key)}")
    print(f"API Secret Length: {len(api_secret)}")
    print(f"API Secret (first 10): {api_secret[:10]}")
    print(f"API Secret (last 10): {api_secret[-10:]}")
    print()
    
    print(f"Timestamp: {timestamp}")
    print(f"RecvWindow: {recv_window}")
    print()
    
    # Test different query string formats
    formats = [
        ("Format 1: urlencode sorted", lambda: urlencode(sorted([('recvWindow', recv_window), ('timestamp', timestamp)]))),
        ("Format 2: Manual recvWindow first", lambda: f"recvWindow={recv_window}&timestamp={timestamp}"),
        ("Format 3: Manual timestamp first", lambda: f"timestamp={timestamp}&recvWindow={recv_window}"),
    ]
    
    for name, query_func in formats:
        print(f"\n{name}:")
        query_string = query_func()
        print(f"  Query: {query_string}")
        
        signature = hmac.new(
            api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        print(f"  Signature: {signature}")
        
        params = {
            'recvWindow': recv_window,
            'timestamp': timestamp,
            'signature': signature
        }
        
        headers = {
            'X-MEXC-APIKEY': api_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.get('https://api.mexc.com/api/v3/account', params=params, headers=headers)
        print(f"  Status: {response.status_code}")
        if response.status_code != 200:
            try:
                error = response.json()
                print(f"  Error: {json.dumps(error, indent=2)}")
            except:
                print(f"  Error: {response.text}")
        else:
            print(f"  ✅ SUCCESS with {name}!")
            return True
    
    return False

if __name__ == '__main__':
    import os
    api_key = os.getenv('MEXC_API_KEY', 'mx0vglnDmOEpXsddhU')
    api_secret = os.getenv('MEXC_API_SECRET', '49402f94c447475993cbe04bb147489c')
    
    print("Testing MEXC API with official format...")
    print()
    
    # Test with debug info
    if test_with_debug_info(api_key, api_secret):
        print("\n✅ Found working format!")
    else:
        print("\n❌ All formats failed")
        print("\nPossible issues:")
        print("1. API key permissions not enabled")
        print("2. IP whitelist not properly configured")
        print("3. API secret is incorrect")
        print("4. API key is expired or invalid")

