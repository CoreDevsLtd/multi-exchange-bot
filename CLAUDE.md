1. Project Overview 

1.1 Purpose 

The client operates an automated trading system driven by a TradingView Pine Script strategy. The current setup has incomplete exchange integrations, a signal logic issue that produces unwanted trades, and lacks a proper interface for reviewing trade performance per asset. 

This project addresses three concrete areas: stabilising the exchange execution layer, tightening the signal logic on the strategy side, and adding a portfolio and trade detail view to the existing dashboard. The goal is to get the system firing reliably across all configured assets with clear visibility into every trade. 

1.2 Scope Summary 

The project is divided into three milestones, delivered in the following priority order: 

Milestone 1: Exchange integration fixes and multi-account architecture 

Milestone 2: TradingView strategy logic enhancement 

Milestone 3: Portfolio and trade detail dashboard 

1.3 Out of Scope 

The following items are not included in this engagement and will require a separate agreement if needed later: 

Strategy development or strategy backtesting work 

Hyperliquid vault integration 

Any exchange integration beyond Bybit and Interactive Brokers 

Bug fixes or modifications to legacy code outside the scope of this project 

New features added after the signing of this document 

 

2. Milestone 1: Exchange Integrations 

Priority: Highest 

2.1 Requirements 

REQ-1.1: Bybit Integration Fix 

The existing Bybit integration has trade execution failures and reliability issues. We will diagnose the root cause and rebuild the integration layer so that signals originating from the strategy are executed on Bybit without failure under normal operating conditions. (FIXED/NEED TO CHECK MANUALLY BY HUMAN SO YOU CAN IGNORE)

REQ-1.2: Interactive Brokers Integration 

We will build the Interactive Brokers integration from scratch. Our team will handle the required gateway setup, authentication, order routing, and session management on the existing DigitalOcean environment. Implementation details of the IBKR connection layer are handled internally by our team. 

REQ-1.3: Multi-Account Architecture 

The system will be restructured to support multiple exchange accounts. The user must be able to add exchange API credentials through the dashboard and assign one ticker per account. Each ticker's signals will be routed to its assigned exchange account for execution. 

REQ-1.4: Account and Ticker Management 

The dashboard will allow the user to add, edit, and remove exchange accounts, and to configure the ticker assigned to each account. The routing logic will read from this configuration at signal time. 

2.2 User Acceptance Criteria 

Bybit integration executes trades correctly at 5x leverage on the 5-minute timeframe 

Bybit integration executes trades correctly at 7x leverage on the 5-minute timeframe 

Interactive Brokers integration executes trades correctly for the configured assets 

The user can add multiple exchange accounts through the dashboard 

Each exchange account can be assigned exactly one ticker 

Signals for a given ticker are routed to the correct exchange account 

 

3. Milestone 2: TradingView Strategy Logic 

Priority: Medium 

3.1 Requirements 

REQ-2.1: RSI Confirmation Filter 

We will extend the existing Pine Script strategy with an additional confirmation layer driven by the RSI indicator. The strategy currently produces signals that do not always align with the prevailing momentum direction. The new filter will prevent signals from firing when the RSI direction contradicts the signal direction. 

REQ-2.2: Filter Logic 

The filter applies the following rules at signal time: 

When RSI indicates a bullish condition and the strategy generates a long signal, the signal fires 

When RSI indicates a bullish condition and the strategy generates a short signal, the signal is suppressed 

When RSI indicates a bearish condition and the strategy generates a short signal, the signal fires 

When RSI indicates a bearish condition and the strategy generates a long signal, the signal is suppressed 

REQ-2.3: No Change to Existing Strategy Logic 

The existing entry, exit, stop loss, and take profit logic remains untouched. Only the RSI confirmation filter is added on top of the current signal generation layer. 

3.2 User Acceptance Criteria 

The RSI confirmation filter is active in the Pine Script strategy 

Signals that satisfy the RSI direction rule fire as expected 

Signals that violate the RSI direction rule are suppressed 

The existing strategy logic continues to function without regression 

 

4. Milestone 3: Portfolio and Trade Detail Dashboard 

Priority: Medium 

4.1 Requirements 

REQ-3.1: Portfolio Page 

A new page will be added to the dashboard that lists all tickers that have at least one trade on record from the go-live date onward. Tickers with no trading history are not shown. The list is the entry point for the drill-down view. 

REQ-3.2: Ticker Detail Page 

Clicking on a ticker in the portfolio page opens a dedicated page for that ticker. This page shows: 

Return on Investment (ROI) for the ticker 

Win rate for the ticker 

Trade history for the ticker, listed chronologically 

REQ-3.3: Trade Detail Page 

Clicking on any trade in the ticker's trade history opens a full breakdown of that individual trade. The following fields are displayed: 

Symbol 

Direction (Long or Short) 

Entry price 

Exit price 

Stop loss 

TP1 hit (Yes or No) 

TP2 hit (Yes or No) 

TP3 hit (Yes or No) 

TP4 hit (Yes or No) 

TP5 (runner) hit (Yes or No) 

Result in dollars 

Result as a percentage 

R-Multiple 

Trade duration 

Max drawdown during trade 

Max profit during trade 

Exit reason (TP, SL, Manual, or Close signal) 

REQ-3.4: R-Multiple Formula 

The R-Multiple is calculated as: 

    R-Multiple = Realized P&L / Initial Risk 

    Initial Risk = | Entry Price minus Stop Loss | 

The client is requested to review this formula and confirm or specify an alternative before development begins on this milestone. 

REQ-3.5: Max Drawdown and Max Profit Calculation 

Max drawdown and max profit during a trade are computed from historical candle data at the moment the user opens the trade detail page. When the user clicks on a trade, the system fetches the candle data covering the trade's open-to-close window and calculates the worst and best price reached during that window based on the trade direction. These values are not stored in advance; they are computed on demand. 

4.2 User Acceptance Criteria 

The portfolio page shows only tickers with at least one trade from go-live onward 

Clicking a ticker opens the ticker detail page with correct ROI, win rate, and trade history 

Clicking a trade opens the trade detail page with all specified fields populated 

Max drawdown and max profit values reflect the correct historical candle range 

The R-Multiple is calculated using the formula agreed upon by the client 

The dashboard continues to function for all existing pages without regression 

 

5. Project Terms 

5.1 Timeline 

The project start date is 2 April 2026. The full scope is delivered within 3 weeks from the start date. Internal milestone deadlines are coordinated between the project manager, the development team, and the client during the execution phase. 

5.2 Client Obligations 

The client is responsible for providing the following to ensure the project can proceed without delay: 

Access to the existing trading system, dashboard, and TradingView strategy 

Credentials for all exchange accounts required for integration and testing 

Any third-party or external API subscriptions needed for the project 

All funds required for testing on live or paper trading environments 

Timely responses to technical questions and acceptance testing requests 

5.3 Support and Warranty 

Core Devs provides 3 months of free bug-fix support following the completion of the project. This support covers only the work delivered under this engagement. Legacy code that existed before this project is outside the scope of the warranty. New features, scope additions, or enhancements requested during or after delivery are handled under a separate agreement. 

5.4 Deployment 

Deployment of the updated system is handled by Core Devs on the client's existing DigitalOcean environment. The final deployment approach is decided at the end of the development phase based on what works best for the system. 