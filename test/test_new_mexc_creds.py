#!/usr/bin/env python3
"""
Test new MEXC credentials
"""

import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode

def test_new_credentials():
    """Test with new credentials from Railway"""
    print("=" * 60)
    print("Testing New MEXC Credentials")
    print("=" * 60)
    
    # From Railway logs
    api_key = 'mx0vgl...7SSY'  # Need full key
    api_secret = 'c4a680...de0640'  # Need full secret
    
    print("⚠️  Need full API key and secret to test")
    print(f"   API Key (from logs): {api_key}")
    print(f"   API Secret (from logs): {api_secret}")
    print()
    print("Please provide:")
    print("1. Full API Key (not masked)")
    print("2. Full API Secret (not masked)")
    print()
    print("Or test manually:")
    print("export MEXC_API_KEY='your_full_key'")
    print("export MEXC_API_SECRET='your_full_secret'")
    print("python3 test/test_mexc_railway_format.py")

if __name__ == '__main__':
    import os
    api_key = os.getenv('MEXC_API_KEY', '')
    api_secret = os.getenv('MEXC_API_SECRET', '')
    
    if not api_key or not api_secret:
        test_new_credentials()
    else:
        timestamp = int(time.time() * 1000)
        params = {'timestamp': timestamp}
        sorted_params = sorted(params.items())
        query_string = urlencode(sorted_params, doseq=False)
        
        signature = hmac.new(
            api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        params['signature'] = signature
        params['recvWindow'] = 5000
        
        headers = {
            'X-MEXC-APIKEY': api_key,
            'Content-Type': 'application/json'
        }
        
        print(f"Testing with API Key: {api_key[:6]}...{api_key[-4:]}")
        print(f"Query string: {query_string}")
        print(f"Signature: {signature}")
        print("Making request...")
        
        response = requests.get('https://api.mexc.com/api/v3/account', params=params, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

