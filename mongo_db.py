"""
MongoDB helper utilities for the trading bot.
Provides lightweight helpers to connect and query collections:
- accounts
- exchange_accounts
- central_risk_management
- trades

Note: Credentials/secrets should be encrypted in production. This helper expects MONGO_URI env var to be set.
"""
from pymongo import MongoClient
import os
from typing import Optional, List, Dict

MONGO_URI = os.getenv('MONGO_URI') or os.getenv('MONGODB_URI')
if not MONGO_URI:
    raise RuntimeError(
        'MONGO_URI environment variable is required. '
        'Set it to your MongoDB connection string (e.g. mongodb+srv://user:pass@cluster/dbname).'
    )

# Determine DB name: prefer explicit MONGO_DB, else parse from URI path, else default
_mongo_db_env = os.getenv('MONGO_DB') or os.getenv('MONGODB_DB')
if _mongo_db_env:
    MONGO_DB = _mongo_db_env
else:
    MONGO_DB = 'multi_exchange_bot'
    try:
        from urllib.parse import urlparse
        parsed = urlparse(MONGO_URI)
        path = (parsed.path or '').lstrip('/')
        db_candidate = path.split('?')[0]
        if db_candidate:
            MONGO_DB = db_candidate
    except Exception:
        pass

# Optional: application-side credential encryption/decryption helpers
try:
    from secrets_manager import decrypt_credentials_dict
except Exception:
    def decrypt_credentials_dict(d):
        return d


_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client


def get_db():
    return get_client()[MONGO_DB]


def get_central_risk() -> Dict:
    """Return central risk management doc (defaults to _id 'default')"""
    db = get_db()
    doc = db.central_risk_management.find_one({})
    if not doc:
        # return reasonable defaults
        return {
            '_id': 'default',
            'stop_loss_percent': 5.0,
            'take_profit_percent': 5.0,
            'position_size_percent': 10.0,
            'use_percentage': True,
            'warn_existing_positions': True,
            'overrides': {}
        }
    return doc


def _maybe_decrypt_doc(doc: Dict) -> Dict:
    if not doc or not isinstance(doc, dict):
        return doc
    if 'credentials' in doc and isinstance(doc['credentials'], dict):
        try:
            doc['credentials'] = decrypt_credentials_dict(doc['credentials'])
        except Exception:
            pass
    return doc


def get_enabled_exchange_accounts() -> List[Dict]:
    db = get_db()
    docs = list(db.exchange_accounts.find({'enabled': True}))
    return [_maybe_decrypt_doc(d) for d in docs]


def get_exchange_accounts_for_symbol(symbol: str) -> List[Dict]:
    """Return exchange account documents that include the given symbol (case-insensitive)."""
    db = get_db()
    sym_norm = str(symbol).strip().upper().replace(' ', '')
    # match if symbol in symbols array or equals symbol field
    docs = list(db.exchange_accounts.find({
        '$or': [
            {'symbols': sym_norm},
            {'symbol': sym_norm}
        ]
    }))
    return [_maybe_decrypt_doc(d) for d in docs]


def get_account(account_id: str) -> Optional[Dict]:
    db = get_db()
    doc = db.accounts.find_one({'_id': account_id})
    return _maybe_decrypt_doc(doc)


def insert_trade(trade_doc: Dict):
    db = get_db()
    return db.trades.insert_one(trade_doc)


def list_accounts() -> List[Dict]:
    db = get_db()
    docs = list(db.accounts.find({}))
    return [_maybe_decrypt_doc(d) for d in docs]


def get_exchange_accounts_for_account(account_id: str) -> List[Dict]:
    db = get_db()
    docs = list(db.exchange_accounts.find({'account_id': account_id}))
    return [_maybe_decrypt_doc(d) for d in docs]


def _serialize_doc(doc: Dict) -> Dict:
    """Convert non-JSON-serializable fields (e.g. BSON ObjectId) to strings."""
    if not doc:
        return doc
    result = {}
    for k, v in doc.items():
        # Convert ObjectId or any non-primitive to str
        if hasattr(v, '__class__') and v.__class__.__name__ == 'ObjectId':
            result[k] = str(v)
        else:
            result[k] = v
    return result


def get_trades(filters: Dict = None, limit: int = 100, skip: int = 0) -> List[Dict]:
    db = get_db()
    q = {}
    if filters:
        if 'account_id' in filters:
            q['account_id'] = filters['account_id']
        if 'exchange_account_id' in filters:
            q['exchange_account_id'] = filters['exchange_account_id']
        if 'symbol' in filters:
            q['symbol'] = filters['symbol'].strip().upper().replace(' ', '')
        if 'timestamp_open_gte' in filters or 'timestamp_open_lte' in filters:
            q['timestamp_open'] = {}
            if 'timestamp_open_gte' in filters:
                q['timestamp_open']['$gte'] = filters['timestamp_open_gte']
            if 'timestamp_open_lte' in filters:
                q['timestamp_open']['$lte'] = filters['timestamp_open_lte']
    cursor = db.trades.find(q).sort('timestamp_open', -1).skip(skip).limit(limit)
    return [_serialize_doc(d) for d in cursor]


def ensure_indexes():
    """Ensure all database indexes exist for performance and data lifecycle"""
    db = get_db()
    db.trades.create_index([('exchange_account_id', 1), ('symbol', 1)])
    db.trades.create_index([('account_id', 1), ('timestamp_open', -1)])
    db.exchange_accounts.create_index('account_id')
    # TTL index: auto-delete webhook logs after 30 days (2592000 seconds)
    db.webhook_logs.create_index('timestamp', expireAfterSeconds=2592000)
