#!/usr/bin/env python3
"""
Test MEXC API v3 signature format with accessKey included
"""

import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode

def test_with_accesskey_in_signature(api_key, api_secret):
    """Test signature format: accessKey + timestamp + parameterString"""
    print("=" * 60)
    print("Test: accessKey + timestamp + parameterString format")
    print("=" * 60)
    
    timestamp = int(time.time() * 1000)
    recv_window = 5000
    
    # Build parameter string (sorted)
    params = {
        'recvWindow': recv_window,
        'timestamp': timestamp
    }
    sorted_params = sorted(params.items())
    param_string = urlencode(sorted_params, doseq=False)
    
    # Signature: accessKey + timestamp + parameterString
    signature_string = f"{api_key}{timestamp}{param_string}"
    print(f"Signature string: {signature_string}")
    
    signature = hmac.new(
        api_secret.encode('utf-8'),
        signature_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    print(f"Generated signature: {signature}")
    
    # Add signature to params
    params['signature'] = signature
    
    headers = {
        'X-MEXC-APIKEY': api_key,
        'Content-Type': 'application/json'
    }
    
    print(f"\nMaking request...")
    response = requests.get('https://api.mexc.com/api/v3/account', params=params, headers=headers)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("\n✅ SUCCESS!")
        return True
    else:
        print("\n❌ Failed")
        return False

def test_standard_format_again(api_key, api_secret):
    """Test our current standard format one more time"""
    print("=" * 60)
    print("Test: Standard format (one more time)")
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
    
    return response.status_code == 200

if __name__ == '__main__':
    import os
    api_key = os.getenv('MEXC_API_KEY', '')
    api_secret = os.getenv('MEXC_API_SECRET', '')
    
    if not api_key or not api_secret:
        print("Error: MEXC_API_KEY and MEXC_API_SECRET must be set")
        print("export MEXC_API_KEY='your_key'")
        print("export MEXC_API_SECRET='your_secret'")
        exit(1)
    
    print("Testing MEXC API v3 signature formats...")
    print()
    
    # Wait a moment in case IP whitelist needs time
    print("Waiting 3 seconds for IP whitelist to propagate...")
    import time as time_module
    time_module.sleep(3)
    print()
    
    # Test with accessKey in signature
    if test_with_accesskey_in_signature(api_key, api_secret):
        print("\n✅ Found working format!")
    else:
        print("\nTrying standard format again...")
        test_standard_format_again(api_key, api_secret)

