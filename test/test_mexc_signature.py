#!/usr/bin/env python3
"""
Test different MEXC signature formats to find the correct one
"""

import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode, quote

def test_signature_format_1(api_key, api_secret):
    """Standard format: timestamp + recvWindow"""
    print("=" * 60)
    print("Test 1: Standard format (timestamp + recvWindow)")
    print("=" * 60)
    
    params = {
        'timestamp': int(time.time() * 1000),
        'recvWindow': 5000
    }
    
    sorted_params = sorted(params.items())
    query_string = urlencode(sorted_params, doseq=False)
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params['signature'] = signature
    
    headers = {
        'X-MEXC-APIKEY': api_key,
        'Content-Type': 'application/json'
    }
    
    print(f"Query string: {query_string}")
    print(f"Signature: {signature}")
    
    response = requests.get('https://api.mexc.com/api/v3/account', params=params, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    print()
    
    return response.status_code == 200

def test_signature_format_2(api_key, api_secret):
    """Include api_key in signature"""
    print("=" * 60)
    print("Test 2: Include api_key in signature")
    print("=" * 60)
    
    params = {
        'api_key': api_key,
        'timestamp': int(time.time() * 1000),
        'recvWindow': 5000
    }
    
    sorted_params = sorted(params.items())
    query_string = urlencode(sorted_params, doseq=False)
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params['signature'] = signature
    
    headers = {
        'X-MEXC-APIKEY': api_key,
        'Content-Type': 'application/json'
    }
    
    print(f"Query string: {query_string}")
    print(f"Signature: {signature}")
    
    response = requests.get('https://api.mexc.com/api/v3/account', params=params, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    print()
    
    return response.status_code == 200

def test_signature_format_3(api_key, api_secret):
    """Manual query string construction (no urlencode)"""
    print("=" * 60)
    print("Test 3: Manual query string (no urlencode)")
    print("=" * 60)
    
    timestamp = int(time.time() * 1000)
    recv_window = 5000
    
    # Manual construction
    query_string = f"recvWindow={recv_window}&timestamp={timestamp}"
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params = {
        'timestamp': timestamp,
        'recvWindow': recv_window,
        'signature': signature
    }
    
    headers = {
        'X-MEXC-APIKEY': api_key,
        'Content-Type': 'application/json'
    }
    
    print(f"Query string: {query_string}")
    print(f"Signature: {signature}")
    
    response = requests.get('https://api.mexc.com/api/v3/account', params=params, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    print()
    
    return response.status_code == 200

def test_signature_format_4(api_key, api_secret):
    """Try with different header name"""
    print("=" * 60)
    print("Test 4: Different header name (API-KEY)")
    print("=" * 60)
    
    params = {
        'timestamp': int(time.time() * 1000),
        'recvWindow': 5000
    }
    
    sorted_params = sorted(params.items())
    query_string = urlencode(sorted_params, doseq=False)
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params['signature'] = signature
    
    headers = {
        'API-KEY': api_key,
        'Content-Type': 'application/json'
    }
    
    print(f"Query string: {query_string}")
    print(f"Signature: {signature}")
    
    response = requests.get('https://api.mexc.com/api/v3/account', params=params, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    print()
    
    return response.status_code == 200

def main():
    import os
    api_key = os.getenv('MEXC_API_KEY', '')
    api_secret = os.getenv('MEXC_API_SECRET', '')
    
    if not api_key or not api_secret:
        print("Error: MEXC_API_KEY and MEXC_API_SECRET must be set")
        print("export MEXC_API_KEY='your_key'")
        print("export MEXC_API_SECRET='your_secret'")
        return False
    
    print("Testing different MEXC signature formats...")
    print()
    
    tests = [
        ("Standard format", test_signature_format_1),
        ("Include api_key", test_signature_format_2),
        ("Manual query string", test_signature_format_3),
        ("Different header", test_signature_format_4),
    ]
    
    for name, test_func in tests:
        try:
            if test_func(api_key, api_secret):
                print(f"✅ {name} - SUCCESS!")
                return True
        except Exception as e:
            print(f"❌ {name} - Error: {e}")
            print()
    
    print("=" * 60)
    print("All signature formats failed.")
    print("This suggests:")
    print("1. IP whitelisting is enabled")
    print("2. API key permissions are incorrect")
    print("3. API key is invalid or expired")
    print("=" * 60)
    return False

if __name__ == '__main__':
    main()

