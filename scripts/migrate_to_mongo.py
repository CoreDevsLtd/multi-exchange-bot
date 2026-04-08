"""
Migration script: migrate existing dashboard_config.json into MongoDB collections:
- accounts
- exchange_accounts
- central_risk_management

Usage: set MONGO_URI and optionally MONGO_DB env vars, then run:
python scripts/migrate_to_mongo.py

This script is idempotent for common fields and inserts/updates based on _id.
"""
import os
import json
from pymongo import MongoClient, UpdateOne

MONGO_URI = os.getenv('MONGO_URI')
MONGO_DB = os.getenv('MONGO_DB', 'trading_bot')
SOURCE = 'dashboard_config.json'

if not MONGO_URI:
    print('Please set MONGO_URI environment variable (e.g. mongodb://user:pass@host:port)')
    raise SystemExit(1)

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

with open(SOURCE, 'r') as f:
    cfg = json.load(f)

# 1) Create a logical account to hold existing exchanges
account_id = cfg.get('account_id', 'account_1')
account_doc = {
    '_id': account_id,
    'name': cfg.get('account_name', 'Default Account'),
    'enabled': True,
    'metadata': {'migrated_from': SOURCE}
}
print('Upserting account', account_id)
db.accounts.update_one({'_id': account_id}, {'$set': account_doc}, upsert=True)

# 2) Migrate exchanges -> exchange_accounts
ops = []
for ex_name, ex_cfg in cfg.get('exchanges', {}).items():
    ex_id = f"{ex_name}_1"
    doc = {
        '_id': ex_id,
        'account_id': account_id,
        'type': ex_name,
        'enabled': bool(ex_cfg.get('enabled', False)),
        'credentials': {
            'api_key': ex_cfg.get('api_key', ''),
            'api_secret': ex_cfg.get('api_secret', '')
        },
        'base_url': ex_cfg.get('base_url', ''),
        'symbols': ex_cfg.get('symbols', []),
        'leverage': ex_cfg.get('leverage', 1),
        'trading_mode': ex_cfg.get('trading_mode') or ex_cfg.get('trading_mode', ''),
        'testnet': ex_cfg.get('testnet', False),
        'use_paper': ex_cfg.get('paper_trading', ex_cfg.get('use_paper', False)),
        'account_id_value': ex_cfg.get('account_id', ''),
        'created_at': None
    }
    ops.append(UpdateOne({'_id': ex_id}, {'$set': doc}, upsert=True))

if ops:
    print('Upserting', len(ops), 'exchange_accounts')
    db.exchange_accounts.bulk_write(ops)

# 3) Central risk
risk = cfg.get('risk_management', {}) or {}
central = {
    '_id': 'default',
    'stop_loss_percent': risk.get('stop_loss_percent', 5.0),
    'take_profit_percent': risk.get('take_profit_percent', 5.0),
    'position_size_percent': cfg.get('trading_settings', {}).get('position_size_percent', 20.0),
    'use_percentage': cfg.get('trading_settings', {}).get('use_percentage', True),
    'warn_existing_positions': cfg.get('trading_settings', {}).get('warn_existing_positions', True),
    'overrides': {}
}
print('Upserting central risk')
db.central_risk_management.update_one({'_id': 'default'}, {'$set': central}, upsert=True)

print('Ensuring indexes')
db.trades.create_index([('exchange_account_id', 1), ('symbol', 1)])
db.trades.create_index([('account_id', 1), ('timestamp_open', -1)])

def summarize():
    print('Accounts:', db.accounts.count_documents({}))
    print('Exchange accounts:', db.exchange_accounts.count_documents({}))
    print('Trades:', db.trades.count_documents({}))

summarize()
print('Migration completed. Please verify documents and rotate credentials to a secrets manager.')
