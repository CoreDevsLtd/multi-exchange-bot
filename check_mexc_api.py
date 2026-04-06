#!/usr/bin/env python3
"""
Check MEXC API Key Status
This script helps diagnose API key issues
"""

import requests
import hmac
import hashlib
import time

api_key = 'mx0vglBPlpnAGTqdEa'
api_secret = '0bcd82df2a5047ed855536a94393732f'

print("=" * 60)
print("MEXC API Key Diagnostic")
print("=" * 60)
print(f"API Key: {api_key}")
print(f"API Secret: {api_secret[:10]}...{api_secret[-5:]}")
print()

# Test 1: Check server time
print("1. Checking MEXC server time...")
try:
    response = requests.get('https://api.mexc.com/api/v3/time', timeout=10)
    if response.status_code == 200:
        server_time = response.json().get('serverTime', 0)
        local_time = int(time.time() * 1000)
        diff = abs(local_time - server_time)
        print(f"   ✅ Server time: {server_time}")
        print(f"   ✅ Local time: {local_time}")
        print(f"   ✅ Difference: {diff}ms ({diff/1000:.1f}s)")
        if diff > 5000:
            print(f"   ⚠️  WARNING: Time difference > 5 seconds!")
    else:
        print(f"   ❌ Failed to get server time: {response.status_code}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Test 2: Try account endpoint with different signature methods
print("2. Testing account endpoint...")

timestamp = int(time.time() * 1000)
recv_window = 5000

# Method: Sorted alphabetically (recvWindow before timestamp)
query_string = f'recvWindow={recv_window}&timestamp={timestamp}'
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

print(f"   Query string: {query_string}")
print(f"   Signature: {signature}")
print(f"   Making request...")

try:
    response = requests.get(
        'https://api.mexc.com/api/v3/account',
        params=params,
        headers=headers,
        timeout=10
    )
    
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:500]}")
    
    if response.status_code == 200:
        print("   ✅ SUCCESS! API key is working!")
        data = response.json()
        print(f"   Permissions: {data.get('permissions', [])}")
        print(f"   Can Trade: {'SPOT' in data.get('permissions', [])}")
    else:
        error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
        error_code = error_data.get('code', '')
        error_msg = error_data.get('msg', response.text)
        
        print(f"   ❌ FAILED!")
        print(f"   Error Code: {error_code}")
        print(f"   Error Message: {error_msg}")
        
        if error_code == 700002:
            print()
            print("   Possible causes:")
            print("   1. API secret is incorrect")
            print("   2. IP whitelisting is enabled (check MEXC dashboard)")
            print("   3. API key doesn't have required permissions")
            print("   4. API key has expired")
            print()
            print("   Action items:")
            print("   - Log into MEXC → API Management")
            print("   - Check API key status and permissions")
            print("   - Verify IP whitelist settings")
            print("   - Ensure 'Account' and 'Trade' permissions are enabled")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)


