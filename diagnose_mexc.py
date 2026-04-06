#!/usr/bin/env python3
"""
Enhanced MEXC API Diagnostic Tool
Helps diagnose signature and connection issues
"""

import os
import sys
import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode

def test_signature_generation(api_key: str, api_secret: str):
    """Test signature generation step by step"""
    print("=" * 60)
    print("Step 1: Signature Generation Test")
    print("=" * 60)
    
    # Prepare parameters exactly as the client does
    params = {
        'timestamp': int(time.time() * 1000),
        'recvWindow': 5000
    }
    
    print(f"Parameters: {params}")
    
    # Sort parameters alphabetically
    sorted_params = sorted(params.items())
    print(f"Sorted params: {sorted_params}")
    
    # Create query string
    query_string = urlencode(sorted_params, doseq=False)
    print(f"Query string: {query_string}")
    
    # Check API secret
    print(f"\nAPI Secret length: {len(api_secret)}")
    print(f"API Secret (first 5): {api_secret[:5]}...")
    print(f"API Secret (last 5): ...{api_secret[-5:]}")
    
    # Check for whitespace issues
    if api_secret != api_secret.strip():
        print("⚠️  WARNING: API secret has leading/trailing whitespace!")
        api_secret = api_secret.strip()
    
    if api_key != api_key.strip():
        print("⚠️  WARNING: API key has leading/trailing whitespace!")
        api_key = api_key.strip()
    
    # Generate signature
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    print(f"Generated signature: {signature}")
    print()
    
    return params, signature, api_key, api_secret

def test_api_request(api_key: str, api_secret: str):
    """Test API request with detailed logging"""
    print("=" * 60)
    print("Step 2: API Request Test")
    print("=" * 60)
    
    # Generate signature
    params, signature, api_key_clean, api_secret_clean = test_signature_generation(api_key, api_secret)
    
    # Add signature to params
    params['signature'] = signature
    
    # Build URL
    url = "https://api.mexc.com/api/v3/account"
    
    print(f"\nRequest URL: {url}")
    print(f"Query params: {params}")
    
    # Headers
    headers = {
        'X-MEXC-APIKEY': api_key_clean,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    print(f"\nHeaders:")
    print(f"  X-MEXC-APIKEY: {api_key_clean[:10]}...{api_key_clean[-5:]}")
    print(f"  Content-Type: application/json")
    print()
    
    try:
        print("Making GET request...")
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: {response.text}")
        print()
        
        if response.status_code == 200:
            print("✅ SUCCESS! Connection works!")
            try:
                data = response.json()
                print(f"Account Data: {json.dumps(data, indent=2)}")
            except:
                pass
            return True
        else:
            print(f"❌ FAILED! Status: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error Details: {json.dumps(error_data, indent=2)}")
                
                # Provide specific guidance
                if 'msg' in error_data:
                    msg = error_data['msg']
                    print(f"\nError Message: {msg}")
                    
                    if 'signature' in msg.lower():
                        print("\n🔍 Signature Error Troubleshooting:")
                        print("1. Verify API secret is correct (no extra spaces)")
                        print("2. Check that parameters are sorted alphabetically")
                        print("3. Ensure timestamp is in milliseconds")
                        print("4. Verify recvWindow is included")
                    elif 'ip' in msg.lower() or 'whitelist' in msg.lower():
                        print("\n🔍 IP Whitelist Error:")
                        print("1. Check Railway server IP in MEXC API settings")
                        print("2. Disable IP whitelist for testing (if possible)")
                        print("3. Add Railway's public IP to whitelist")
                    elif 'permission' in msg.lower():
                        print("\n🔍 Permission Error:")
                        print("1. Enable 'Account' permission in MEXC")
                        print("2. Enable 'Trade' permission in MEXC")
                        print("3. Check API key restrictions")
            except:
                pass
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main diagnostic function"""
    print("=" * 60)
    print("MEXC API Diagnostic Tool")
    print("=" * 60)
    print()
    
    # Get API keys
    api_key = os.getenv('MEXC_API_KEY', '').strip()
    api_secret = os.getenv('MEXC_API_SECRET', '').strip()
    
    if not api_key or not api_secret:
        print("❌ Error: MEXC_API_KEY and MEXC_API_SECRET must be set")
        print("\nOptions:")
        print("1. Set environment variables:")
        print("   export MEXC_API_KEY='your_key'")
        print("   export MEXC_API_SECRET='your_secret'")
        print("\n2. Or pass as arguments:")
        print("   python diagnose_mexc.py YOUR_KEY YOUR_SECRET")
        print()
        
        # Try command line args
        if len(sys.argv) >= 3:
            api_key = sys.argv[1].strip()
            api_secret = sys.argv[2].strip()
            print(f"Using keys from command line arguments")
        else:
            return False
    
    print(f"API Key: {api_key[:10]}...{api_key[-5:]}")
    print(f"API Secret: {'*' * 20}...{api_secret[-5:]}")
    print()
    
    # Check for common issues
    print("Checking for common issues...")
    issues = []
    
    if len(api_key) < 10:
        issues.append("API key seems too short")
    if len(api_secret) < 20:
        issues.append("API secret seems too short")
    if ' ' in api_key or '\n' in api_key:
        issues.append("API key contains spaces or newlines")
    if ' ' in api_secret or '\n' in api_secret:
        issues.append("API secret contains spaces or newlines")
    
    if issues:
        print("⚠️  Potential issues found:")
        for issue in issues:
            print(f"   - {issue}")
        print()
    else:
        print("✅ No obvious issues with key format")
        print()
    
    # Test request
    success = test_api_request(api_key, api_secret)
    
    print()
    print("=" * 60)
    if success:
        print("✅ DIAGNOSIS COMPLETE - Connection successful!")
    else:
        print("❌ DIAGNOSIS COMPLETE - Connection failed")
        print("\nNext Steps:")
        print("1. Check MEXC API key permissions (Account + Trade)")
        print("2. Verify IP whitelisting settings in MEXC")
        print("3. Check if API key has expired")
        print("4. Try recreating the API key")
        print("5. Check Railway logs for more details")
    print("=" * 60)
    
    return success

if __name__ == '__main__':
    import json
    success = main()
    sys.exit(0 if success else 1)

