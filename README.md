Multi-Exchange Trading Bot — MongoDB Migration & Dashboard Updates

Overview

This README documents the MongoDB migration, backend refactor, and dashboard UI changes performed to support centralized risk management, multi-account/multi-exchange support, and trade history persistence.

Summary of work performed

- Integrated MongoDB (supports MONGO_URI or MONGODB_URI). DB name is taken from MONGO_DB env, MONGODB_DB env, or parsed from the URI path.
- New/updated collections: accounts, exchange_accounts, central_risk_management, trades.
- Implemented mongo_db.py with helpers: get_client, get_db, get_central_risk, list_accounts, get_exchange_accounts_for_account, get_trades, insert_trade, ensure_indexes.
- Added idempotent migration script: scripts/migrate_to_mongo.py (migrates dashboard_config.json → Mongo collections, creates indexes).
- Refactored dashboard (dashboard.py): Mongo-backed endpoints for accounts, exchange accounts, risk management, trades; fixed DELETE exchange route placement and added endpoints for CRUD operations.
- Frontend updates (static/js/dashboard.js, templates/dashboard.html): Accounts page, account/exchange CRUD wiring, masked API secrets in responses, exchange modal improvements and parent-account support.
- Entrypoint (main_with_dashboard.py) updated to prefer centralized risk from Mongo and integrate webhook routes into the dashboard Flask app.
- Started dashboard during testing on alternate ports (8081/8082) to avoid killing existing server; verified /api/accounts and /api/exchanges responses.

MongoDB schema examples

Accounts (logical accounts)
{
  "_id": "account_1",
  "name": "Main Account",
  "enabled": true
}

ExchangeAccounts (1:M under an account)
{
  "_id": "bybit_1",
  "account_id": "account_1",
  "type": "bybit",
  "enabled": true,
  "credentials": {"api_key": "...", "api_secret": "..."},
  "symbol": "BTCUSDT",
  "symbols": ["BTCUSDT"],
  "leverage": 5,
  "trading_mode": "futures",
  "testnet": false,
  "connection_info": {}
}

CentralRiskManagement
{
  "_id": "default",
  "stop_loss_percent": 3,
  "take_profit_percent": 5,
  "position_size_percent": 10,
  "use_percentage": true,
  "warn_existing_positions": true,
  "overrides": {}
}

Trades (append-only ledger example)
{
  "_id": "trade_001",
  "exchange_account_id": "bybit_1",
  "account_id": "account_1",
  "symbol": "BTCUSDT",
  "direction": "LONG",
  "entry_price": 30000,
  "exit_price": 31000,
  "stop_loss": 29500,
  "tp_hits": [true, false],
  "r_multiple": 2,
  "result_usd": 1000,
  "result_percent": 3.33,
  "trade_duration_sec": 3600,
  "max_drawdown": 200,
  "max_profit": 1200,
  "exit_reason": "TP",
  "timestamp_open": "2026-04-07T10:00:00Z",
  "timestamp_close": "2026-04-07T11:00:00Z"
}

API endpoints (dashboard)

- GET /api/accounts — list logical accounts
- POST /api/accounts — create account
- GET /api/accounts/<account_id>/exchanges — list exchanges for account
- POST /api/accounts/<account_id>/exchanges — create exchange account under account
- GET /api/exchanges — list all exchange accounts (mapped to config shape)
- GET /api/exchanges/<exchange_id> — get exchange account
- POST /api/exchanges/<exchange_id> — update exchange account
- DELETE /api/exchanges/<exchange_id> — delete exchange account
- GET /api/risk-management — get central risk (Mongo-backed)
- POST /api/risk-management — update central risk
- GET /api/trades — query trades (filters: account_id, exchange_account_id, symbol)

How to run (development)

1. Set environment variables (example):
   - MONGO_URI or MONGODB_URI (connection string)
   - Optional: MONGO_DB (explicit DB name) or include DB in the URI path
   - LOG_LEVEL, DASHBOARD_PORT (defaults to 8080), DEMO_MODE=true for demo

2. Run migration (idempotent):
   python3 scripts/migrate_to_mongo.py --uri "$MONGO_URI" --db "$MONGO_DB"

3. Start the app (single Flask server for dashboard + webhook):
   python3 main_with_dashboard.py

Notes & troubleshooting

- The app accepts either MONGO_URI or MONGODB_URI. If MONGO_DB is not set, mongo_db.py attempts to parse the DB name from the URI path.
- During testing the server was started on alternate ports (8081/8082) to avoid killing running processes. Stop other instances before starting on default port.
- The dashboard masks api_secret in responses (shows '***'). The migration stores credentials in DB plaintext — rotate keys and use a secrets manager for production.
- Trades collection has indexes on (exchange_account_id, symbol) and (account_id, timestamp_open). Consider sharding trades by exchange_account_id for high-volume workloads.

Remaining work / next steps

- Finish exchange create/edit UI flows: secrets-reveal/replace UX, validation, and assigning account during creation.
- Sweep codebase to remove any remaining per-account risk reads and use centralized risk fetch.
- Add idempotency keys and dedupe logic to trade persistence; consider Mongo transactions for safety.
- Integrate secret encryption / Vault for credentials at rest.
- Add tests for migration script and API endpoints.

Security notice

- Do NOT commit real API keys or DB credentials. Rotate keys migrated into the DB and use Vault/KMS for production secret management.

Support

Runbook (quick)

- Start (development):
  1. Export env vars: MONGO_URI (or MONGODB_URI), optional MONGO_DB, LOG_LEVEL, DASHBOARD_PORT
  2. Run migration (idempotent):
     python3 scripts/migrate_to_mongo.py --uri "$MONGO_URI" --db "$MONGO_DB"
  3. Start app (dashboard + webhook):
     python3 main_with_dashboard.py

- Start on alternate port (avoid killing running server):
     DASHBOARD_PORT=8081 PORT=8081 nohup python3 main_with_dashboard.py &> /tmp/dashboard_stdout.log &

- Stop:
  - Find PID: ps aux | grep main_with_dashboard.py
  - Kill safely: kill <PID>

- Quick health checks:
  - GET /api/accounts
  - GET /api/exchanges
  - GET /api/risk-management

Deployment notes (Docker / Gunicorn / systemd)

- Docker: simplest option is to containerize the app and run with environment variables injected. Example Dockerfile should run python3 main_with_dashboard.py as the container CMD. Use an orchestrator (docker-compose, Kubernetes) and mount secrets securely.

- Gunicorn: this repo uses an application entrypoint that calls Dashboard(). For production WSGI, create a small wsgi.py that imports Dashboard and exposes the Flask app:

  # wsgi.py
  from dashboard import Dashboard
  app = Dashboard().app

  # run with gunicorn
  gunicorn -w 4 -b 0.0.0.0:8080 wsgi:app

- systemd service (example):

  [Unit]
  Description=Multi-Exchange Trading Bot
  After=network.target

  [Service]
  Type=simple
  User=youruser
  WorkingDirectory=/home/youruser/workspace/MultiExchangeTradingBot-main
  Environment="MONGO_URI=..."
  ExecStart=/usr/bin/python3 main_with_dashboard.py
  Restart=on-failure

  [Install]
  WantedBy=multi-user.target

Security recommendations (short)

- Rotate any API keys migrated into the DB immediately.
- Use a secrets manager (Vault, AWS KMS/Secrets Manager, GCP Secret Manager) to avoid storing plaintext credentials in Mongo.
- Restrict the MongoDB user to the minimum required privileges and enable network-level access controls (VPC, IP whitelisting).
- Use TLS for MongoDB connections and limit the lifetime of any long-lived keys.
- Consider encrypting credential fields at rest (application-side encryption) before writing to the DB.

Application-side credential encryption

A lightweight helper is provided (secrets_manager.py) that uses Fernet symmetric encryption when ENCRYPTION_KEY is set. Behavior:
- Set ENCRYPTION_KEY to a Fernet key (base64 urlsafe string). Generate one with:
    from secrets_manager import generate_key; print(generate_key())
- When ENCRYPTION_KEY is set, exchange credentials are encrypted before being written to Mongo and decrypted on read.
- If ENCRYPTION_KEY is not set or cryptography is unavailable, the helper is a no-op and credentials remain unchanged (backwards compatible).

Included deployment files (added):

- wsgi.py — WSGI entrypoint exposing Flask app for production WSGI servers
- Dockerfile — updated to use Gunicorn (production WSGI) and Python 3.12-slim
- docker-compose.yml — service definition for local/containerized runs
- .dockerignore — recommended ignores for Docker builds
- gunicorn.service — example systemd unit file for Gunicorn

Next steps:
- Implement secrets-store integration (Vault) and credential encryption helpers, or
- Finish Exchange create/edit UI and secrets UX work (reveal/replace pattern, validation).

