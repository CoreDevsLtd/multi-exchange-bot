#!/usr/bin/env python3
"""
Test Bybit webhook trading with different leverage scenarios
Tests 3 scenarios:
1. Current leverage (7x) - BUY then SELL
2. Different leverage (5x or 10x) - BUY then SELL
3. 1x leverage - BUY then SELL
"""

import requests
import json
import time
from datetime import datetime

# Configuration
WEBHOOK_URL = "http://localhost:8080/webhook"
SYMBOL = "DOGEUSDT"
EXCHANGE = "account_3a19389e_bybit"

def send_webhook(signal_type: str, leverage: int = None):
    """Send webhook signal to test trading"""

    # Base signal
    signal_data = {
        "symbol": SYMBOL,
        "signal": signal_type,  # BUY or SELL
        "indicators": {
            "rsi": 65 if signal_type == "BUY" else 35,
            "ema": 0.095,
            "wt": 0.5
        },
        "price": {
            "open": 0.0945,
            "high": 0.0950,
            "low": 0.0943,
            "close": 0.0948
        },
        "exchange": EXCHANGE
    }

    # Add leverage if specified
    if leverage:
        signal_data["leverage"] = leverage

    print(f"\n{'='*70}")
    print(f"📤 Sending {signal_type} webhook for {SYMBOL}")
    if leverage:
        print(f"   Leverage: {leverage}x")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   URL: {WEBHOOK_URL}")
    print(f"{'='*70}")
    print(f"Payload: {json.dumps(signal_data, indent=2)}")

    try:
        response = requests.post(WEBHOOK_URL, json=signal_data, timeout=10)
        print(f"\n✅ Response Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

def test_scenario_1():
    """Test 1: Current leverage (7x) - BUY and SELL"""
    print("\n" + "🔷"*35)
    print("TEST SCENARIO 1: Current Leverage (7x) - BUY then SELL")
    print("🔷"*35)

    buy_ok = send_webhook("BUY", leverage=7)
    time.sleep(15)  # Wait for BUY + TP orders to complete before SELL

    sell_ok = send_webhook("SELL", leverage=7)

    return buy_ok and sell_ok

def test_scenario_2():
    """Test 2: Different leverage (5x or 10x) - BUY and SELL"""
    print("\n" + "🟦"*35)
    print("TEST SCENARIO 2: Different Leverage (5x) - BUY then SELL")
    print("🟦"*35)

    buy_ok = send_webhook("BUY", leverage=5)
    time.sleep(15)  # Wait for BUY + TP orders to complete before SELL

    sell_ok = send_webhook("SELL", leverage=5)

    return buy_ok and sell_ok

def test_scenario_3():
    """Test 3: 1x leverage - BUY and SELL"""
    print("\n" + "🔶"*35)
    print("TEST SCENARIO 3: Minimum Leverage (1x) - BUY then SELL")
    print("🔶"*35)

    buy_ok = send_webhook("BUY", leverage=1)
    time.sleep(15)  # Wait for BUY + TP orders to complete before SELL

    sell_ok = send_webhook("SELL", leverage=1)

    return buy_ok and sell_ok

def main():
    print("\n" + "="*70)
    print("🚀 BYBIT WEBHOOK TRADING TEST - 3 LEVERAGE SCENARIOS")
    print("="*70)
    print(f"Webhook URL: {WEBHOOK_URL}")
    print(f"Trading Symbol: {SYMBOL}")
    print(f"Exchange Account: {EXCHANGE}")
    print("="*70)

    results = {
        "Scenario 1 (7x)": test_scenario_1(),
        "Scenario 2 (5x)": test_scenario_2(),
        "Scenario 3 (1x)": test_scenario_3(),
    }

    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    for scenario, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{scenario:25} → {status}")

    all_passed = all(results.values())
    print("="*70)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Ready for VPS deployment")
    else:
        print("⚠️  SOME TESTS FAILED - Check logs and fix issues before deploying")
    print("="*70 + "\n")

    return all_passed

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
