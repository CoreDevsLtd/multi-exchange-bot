MongoDB schema and examples for MultiExchangeTradingBot

1) Accounts collection (logical accounts)

Example document:
{
  "_id": "account_1",
  "name": "Main Account",
  "enabled": true,
  "metadata": { "owner": "ops-team", "tags": ["live"] }
}

2) ExchangeAccounts collection (one document per exchange connection)

Example document (Bybit):
{
  "_id": "bybit_1",
  "account_id": "account_1",
  "type": "bybit",
  "enabled": true,
  "credentials": {
    "api_key": "<encrypted_or_reference>",
    "api_secret": "<encrypted_or_reference>"
  },
  "symbol": "BTCUSDT",
  "symbols": ["BTCUSDT"],
  "leverage": 5,
  "trading_mode": "futures",
  "testnet": false,
  "connection_info": { "base_url": "https://api.bybit.com" }
}

Notes: store secrets encrypted or store a credential reference to a secrets manager (recommended).

3) CentralRiskManagement collection (single doc with per-exchange risk profiles)

Example document:
{
  "_id": "default",
  "bybit": {
    "stop_loss_percent": 3,
    "take_profit_percent": 5,
    "position_size_percent": 10,
    "use_percentage": true,
    "warn_existing_positions": true,
    "tp_mode": "ladder",
    "tp1_target": 1.0,
    "tp2_target": 2.0,
    "tp3_target": 5.0,
    "tp4_target": 6.5,
    "tp5_target": 8.0
  },
  "alpaca": {
    "stop_loss_percent": 3,
    "take_profit_percent": 5,
    "position_size_percent": 10,
    "use_percentage": true,
    "warn_existing_positions": true,
    "tp_mode": "single"
  }
}

4) Trades collection (append-only ledger)

Example document:
{
  "_id": "trade_001",
  "exchange_account_id": "bybit_1",
  "account_id": "account_1",
  "symbol": "BTCUSDT",
  "direction": "LONG",
  "entry_price": 30000,
  "exit_price": 31000,
  "stop_loss": 29500,
  "tp_hits": [true, false, false, false, false],
  "r_multiple": 2,
  "result_usd": 1000,
  "result_percent": 3.33,
  "trade_duration_sec": 3600,
  "max_drawdown": 200,
  "max_profit": 1200,
  "exit_reason": "TP",
  "timestamp_open": "2026-04-07T10:00:00Z",
  "timestamp_close": "2026-04-07T11:00:00Z",
  "execution_meta": { "order_ids": ["o1","o2"], "fees": 5.0 }
}

Indexes and scaling guidance
- Trades: index on (exchange_account_id, symbol) and (account_id, timestamp_open desc)
- Shard trades by hashed exchange_account_id for even distribution at scale
- Use bulk writes for migrations and high-throughput ingestion
- Archive older trades to trades_archive collection or use MongoDB Online Archive

Migration guidance
- Use scripts/migrate_to_mongo.py as a starting point to migrate dashboard_config.json -> accounts, exchange_accounts, central_risk_management
- Migrate existing trades by mapping old fields to exchange_account_id and account_id and bulk insert
- Verify counts and spot-check a few docs

Code integration notes
- Set MONGO_URI and MONGO_DB env vars to enable Mongo-backed operation
- webhook_handler will prefer Mongo when MONGO_URI is set and automatically create TradingExecutor instances per ExchangeAccount
- PositionManager will persist trades to trades collection on close (best-effort)
- Use mongo_db.py for helper methods and index creation

Security
- Do not store API secrets in plaintext; use KMS/Vault and store references in exchange_accounts instead
