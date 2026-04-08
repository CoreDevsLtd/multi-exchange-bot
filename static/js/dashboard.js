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
                                <td><span class="signal-badge ${trade.side.toLowerCase()}">${trade.side}</span></td>
                                <td>$${trade.price.toFixed(2)}</td>
                                <td>${trade.quantity.toFixed(6)}</td>
                                <td>$${trade.amount.toFixed(2)}</td>
                                <td><span class="status-badge executed">${trade.status}</span></td>
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
                                <td><span class="signal-badge ${pos.side.toLowerCase()}">${pos.side}</span></td>
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

// Render accounts list (Mongo-backed)
async function renderAccounts() {
    try {
        const resp = await fetch('/api/accounts');
        const container = document.getElementById('accountsList');
        if (!container) return;
        if (!resp.ok) {
            container.innerHTML = '<div class="no-signals">Failed to load accounts</div>';
            return;
        }
        const data = await resp.json();
        const accounts = data.accounts || [];
        // update global client state
        window.AppState.accounts = accounts;
        if (accounts.length === 0) {
            container.innerHTML = '<div class="no-signals">No accounts found. Click "Create Account" to add one.</div>';
            return;
        }
        container.innerHTML = accounts.map(ac => {
            return `
                <div class="account-card" style="padding:12px; border-radius:6px; border:1px solid var(--border); margin-bottom:8px; background:var(--bg-tertiary);">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <div style="font-weight:600">${ac.name || ac._id}</div>
                            <div style="font-size:12px; color:var(--text-secondary)">ID: ${ac._id}</div>
                        </div>
                        <div style="display:flex; gap:8px; align-items:center">
                            <button class="btn btn-sm" onclick="viewAccountExchanges('${ac._id}')">View Exchanges</button>
                            <button class="btn btn-sm" onclick="openAccountModal('${ac._id}')">Edit</button>
                            <button class="btn btn-sm" onclick="toggleAccountEnabled('${ac._id}', ${ac.enabled ? 'false' : 'true'})">${ac.enabled ? 'Disable' : 'Enable'}</button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (e) {
        console.error('Error rendering accounts', e);
    }
}

// View exchanges for an account and open exchanges page
async function viewAccountExchanges(accountId) {
    try {
        const resp = await fetch(`/api/accounts/${accountId}/exchanges`);
        if (!resp.ok) return;
        const data = await resp.json();
        const exchanges = data.exchanges || [];
        // Switch to Exchanges page and populate the exchangesList with these entries
        showPage('exchanges');
        const list = document.getElementById('exchangesList');
        if (!list) return;
        list.innerHTML = exchanges.map(ex => {
            return `
                <div class="exchange-card" style="padding:10px; border-radius:6px; border:1px solid var(--border); margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <div style="font-weight:600">${ex.type} (${ex._id})</div>
                            <div style="font-size:12px; color:var(--text-secondary)">Symbols: ${(ex.symbols||[]).join(', ')}</div>
                        </div>
                        <div>
                            <button class="btn btn-sm" onclick="editExchange('${ex._id}')">Edit</button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (e) { console.error(e); }
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
                                    testnet: !!ex.testnet,
                                    trading_mode: ex.trading_mode || ex.trading_mode || 'spot',
                                    leverage: ex.leverage || 1,
                                    proxy: ex.proxy || '',
                                    symbols: ex.symbols || (ex.symbol ? [ex.symbol] : [])
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

// Render exchanges
async function renderExchanges() {
    const list = document.getElementById('exchangesList');
    list.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-muted);">Loading exchanges...</div>';
    
    // Ensure config.exchanges exists
    if (!config || !config.exchanges) {
        console.error('Config or exchanges not loaded');
        list.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--error);">Error: Exchanges configuration not loaded</div>';
        return;
    }
    
    console.log('Rendering exchanges:', Object.keys(config.exchanges));
    
    // Fetch exchange status (connection + balances)
    let exchangeStatus = {};
    try {
        const response = await fetch('/api/exchanges/status');
        if (response.ok) {
            exchangeStatus = await response.json();
        }
    } catch (error) {
        console.error('Error fetching exchange status:', error);
    }
    
    list.innerHTML = '';
    
    // Show all configured exchanges
    Object.entries(config.exchanges)
        .forEach(([key, exchange]) => {
            console.log(`Rendering exchange ${key}:`, {
                enabled: exchange.enabled,
                has_key: !!(exchange.api_key),
                has_secret: !!(exchange.api_secret)
            });
        const item = document.createElement('div');
        item.className = `exchange-item ${exchange.enabled ? 'enabled' : ''}`;
        
        const status = exchangeStatus[key] || {};
        const modeText = exchange.paper_trading !== undefined 
            ? (exchange.paper_trading ? 'Paper' : 'Live') 
            : (exchange.name === 'MEXC' ? 'Live' : '');
        
        // Connection status indicator (only show if connected, hide errors)
        let connectionStatus = '';
        if (status.connected) {
            connectionStatus = '<span style="color: var(--success); font-size: 10px;">● Connected</span>';
        } else {
            // Don't show error messages, just show "Not connected" if not connected
            connectionStatus = '<span style="color: var(--text-muted); font-size: 10px;">● Not connected</span>';
        }
        
        // Small summary of configured symbols for this exchange
        let symbolsSummary = '';
        const symbols = Array.isArray(exchange.symbols) ? exchange.symbols : [];
        if (symbols.length > 0) {
            const preview = symbols.slice(0, 3).join(', ');
            const moreCount = symbols.length - 3;
            const moreText = moreCount > 0 ? ` (+${moreCount} more)` : '';
            symbolsSummary = `<div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Symbols: ${preview}${moreText}</div>`;
        } else {
            symbolsSummary = `<div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">Symbols: None configured</div>`;
        }
        
        // Format balances - show all balances, not just > 0.01
        let balanceText = '';
        if (status.connected) {
            // Exchange is connected, check if balances were fetched
            if (status.balances !== undefined && status.balances !== null) {
                // Balances were fetched (even if empty)
                if (Object.keys(status.balances).length > 0) {
                    const balanceParts = [];
                    try {
                        for (const [asset, bal] of Object.entries(status.balances)) {
                            try {
                                // Handle different balance formats
                                let total = 0;
                                if (typeof bal === 'object' && bal !== null) {
                                    // Standard format: {free, locked, total}
                                    total = parseFloat(bal.total || bal.free || 0);
                                } else if (typeof bal === 'number') {
                                    // Direct number format
                                    total = parseFloat(bal);
                                } else if (typeof bal === 'string') {
                                    // String format
                                    total = parseFloat(bal) || 0;
                                }
                                
                                if (total > 0 && !isNaN(total)) {
                                    // Format with appropriate decimal places
                                    let formatted;
                                    if (total >= 1) {
                                        formatted = total.toFixed(2);
                                    } else if (total >= 0.01) {
                                        formatted = total.toFixed(4);
                                    } else {
                                        formatted = total.toFixed(8);
                                    }
                                    balanceParts.push(`${asset}: ${formatted}`);
                                }
                            } catch (e) {
                                console.error(`Error parsing balance for ${asset}:`, e, bal);
                                // Skip this balance and continue
                            }
                        }
                    } catch (e) {
                        console.error('Error processing balances:', e, status.balances);
                        balanceText = `<div style="font-size: 11px; color: var(--error); margin-top: 4px;">⚠️ Error loading balances</div>`;
                    }
                    if (balanceParts.length > 0) {
                        balanceText = `<div style="font-size: 11px; color: var(--text-secondary); margin-top: 4px; font-weight: 500;">💰 ${balanceParts.join(' • ')}</div>`;
                    } else {
                        // Connected but all balances are zero
                        balanceText = `<div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">💰 All balances: 0.00</div>`;
                    }
                } else {
                    // Connected but balances object is empty (no assets with balance)
                    balanceText = `<div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">💰 All balances: 0.00</div>`;
                }
                // MEXC: Show note about Spot-only balance (common cause of balance mismatch)
                if (key === 'mexc' && status.connected) {
                    balanceText += `<div style="font-size: 10px; color: var(--text-muted); margin-top: 2px;"><a href="https://www.mexc.com/user/transfer" target="_blank" rel="noopener" style="color: var(--accent);">Balance mismatch?</a> Bot shows Spot wallet only. Transfer from Fiat/Earn to Spot on MEXC.</div>`;
                }
            } else {
                // Connected but balances not fetched yet
                balanceText = `<div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Loading balances...</div>`;
            }
        }
        // If not connected, don't show balance text
        
        item.innerHTML = `
            <div class="exchange-item-left">
                <div>
                    <div class="exchange-name">${exchange.name}</div>
                    <div class="exchange-status">
                        ${exchange.enabled ? 'Enabled' : 'Disabled'} ${modeText ? '• ' + modeText : ''}
                        ${connectionStatus ? ' • ' + connectionStatus : ''}
                    </div>
                    ${balanceText}
                    ${symbolsSummary}
                </div>
            </div>
            <div class="exchange-item-right">
                <label class="exchange-toggle">
                    <input type="checkbox" ${exchange.enabled ? 'checked' : ''} 
                           onchange="toggleExchange('${key}', this.checked)">
                    <span class="exchange-toggle-slider"></span>
                </label>
                <div style="display: flex; gap: 6px;">
                    <button class="btn btn-sm" onclick="openExchangeModal('${key}')" title="Configure">
                        <i class="fas fa-cog"></i>
                    </button>
                    <button class="btn btn-sm" onclick="openSymbolsManager('${key}')" title="Manage Symbols">
                        <i class="fas fa-list"></i>
                    </button>
                </div>
            </div>
        `;
        list.appendChild(item);
    });
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
    
    const enabledExchanges = Object.values(config.exchanges).filter(e => e.enabled).length;
    
    if (enabledExchanges > 0) {
        statusDot.className = 'status-dot active';
        statusText.textContent = `${enabledExchanges} Exchange(s) Active`;
    } else {
        statusDot.className = 'status-dot inactive';
        statusText.textContent = 'No Exchanges Active';
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
    const modal = document.getElementById('exchangeModal');
    var credFields = document.querySelectorAll('.exchange-credential-field');
    var ibkrGw = document.getElementById('ibkrGatewayGroup');
    credFields.forEach(function(el) { el.style.display = 'block'; });
    if (ibkrGw) ibkrGw.style.display = 'none';
    
    document.getElementById('exchangeName').value = exchangeName;
    document.getElementById('modalTitle').textContent = `Configure ${exchange.name}`;
    document.getElementById('exchangeEnabled').checked = exchange.enabled || false;
    // Set API key (show actual value if saved)
    const apiKeyField = document.getElementById('exchangeApiKey');
    apiKeyField.value = exchange.api_key || '';
    console.log(`Loading exchange ${exchangeName}: API Key length = ${(exchange.api_key || '').length}`);
    
    // Set API secret (show '***' if secret exists, empty if not)
    const apiSecretField = document.getElementById('exchangeApiSecret');
    apiSecretField.value = (exchange.api_secret && exchange.api_secret !== '') ? '***' : '';
    // Store original secret status for later comparison
    apiSecretField.dataset.hasSecret = (exchange.api_secret && exchange.api_secret !== '') ? 'true' : 'false';
    console.log(`Loading exchange ${exchangeName}: API Secret present = ${apiSecretField.dataset.hasSecret}`);
    document.getElementById('exchangeBaseUrl').value = exchange.base_url || '';
    
    // Show paper trading option for Alpaca
    const paperTradingGroup = document.getElementById('paperTradingGroup');
    if (exchange.paper_trading !== undefined) {
        paperTradingGroup.style.display = 'block';
        document.getElementById('exchangePaperTrading').checked = exchange.paper_trading || false;
    } else {
        paperTradingGroup.style.display = 'none';
    }
    
    // Show sub-account option for MEXC
    const subAccountGroup = document.getElementById('subAccountGroup');
    const subAccountIdInput = document.getElementById('exchangeSubAccountId');
    const mexcWarning = document.getElementById('mexcWarning');
    
    // Trading mode + leverage (for exchanges that support it)
    const tradingModeGroup = document.getElementById('tradingModeGroup');
    const tradingModeSelect = document.getElementById('exchangeTradingMode');

    // Show leverage option for IBKR / futures-capable exchanges
    const leverageGroup = document.getElementById('leverageGroup');
    
    if (exchangeName === 'mexc') {
        subAccountGroup.style.display = 'block';
        const useSubAccountCheckbox = document.getElementById('exchangeUseSubAccount');
        useSubAccountCheckbox.checked = exchange.use_sub_account || false;
        subAccountIdInput.value = exchange.sub_account_id || '';
        
        // Show sub-account ID input when checkbox is checked
        const toggleSubAccountInput = function() {
            subAccountIdInput.style.display = useSubAccountCheckbox.checked ? 'block' : 'none';
        };
        useSubAccountCheckbox.addEventListener('change', toggleSubAccountInput);
        toggleSubAccountInput(); // Set initial state
        
        // Show MEXC real trading warning
        mexcWarning.style.display = 'block';
        // MEXC currently spot-only in this UI
        tradingModeGroup.style.display = 'none';
        leverageGroup.style.display = 'none';
    } else if (exchangeName === 'ibkr') {
        credFields.forEach(function(el) { el.style.display = 'none'; });
        if (ibkrGw) ibkrGw.style.display = 'block';
        var bu = document.getElementById('exchangeBaseUrl');
        bu.placeholder = 'https://localhost:5000';
        tradingModeGroup.style.display = 'none';
        leverageGroup.style.display = 'block';
        document.getElementById('exchangeLeverage').value = exchange.leverage || '1';
        subAccountGroup.style.display = 'none';
        mexcWarning.style.display = 'none';
    } else if (exchangeName === 'bybit') {
        tradingModeGroup.style.display = 'block';
        const mode = (exchange.trading_mode || 'spot').toLowerCase();
        tradingModeSelect.value = mode === 'futures' ? 'futures' : 'spot';

        leverageGroup.style.display = (tradingModeSelect.value === 'futures') ? 'block' : 'none';
        document.getElementById('exchangeLeverage').value = exchange.leverage || '1';

        document.getElementById('proxyGroup').style.display = 'block';
        document.getElementById('exchangeProxy').value = exchange.proxy || '';

        subAccountGroup.style.display = 'none';
        mexcWarning.style.display = 'none';

        tradingModeSelect.onchange = function() {
            leverageGroup.style.display = (tradingModeSelect.value === 'futures') ? 'block' : 'none';
        };
    } else {
        subAccountGroup.style.display = 'none';
        mexcWarning.style.display = 'none';
        tradingModeGroup.style.display = 'none';
        leverageGroup.style.display = 'none';
        document.getElementById('proxyGroup').style.display = 'none';
    }
    
    modal.classList.add('show');
}

// Close modal
function closeModal() {
    document.getElementById('exchangeModal').classList.remove('show');
}

// Save exchange
async function saveExchange() {
    const exchangeName = document.getElementById('exchangeName').value;
    const exchange = config.exchanges[exchangeName];
    
    const data = {
        enabled: document.getElementById('exchangeEnabled').checked,
        api_key: document.getElementById('exchangeApiKey').value.trim(),
        api_secret: document.getElementById('exchangeApiSecret').value.trim(),
        base_url: document.getElementById('exchangeBaseUrl').value
    };
    
    // Only include paper_trading if it exists for this exchange
    if (exchange.paper_trading !== undefined) {
        data.paper_trading = document.getElementById('exchangePaperTrading').checked;
    }
    
    // Include sub-account settings for MEXC
    if (exchangeName === 'mexc') {
        data.use_sub_account = document.getElementById('exchangeUseSubAccount').checked;
        data.sub_account_id = document.getElementById('exchangeSubAccountId').value;
    }
    
    // Include leverage for IBKR and futures-capable exchanges (e.g., Bybit)
    if (exchangeName === 'ibkr' || exchangeName === 'bybit') {
        const leverage = document.getElementById('exchangeLeverage').value;
        data.leverage = leverage ? parseInt(leverage) : 1;
    }

    // Include trading_mode and proxy for Bybit (spot / futures)
    if (exchangeName === 'bybit') {
        const tradingModeSelect = document.getElementById('exchangeTradingMode');
        if (tradingModeSelect) {
            data.trading_mode = tradingModeSelect.value || 'spot';
        }
        const proxyEl = document.getElementById('exchangeProxy');
        if (proxyEl) {
            data.proxy = proxyEl.value.trim();
        }
    }

    // Include account_id and use_paper for IBKR
    if (exchangeName === 'ibkr') {
        if (exchange.account_id !== undefined) {
            data.account_id = exchange.account_id || '';
        }
        if (exchange.use_paper !== undefined) {
            data.use_paper = exchange.use_paper || false;
        }
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
        const response = await fetch(`/api/exchanges/${exchangeName}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showToast('Exchange configuration saved successfully', 'success');
            closeModal();
            loadDashboard();
        } else {
            showToast(result.error || 'Failed to save exchange', 'error');
        }
    } catch (error) {
        console.error('Error saving exchange:', error);
        showToast('Error saving exchange', 'error');
    }
}

// Test connection
async function testConnection() {
    const exchangeName = document.getElementById('exchangeName').value;
    var apiKeyEl = document.getElementById('exchangeApiKey');
    var apiSecretEl = document.getElementById('exchangeApiSecret');
    var baseUrlEl = document.getElementById('exchangeBaseUrl');
    const apiKey = (apiKeyEl && apiKeyEl.value ? apiKeyEl.value : '').trim();
    const apiSecret = (apiSecretEl && apiSecretEl.value ? apiSecretEl.value : '').trim();
    const baseUrl = (baseUrlEl && baseUrlEl.value ? baseUrlEl.value : '').trim();
    
    showToast('Testing connection...', 'success');
    
    try {
        const body = {};
        if (apiKey) body.api_key = apiKey;
        if (apiSecret && apiSecret !== '***') body.api_secret = apiSecret;
        if (baseUrl) body.base_url = baseUrl;
        if (exchangeName === 'ibkr') {
            var levIbkr = document.getElementById('exchangeLeverage');
            if (levIbkr) body.leverage = parseInt(levIbkr.value, 10) || 1;
        }
        if (exchangeName === 'bybit') {
            const modeEl = document.getElementById('exchangeTradingMode');
            const levEl = document.getElementById('exchangeLeverage');
            const proxyEl = document.getElementById('exchangeProxy');
            if (modeEl) body.trading_mode = modeEl.value;
            if (levEl) body.leverage = parseInt(levEl.value) || 1;
            if (proxyEl && proxyEl.value.trim()) body.proxy = proxyEl.value.trim();
        }
        
        const response = await fetch(`/api/test-connection/${exchangeName}`, {
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
        const connectionDot = document.querySelector('#webhookConnectionIndicator .connection-dot');
        const statusText = document.getElementById('webhookStatusText');
        const webhookStatus = document.getElementById('webhookStatus');
        const lastSignalTime = document.getElementById('lastSignalTime');
        const timeSinceLast = document.getElementById('timeSinceLast');
        const totalSignals = document.getElementById('totalSignals');
        const successfulTrades = document.getElementById('successfulTrades');
        const failedTrades = document.getElementById('failedTrades');
        
        if (status.webhook_status === 'connected') {
            connectionDot.className = 'connection-dot connected';
            statusText.textContent = 'Connected';
            webhookStatus.textContent = 'Connected';
            webhookStatus.className = 'status-value success';
        } else {
            // Show "Waiting for signals" if no signals received yet (webhook is ready, just waiting)
            connectionDot.className = 'connection-dot disconnected';
            if (status.total_signals === 0) {
                statusText.textContent = 'Waiting for signals';
                webhookStatus.textContent = 'Waiting for signals';
                webhookStatus.className = 'status-value';
            } else {
                statusText.textContent = 'Disconnected';
                webhookStatus.textContent = 'Disconnected';
                webhookStatus.className = 'status-value error';
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
        // Mark as disconnected on error
        const connectionDot = document.querySelector('#webhookConnectionIndicator .connection-dot');
        const statusText = document.getElementById('webhookStatusText');
        if (connectionDot) {
            connectionDot.className = 'connection-dot disconnected';
            statusText.textContent = 'Disconnected';
        }
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
        inner = '<div class="signal-reason-category">Success</div>' +
            '<div class="signal-reason-detail success">The bot placed the order on at least one connected exchange and reported success. Check your exchange for fills, positions, and balances.</div>';
        return '<td class="signal-what-happened"><div class="signal-what-happened-inner">' + inner + '</div></td>';
    }

    if (err) {
        var cat = 'Could not complete';
        var hint = '';
        var elower = err.toLowerCase();
        if (elower.indexOf('leverage') !== -1 && elower.indexOf('bybit') !== -1) {
            cat = 'Leverage blocked (Bybit)';
            hint = '<div class="signal-reason-detail hint">Usually: API key missing futures permissions, wrong margin mode (cross/isolated), or symbol not allowed at that leverage. Fix on Bybit, then try again.</div>';
        } else if (elower.indexOf('no position') !== -1 || elower.indexOf('balance to sell') !== -1) {
            cat = 'Nothing to sell';
            hint = '<div class="signal-reason-detail hint">There was no open position (or free balance) for this symbol on the exchange when the SELL ran—often after a failed BUY or if you already closed the trade.</div>';
        } else if (elower.indexOf('executor') !== -1 || elower.indexOf('no trading executor') !== -1) {
            cat = 'Bot not ready';
            hint = '<div class="signal-reason-detail hint">Enable the exchange, add API credentials or complete IBKR Gateway login, and ensure the symbol is in the allowed list.</div>';
        } else if (elower.indexOf('not configured for any enabled') !== -1 || elower.indexOf('symbol') !== -1 && elower.indexOf('manage symbols') !== -1) {
            cat = 'Symbol not routed';
            hint = '<div class="signal-reason-detail hint">Add this symbol to the exchange in Exchanges → Manage Symbols (or global Symbols &amp; Routing).</div>';
        } else if (elower.indexOf('validation failed') !== -1) {
            cat = 'Signal rejected';
            hint = '<div class="signal-reason-detail hint">Payload missing fields or strategy blocked the trade. Check your TradingView alert JSON.</div>';
        } else if (elower.indexOf('position size') !== -1 || elower.indexOf('balance') !== -1) {
            cat = 'Size or balance';
            hint = '<div class="signal-reason-detail hint">Position size was zero or wallet balance is insufficient for the order.</div>';
        }
        inner = '<div class="signal-reason-category">' + escapeHtmlSignal(cat) + '</div>' +
            '<div class="signal-reason-detail error">' + escapeHtmlSignal(err) + '</div>' + hint;
        return '<td class="signal-what-happened"><div class="signal-what-happened-inner">' + inner + '</div></td>';
    }

    inner = '<div class="signal-reason-category">Pending / unknown</div>' +
        '<div class="signal-reason-detail muted">No error was stored for this row. It may still be processing, or the webhook only logged the signal. If status stays Pending, confirm the exchange is connected and this symbol is allowed.</div>';
    return '<td class="signal-what-happened"><div class="signal-what-happened-inner">' + inner + '</div></td>';
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
    var statusClass = signal.executed ? 'executed' : (signal.error ? 'failed' : 'pending');
    var statusText = signal.executed ? 'Executed' : (signal.error ? 'Failed' : 'Pending');
    var priceStr = signal.price ? signal.price.toFixed(2) : '-';
    var titleErr = (signal.error || '').replace(/"/g, '&quot;');
    var statusHtml = '<span class="status-badge ' + statusClass + '"' + (titleErr ? ' title="' + titleErr + '"' : '') + '>' + statusText + '</span>';
    var whatCell = buildSignalWhatHappenedCell(signal);
    return '<tr><td>' + date.toLocaleString() + '</td><td>' + (signal.symbol || '-') + '</td><td><span class="signal-badge ' + signalType + '">' + signal.signal + '</span></td><td>' + priceStr + '</td><td>' + statusHtml + '</td>' + whatCell + '</tr>';
}

function renderRecentSignalsFromCache() {
    var f = readRecentSignalsFiltersFromSuffix('Overview');

    var rowsHtml;
    if (recentSignalsCache.length === 0) {
        rowsHtml = '<tr><td colspan="6" class="no-signals">No signals received yet</td></tr>';
    } else {
        var filtered = applyRecentSignalsFilters(recentSignalsCache, f);
        var sorted = sortRecentSignalsList(filtered, f.sort);
        if (sorted.length === 0) {
            rowsHtml = '<tr><td colspan="6" class="no-signals">No signals match your filters. Set Status to All or clear the symbol box.</td></tr>';
        } else {
            rowsHtml = sorted.map(buildRecentSignalRowHtml).join('');
        }
    }

    var tbodyOverview = document.getElementById('signalsTableBody');
    var tbodyActivity = document.getElementById('activitySignalsTableBody');
    if (tbodyOverview) tbodyOverview.innerHTML = rowsHtml;
    if (tbodyActivity) tbodyActivity.innerHTML = rowsHtml;
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
    const main = document.querySelector('.dashboard-main');
    if (!main) return;
    const sections = main.querySelectorAll('.dashboard-section');
    sections.forEach(section => {
        // Keep symbols section control separate
        if (section.id === 'exchangeSymbolsSection') {
            section.style.display = show ? 'none' : 'block';
        } else {
            section.style.display = show ? '' : 'none';
        }
    });
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
                <td>${sym}</td>
                <td><span class="status-badge executed">Active</span></td>
                <td>
                    <button class="btn btn-sm" onclick="removeSymbolFromExchange('${sym}')">
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
            dropdown.innerHTML = '<div class="symbol-search-dropdown-empty">Unable to load symbols</div>';
            dropdown.style.display = 'block';
            return;
        }
        const data = await resp.json();
        const symbols = Array.isArray(data.symbols) ? data.symbols : [];

        if (symbols.length === 0) {
            dropdown.innerHTML = '<div class="symbol-search-dropdown-empty">No matching symbols found</div>';
        } else {
            dropdown.innerHTML = symbols.map(sym => {
                const s = String(sym || '');
                const attrEscaped = s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                const textEscaped = s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                return `<div class="symbol-search-dropdown-item" data-symbol="${attrEscaped}">${textEscaped}</div>`;
            }).join('');
            dropdown.querySelectorAll('.symbol-search-dropdown-item').forEach(el => {
                el.addEventListener('click', () => selectSymbolFromSearch(el.dataset.symbol || ''));
            });
        }
        dropdown.style.display = 'block';
    } catch (e) {
        console.error('Symbol search error:', e);
        dropdown.innerHTML = '<div class="symbol-search-dropdown-empty">Error loading symbols</div>';
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
        const isPaper = exchange.paper_trading === true;
        const isTestnet = exchange.testnet === true;
        let envText = '';
        if (isPaper) envText = 'Paper';
        else if (isTestnet) envText = 'Testnet';
        else envText = 'Live';

        const symbols = Array.isArray(exchange.symbols) ? exchange.symbols : [];
        if (symbols.length === 0) {
            rows.push(`
                <tr>
                    <td>${exchange.name}</td>
                    <td>${envText}</td>
                    <td style="color: var(--text-muted); font-style: italic;">None configured</td>
                </tr>
            `);
        } else {
            symbols.forEach((sym, idx) => {
                rows.push(`
                    <tr>
                        <td>${idx === 0 ? exchange.name : ''}</td>
                        <td>${idx === 0 ? envText : ''}</td>
                        <td>${sym}</td>
                    </tr>
                `);
            });
        }
    }

    if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="no-signals">No symbols configured yet</td></tr>';
    } else {
        tbody.innerHTML = rows.join('');
    }
}

