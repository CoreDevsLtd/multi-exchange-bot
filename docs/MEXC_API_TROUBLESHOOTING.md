# MEXC API Connection Troubleshooting

## Common 400 Bad Request Errors

### 1. **API Key Permissions**
Make sure your API key has the correct permissions:
- ✅ **Account**: View Account Details
- ✅ **Trade**: View Order Details, Trade

**How to check:**
1. Log into MEXC
2. Go to API Management
3. Check your API key permissions
4. Enable required permissions if missing

### 2. **API Key Format**
- Ensure API key and secret are copied correctly
- No extra spaces or newlines
- Keys are case-sensitive

### 3. **IP Whitelisting**
If IP whitelisting is enabled:
- Add your server's IP address to the whitelist
- For local testing, add your local IP
- For deployment, add your server's public IP

**How to check:**
1. Go to API Management in MEXC
2. Check if IP whitelist is enabled
3. Add required IPs or disable whitelisting for testing

### 4. **API Key Expiration**
- Check if your API key has expired
- MEXC allows renewal 5 days before expiration
- Renew for 90 days extension

### 5. **Signature Generation**
The signature is generated from:
- Sorted parameters (alphabetically by key)
- Query string format: `key1=value1&key2=value2`
- HMAC-SHA256 with API secret

**Common issues:**
- Parameters not sorted correctly
- Signature includes itself (shouldn't)
- Wrong encoding

### 6. **Request Format**
For GET requests:
- Parameters go in query string
- Signature is included in query string
- Header: `X-MEXC-APIKEY: your_api_key`

### 7. **Timestamp Issues**
- Timestamp must be in milliseconds
- Current implementation: `int(time.time() * 1000)`
- recvWindow: 5000ms (5 seconds tolerance)

## Testing Your API Keys

### Manual Test with curl

```bash
# Replace with your actual values
API_KEY="your_api_key"
API_SECRET="your_api_secret"
TIMESTAMP=$(date +%s)000
RECV_WINDOW=5000

# Create query string (sorted)
QUERY_STRING="recvWindow=${RECV_WINDOW}&timestamp=${TIMESTAMP}"

# Generate signature
SIGNATURE=$(echo -n "${QUERY_STRING}" | openssl dgst -sha256 -hmac "${API_SECRET}" | sed 's/^.* //')

# Make request
curl -X GET "https://api.mexc.com/api/v3/account?${QUERY_STRING}&signature=${SIGNATURE}" \
  -H "X-MEXC-APIKEY: ${API_KEY}"
```

### Python Test Script

```python
import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode

api_key = "your_api_key"
api_secret = "your_api_secret"

# Prepare parameters
params = {
    'timestamp': int(time.time() * 1000),
    'recvWindow': 5000
}

# Generate signature
sorted_params = sorted(params.items())
query_string = urlencode(sorted_params)
signature = hmac.new(
    api_secret.encode('utf-8'),
    query_string.encode('utf-8'),
    hashlib.sha256
).hexdigest()

params['signature'] = signature

# Make request
headers = {
    'X-MEXC-APIKEY': api_key,
    'Content-Type': 'application/json'
}

response = requests.get(
    'https://api.mexc.com/api/v3/account',
    params=params,
    headers=headers
)

print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
```

## Error Messages

### "Invalid API-key"
- API key is incorrect
- API key doesn't exist
- Check key is copied correctly

### "Invalid signature"
- Signature generation is wrong
- API secret is incorrect
- Parameters not sorted correctly

### "Timestamp out of range"
- Server time is out of sync
- recvWindow too small
- Check system clock

### "IP not in whitelist"
- IP whitelisting is enabled
- Your IP is not whitelisted
- Add IP or disable whitelisting

### "API key expired"
- API key has expired
- Renew the key
- Create a new key

## Debug Steps

1. **Check API Key Status**
   - Log into MEXC
   - Go to API Management
   - Verify key is active and not expired

2. **Verify Permissions**
   - Ensure Account and Trade permissions are enabled
   - Check if any restrictions are set

3. **Test with Simple Request**
   - Try getting account info first
   - Don't try trading until account info works

4. **Check Logs**
   - Enable DEBUG logging
   - Check signature generation
   - Verify request format

5. **Test Locally First**
   - Test API keys locally
   - Verify connection works
   - Then deploy

## Quick Fixes

### Fix 1: Recreate API Key
1. Delete old API key
2. Create new one with all permissions
3. Copy key and secret carefully
4. Test immediately

### Fix 2: Disable IP Whitelisting (for testing)
1. Go to API Management
2. Edit API key
3. Disable IP whitelist (for testing only)
4. Re-enable after testing

### Fix 3: Check System Time
```bash
# Check if system time is correct
date

# Sync time if needed (Linux)
sudo ntpdate -s time.nist.gov
```

### Fix 4: Increase recvWindow
If you have time sync issues, increase recvWindow:
```python
params['recvWindow'] = 10000  # 10 seconds instead of 5
```

## Still Not Working?

1. **Contact MEXC Support**
   - They can check your API key status
   - Verify account permissions
   - Check for account restrictions

2. **Check MEXC Status**
   - Visit MEXC status page
   - Check for API maintenance
   - Look for announcements

3. **Review MEXC API Docs**
   - Check latest API documentation
   - Verify endpoint URLs
   - Check for recent changes


