// Dashboard JavaScript

let config = {};
let currentPage = 'overview';

// Application-wide client-side state to avoid scattered global vars
window.AppState = {
    usingMongo: false,
    exchanges: {},
    accounts: [],
    lastFetch: {}
};

// Initialize dashboard
// Check and display demo mode
async function checkDemoMode() {
    try {
        const response = await fetch('/api/status');
        if (response.ok) {
            const status = await response.json();
            const demoBadge = document.getElementById('demoModeBadge');
            const tradingSection = document.getElementById('tradingActivitySection');
            
            if (status.demo_mode) {
                if (demoBadge) demoBadge.style.display = 'block';
                if (tradingSection) tradingSection.style.display = 'block';
                await loadDemoData();
                // Refresh demo data every 10 seconds
                setInterval(loadDemoData, 10000);
            } else {
                if (demoBadge) demoBadge.style.display = 'none';
                if (tradingSection) tradingSection.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error checking demo mode:', error);
    }
}

// Load demo trading data
async function loadDemoData() {
    try {
        // Load demo stats
        const statsResponse = await fetch('/api/demo/stats');
        if (statsResponse.ok) {
            const statsData = await statsResponse.json();
            const stats = statsData.stats || {};
            
            const statsContainer = document.getElementById('tradingStats');
            if (statsContainer) {
                statsContainer.innerHTML = `
                    <div style="background: var(--bg-tertiary); padding: 12px; border-radius: 6px; border: 1px solid var(--border);">
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Total Trades</div>
                        <div style="font-size: 18px; font-weight: 600; color: var(--text-primary);">${stats.total_trades || 0}</div>
                    </div>
                    <div style="background: var(--bg-tertiary); padding: 12px; border-radius: 6px; border: 1px solid var(--border);">
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Total Volume</div>
                        <div style="font-size: 18px; font-weight: 600; color: var(--text-primary);">$${stats.total_volume || 0}</div>
                    </div>
                    <div style="background: var(--bg-tertiary); padding: 12px; border-radius: 6px; border: 1px solid var(--border);">
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Open Positions</div>
                        <div style="font-size: 18px; font-weight: 600; color: var(--text-primary);">${stats.open_positions || 0}</div>
                    </div>
                    <div style="background: var(--bg-tertiary); padding: 12px; border-radius: 6px; border: 1px solid var(--border);">
                        <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">Uptime</div>
                        <div style="font-size: 18px; font-weight: 600; color: var(--text-primary);">${Math.floor((stats.uptime_seconds || 0) / 60)}m</div>
                    </div>
                `;
            }
        }
        
        // Load demo trades
        const tradesResponse = await fetch('/api/demo/trades?limit=10');
        if (tradesResponse.ok) {
            const tradesData = await tradesResponse.json();
            const trades = tradesData.trades || [];
            
            const tradesBody = document.getElementById('demoTradesTableBody');
            if (tradesBody) {
                if (trades.length === 0) {
                    tradesBody.innerHTML = '<tr><td colspan="7" class="no-signals">No trades yet</td></tr>';
                } else {
                    tradesBody.innerHTML = trades.reverse().map(trade => {
                        const date = new Date(trade.timestamp);
                        const timeStr = date.toLocaleTimeString();
                        return `
                            <tr>
                                <td>${timeStr}</td>
                                <td>${trade.symbol}</td>
                                <td><span class="sig-badge ${trade.side.toLowerCase()}">${trade.side}</span></td>
                                <td>$${trade.price.toFixed(2)}</td>
                                <td>${trade.quantity.toFixed(6)}</td>
                                <td>$${trade.amount.toFixed(2)}</td>
                                <td><span class="sig-badge ok">${trade.status}</span></td>
                            </tr>
                        `;
                    }).join('');
                }
            }
        }
        
        // Load demo positions
        const positionsResponse = await fetch('/api/demo/positions');
        if (positionsResponse.ok) {
            const positionsData = await positionsResponse.json();
            const positions = positionsData.positions || [];
            
            const positionsBody = document.getElementById('demoPositionsTableBody');
            if (positionsBody) {
                if (positions.length === 0) {
                    positionsBody.innerHTML = '<tr><td colspan="6" class="no-signals">No open positions</td></tr>';
                } else {
                    positionsBody.innerHTML = positions.map(pos => {
                        const pnlColor = pos.unrealized_pnl >= 0 ? 'var(--success)' : 'var(--error)';
                        return `
                            <tr>
                                <td>${pos.symbol}</td>
                                <td><span class="sig-badge ${pos.side.toLowerCase()}">${pos.side}</span></td>
                                <td>$${pos.entry_price.toFixed(2)}</td>
                                <td>$${pos.current_price.toFixed(2)}</td>
                                <td>${pos.quantity.toFixed(6)}</td>
                                <td style="color: ${pnlColor}; font-weight: 600;">$${pos.unrealized_pnl.toFixed(2)}</td>
                            </tr>
                        `;
                    }).join('');
                }
            }
        }
    } catch (error) {
        console.error('Error loading demo data:', error);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    loadDashboard();
    setupSymbolSearch();
    initRecentSignalsToolbar();
    setInterval(updateStatus, 30000); // Update status every 30 seconds (includes exchange balances)
    setInterval(updateSignalStatus, 5000); // Update signal status every 5 seconds
    setInterval(updateRecentSignals, 10000); // Update recent signals every 10 seconds
    setInterval(async () => { await renderExchanges(); }, 30000); // Refresh exchange balances every 30 seconds

    // Initialize default page
    showPage('overview');
});

// High-level page switching
function showPage(pageId) {
    currentPage = pageId;
    const pages = ['overview', 'exchanges', 'accounts', 'symbolsRouting', 'tradingSettings', 'risk', 'activity'];
    pages.forEach(function(p) {
        const el = document.getElementById('page-' + p);
        if (el) {
            el.style.display = (p === pageId ? 'block' : 'none');
        }
    });
    // Update sidebar active state
    const items = document.querySelectorAll('.sidebar-item');
    items.forEach(function(btn) {
        const target = btn.getAttribute('data-page');
        if (target === pageId) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    // Refresh page-specific data when navigating
    if (pageId === 'symbolsRouting') {
        refreshSymbolsRouting();
    } else if (pageId === 'accounts') {
        renderAccounts();
    } else if (pageId === 'activity') {
        updateRecentSignals();
        if (typeof loadDemoData === 'function') loadDemoData();
    }
}

// HTML-escape helper
function escapeHtml(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Render accounts list (Mongo-backed)
async function renderAccounts() {
    try {
        const resp = await fetch('/api/accounts');
        const container = document.getElementById('accountsList');
        if (!container) return;
        if (!resp.ok) {
            container.innerHTML = `<div class="empty-state"><i class="fas fa-exclamation-circle"></i><div class="empty-title">Failed to load accounts</div><p>Make sure MONGO_URI is configured.</p></div>`;
            return;
        }
        const data = await resp.json();
        const accounts = data.accounts || [];
        window.AppState.accounts = accounts;

        if (accounts.length === 0) {
            container.innerHTML = `<div class="empty-state"><i class="fas fa-user-plus"></i><div class="empty-title">No accounts yet</div><p>Create your first account to get started.</p></div>`;
            return;
        }

        container.innerHTML = accounts.map(ac => {
            const enabled = ac.enabled !== false;
            return `
                <div class="account-card ${enabled ? 'enabled' : ''}">
                    <div class="account-card-header">
                        <div>
                            <div class="account-card-name">${escapeHtml(ac.name || ac._id)}</div>
                            <div class="account-card-id">${escapeHtml(ac._id)}</div>
                        </div>
                        <span class="badge ${enabled ? 'badge-success' : 'badge-neutral'}">${enabled ? 'Enabled' : 'Disabled'}</span>
                    </div>
                    <div class="account-card-footer">
                        <button class="btn btn-sm btn-primary" onclick="openCreateExchangeModal('${ac._id}')"><i class="fas fa-plus"></i> Add Exchange</button>
                        <button class="btn btn-sm" onclick="viewAccountExchanges('${ac._id}')"><i class="fas fa-list"></i> Exchanges</button>
                        <button class="btn btn-sm" onclick="openAccountModal('${ac._id}')"><i class="fas fa-edit"></i> Edit</button>
                        <button class="btn btn-sm" onclick="toggleAccountEnabled('${ac._id}', ${!enabled})">${enabled ? 'Disable' : 'Enable'}</button>
                        <button class="btn btn-sm btn-danger btn-icon" onclick="deleteAccount('${ac._id}')"><i class="fas fa-trash"></i></button>
                    </div>
                </div>
            `;
        }).join('');
        renderOverviewStats();
    } catch (e) {
        console.error('Error rendering accounts', e);
    }
}

// Edit exchange (fetch from API then open modal)
async function editExchange(exchangeId) {
    try {
        const resp = await fetch(`/api/exchanges/${exchangeId}`);
        if (!resp.ok) { showToast('Failed to fetch exchange', 'error'); return; }
        const data = await resp.json();
        // Map API response to the shape expected by openExchangeModal
        const mapped = {
            enabled: data.enabled || false,
            api_key: data.api_key || '',
            api_secret: data.api_secret || '',
            base_url: data.base_url || '',
            name: data.name || exchangeId,
            type: (data.name || exchangeId).toLowerCase(),
            testnet: data.testnet || false,
            trading_mode: data.trading_mode || 'spot',
            leverage: data.leverage || 1,
            proxy: data.proxy || '',
            symbols: data.symbols || [],
            account_id: data.account_id || ''
        };
        if (!config.exchanges) config.exchanges = {};
        config.exchanges[exchangeId] = mapped;
        const parentAcct = document.getElementById('exchangeParentAccount');
        if (parentAcct) parentAcct.value = '';
        openExchangeModal(exchangeId);
    } catch (e) {
        console.error('Error fetching exchange for edit', e);
        showToast('Error fetching exchange', 'error');
    }
}

// Delete exchange (mongo-backed or config-file)
async function deleteExchange(exchangeId) {
    if (!confirm('Are you sure you want to delete exchange ' + exchangeId + '? This cannot be undone.')) return;
    try {
        const resp = await fetch(`/api/exchanges/${exchangeId}`, { method: 'DELETE' });
        const result = await resp.json();
        if (resp.ok && result.status === 'success') {
            showToast('Exchange deleted', 'success');
            await loadDashboard();
        } else {
            showToast(result.error || 'Failed to delete exchange', 'error');
        }
    } catch (e) {
        console.error('Error deleting exchange', e);
        showToast('Error deleting exchange', 'error');
    }
}

// View exchanges for an account and open exchanges page
async function viewAccountExchanges(accountId) {
    try {
        const resp = await fetch(`/api/accounts/${accountId}/exchanges`);
        if (!resp.ok) return;
        const data = await resp.json();
        const exchanges = data.exchanges || [];
        showPage('exchanges');
        const list = document.getElementById('exchangesList');
        const actions = document.getElementById('exchangesPageActions');
        if (!list) return;

        if (actions) {
            actions.innerHTML = `
                <button class="btn" onclick="renderExchanges(); document.getElementById('exchangesPageActions').innerHTML = '<button class=\\'btn btn-primary\\' onclick=\\'showPage(\\'accounts\\')\\'><i class=\\'fas fa-plus\\'></i> Add Exchange Account</button>'">
                    <i class="fas fa-arrow-left"></i> All Exchanges
                </button>
                <button class="btn btn-primary" onclick="openCreateExchangeModal('${accountId}')">
                    <i class="fas fa-plus"></i> Add Exchange
                </button>`;
        }

        if (exchanges.length === 0) {
            list.innerHTML = `<div class="empty-state"><i class="fas fa-plug"></i><div class="empty-title">No exchange accounts</div><p>Add an exchange account to this account.</p></div>`;
            return;
        }

        let exchangeStatus = {};
        try {
            const sr = await fetch('/api/exchanges/status');
            if (sr.ok) exchangeStatus = await sr.json();
        } catch (e) {}

        list.innerHTML = '';
        exchanges.forEach(ex => {
            const key = ex._id;
            const exObj = {
                enabled: ex.enabled !== false,
                name: (ex.type || key).toUpperCase(),
                type: (ex.type || key).toLowerCase(),
                trading_mode: ex.trading_mode || 'spot',
                leverage: ex.leverage || 1,
                testnet: !!ex.testnet,
                paper_trading: !!ex.paper_trading,
                symbols: ex.symbols || (ex.symbol ? [ex.symbol] : []),
                account_id: accountId
            };
            list.appendChild(_buildExchangeCard(key, exObj, exchangeStatus[key] || {}));
        });
    } catch (e) { console.error(e); }
}

// Delete account and all its exchange accounts
async function deleteAccount(accountId) {
    if (!confirm(`Delete account "${accountId}" and ALL its exchange accounts? This cannot be undone.`)) return;
    try {
        const resp = await fetch(`/api/accounts/${accountId}`, { method: 'DELETE' });
        const result = await resp.json();
        if (resp.ok && result.status === 'success') {
            showToast('Account deleted', 'success');
            await loadDashboard();
            renderAccounts();
        } else {
            showToast(result.error || 'Failed to delete account', 'error');
        }
    } catch (e) {
        console.error('Error deleting account', e);
        showToast('Error deleting account', 'error');
    }
}

// Open exchange modal in create mode under a logical account
function openCreateExchangeModal(accountId) {
    const modal = document.getElementById('exchangeModal');

    // Show exchange type selector
    const typeGroup = document.getElementById('exchangeTypeGroup');
    if (typeGroup) typeGroup.style.display = 'block';

    // Reset hidden fields
    document.getElementById('exchangeName').value = '';
    document.getElementById('exchangeParentAccount').value = accountId || '';
    document.getElementById('modalTitle').textContent = 'Add Exchange Account';
    document.getElementById('exchangeEnabled').checked = true;
    document.getElementById('exchangeApiKey').value = '';
    const secretEl = document.getElementById('exchangeApiSecret');
    secretEl.value = '';
    secretEl.dataset.hasSecret = 'false';
    document.getElementById('exchangeBaseUrl').value = '';

    // Default to bybit and apply its field set
    const typeEl = document.getElementById('newExchangeType');
    if (typeEl) typeEl.value = 'bybit';
    _applyExchangeTypeUi('bybit', {});

    modal.classList.add('show');
}

async function toggleAccountEnabled(accountId, enabled) {
    try {
        const resp = await fetch(`/api/accounts`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ _id: accountId, enabled: enabled }) });
        if (resp.ok) renderAccounts();
    } catch (e) { console.error(e); }
}

async function createAccountPrompt() {
    // Open account modal for creation
    openAccountModal();
}

// Open Account modal for create or edit
function openAccountModal(account) {
    const modal = document.getElementById('accountModal');
    const idEl = document.getElementById('accountId');
    const nameEl = document.getElementById('accountName');
    const enabledEl = document.getElementById('accountEnabled');

    // Accept either account object or account id string
    if (typeof account === 'string') {
        account = (window.AppState && window.AppState.accounts) ? window.AppState.accounts.find(a => a._id === account) : null;
    }

    if (account) {
        idEl.value = account._id || '';
        nameEl.value = account.name || account._id || '';
        enabledEl.checked = account.enabled !== false;
        document.getElementById('accountModalTitle').textContent = 'Edit Account';
    } else {
        idEl.value = '';
        nameEl.value = '';
        enabledEl.checked = true;
        document.getElementById('accountModalTitle').textContent = 'Create Account';
    }

    modal.classList.add('show');
}

function closeAccountModal() {
    const modal = document.getElementById('accountModal');
    modal.classList.remove('show');
}

async function saveAccount() {
    const id = document.getElementById('accountId').value.trim();
    const name = document.getElementById('accountName').value.trim();
    const enabled = document.getElementById('accountEnabled').checked;
    if (!name) { showToast('Please enter a name for the account', 'error'); return; }
    try {
        const body = { name, enabled };
        if (id) body._id = id;
        const resp = await fetch('/api/accounts', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
        const result = await resp.json();
        if (resp.ok && result.status === 'success') {
            showToast('Account saved', 'success');
            closeAccountModal();
            renderAccounts();
            // reload exchanges in case new account created
            await loadDashboard();
        } else {
            showToast(result.error || 'Failed to save account', 'error');
        }
    } catch (e) {
        console.error('Error saving account', e);
        showToast('Error saving account', 'error');
    }
}

// Refresh Symbols & Routing with latest data from server
async function refreshSymbolsRouting() {
    try {
        var resp = await fetch('/api/exchanges');
        if (resp.ok) {
            var exchanges = await resp.json();
            if (config && config.exchanges) {
                for (var k in exchanges) config.exchanges[k] = exchanges[k];
            }
        }
    } catch (e) { /* ignore */ }
    renderSymbolsRouting();
}

// Load dashboard data
async function loadDashboard() {
    try {
        console.log('Loading dashboard configuration...');

        // Prefer Mongo-backed accounts/exchanges if available
        let usingMongo = false;
        let exchanges = {};
        try {
            const accountsResp = await fetch('/api/accounts');
            if (accountsResp.ok) {
                const accountsData = await accountsResp.json();
                if (accountsData && Array.isArray(accountsData.accounts) && accountsData.accounts.length > 0) {
                    // Mongo-backed mode: fetch exchanges per account
                    usingMongo = true;
                    // update global client state
                    window.AppState.usingMongo = true;
                    window.AppState.accounts = accountsData.accounts;
                    for (const acct of accountsData.accounts) {
                        try {
                            const exResp = await fetch(`/api/accounts/${acct._id}/exchanges`);
                            if (!exResp.ok) continue;
                            const exData = await exResp.json();
                            const list = exData.exchanges || [];
                            for (const ex of list) {
                                // Map to a config-like exchange object keyed by exchange account id
                                const key = ex._id;
                                exchanges[key] = {
                                    enabled: !!ex.enabled,
                                    api_key: (ex.credentials && ex.credentials.api_key) || '',
                                    api_secret: (ex.credentials && ex.credentials.api_secret) ? '***' : '',
                                    base_url: ex.base_url || (ex.connection_info && ex.connection_info.base_url) || '',
                                    name: ex.type || key,
                                    type: (ex.type || key).toLowerCase(),
                                    testnet: !!ex.testnet,
                                    trading_mode: ex.trading_mode || 'spot',
                                    leverage: ex.leverage || 1,
                                    proxy: ex.proxy || '',
                                    symbols: ex.symbols || (ex.symbol ? [ex.symbol] : []),
                                    account_id: acct._id
                                };
                            }
                        } catch (e) { /* continue */ }
                    }
                }
            }
        } catch (e) { /* ignore */ }

        if (!usingMongo) {
            // Load exchanges (config-file mode)
            const exchangesResponse = await fetch('/api/exchanges');
            if (!exchangesResponse.ok) {
                throw new Error(`Failed to load exchanges: ${exchangesResponse.statusText}`);
            }
            exchanges = await exchangesResponse.json();
            // Ensure each config-file exchange has a `type` field for modal rendering
            for (const [key, ex] of Object.entries(exchanges)) {
                if (!ex.type) ex.type = key.toLowerCase();
            }
            console.log('Loaded exchanges:', Object.keys(exchanges));
        } else {
            console.log('Using Mongo-backed exchanges:', Object.keys(exchanges));
        }

        // Load trading settings
        const tradingSettingsResponse = await fetch('/api/trading-settings');
        const tradingSettings = await tradingSettingsResponse.json();

        // Load risk management
        const riskManagementResponse = await fetch('/api/risk-management');
        const riskManagement = await riskManagementResponse.json();

        // Load status
        const statusResponse = await fetch('/api/status');
        const status = await statusResponse.json();

        config = { exchanges, tradingSettings, riskManagement, status };
        // reflect into AppState for other components
        window.AppState.exchanges = exchanges;
        window.AppState.usingMongo = usingMongo;

        renderExchanges();
        renderTradingSettings();
        renderRiskManagement();
        renderSymbolsRouting();
        renderOverviewStats();
        updateStatusIndicator();

        // Check for demo mode
        checkDemoMode();

        // Load initial signal status
        updateSignalStatus();
        updateRecentSignals();
        
        console.log('Dashboard configuration loaded successfully');
        
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showToast('Error loading dashboard data', 'error');
    }
}

// Get 2-letter abbreviation for an exchange type
function _getExchangeTypeAbbr(type) {
    const t = (type || '').toLowerCase();
    if (t === 'bybit') return 'BY';
    if (t === 'mexc') return 'MX';
    if (t === 'alpaca') return 'AL';
    if (t === 'ibkr') return 'IB';
    return (type || '?').substring(0, 2).toUpperCase();
}

// Build an exchange card DOM element
function _buildExchangeCard(key, exchange, status) {
    const enabled = exchange.enabled !== false;
    const type = (exchange.type || exchange.name || key).toLowerCase();
    const abbr = _getExchangeTypeAbbr(type);
    const connected = !!(status && status.connected);

    // Symbols
    const symbols = Array.isArray(exchange.symbols) ? exchange.symbols : [];
    const symbolsHtml = symbols.length > 0
        ? symbols.map(s => `<span class="symbol-badge">${escapeHtml(s)}</span>`).join('')
        : '<span class="text-muted" style="font-size:11px;">No symbols</span>';

    // Balance
    let balanceHtml = '';
    if (connected && status.balances && Object.keys(status.balances).length > 0) {
        const parts = [];
        for (const [asset, bal] of Object.entries(status.balances)) {
            let total = 0;
            if (typeof bal === 'object' && bal !== null) total = parseFloat(bal.total || bal.free || 0);
            else if (typeof bal === 'number') total = bal;
            else total = parseFloat(bal) || 0;
            if (total > 0 && !isNaN(total)) {
                const fmt = total >= 1 ? total.toFixed(2) : total >= 0.01 ? total.toFixed(4) : total.toFixed(8);
                parts.push(`${asset}: ${fmt}`);
            }
        }
        if (parts.length > 0) {
            balanceHtml = `<div class="exchange-card-row"><span class="exchange-card-row-label">Balance</span><span class="exchange-card-row-value" style="font-size:11px;">${parts.slice(0, 4).join(' · ')}</span></div>`;
        }
    }

    // Mode
    let modeText = exchange.trading_mode
        ? (exchange.trading_mode.charAt(0).toUpperCase() + exchange.trading_mode.slice(1))
        : (exchange.paper_trading ? 'Paper' : (exchange.testnet ? 'Testnet' : 'Live'));
    const leverageText = (exchange.leverage && exchange.leverage > 1) ? ` · ${exchange.leverage}x` : '';

    const div = document.createElement('div');
    div.className = `exchange-card ${enabled ? 'enabled' : 'disabled'}`;
    div.innerHTML = `
        <div class="exchange-card-header">
            <div class="exchange-card-title-row">
                <div class="exchange-type-icon ${type}">${abbr}</div>
                <div>
                    <div class="exchange-card-name">${escapeHtml(exchange.name || type.toUpperCase())}</div>
                    <div class="exchange-card-id">${escapeHtml(key)}</div>
                </div>
            </div>
            <span class="badge ${connected ? 'badge-success' : 'badge-neutral'}">${connected ? '● Connected' : '○ Offline'}</span>
        </div>
        <div class="exchange-card-body">
            <div class="exchange-card-row">
                <span class="exchange-card-row-label">Mode</span>
                <span class="exchange-card-row-value">${modeText}${leverageText}</span>
            </div>
            ${balanceHtml}
            <div class="exchange-symbols-row">${symbolsHtml}</div>
        </div>
        <div class="exchange-card-footer">
            <div class="exchange-card-footer-left">
                <button class="btn btn-sm" onclick="openExchangeModal('${key}')"><i class="fas fa-cog"></i> Configure</button>
                <button class="btn btn-sm" onclick="openSymbolsManager('${key}')"><i class="fas fa-list"></i> Symbols</button>
                <button class="btn btn-sm btn-danger btn-icon" onclick="deleteExchange('${key}')"><i class="fas fa-trash"></i></button>
            </div>
            <div class="exchange-card-footer-right">
                <label class="toggle" title="${enabled ? 'Disable' : 'Enable'}">
                    <input type="checkbox" ${enabled ? 'checked' : ''} onchange="toggleExchange('${key}', this.checked)">
                    <span class="toggle-track"></span>
                </label>
            </div>
        </div>
    `;
    return div;
}

// Render exchanges
async function renderExchanges() {
    const list = document.getElementById('exchangesList');
    if (!list) return;
    list.innerHTML = '<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><p>Loading exchanges...</p></div>';

    if (!config || !config.exchanges) {
        list.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-circle"></i><div class="empty-title">Not loaded</div><p>Exchanges configuration not available.</p></div>';
        return;
    }

    let exchangeStatus = {};
    try {
        const response = await fetch('/api/exchanges/status');
        if (response.ok) exchangeStatus = await response.json();
    } catch (error) { console.error('Error fetching exchange status:', error); }

    const entries = Object.entries(config.exchanges);
    if (entries.length === 0) {
        list.innerHTML = '<div class="empty-state"><i class="fas fa-plug"></i><div class="empty-title">No exchange accounts</div><p>Go to Accounts to add an exchange account.</p></div>';
        return;
    }

    list.innerHTML = '';
    entries.forEach(([key, exchange]) => {
        list.appendChild(_buildExchangeCard(key, exchange, exchangeStatus[key] || {}));
    });
    renderOverviewStats();
}

// Render trading settings
function renderTradingSettings() {
    const settings = config.tradingSettings || {};
    const positionSize = settings.position_size_percent || 20;
    const elPercent = document.getElementById('positionSizePercent');
    const elValue = document.getElementById('positionSizeValue');
    const elFixed = document.getElementById('positionSizeFixed');
    const elUsePct = document.getElementById('usePercentage');
    const elWarn = document.getElementById('warnExistingPositions');
    if (elPercent) elPercent.value = positionSize;
    if (elValue) elValue.textContent = positionSize;
    if (elFixed) elFixed.value = settings.position_size_fixed || '';
    if (elUsePct) elUsePct.checked = settings.use_percentage !== false;
    if (elWarn) elWarn.checked = settings.warn_existing_positions !== false;
}

// Render risk management
function renderRiskManagement() {
    const risk = config.riskManagement || {};
    const el = (id) => document.getElementById(id);
    if (el('stopLossPercent')) el('stopLossPercent').value = risk.stop_loss_percent || 5.0;
    if (el('takeProfit1')) el('takeProfit1').value = 1.0;
    if (el('takeProfit2')) el('takeProfit2').value = 2.0;
    if (el('takeProfit3')) el('takeProfit3').value = 5.0;
    if (el('takeProfit4')) el('takeProfit4').value = 6.5;
    if (el('takeProfit5')) el('takeProfit5').value = 8.0;
}

// Update status indicator
function updateStatusIndicator() {
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');

    const enabledExchanges = Object.values(config.exchanges || {}).filter(e => e.enabled).length;
    const total = Object.keys(config.exchanges || {}).length;

    if (enabledExchanges > 0) {
        statusDot.className = 'status-dot active';
        statusText.textContent = `${enabledExchanges} of ${total} Exchange Account(s) Active`;
    } else if (total > 0) {
        statusDot.className = 'status-dot inactive';
        statusText.textContent = `${total} Exchange Account(s) — None Enabled`;
    } else {
        statusDot.className = 'status-dot inactive';
        statusText.textContent = 'No Exchange Accounts Configured';
    }
}

// Toggle exchange
async function toggleExchange(exchangeName, enabled) {
    try {
        const response = await fetch(`/api/exchanges/${exchangeName}/toggle`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled })
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            config.exchanges[exchangeName].enabled = enabled;
            renderExchanges();
            updateStatusIndicator();
            showToast(result.message, 'success');
        } else {
            showToast(result.error || 'Failed to toggle exchange', 'error');
        }
    } catch (error) {
        console.error('Error toggling exchange:', error);
        showToast('Error toggling exchange', 'error');
    }
}

function isIbkrLocalGatewayHost(url) {
    try {
        var normalized = (url || '').trim();
        if (!normalized) return false;
        var u = new URL(normalized.indexOf('://') === -1 ? 'https://' + normalized : normalized);
        var h = (u.hostname || '').toLowerCase();
        return h === 'localhost' || h === '127.0.0.1' || h === '[::1]';
    } catch (e) {
        return false;
    }
}

function dashboardIsViewedLocally() {
    var h = (window.location.hostname || '').toLowerCase();
    return h === 'localhost' || h === '127.0.0.1' || h === '[::1]';
}

function openIbkrGatewayLogin() {
    var baseUrlEl = document.getElementById('exchangeBaseUrl');
    var base = (baseUrlEl && baseUrlEl.value ? baseUrlEl.value : '').trim();
    var remoteDashboard = !dashboardIsViewedLocally();

    if (!base) {
        if (remoteDashboard) {
            showToast(
                'Enter your IB Gateway Base URL first. For a hosted dashboard it cannot be localhost — use an HTTPS URL from your PC to Gateway (e.g. ngrok/Cloudflare Tunnel), same URL the bot uses.',
                'error'
            );
            return;
        }
        base = 'https://localhost:5000';
    }
    base = base.replace(/\/$/, '');
    if (remoteDashboard && isIbkrLocalGatewayHost(base)) {
        showToast(
            'localhost in Base URL only opens IB Gateway on the computer running this browser, not your trading server. Save a public/tunnel URL that reaches the machine where Gateway runs, then try again.',
            'error'
        );
        return;
    }
    window.open(base + '/', '_blank', 'noopener,noreferrer');
    showToast('Sign in to IBKR in the new tab, then return here and click Test Connection.', 'success');
}

// Open exchange modal
async function openExchangeModal(exchangeName) {
    const exchange = config.exchanges[exchangeName];
    if (!exchange) {
        showToast('Exchange configuration not found', 'error');
        return;
    }
    // Determine the canonical type (bybit/mexc/alpaca/ibkr) from the 'type' field
    // or fall back to the name/exchangeName for legacy config-file mode
    const exchangeType = (exchange.type || exchange.name || exchangeName).toLowerCase();

    const modal = document.getElementById('exchangeModal');

    // Hide type selector (this is edit mode, not create)
    const typeGroup = document.getElementById('exchangeTypeGroup');
    if (typeGroup) typeGroup.style.display = 'none';

    document.getElementById('exchangeName').value = exchangeName;
    document.getElementById('exchangeParentAccount').value = exchange.account_id || '';
    document.getElementById('modalTitle').textContent = `Configure ${exchange.name || exchangeName}`;
    document.getElementById('exchangeEnabled').checked = exchange.enabled || false;

    const apiKeyField = document.getElementById('exchangeApiKey');
    apiKeyField.value = exchange.api_key || '';

    const apiSecretField = document.getElementById('exchangeApiSecret');
    apiSecretField.value = (exchange.api_secret && exchange.api_secret !== '') ? '***' : '';
    apiSecretField.dataset.hasSecret = (exchange.api_secret && exchange.api_secret !== '') ? 'true' : 'false';
    document.getElementById('exchangeBaseUrl').value = exchange.base_url || '';

    // Apply type-specific UI configuration
    _applyExchangeTypeUi(exchangeType, exchange);

    modal.classList.add('show');
}

// Apply type-specific field visibility and values to the exchange modal.
// Called both from openExchangeModal (edit) and openCreateExchangeModal (create).
function _applyExchangeTypeUi(exchangeType, exchange) {
    exchange = exchange || {};
    const credFields = document.querySelectorAll('.exchange-credential-field');
    const ibkrGw = document.getElementById('ibkrGatewayGroup');
    const paperTradingGroup = document.getElementById('paperTradingGroup');
    const subAccountGroup = document.getElementById('subAccountGroup');
    const subAccountIdInput = document.getElementById('exchangeSubAccountId');
    const mexcWarning = document.getElementById('mexcWarning');
    const tradingModeGroup = document.getElementById('tradingModeGroup');
    const tradingModeSelect = document.getElementById('exchangeTradingMode');
    const leverageGroup = document.getElementById('leverageGroup');
    const proxyGroup = document.getElementById('proxyGroup');

    // Reset to defaults
    credFields.forEach(el => el.style.display = 'block');
    if (ibkrGw) ibkrGw.style.display = 'none';
    paperTradingGroup.style.display = 'none';
    subAccountGroup.style.display = 'none';
    mexcWarning.style.display = 'none';
    tradingModeGroup.style.display = 'none';
    leverageGroup.style.display = 'none';
    proxyGroup.style.display = 'none';
    tradingModeSelect.onchange = null;

    if (exchangeType === 'mexc') {
        subAccountGroup.style.display = 'block';
        mexcWarning.style.display = 'block';
        const useSubCb = document.getElementById('exchangeUseSubAccount');
        useSubCb.checked = exchange.use_sub_account || false;
        subAccountIdInput.value = exchange.sub_account_id || '';
        const toggleSub = () => { subAccountIdInput.style.display = useSubCb.checked ? 'block' : 'none'; };
        useSubCb.onchange = toggleSub;
        toggleSub();
        document.getElementById('exchangeBaseUrl').placeholder = 'https://api.mexc.com';

    } else if (exchangeType === 'ibkr') {
        credFields.forEach(el => el.style.display = 'none');
        if (ibkrGw) ibkrGw.style.display = 'block';
        leverageGroup.style.display = 'block';
        document.getElementById('exchangeLeverage').value = exchange.leverage || '1';
        document.getElementById('exchangeBaseUrl').placeholder = 'https://localhost:5000';

    } else if (exchangeType === 'bybit') {
        tradingModeGroup.style.display = 'block';
        const mode = (exchange.trading_mode || 'spot').toLowerCase();
        tradingModeSelect.value = mode === 'futures' ? 'futures' : 'spot';
        leverageGroup.style.display = (tradingModeSelect.value === 'futures') ? 'block' : 'none';
        document.getElementById('exchangeLeverage').value = exchange.leverage || '1';
        proxyGroup.style.display = 'block';
        document.getElementById('exchangeProxy').value = exchange.proxy || '';
        document.getElementById('exchangeBaseUrl').placeholder = 'https://api.bybit.com';
        tradingModeSelect.onchange = function() {
            leverageGroup.style.display = (tradingModeSelect.value === 'futures') ? 'block' : 'none';
        };

    } else if (exchangeType === 'alpaca') {
        paperTradingGroup.style.display = 'block';
        document.getElementById('exchangePaperTrading').checked = exchange.paper_trading !== undefined ? exchange.paper_trading : true;
        document.getElementById('exchangeBaseUrl').placeholder = 'https://paper-api.alpaca.markets';

    } else {
        document.getElementById('exchangeBaseUrl').placeholder = '';
    }
}

// Close modal
function closeModal() {
    document.getElementById('exchangeModal').classList.remove('show');
}

// Save exchange
async function saveExchange() {
    const exchangeName = document.getElementById('exchangeName').value;
    const parentAcct = document.getElementById('exchangeParentAccount');
    const parentAccountId = parentAcct ? parentAcct.value.trim() : '';

    // Determine the real exchange type (bybit/mexc/alpaca/ibkr)
    // In create mode, use the type selector; in edit mode, use stored config
    let exchangeType;
    if (!exchangeName && parentAccountId) {
        // Create mode — type comes from selector
        const typeEl = document.getElementById('newExchangeType');
        exchangeType = typeEl ? typeEl.value : 'bybit';
    } else {
        const exchange = (config.exchanges || {})[exchangeName] || {};
        exchangeType = (exchange.type || exchange.name || exchangeName).toLowerCase();
    }

    const exchange = (config.exchanges || {})[exchangeName] || {};

    const data = {
        enabled: document.getElementById('exchangeEnabled').checked,
        api_key: document.getElementById('exchangeApiKey').value.trim(),
        api_secret: document.getElementById('exchangeApiSecret').value.trim(),
        base_url: document.getElementById('exchangeBaseUrl').value.trim()
    };

    // Type-specific fields
    if (exchangeType === 'alpaca') {
        data.paper_trading = document.getElementById('exchangePaperTrading').checked;
    }
    if (exchangeType === 'mexc') {
        data.use_sub_account = document.getElementById('exchangeUseSubAccount').checked;
        data.sub_account_id = document.getElementById('exchangeSubAccountId').value;
    }
    if (exchangeType === 'ibkr' || exchangeType === 'bybit') {
        const leverage = document.getElementById('exchangeLeverage').value;
        data.leverage = leverage ? parseInt(leverage) : 1;
    }
    if (exchangeType === 'bybit') {
        const tradingModeSelect = document.getElementById('exchangeTradingMode');
        if (tradingModeSelect) data.trading_mode = tradingModeSelect.value || 'spot';
        const proxyEl = document.getElementById('exchangeProxy');
        if (proxyEl) data.proxy = proxyEl.value.trim();
    }
    if (exchangeType === 'ibkr') {
        if (exchange.account_id !== undefined) data.account_id = exchange.account_id || '';
        if (exchange.use_paper !== undefined) data.use_paper = exchange.use_paper || false;
    }

    
    // Don't send masked secret
    // Don't send '***' as the secret - it means "keep existing secret"
    const secretField = document.getElementById('exchangeApiSecret');
    if (data.api_secret === '***' || (data.api_secret === '' && secretField.dataset.hasSecret === 'true')) {
        // If field shows '***' or is empty but we had a secret, don't update it
        delete data.api_secret;
        console.log('Keeping existing API secret (not updating)');
    } else if (data.api_secret === '') {
        // If field is empty and we didn't have a secret, send empty to clear it
        console.log('Clearing API secret');
    } else {
        // New secret provided
        console.log('Updating API secret (new value provided)');
    }
    
    try {
        let response, result;
        if (parentAccountId) {
            // Creating an exchange under a logical account
            response = await fetch(`/api/accounts/${parentAccountId}/exchanges`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(Object.assign({ type: exchangeType }, data))
            });
            result = await response.json();
            if (response.ok && result.status === 'success') {
                showToast('Exchange account created successfully', 'success');
                closeModal();
                await loadDashboard();
                renderAccounts();
            } else {
                showToast(result.error || 'Failed to create exchange', 'error');
            }
        } else {
            response = await fetch(`/api/exchanges/${exchangeName}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            result = await response.json();
            if (result.status === 'success') {
                showToast('Exchange configuration saved successfully', 'success');
                closeModal();
                await loadDashboard();
            } else {
                showToast(result.error || 'Failed to save exchange', 'error');
            }
        }
    } catch (error) {
        console.error('Error saving exchange:', error);
        showToast('Error saving exchange', 'error');
    }
}

// Test connection
async function testConnection() {
    const exchangeName = document.getElementById('exchangeName').value;
    const parentAccountId = (document.getElementById('exchangeParentAccount') || {}).value || '';

    // Determine effective exchange type (for API endpoint)
    let exchangeType;
    if (!exchangeName && parentAccountId) {
        const typeEl = document.getElementById('newExchangeType');
        exchangeType = typeEl ? typeEl.value : 'bybit';
    } else {
        const exchange = (config.exchanges || {})[exchangeName] || {};
        exchangeType = (exchange.type || exchange.name || exchangeName).toLowerCase();
    }

    // Use exchangeName (may be a Mongo ID like bybit_1) for the API call so it can look up credentials
    const testTarget = exchangeName || exchangeType;

    const apiKey = (document.getElementById('exchangeApiKey').value || '').trim();
    const apiSecret = (document.getElementById('exchangeApiSecret').value || '').trim();
    const baseUrl = (document.getElementById('exchangeBaseUrl').value || '').trim();

    showToast('Testing connection...', 'success');

    try {
        const body = {};
        if (apiKey) body.api_key = apiKey;
        if (apiSecret && apiSecret !== '***') body.api_secret = apiSecret;
        if (baseUrl) body.base_url = baseUrl;
        if (exchangeType === 'ibkr') {
            const levEl = document.getElementById('exchangeLeverage');
            if (levEl) body.leverage = parseInt(levEl.value, 10) || 1;
        }
        if (exchangeType === 'bybit') {
            const modeEl = document.getElementById('exchangeTradingMode');
            const levEl = document.getElementById('exchangeLeverage');
            const proxyEl = document.getElementById('exchangeProxy');
            if (modeEl) body.trading_mode = modeEl.value;
            if (levEl) body.leverage = parseInt(levEl.value) || 1;
            if (proxyEl && proxyEl.value.trim()) body.proxy = proxyEl.value.trim();
        }

        const response = await fetch(`/api/test-connection/${testTarget}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const result = await response.json();
        if (result.status === 'success') {
            showToast('Connection successful!', 'success');
        } else {
            showToast(result.error || result.message || 'Connection failed', 'error');
        }
    } catch (error) {
        console.error('Error testing connection:', error);
        showToast('Error testing connection', 'error');
    }
}

// Save trading settings
async function saveTradingSettings() {
    const el = (id) => document.getElementById(id);
    const p = el('positionSizePercent'), f = el('positionSizeFixed'), u = el('usePercentage'), w = el('warnExistingPositions');
    const data = {
        position_size_percent: p ? p.value : 20,
        position_size_fixed: f ? f.value : '',
        use_percentage: u ? u.checked : true,
        warn_existing_positions: w ? w.checked : true
    };
    
    try {
        const response = await fetch('/api/trading-settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showToast('Trading settings saved successfully', 'success');
            loadDashboard();
        } else {
            showToast(result.error || 'Failed to save settings', 'error');
        }
    } catch (error) {
        console.error('Error saving trading settings:', error);
        showToast('Error saving trading settings', 'error');
    }
}

// Save risk management
async function saveRiskManagement() {
    const data = {
        stop_loss_percent: document.getElementById('stopLossPercent').value
        // TP levels are fixed - not configurable
    };
    
    try {
        const response = await fetch('/api/risk-management', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showToast('Risk management settings saved successfully', 'success');
            loadDashboard();
        } else {
            showToast(result.error || 'Failed to save settings', 'error');
        }
    } catch (error) {
        console.error('Error saving risk management:', error);
        showToast('Error saving risk management', 'error');
    }
}

// Update status
async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();
        config.status = status;
        updateStatusIndicator();
    } catch (error) {
        console.error('Error updating status:', error);
    }
}

// Update signal status
async function updateSignalStatus() {
    try {
        // Ping health endpoint to mark webhook as active (this helps show connection status)
        try {
            await fetch('/health');
        } catch (e) {
            // Ignore health check errors, webhook might still be working
        }
        
        const response = await fetch('/api/signals/status');
        const status = await response.json();
        
        // Update webhook connection status
        const connectionDot = document.getElementById('connectionDot');
        const statusText = document.getElementById('webhookStatusText');
        const webhookStatus = document.getElementById('webhookStatus');
        const lastSignalTime = document.getElementById('lastSignalTime');
        const timeSinceLast = document.getElementById('timeSinceLast');
        const totalSignals = document.getElementById('totalSignals');
        const successfulTrades = document.getElementById('successfulTrades');
        const failedTrades = document.getElementById('failedTrades');
        
        if (status.webhook_status === 'connected') {
            connectionDot.className = 'dot on pulse';
            statusText.textContent = 'Connected';
            webhookStatus.textContent = 'Connected';
            webhookStatus.className = 'signal-stat-value ok';
        } else {
            connectionDot.className = 'dot';
            if (status.total_signals === 0) {
                statusText.textContent = 'Waiting for signals';
                webhookStatus.textContent = 'Waiting for signals';
                webhookStatus.className = 'signal-stat-value';
            } else {
                statusText.textContent = 'Disconnected';
                webhookStatus.textContent = 'Disconnected';
                webhookStatus.className = 'signal-stat-value err';
            }
        }
        
        // Update last signal time
        if (status.last_signal_datetime) {
            const date = new Date(status.last_signal_datetime);
            lastSignalTime.textContent = date.toLocaleString();
            
            if (status.time_since_last_signal) {
                const seconds = Math.floor(status.time_since_last_signal);
                const minutes = Math.floor(seconds / 60);
                const hours = Math.floor(minutes / 60);
                
                if (hours > 0) {
                    timeSinceLast.textContent = `${hours}h ${minutes % 60}m ago`;
                } else if (minutes > 0) {
                    timeSinceLast.textContent = `${minutes}m ${seconds % 60}s ago`;
                } else {
                    timeSinceLast.textContent = `${seconds}s ago`;
                }
            }
        } else {
            lastSignalTime.textContent = 'Never';
            timeSinceLast.textContent = '-';
        }
        
        // Update statistics
        totalSignals.textContent = status.total_signals || 0;
        successfulTrades.textContent = status.successful_trades || 0;
        failedTrades.textContent = status.failed_trades || 0;
        
    } catch (error) {
        console.error('Error updating signal status:', error);
        const connectionDot = document.getElementById('connectionDot');
        const statusText = document.getElementById('webhookStatusText');
        if (connectionDot) connectionDot.className = 'dot';
        if (statusText) statusText.textContent = 'Disconnected';
    }
}

function escapeHtmlSignal(s) {
    if (s === undefined || s === null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

/** Plain-language category + full detail for Recent Signals table */
function buildSignalWhatHappenedCell(signal) {
    var err = (signal.error || '').trim();
    var inner = '';

    if (signal.executed) {
        inner = '<div class="signal-detail">' +
            '<span class="cat">Success</span>' +
            '<span class="msg ok">Order placed on exchange. Check your exchange for fills, positions, and balances.</span>' +
            '</div>';
        return '<td>' + inner + '</td>';
    }

    if (err) {
        var cat = 'Could not complete';
        var hint = '';
        var elower = err.toLowerCase();
        if (elower.indexOf('leverage') !== -1 && elower.indexOf('bybit') !== -1) {
            cat = 'Leverage blocked (Bybit)';
            hint = '<span class="hint">Usually: API key missing futures permissions, wrong margin mode (cross/isolated), or symbol not allowed at that leverage. Fix on Bybit, then retry.</span>';
        } else if (elower.indexOf('no position') !== -1 || elower.indexOf('balance to sell') !== -1) {
            cat = 'Nothing to sell';
            hint = '<span class="hint">No open position or free balance for this symbol when SELL ran — often after a failed BUY or already-closed trade.</span>';
        } else if (elower.indexOf('executor') !== -1 || elower.indexOf('no trading executor') !== -1) {
            cat = 'Bot not ready';
            hint = '<span class="hint">Enable the exchange, add API credentials or complete IBKR Gateway login, and ensure the symbol is in the allowed list.</span>';
        } else if (elower.indexOf('not configured for any enabled') !== -1 || (elower.indexOf('symbol') !== -1 && elower.indexOf('manage symbols') !== -1)) {
            cat = 'Symbol not routed';
            hint = '<span class="hint">Add this symbol in Exchanges → Manage Symbols (or Symbols &amp; Routing).</span>';
        } else if (elower.indexOf('validation failed') !== -1) {
            cat = 'Signal rejected';
            hint = '<span class="hint">Payload missing fields or strategy blocked the trade. Check your TradingView alert JSON.</span>';
        } else if (elower.indexOf('position size') !== -1 || elower.indexOf('balance') !== -1) {
            cat = 'Size or balance';
            hint = '<span class="hint">Position size was zero or wallet balance insufficient for the order.</span>';
        }
        inner = '<div class="signal-detail">' +
            '<span class="cat">' + escapeHtmlSignal(cat) + '</span>' +
            '<span class="msg err">' + escapeHtmlSignal(err) + '</span>' +
            hint +
            '</div>';
        return '<td>' + inner + '</td>';
    }

    inner = '<div class="signal-detail">' +
        '<span class="cat">Pending / unknown</span>' +
        '<span class="msg dim">No error stored. May still be processing. If status stays Pending, confirm exchange is connected and symbol is allowed.</span>' +
        '</div>';
    return '<td>' + inner + '</td>';
}

/** Raw list from API; filter/sort applied in renderRecentSignalsFromCache */
var recentSignalsCache = [];
var recentSignalsToolbarInited = false;
var recentSignalsSymbolFilterTimer = null;

function signalStatusBucket(signal) {
    if (signal.executed) return 'executed';
    if (signal.error) return 'failed';
    return 'pending';
}

function statusSortKey(signal) {
    if (signal.executed) return '3_executed';
    if (signal.error) return '1_failed';
    return '2_pending';
}

function readRecentSignalsFiltersFromSuffix(suffix) {
    var st = document.getElementById('recentSignalsFilterStatus' + suffix);
    var sg = document.getElementById('recentSignalsFilterSignal' + suffix);
    var sy = document.getElementById('recentSignalsFilterSymbol' + suffix);
    var so = document.getElementById('recentSignalsSort' + suffix);
    return {
        status: st ? st.value : 'all',
        signal: sg ? sg.value : 'all',
        symbol: sy ? sy.value.trim() : '',
        sort: so ? so.value : 'time_desc'
    };
}

function mirrorRecentSignalsToolbar(fromSuffix) {
    var other = fromSuffix === 'Overview' ? 'Activity' : 'Overview';
    var ids = ['recentSignalsFilterStatus', 'recentSignalsFilterSignal', 'recentSignalsSort'];
    ids.forEach(function(base) {
        var a = document.getElementById(base + fromSuffix);
        var b = document.getElementById(base + other);
        if (a && b) b.value = a.value;
    });
    var sa = document.getElementById('recentSignalsFilterSymbol' + fromSuffix);
    var sb = document.getElementById('recentSignalsFilterSymbol' + other);
    if (sa && sb) sb.value = sa.value;
}

function applyRecentSignalsFilters(list, f) {
    return list.filter(function(signal) {
        if (f.status !== 'all' && signalStatusBucket(signal) !== f.status) {
            return false;
        }
        if (f.signal !== 'all' && String(signal.signal || '').toUpperCase() !== f.signal) {
            return false;
        }
        if (f.symbol) {
            var sym = String(signal.symbol || '').toUpperCase();
            if (sym.indexOf(f.symbol.toUpperCase()) === -1) return false;
        }
        return true;
    });
}

function sortRecentSignalsList(list, sortKey) {
    var arr = list.slice();
    switch (sortKey) {
        case 'time_asc':
            arr.sort(function(a, b) { return (a.timestamp || 0) - (b.timestamp || 0); });
            break;
        case 'symbol_asc':
            arr.sort(function(a, b) {
                var c = String(a.symbol || '').localeCompare(String(b.symbol || ''), undefined, { sensitivity: 'base' });
                if (c !== 0) return c;
                return (b.timestamp || 0) - (a.timestamp || 0);
            });
            break;
        case 'symbol_desc':
            arr.sort(function(a, b) {
                var c = String(b.symbol || '').localeCompare(String(a.symbol || ''), undefined, { sensitivity: 'base' });
                if (c !== 0) return c;
                return (b.timestamp || 0) - (a.timestamp || 0);
            });
            break;
        case 'status_group':
            arr.sort(function(a, b) {
                var ka = statusSortKey(a);
                var kb = statusSortKey(b);
                if (ka !== kb) return ka < kb ? -1 : 1;
                return (b.timestamp || 0) - (a.timestamp || 0);
            });
            break;
        case 'time_desc':
        default:
            arr.sort(function(a, b) { return (b.timestamp || 0) - (a.timestamp || 0); });
            break;
    }
    return arr;
}

function buildRecentSignalRowHtml(signal) {
    var date = new Date(signal.datetime);
    var signalType = (signal.signal || '').toLowerCase();
    var statusSigClass = signal.executed ? 'ok' : (signal.error ? 'fail' : 'skip');
    var statusText = signal.executed ? 'Executed' : (signal.error ? 'Failed' : 'Pending');
    var priceStr = signal.price ? signal.price.toFixed(2) : '—';
    var statusHtml = '<span class="sig-badge ' + statusSigClass + '">' + statusText + '</span>';
    var whatCell = buildSignalWhatHappenedCell(signal);
    return '<tr><td>' + date.toLocaleTimeString() + '<br><span style="font-size:10px;opacity:.6">' + date.toLocaleDateString() + '</span></td><td><strong>' + escapeHtmlSignal(signal.symbol || '—') + '</strong></td><td><span class="sig-badge ' + signalType + '">' + escapeHtmlSignal(signal.signal || '—') + '</span></td><td>' + priceStr + '</td><td>' + statusHtml + '</td>' + whatCell + '</tr>';
}

function renderRecentSignalsFromCache() {
    var f = readRecentSignalsFiltersFromSuffix('Overview');

    var rowsHtml = null;
    var noSignals = recentSignalsCache.length === 0;

    if (!noSignals) {
        var filtered = applyRecentSignalsFilters(recentSignalsCache, f);
        var sorted = sortRecentSignalsList(filtered, f.sort);
        if (sorted.length > 0) rowsHtml = sorted.map(buildRecentSignalRowHtml).join('');
    }

    var tbodyOverview = document.getElementById('signalsTableBody');
    var tbodyActivity = document.getElementById('activitySignalsTableBody');

    if (tbodyOverview) {
        tbodyOverview.innerHTML = rowsHtml ||
            (noSignals
                ? '<tr><td colspan="6" class="no-signals">No signals received yet</td></tr>'
                : '<tr><td colspan="6" class="no-signals">No signals match your filters.</td></tr>');
    }
    if (tbodyActivity) {
        tbodyActivity.innerHTML = rowsHtml ||
            (noSignals
                ? '<tr><td colspan="6" class="no-data">No signals received yet</td></tr>'
                : '<tr><td colspan="6" class="no-data">No signals match your filters.</td></tr>');
    }
}

function initRecentSignalsToolbar() {
    if (recentSignalsToolbarInited) return;
    recentSignalsToolbarInited = true;
    function wire(suffix) {
        var st = document.getElementById('recentSignalsFilterStatus' + suffix);
        var sg = document.getElementById('recentSignalsFilterSignal' + suffix);
        var so = document.getElementById('recentSignalsSort' + suffix);
        var sy = document.getElementById('recentSignalsFilterSymbol' + suffix);
        var handler = function() {
            mirrorRecentSignalsToolbar(suffix);
            renderRecentSignalsFromCache();
        };
        if (st) st.addEventListener('change', handler);
        if (sg) sg.addEventListener('change', handler);
        if (so) so.addEventListener('change', handler);
        if (sy) {
            sy.addEventListener('input', function() {
                mirrorRecentSignalsToolbar(suffix);
                if (recentSignalsSymbolFilterTimer) clearTimeout(recentSignalsSymbolFilterTimer);
                recentSignalsSymbolFilterTimer = setTimeout(function() {
                    renderRecentSignalsFromCache();
                }, 200);
            });
        }
    }
    wire('Overview');
    wire('Activity');
}

// Update recent signals (from last 24 hours)
async function updateRecentSignals() {
    try {
        const response = await fetch('/api/signals/recent?limit=100&hours=24');
        const data = await response.json();
        recentSignalsCache = data.signals || [];
        const el = document.getElementById('statSignals24h');
        if (el) el.textContent = recentSignalsCache.length;
        initRecentSignalsToolbar();
        renderRecentSignalsFromCache();
    } catch (error) {
        console.error('Error updating recent signals:', error);
    }
}

// Show toast notification
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Close modal on outside click
window.onclick = function(event) {
    const modal = document.getElementById('exchangeModal');
    if (event.target === modal) {
        closeModal();
    }
}

// ===== Exchange Symbols Management =====

let currentSymbolsExchange = null;

function showMainSections(show) {
    const overview = document.getElementById('exchangesOverviewSection');
    const symbols = document.getElementById('exchangeSymbolsSection');
    if (overview) overview.style.display = show ? '' : 'none';
    if (symbols) symbols.style.display = show ? 'none' : 'block';
}

async function openSymbolsManager(exchangeName) {
    const exchange = config.exchanges[exchangeName];
    if (!exchange) {
        showToast('Exchange configuration not found', 'error');
        return;
    }
    
    currentSymbolsExchange = exchangeName;
    
    // Hide main dashboard sections and show symbols section
    const symbolsSection = document.getElementById('exchangeSymbolsSection');
    if (!symbolsSection) return;
    showMainSections(false);
    symbolsSection.style.display = 'block';
    
    // Set title
    const titleEl = document.getElementById('exchangeSymbolsTitle');
    if (titleEl) {
        titleEl.textContent = `Manage Symbols – ${exchange.name}`;
    }
    
    // Exchange info (environment, etc.)
    const infoEl = document.getElementById('exchangeSymbolsInfo');
    if (infoEl) {
        const isPaper = exchange.paper_trading === true;
        const isTestnet = exchange.testnet === true;
        let envText = '';
        if (isPaper) envText = 'Paper Trading';
        else if (isTestnet) envText = 'Testnet';
        else envText = 'Live';
        
        infoEl.innerHTML = `
            <div><strong>Exchange:</strong> ${exchange.name}</div>
            <div><strong>Environment:</strong> ${envText}</div>
            <div style="margin-top: 4px; font-size: 12px; color: var(--text-muted);">
                Only the symbols listed below will be traded on this exchange.
            </div>
        `;
    }
    
    // Load symbols from backend to ensure latest version
    try {
        const resp = await fetch(`/api/exchanges/${exchangeName}/symbols`);
        if (resp.ok) {
            const data = await resp.json();
            const symbols = Array.isArray(data.symbols) ? data.symbols : [];
            config.exchanges[exchangeName].symbols = symbols;
        }
    } catch (e) {
        console.error('Error loading exchange symbols:', e);
    }
    
    renderExchangeSymbols();
}

function closeSymbolsManager() {
    currentSymbolsExchange = null;
    const symbolsSection = document.getElementById('exchangeSymbolsSection');
    if (symbolsSection) {
        symbolsSection.style.display = 'none';
    }
    // Show main sections again (within Exchanges page)
    showMainSections(true);
}

function renderExchangeSymbols() {
    const tbody = document.getElementById('exchangeSymbolsTableBody');
    if (!tbody) return;
    if (!currentSymbolsExchange || !config.exchanges[currentSymbolsExchange]) {
        tbody.innerHTML = '<tr><td colspan="3" class="no-signals">No exchange selected</td></tr>';
        return;
    }
    
    const exchange = config.exchanges[currentSymbolsExchange];
    const symbols = Array.isArray(exchange.symbols) ? exchange.symbols : [];
    
    if (symbols.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="no-signals">No symbols configured yet</td></tr>';
        return;
    }
    
    tbody.innerHTML = symbols.map(sym => {
        return `
            <tr>
                <td><span class="symbol-badge">${escapeHtml(sym)}</span></td>
                <td><span class="badge badge-success">Active</span></td>
                <td>
                    <button class="btn btn-sm btn-danger" onclick="removeSymbolFromExchange('${escapeHtml(sym)}')">
                        <i class="fas fa-trash"></i> Remove
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

async function saveExchangeSymbols(symbols) {
    if (!currentSymbolsExchange) return;
    
    try {
        const resp = await fetch(`/api/exchanges/${currentSymbolsExchange}/symbols`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ symbols })
        });
        const result = await resp.json();
        if (resp.ok && result.status === 'success') {
            config.exchanges[currentSymbolsExchange].symbols = result.symbols || symbols;
            showToast(result.message || 'Symbols updated successfully', 'success');
            renderExchangeSymbols();
            renderExchanges();
            renderSymbolsRouting();
        } else {
            showToast(result.error || 'Failed to update symbols', 'error');
        }
    } catch (e) {
        console.error('Error saving exchange symbols:', e);
        showToast('Error updating symbols', 'error');
    }
}

// Symbol search - TradingView-style (search bar with market symbols dropdown)
let symbolSearchDebounceTimer = null;

function setupSymbolSearch() {
    const input = document.getElementById('exchangeSymbolInput');
    const dropdown = document.getElementById('symbolSearchDropdown');
    if (!input || !dropdown) return;

    input.addEventListener('input', function() {
        const q = (this.value || '').trim();
        clearTimeout(symbolSearchDebounceTimer);
        if (!currentSymbolsExchange) {
            dropdown.style.display = 'none';
            return;
        }
        if (q.length < 1) {
            dropdown.style.display = 'none';
            return;
        }
        symbolSearchDebounceTimer = setTimeout(() => searchMarketSymbols(q), 200);
    });

    input.addEventListener('focus', function() {
        const q = (this.value || '').trim();
        if (q.length >= 1 && currentSymbolsExchange) {
            searchMarketSymbols(q);
        }
    });

    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            const q = (this.value || '').trim();
            if (q && currentSymbolsExchange) {
                selectSymbolFromSearch(q);
                this.value = '';
                document.getElementById('symbolSearchDropdown').style.display = 'none';
            }
        }
    });

    document.addEventListener('click', function(e) {
        if (!input.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.style.display = 'none';
        }
    });
}

async function searchMarketSymbols(query) {
    const dropdown = document.getElementById('symbolSearchDropdown');
    if (!dropdown || !currentSymbolsExchange) return;

    try {
        const resp = await fetch(`/api/exchanges/${currentSymbolsExchange}/market-symbols?q=${encodeURIComponent(query)}`);
        if (!resp.ok) {
            dropdown.innerHTML = '<div class="symbol-dropdown-empty">Unable to load symbols</div>';
            dropdown.style.display = 'block';
            return;
        }
        const data = await resp.json();
        const symbols = Array.isArray(data.symbols) ? data.symbols : [];

        if (symbols.length === 0) {
            dropdown.innerHTML = '<div class="symbol-dropdown-empty">No matching symbols found</div>';
        } else {
            dropdown.innerHTML = symbols.map(sym => {
                const s = String(sym || '');
                const attrEscaped = s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                const textEscaped = s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                return `<div class="symbol-dropdown-item" data-symbol="${attrEscaped}">${textEscaped}</div>`;
            }).join('');
            dropdown.querySelectorAll('.symbol-dropdown-item').forEach(el => {
                el.addEventListener('click', () => selectSymbolFromSearch(el.dataset.symbol || ''));
            });
        }
        dropdown.style.display = 'block';
    } catch (e) {
        console.error('Symbol search error:', e);
        dropdown.innerHTML = '<div class="symbol-dropdown-empty">Error loading symbols</div>';
        dropdown.style.display = 'block';
    }
}

function selectSymbolFromSearch(symbol) {
    const input = document.getElementById('exchangeSymbolInput');
    const dropdown = document.getElementById('symbolSearchDropdown');
    if (input) input.value = '';
    if (dropdown) dropdown.style.display = 'none';

    if (!currentSymbolsExchange || !config.exchanges[currentSymbolsExchange]) {
        showToast('No exchange selected', 'error');
        return;
    }

    const sym = String(symbol).trim().toUpperCase().replace(/\s+/g, '');
    if (!sym) return;

    const exchange = config.exchanges[currentSymbolsExchange];
    const symbols = Array.isArray(exchange.symbols) ? [...exchange.symbols] : [];

    if (symbols.includes(sym)) {
        showToast('Symbol already added', 'error');
        return;
    }

    symbols.push(sym);
    saveExchangeSymbols(symbols);
    showToast(`Added ${sym}`, 'success');
}

function addSymbolToExchange() {
    const input = document.getElementById('exchangeSymbolInput');
    if (!input) return;
    const sym = (input.value || '').trim();
    if (!sym) {
        showToast('Search and select a symbol from the dropdown', 'error');
        return;
    }
    selectSymbolFromSearch(sym);
    input.value = '';
}

function removeSymbolFromExchange(symbol) {
    if (!currentSymbolsExchange || !config.exchanges[currentSymbolsExchange]) {
        showToast('No exchange selected', 'error');
        return;
    }
    const exchange = config.exchanges[currentSymbolsExchange];
    const symbols = Array.isArray(exchange.symbols) ? exchange.symbols.filter(s => s !== symbol) : [];
    saveExchangeSymbols(symbols);
}

// Render global Symbols & Routing overview table
function renderSymbolsRouting() {
    const tbody = document.getElementById('symbolsRoutingTableBody');
    if (!tbody || !config || !config.exchanges) return;

    const rows = [];

    for (const [name, exchange] of Object.entries(config.exchanges)) {
        const type = (exchange.type || exchange.name || name).toLowerCase();
        const abbr = _getExchangeTypeAbbr(type);
        const isPaper = exchange.paper_trading === true;
        const isTestnet = exchange.testnet === true;
        const envText = isPaper ? 'Paper' : isTestnet ? 'Testnet' : 'Live';

        const symbols = Array.isArray(exchange.symbols) ? exchange.symbols : [];
        if (symbols.length === 0) {
            rows.push(`<tr>
                <td>${escapeHtml(exchange.name || name)}</td>
                <td><span class="badge badge-${type}">${abbr}</span></td>
                <td>${envText}</td>
                <td style="color:var(--text-muted); font-style:italic;">None configured</td>
            </tr>`);
        } else {
            symbols.forEach((sym, idx) => {
                rows.push(`<tr>
                    <td>${idx === 0 ? escapeHtml(exchange.name || name) : ''}</td>
                    <td>${idx === 0 ? `<span class="badge badge-${type}">${abbr}</span>` : ''}</td>
                    <td>${idx === 0 ? envText : ''}</td>
                    <td><span class="symbol-badge">${escapeHtml(sym)}</span></td>
                </tr>`);
            });
        }
    }

    if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="no-data">No symbols configured yet</td></tr>';
    } else {
        tbody.innerHTML = rows.join('');
    }
}

// Update overview stat cards
function renderOverviewStats() {
    const accounts = window.AppState.accounts || [];
    const exchanges = config.exchanges || {};
    const total = Object.keys(exchanges).length;
    const enabled = Object.values(exchanges).filter(e => e.enabled !== false).length;
    const el = id => document.getElementById(id);
    if (el('statAccounts')) el('statAccounts').textContent = accounts.length;
    if (el('statExchanges')) el('statExchanges').textContent = total;
    if (el('statEnabled')) el('statEnabled').textContent = enabled;
}

