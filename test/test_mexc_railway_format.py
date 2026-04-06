#!/usr/bin/env python3
"""
Test MEXC signature format with Railway credentials
Based on actual Railway logs
"""

import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode

def test_current_format():
    """Test current format (what we're using)"""
    print("=" * 60)
    print("Test: Current Format (recvWindow + timestamp)")
    print("=" * 60)
    
    api_key = 'mx0vglnDmOEpXsddhU'
    api_secret = '49402f94c447475993cbe04bb147489c'
    timestamp = 1767026697603
    
    params = {
        'recvWindow': 5000,
        'timestamp': timestamp
    }
    
    sorted_params = sorted(params.items())
    query_string = urlencode(sorted_params, doseq=False)
    
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params['signature'] = signature
    
    print(f"Query string: {query_string}")
    print(f"Signature: {signature}")
    print(f"Expected: a53a625c13012534e16f7e6fb0b80ac0da23c5d5f5ae68b4576c7eed147aa9d0")
    print(f"Match: {signature == 'a53a625c13012534e16f7e6fb0b80ac0da23c5d5f5ae68b4576c7eed147aa9d0'}")
    
    headers = {
        'X-MEXC-APIKEY': api_key,
        'Content-Type': 'application/json'
    }
    
    response = requests.get('https://api.mexc.com/api/v3/account', params=params, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    print()
    
    return response.status_code == 200

def test_with_api_key_in_signature():
    """Test with API key included in signature string"""
    print("=" * 60)
    print("Test: API Key in Signature String")
    print("=" * 60)
    
    api_key = 'mx0vglnDmOEpXsddhU'
    api_secret = '49402f94c447475993cbe04bb147489c'
    timestamp = int(time.time() * 1000)
    
    # Format: accessKey + timestamp + parameterString
    params = {
        'recvWindow': 5000,
        'timestamp': timestamp
    }
    
    sorted_params = sorted(params.items())
    param_string = urlencode(sorted_params, doseq=False)
    
    # Signature string: api_key + timestamp + param_string
    signature_string = f"{api_key}{timestamp}{param_string}"
    
    signature = hmac.new(
        api_secret.encode('utf-8'),
        signature_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params['signature'] = signature
    
    print(f"Signature string: {signature_string}")
    print(f"Signature: {signature}")
    
    headers = {
        'X-MEXC-APIKEY': api_key,
        'Content-Type': 'application/json'
    }
    
    response = requests.get('https://api.mexc.com/api/v3/account', params=params, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    print()
    
    return response.status_code == 200

def test_without_recvWindow():
    """Test without recvWindow parameter"""
    print("=" * 60)
    print("Test: Without recvWindow (timestamp only)")
    print("=" * 60)
    
    api_key = 'mx0vglnDmOEpXsddhU'
    api_secret = '49402f94c447475993cbe04bb147489c'
    timestamp = int(time.time() * 1000)
    
    params = {
        'timestamp': timestamp
    }
    
    sorted_params = sorted(params.items())
    query_string = urlencode(sorted_params, doseq=False)
    
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    params['signature'] = signature
    
    print(f"Query string: {query_string}")
    print(f"Signature: {signature}")
    
    headers = {
        'X-MEXC-APIKEY': api_key,
        'Content-Type': 'application/json'
    }
    
    response = requests.get('https://api.mexc.com/api/v3/account', params=params, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    print()
    
    return response.status_code == 200

if __name__ == '__main__':
    print("Testing MEXC signature formats with Railway credentials...")
    print()
    
    # Test current format
    if test_current_format():
        print("✅ Current format works!")
    else:
        print("❌ Current format failed")
        print()
        
        # Try alternative formats
        if test_with_api_key_in_signature():
            print("✅ API key in signature works!")
        elif test_without_recvWindow():
            print("✅ Without recvWindow works!")
        else:
            print("❌ All formats failed")
            print()
            print("Possible issues:")
            print("1. API key/secret mismatch in MEXC")
            print("2. API key expired or invalid")
            print("3. API key permissions incorrect")
            print("4. Different signature format required")

