"""
Check current trade data in MongoDB
Verify we have all fields needed for Milestone 3
"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient
import json
from datetime import datetime

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI') or os.getenv('MONGODB_URI')
MONGO_DB = os.getenv('MONGO_DB') or 'multi_exchange_bot'

def check_trades():
    """Check trades collection"""
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]

    print("\n" + "="*70)
    print("TRADES COLLECTION ANALYSIS")
    print("="*70)

    # Count trades
    trade_count = db.trades.count_documents({})
    print(f"\nTotal trades in collection: {trade_count}")

    if trade_count == 0:
        print("⚠️  No trades found in collection yet")
        print("Trading system is operational, but no trades have executed\n")
        return

    # Get sample trade
    sample = db.trades.find_one({})
    if sample:
        print("\nSample Trade Document:")
        print("-" * 70)
        for key, value in sample.items():
            if key == '_id':
                print(f"  {key}: {str(value)[:50]}...")
            else:
                print(f"  {key}: {value}")

    # Check for required fields
    print("\n" + "-"*70)
    print("REQUIRED FIELD ANALYSIS (For Milestone 3)")
    print("-" * 70)

    required_fields = {
        'symbol': 'Ticker symbol',
        'direction': 'Long/Short',
        'entry_price': 'Entry price',
        'exit_price': 'Exit price',
        'stop_loss': 'Stop loss price',
        'tp_hits': 'Take profit hits (array)',
        'result_usd': 'P&L in dollars',
        'result_percent': 'P&L in percent',
        'exit_reason': 'Why trade exited',
        'trade_duration_sec': 'Trade duration in seconds',
        'timestamp_open': 'Trade open timestamp',
        'timestamp_close': 'Trade close timestamp',
        'initial_quantity': 'Entry quantity'
    }

    missing_fields = []
    for field, description in required_fields.items():
        if sample and field in sample:
            value = sample[field]
            status = "✅"
            print(f"{status} {field:25} {description:30} {str(value)[:30]}")
        else:
            status = "❌"
            missing_fields.append(field)
            print(f"{status} {field:25} {description:30} NOT FOUND")

    # Get unique symbols
    print("\n" + "-"*70)
    print("TICKER ANALYSIS")
    print("-" * 70)

    symbols = db.trades.distinct('symbol')
    print(f"\nTickers with trades: {len(symbols)}")
    for symbol in sorted(symbols):
        count = db.trades.count_documents({'symbol': symbol})
        print(f"  {symbol}: {count} trades")

    # Get date range
    print("\n" + "-"*70)
    print("DATE RANGE ANALYSIS")
    print("-" * 70)

    first_trade = db.trades.find_one({}, sort=[('timestamp_open', 1)])
    last_trade = db.trades.find_one({}, sort=[('timestamp_open', -1)])

    if first_trade:
        first_date = first_trade.get('timestamp_open', 'Unknown')
        print(f"\nFirst trade: {first_date}")

    if last_trade:
        last_date = last_trade.get('timestamp_open', 'Unknown')
        print(f"Last trade: {last_date}")

    # Win/Loss analysis
    print("\n" + "-"*70)
    print("TRADE OUTCOME ANALYSIS")
    print("-" * 70)

    winning_trades = db.trades.count_documents({'result_usd': {'$gt': 0}})
    losing_trades = db.trades.count_documents({'result_usd': {'$lt': 0}})
    break_even_trades = db.trades.count_documents({'result_usd': 0})

    print(f"\nWinning trades: {winning_trades}")
    print(f"Losing trades: {losing_trades}")
    print(f"Break-even trades: {break_even_trades}")

    if trade_count > 0:
        win_rate = (winning_trades / trade_count) * 100
        print(f"Win rate: {win_rate:.2f}%")

        total_pnl = db.trades.aggregate([
            {'$group': {'_id': None, 'total': {'$sum': '$result_usd'}}}
        ])
        total_pnl_value = next(total_pnl)['total']
        print(f"Total P&L: ${total_pnl_value:,.2f}")

    # Check exit reasons
    print("\n" + "-"*70)
    print("EXIT REASON ANALYSIS")
    print("-" * 70)

    exit_reasons = db.trades.aggregate([
        {'$group': {'_id': '$exit_reason', 'count': {'$sum': 1}}}
    ])

    for reason_group in exit_reasons:
        reason = reason_group['_id'] or 'Not specified'
        count = reason_group['count']
        print(f"  {reason}: {count}")

    # Summary
    print("\n" + "="*70)
    print("MILESTONE 3 READINESS ASSESSMENT")
    print("="*70)

    if trade_count == 0:
        print("\n⚠️  No trades in database yet")
        print("Status: NOT READY")
        print("\nNext steps:")
        print("1. Wait for trading system to execute trades")
        print("2. Monitor dashboard webhook logs")
        print("3. Verify trades are persisted to MongoDB")
        print("4. Once trades exist, Milestone 3 can be developed")

    elif missing_fields:
        print(f"\n⚠️  Missing {len(missing_fields)} required field(s)")
        print(f"Missing: {', '.join(missing_fields)}")
        print("Status: PARTIALLY READY")
        print("\nNext steps:")
        print("1. Fix trade persistence to include all fields")
        print("2. Ensure position_manager.py stores missing fields")
        print("3. Re-execute trades and verify complete data")

    else:
        print("\n✅ All required fields present in trades collection")
        print("Status: READY FOR MILESTONE 3")
        print("\nCan proceed with:")
        print("1. API endpoint development")
        print("2. Dashboard page creation")
        print("3. Metric calculations")
        print("4. Testing and validation")

    print()


if __name__ == "__main__":
    check_trades()
