# MEXC API Connection Checklist

## Current Status
❌ **Connection Failed**: "Signature for this request is not valid"

## Your Current IP Address
Run this to get your IP:
```bash
curl https://api.ipify.org
```

## Step-by-Step Fix

### 1. Check IP Whitelisting (MOST COMMON ISSUE)

**In MEXC Dashboard:**
1. Log into MEXC
2. Go to **API Management**
3. Find your API key: `mx0vglnDmOEpXsddhU`
4. Check if **IP Whitelist** is enabled
5. If enabled:
   - **Option A**: Add your current IP address to the whitelist
   - **Option B**: Temporarily disable IP whitelist for testing (not recommended for production)

**How to add IP:**
- Click "Edit" on your API key
- Add your IP address (from `curl https://api.ipify.org`)
- Save changes
- Wait 1-2 minutes for changes to take effect

### 2. Verify API Key Permissions

**Required Permissions:**
- ✅ **Account** - View Account Details
- ✅ **Trade** - View Order Details, Trade

**How to check:**
1. Go to API Management in MEXC
2. Click on your API key
3. Verify both "Account" and "Trade" are enabled
4. If not, enable them and save

### 3. Check API Key Status

**Verify:**
- API key is **Active** (not expired)
- API key is **not restricted**
- API key was created correctly

**If expired:**
- Create a new API key
- Copy both key and secret carefully
- Update in dashboard

### 4. Test After Changes

After making changes:
1. Wait 1-2 minutes
2. Run test again:
   ```bash
   export MEXC_API_KEY='mx0vglnDmOEpXsddhU'
   export MEXC_API_SECRET='49402f94c447475993cbe04bb147489c'
   python3 diagnose_mexc.py
   ```

## Common Issues

### Issue: IP Whitelist Enabled
**Symptom**: "Signature for this request is not valid"
**Solution**: Add your IP to whitelist or disable whitelist

### Issue: Missing Permissions
**Symptom**: "Signature for this request is not valid" or "Permission denied"
**Solution**: Enable Account and Trade permissions

### Issue: API Key Expired
**Symptom**: "Invalid API key"
**Solution**: Create new API key

### Issue: Wrong API Secret
**Symptom**: "Signature for this request is not valid"
**Solution**: Double-check secret is copied correctly (no spaces)

## Quick Test Commands

```bash
# Get your IP
curl https://api.ipify.org

# Test connection
export MEXC_API_KEY='mx0vglnDmOEpXsddhU'
export MEXC_API_SECRET='49402f94c447475993cbe04bb147489c'
python3 diagnose_mexc.py
```

## Next Steps

1. ✅ Check IP whitelisting in MEXC
2. ✅ Verify API key permissions
3. ✅ Test connection again
4. ✅ If still failing, try creating a new API key

