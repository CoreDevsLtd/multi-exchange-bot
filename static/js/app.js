/**
 * Trading Bot Dashboard - Vue 3 SPA
 * Self-hosted Vue, no build process, clean state management
 */

const { createApp, ref, reactive, computed, watch, onMounted, onUnmounted } = Vue;

// ============================================================================
// GLOBAL STORE & API
// ============================================================================

const store = reactive({
  currentPage: 'overview',
  currentAccountId: null,
  accounts: [],
  exchanges: {},
  exchangeStatus: {},
  tradingSettings: {},
  riskManagement: {},
  signals: [],
  status: {},
  loading: false,
  toast: { message: '', type: '', visible: false, timeout: null }
});

const api = {
  async loadAccounts() {
    try {
      const resp = await fetch('/api/accounts');
      const data = await resp.json();
      store.accounts = data.accounts || [];
      return data;
    } catch (e) {
      console.error('Error loading accounts:', e);
      showToast('Failed to load accounts', 'error');
    }
  },

  async loadExchangesForAccount(accountId) {
    try {
      const resp = await fetch(`/api/accounts/${accountId}/exchanges`);
      const data = await resp.json();
      const exchanges = data.exchanges || [];
      exchanges.forEach(ex => {
        store.exchanges[ex._id] = ex;
      });
      return exchanges;
    } catch (e) {
      console.error('Error loading exchanges for account:', e);
      showToast('Failed to load exchanges', 'error');
    }
  },

  async loadAllExchanges() {
    try {
      const resp = await fetch('/api/exchanges');
      const data = await resp.json();
      store.exchanges = data;
      return data;
    } catch (e) {
      console.error('Error loading all exchanges:', e);
    }
  },

  async loadTradingSettings() {
    try {
      const resp = await fetch('/api/trading-settings');
      const data = await resp.json();
      store.tradingSettings = data || {};
      return data;
    } catch (e) {
      console.error('Error loading trading settings:', e);
    }
  },

  async loadRiskManagement() {
    try {
      const resp = await fetch('/api/risk-management');
      const data = await resp.json();
      store.riskManagement = data || {};
      return data;
    } catch (e) {
      console.error('Error loading risk management:', e);
    }
  },

  async loadSignals() {
    try {
      const resp = await fetch('/api/signals/recent?limit=100&hours=24');
      const data = await resp.json();
      store.signals = data.signals || [];
      return data;
    } catch (e) {
      console.error('Error loading signals:', e);
    }
  },

  async loadStatus() {
    try {
      const resp = await fetch('/api/status');
      const data = await resp.json();
      store.status = data || {};
      return data;
    } catch (e) {
      console.error('Error loading status:', e);
    }
  },

  async loadExchangeStatus() {
    try {
      const resp = await fetch('/api/exchanges/status');
      const data = await resp.json();
      store.exchangeStatus = data || {};
      return data;
    } catch (e) {
      console.error('Error loading exchange status:', e);
    }
  },

  async saveAccount(data) {
    try {
      const resp = await fetch('/api/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      const result = await resp.json();
      if (result.status === 'success') {
        await api.loadAccounts();
        showToast('Account saved', 'success');
        return result;
      } else {
        showToast(result.error || 'Failed to save account', 'error');
      }
    } catch (e) {
      console.error('Error saving account:', e);
      showToast('Error saving account', 'error');
    }
  },

  async deleteAccount(accountId) {
    try {
      const resp = await fetch(`/api/accounts/${accountId}`, { method: 'DELETE' });
      const result = await resp.json();
      if (result.status === 'success') {
        store.accounts = store.accounts.filter(a => a._id !== accountId);
        // Clean up exchanges for this account
        Object.keys(store.exchanges).forEach(exId => {
          if (store.exchanges[exId].account_id === accountId) {
            delete store.exchanges[exId];
          }
        });
        showToast('Account deleted', 'success');
        return result;
      } else {
        showToast(result.error || 'Failed to delete account', 'error');
      }
    } catch (e) {
      console.error('Error deleting account:', e);
      showToast('Error deleting account', 'error');
    }
  },

  async toggleExchange(exchangeId, enabled) {
    try {
      const resp = await fetch(`/api/exchanges/${exchangeId}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      const result = await resp.json();
      if (result.status === 'success' && store.exchanges[exchangeId]) {
        store.exchanges[exchangeId].enabled = enabled;
        showToast(enabled ? 'Exchange enabled' : 'Exchange disabled', 'success');
        return result;
      }
    } catch (e) {
      console.error('Error toggling exchange:', e);
      showToast('Error toggling exchange', 'error');
    }
  },

  async saveExchange(exchangeId, data) {
    try {
      const resp = await fetch(`/api/accounts/${data.account_id}/exchanges`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...data, _id: exchangeId })
      });
      const result = await resp.json();
      if (result.status === 'success') {
        await api.loadExchangesForAccount(data.account_id);
        showToast('Exchange saved', 'success');
        return result;
      } else {
        showToast(result.error || 'Failed to save exchange', 'error');
      }
    } catch (e) {
      console.error('Error saving exchange:', e);
      showToast('Error saving exchange', 'error');
    }
  },

  async testConnection(exchangeId, body) {
    try {
      const resp = await fetch(`/api/test-connection/${exchangeId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const result = await resp.json();
      if (result.status === 'success') {
        showToast('Connection successful!', 'success');
      } else {
        showToast(result.error || result.message || 'Connection failed', 'error');
      }
      return result;
    } catch (e) {
      console.error('Error testing connection:', e);
      showToast('Error testing connection', 'error');
    }
  },

  async saveSymbols(exchangeId, symbols) {
    try {
      const resp = await fetch(`/api/exchanges/${exchangeId}/symbols`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbols })
      });
      const result = await resp.json();
      if (result.status === 'success') {
        if (store.exchanges[exchangeId]) {
          store.exchanges[exchangeId].symbols = result.symbols || symbols;
        }
        showToast('Symbols saved', 'success');
        return result;
      }
    } catch (e) {
      console.error('Error saving symbols:', e);
      showToast('Error saving symbols', 'error');
    }
  },

  async searchMarketSymbols(exchangeId, q) {
    try {
      const resp = await fetch(`/api/exchanges/${exchangeId}/market-symbols?q=${encodeURIComponent(q)}`);
      const data = await resp.json();
      return data.symbols || [];
    } catch (e) {
      console.error('Error searching symbols:', e);
      return [];
    }
  },

  async saveTradingSettings(settings) {
    try {
      const resp = await fetch('/api/trading-settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      const result = await resp.json();
      if (result.status === 'success') {
        store.tradingSettings = settings;
        showToast('Trading settings saved', 'success');
      }
      return result;
    } catch (e) {
      console.error('Error saving trading settings:', e);
      showToast('Error saving trading settings', 'error');
    }
  },

  async saveRiskManagement(settings) {
    try {
      const resp = await fetch('/api/risk-management', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      const result = await resp.json();
      if (result.status === 'success') {
        store.riskManagement = settings;
        showToast('Risk management saved', 'success');
      }
      return result;
    } catch (e) {
      console.error('Error saving risk management:', e);
      showToast('Error saving risk management', 'error');
    }
  }
};

// ============================================================================
// ROUTER
// ============================================================================

// Map page names to URL paths and vice versa
function pageToPath(page, accountId = null) {
  if (page === 'overview') return '/';
  if (page === 'accounts') return '/accounts';
  if (page === 'exchanges' && accountId) return `/exchanges/${encodeURIComponent(accountId)}`;
  if (page === 'symbolsRouting') return '/symbols-routing';
  if (page === 'tradingSettings') return '/trading-settings';
  if (page === 'risk') return '/risk-management';
  if (page === 'activity') return '/activity';
  return '/';
}

function pathToPage(pathname) {
  pathname = pathname || '/';
  if (pathname === '/') return { page: 'overview', accountId: null };
  if (pathname === '/accounts') return { page: 'accounts', accountId: null };
  if (pathname.startsWith('/exchanges/')) {
    const accountId = decodeURIComponent(pathname.split('/')[2]);
    return { page: 'exchanges', accountId };
  }
  if (pathname === '/symbols-routing') return { page: 'symbolsRouting', accountId: null };
  if (pathname === '/trading-settings') return { page: 'tradingSettings', accountId: null };
  if (pathname === '/risk-management') return { page: 'risk', accountId: null };
  if (pathname === '/activity') return { page: 'activity', accountId: null };
  return { page: 'overview', accountId: null };
}

function pushRoute(page, accountId = null) {
  store.currentPage = page;
  store.currentAccountId = accountId;
  const url = pageToPath(page, accountId);
  history.pushState({ page, accountId }, '', url);
}

function restoreFromURL() {
  return pathToPage(location.pathname);
}

window.addEventListener('popstate', async (event) => {
  const state = event.state || {};
  const page = state.page || 'overview';
  const accountId = state.accountId || null;
  store.currentPage = page;
  store.currentAccountId = accountId;
  if (page === 'exchanges' && accountId) {
    await api.loadExchangesForAccount(accountId);
  }
});

// ============================================================================
// UTILITIES
// ============================================================================

function escapeHtml(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function showToast(message, type = 'info') {
  store.toast.message = message;
  store.toast.type = type;
  store.toast.visible = true;
  if (store.toast.timeout) clearTimeout(store.toast.timeout);
  store.toast.timeout = setTimeout(() => {
    store.toast.visible = false;
  }, 4000);
}

function getExchangeTypeAbbr(type) {
  const t = (type || '').toLowerCase();
  if (t === 'bybit') return 'BY';
  if (t === 'mexc') return 'MX';
  if (t === 'alpaca') return 'AL';
  if (t === 'ibkr') return 'IB';
  return (type || '?').substring(0, 2).toUpperCase();
}

function formatTime(isoString) {
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  return date.toLocaleString();
}

// ============================================================================
// MIXIN (for all components)
// ============================================================================

const componentMixin = {
  methods: {
    formatTime,
    escapeHtml,
    showToast,
    pushRoute,
    getExchangeTypeAbbr
  },
  data() {
    return { store, api };
  }
};

// ============================================================================
// REUSABLE COMPONENTS
// ============================================================================

const ExchangeTypeIcon = {
  props: ['type'],
  template: `<div :class="['exchange-type-icon', type]">{{ abbr }}</div>`,
  computed: {
    abbr() { return getExchangeTypeAbbr(this.type); }
  }
};

const StatCard = {
  props: ['label', 'value', 'sub', 'variant'],
  template: `<div :class="['stat-card', variant]"><div class="stat-card-label">{{ label }}</div><div class="stat-card-value">{{ value }}</div><div class="stat-card-sub">{{ sub }}</div></div>`
};

const Badge = {
  props: ['text', 'variant'],
  template: `<span :class="['badge', 'badge-' + variant]">{{ text }}</span>`
};

const Toggle = {
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: `
    <label class="toggle">
      <input type="checkbox" :checked="modelValue" @change="$emit('update:modelValue', $event.target.checked)">
      <span class="toggle-track"></span>
    </label>
  `
};

// ============================================================================
// MODALS
// ============================================================================

const AccountModal = {
  data() {
    return {
      visible: false,
      isEdit: false,
      form: { _id: '', name: '', enabled: true }
    };
  },
  provide() {
    return { accountModal: this };
  },
  template: `
    <div v-if="visible" class="modal">
      <div class="modal-content" style="max-width: 500px;">
        <div class="modal-header">
          <h3><i class="fas fa-user"></i> {{ isEdit ? 'Edit' : 'Create' }} Account</h3>
          <button class="modal-close" @click="close()">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>Account Name</label>
            <input v-model="form.name" type="text" placeholder="e.g. Main Account">
          </div>
          <div class="form-group">
            <label class="with-check">
              <input v-model="form.enabled" type="checkbox">
              Enabled
            </label>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn" @click="close()">Cancel</button>
          <button class="btn btn-primary" @click="save()">Save</button>
        </div>
      </div>
    </div>
  `,
  methods: {
    open(account = null) {
      this.isEdit = !!account;
      if (account) {
        this.form = { ...account };
      } else {
        this.form = { _id: '', name: '', enabled: true };
      }
      this.visible = true;
    },
    close() {
      this.visible = false;
    },
    async save() {
      if (!this.form.name.trim()) {
        showToast('Please enter account name', 'error');
        return;
      }
      const data = { name: this.form.name, enabled: this.form.enabled };
      if (this.form._id) data._id = this.form._id;
      await api.saveAccount(data);
      this.close();
    }
  }
};

const ExchangeModal = {
  data() {
    return {
      visible: false,
      exchangeId: null,
      accountId: null,
      type: 'bybit',
      form: {
        enabled: false,
        api_key: '',
        api_secret: '',
        base_url: '',
        trading_mode: 'spot',
        leverage: 1,
        testnet: false,
        paper_trading: false,
        sub_account_id: '',
        use_sub_account: false,
        proxy: ''
      },
      testingConnection: false,
      testResult: null
    };
  },
  provide() {
    return { exchangeModal: this };
  },
  template: `
    <div v-if="visible" class="modal">
      <div class="modal-content" style="max-width: 600px;">
        <div class="modal-header">
          <h3><i class="fas fa-cog"></i> Configure {{ type.toUpperCase() }}</h3>
          <button class="modal-close" @click="close()">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="with-check">
              <input v-model="form.enabled" type="checkbox">
              Enable Exchange
            </label>
          </div>

          <!-- API Credentials (hidden for IBKR) -->
          <template v-if="type !== 'ibkr'">
            <div class="form-group">
              <label>API Key</label>
              <input v-model="form.api_key" type="text" placeholder="API Key">
            </div>
            <div class="form-group">
              <label>API Secret</label>
              <input v-model="form.api_secret" type="password" placeholder="API Secret">
            </div>
            <div class="form-group">
              <label>Base URL</label>
              <input v-model="form.base_url" type="text" :placeholder="getBaseUrlPlaceholder()">
            </div>
          </template>

          <!-- Bybit specific -->
          <template v-if="type === 'bybit'">
            <div class="form-group">
              <label>Trading Mode</label>
              <select v-model="form.trading_mode">
                <option value="spot">Spot</option>
                <option value="futures">Futures</option>
              </select>
            </div>
            <div v-if="form.trading_mode === 'futures'" class="form-group">
              <label>Leverage</label>
              <input v-model.number="form.leverage" type="number" min="1" max="100">
            </div>
            <div class="form-group">
              <label>Proxy URL (optional)</label>
              <input v-model="form.proxy" type="text" placeholder="http://proxy:port">
            </div>
          </template>

          <!-- MEXC specific -->
          <template v-if="type === 'mexc'">
            <div class="form-group">
              <label class="with-check">
                <input v-model="form.use_sub_account" type="checkbox">
                Use Sub-Account
              </label>
            </div>
            <div v-if="form.use_sub_account" class="form-group">
              <label>Sub-Account ID</label>
              <input v-model="form.sub_account_id" type="text" placeholder="Sub-account ID">
            </div>
            <div class="alert alert-warning">
              <i class="fas fa-exclamation-triangle"></i> Sub-account feature requires additional configuration.
            </div>
          </template>

          <!-- Alpaca specific -->
          <template v-if="type === 'alpaca'">
            <div class="form-group">
              <label class="with-check">
                <input v-model="form.paper_trading" type="checkbox">
                Paper Trading (Demo)
              </label>
            </div>
          </template>

          <!-- IBKR specific -->
          <template v-if="type === 'ibkr'">
            <div class="form-group">
              <label>Gateway Base URL</label>
              <input v-model="form.base_url" type="text" placeholder="https://localhost:5000">
            </div>
            <div class="form-group">
              <label>Leverage</label>
              <input v-model.number="form.leverage" type="number" min="1" max="100">
            </div>
            <button class="btn btn-ghost" @click="openIBKRGateway()">
              <i class="fas fa-external-link-alt"></i> Open Gateway Login
            </button>
          </template>

          <!-- Test Result -->
          <div v-if="testResult" :class="['alert', testResult.status === 'success' ? 'alert-info' : 'alert-error']">
            {{ testResult.message }}
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-ghost" @click="testConnection()" :disabled="testingConnection">
            <i class="fas fa-plug"></i> {{ testingConnection ? 'Testing...' : 'Test' }}
          </button>
          <button class="btn" @click="close()">Cancel</button>
          <button class="btn btn-primary" @click="save()">Save</button>
        </div>
      </div>
    </div>
  `,
  methods: {
    open(exchange, account) {
      this.exchangeId = exchange._id;
      this.accountId = account._id;
      this.type = exchange.type;
      this.form = {
        enabled: exchange.enabled || false,
        api_key: exchange.credentials?.api_key || '',
        api_secret: exchange.credentials?.api_secret ? '***' : '',
        base_url: exchange.base_url || '',
        trading_mode: exchange.trading_mode || 'spot',
        leverage: exchange.leverage || 1,
        testnet: exchange.testnet || false,
        paper_trading: exchange.paper_trading || false,
        sub_account_id: exchange.sub_account_id || '',
        use_sub_account: exchange.use_sub_account || false,
        proxy: exchange.proxy || ''
      };
      this.testResult = null;
      this.visible = true;
    },
    close() {
      this.visible = false;
    },
    getBaseUrlPlaceholder() {
      const placeholders = {
        bybit: 'https://api.bybit.com',
        mexc: 'https://api.mexc.com',
        alpaca: 'https://paper-api.alpaca.markets'
      };
      return placeholders[this.type] || '';
    },
    openIBKRGateway() {
      const url = this.form.base_url || 'https://localhost:5000';
      window.open(url + '/', '_blank', 'noopener,noreferrer');
      showToast('Sign in to IBKR in the new window, then click Test Connection', 'success');
    },
    async testConnection() {
      this.testingConnection = true;
      this.testResult = null;
      const result = await api.testConnection(this.exchangeId, {
        api_key: this.form.api_key,
        api_secret: this.form.api_secret === '***' ? undefined : this.form.api_secret,
        base_url: this.form.base_url,
        trading_mode: this.form.trading_mode,
        leverage: this.form.leverage
      });
      this.testResult = result;
      this.testingConnection = false;
    },
    async save() {
      const data = {
        account_id: this.accountId,
        enabled: this.form.enabled,
        type: this.type,
        api_key: this.form.api_key,
        base_url: this.form.base_url,
        trading_mode: this.form.trading_mode,
        leverage: this.form.leverage,
        testnet: this.form.testnet,
        paper_trading: this.form.paper_trading,
        proxy: this.form.proxy
      };
      if (this.form.api_secret && this.form.api_secret !== '***') {
        data.api_secret = this.form.api_secret;
      }
      if (this.type === 'mexc') {
        data.use_sub_account = this.form.use_sub_account;
        data.sub_account_id = this.form.sub_account_id;
      }
      await api.saveExchange(this.exchangeId, data);
      this.close();
    }
  }
};

// ============================================================================
// PAGES
// ============================================================================

const OverviewPage = {
  mixins: [componentMixin],
  template: `<div class="page-content">
    <div class="stat-cards-grid">
      <stat-card label="Accounts" :value="accountCount" sub="configured" variant="info"></stat-card>
      <stat-card label="Exchange Accounts" :value="exchangeCount" sub="configured" variant="accent"></stat-card>
      <stat-card label="Enabled" :value="enabledCount" sub="active" variant="success"></stat-card>
      <stat-card label="Signals (24h)" :value="signalCount" sub="received" variant="info"></stat-card>
    </div>
    <div class="signal-hero">
      <div class="signal-hero-header">
        <div class="signal-hero-title"><i class="fas fa-satellite-dish"></i> TradingView Signal Monitor</div>
        <div class="connection-pill">
          <span class="dot" :style="{background: isConnected ? '#10b981' : '#ef4444'}"></span>
          <span>{{ isConnected ? '● Connected' : '○ Offline' }}</span>
        </div>
      </div>
      <div class="signal-status-cards">
        <div class="signal-status-card">
          <div class="signal-status-card-title">Webhook Status</div>
          <div class="signal-stat-row"><span class="signal-stat-label">Status</span><span class="signal-stat-value">{{ webhookStatus }}</span></div>
          <div class="signal-stat-row"><span class="signal-stat-label">Last Signal</span><span class="signal-stat-value">{{ lastSignalTime }}</span></div>
        </div>
        <div class="signal-status-card">
          <div class="signal-status-card-title">Statistics</div>
          <div class="signal-stat-row"><span class="signal-stat-label">Total Signals</span><span class="signal-stat-value">{{ signalCount }}</span></div>
        </div>
      </div>
    </div>
    <div style="margin-top: 2rem;">
      <div class="section-title">Recent Signals</div>
      <table class="signals-table">
        <thead>
          <tr><th>Time</th><th>Symbol</th><th>Signal</th><th>Price</th><th>Status</th></tr>
        </thead>
        <tbody>
          <tr v-for="sig in recentSignals" :key="sig.id">
            <td>{{ formatTime(sig.timestamp) }}</td>
            <td><strong>{{ sig.symbol }}</strong></td>
            <td><span :class="['sig-badge', sig.signal.toLowerCase()]">{{ sig.signal }}</span></td>
            <td>{{ sig.price ? sig.price.toFixed(4) : '—' }}</td>
            <td>✓ Received</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!recentSignals || recentSignals.length === 0" class="empty-state" style="margin-top: 2rem;">
        <i class="fas fa-inbox"></i>
        <p>No signals received in the last 24 hours</p>
      </div>
    </div>
  </div>`,
  computed: {
    accountCount() { return store.accounts.length; },
    exchangeCount() { return Object.keys(store.exchanges).length; },
    enabledCount() { return Object.values(store.exchanges).filter(e => e.enabled).length; },
    signalCount() { return store.signals.length; },
    recentSignals() { return store.signals.slice(0, 20); },
    isConnected() { return store.status && store.status.webhook_connected; },
    webhookStatus() { return store.status && store.status.webhook_status ? 'Active' : 'Inactive'; },
    lastSignalTime() { return formatTime(store.status && store.status.last_signal_time); }
  }
};

const AccountsPage = {
  mixins: [componentMixin],
  template: `<div class="page-content">
    <div class="page-header">
      <h2><i class="fas fa-user"></i> Accounts</h2>
      <div class="page-header-actions">
        <button class="btn btn-primary" @click="createAccount()"><i class="fas fa-plus"></i> New Account</button>
      </div>
    </div>
    <div v-if="store.accounts.length === 0" class="empty-state">
      <i class="fas fa-user-plus"></i>
      <div class="empty-title">No accounts yet</div>
      <p>Create your first account to get started.</p>
    </div>
    <div v-else class="accounts-grid">
      <div v-for="account in store.accounts" :key="account._id" :class="['account-card', {enabled: account.enabled}]">
        <div class="account-card-header">
          <div>
            <div class="account-card-name">{{ account.name || account._id }}</div>
            <div class="account-card-id">{{ account._id }}</div>
          </div>
          <span :class="['badge', account.enabled ? 'badge-success' : 'badge-neutral']">{{ account.enabled ? 'Enabled' : 'Disabled' }}</span>
        </div>
        <div class="account-card-footer">
          <button class="btn btn-sm" @click="viewExchanges(account._id)"><i class="fas fa-list"></i> Exchanges</button>
          <button class="btn btn-sm" @click="editAccount(account)"><i class="fas fa-edit"></i> Edit</button>
          <button class="btn btn-sm" @click="toggleAccount(account._id, !account.enabled)">{{ account.enabled ? 'Disable' : 'Enable' }}</button>
          <button class="btn btn-sm btn-danger btn-icon" @click="deleteAccount(account._id)"><i class="fas fa-trash"></i></button>
        </div>
      </div>
    </div>
  </div>`,
  methods: {
    createAccount() {
      this.$root.$refs.accountModal.open();
    },
    editAccount(account) {
      this.$root.$refs.accountModal.open(account);
    },
    viewExchanges(accountId) {
      pushRoute('exchanges', accountId);
    },
    toggleAccount(accountId, enabled) {
      const account = store.accounts.find(a => a._id === accountId);
      if (account) account.enabled = enabled;
      api.saveAccount({ _id: accountId, enabled });
    },
    async deleteAccount(accountId) {
      if (!confirm(`Delete account and all its exchanges? This cannot be undone.`)) return;
      await api.deleteAccount(accountId);
    }
  }
};

const ExchangesPage = {
  template: `<div class="page-content">
    <div class="page-header">
      <h2><i class="fas fa-exchange-alt"></i> Exchanges{{ currentAccountName ? ' - ' + currentAccountName : '' }}</h2>
      <div class="page-header-actions">
        <button class="btn" @click="goBack()"><i class="fas fa-arrow-left"></i> Back</button>
      </div>
    </div>
    <div v-if="!currentAccountId" class="empty-state">
      <p>Please select an account</p>
    </div>
    <div v-else class="exchange-cards-grid">
      <div v-for="ex in accountExchanges" :key="ex._id" :class="['exchange-card', {enabled: ex.enabled}]">
        <div class="exchange-card-header">
          <div class="exchange-card-title-row">
            <exchange-type-icon :type="ex.type"></exchange-type-icon>
            <div>
              <div class="exchange-card-name">{{ ex.type.toUpperCase() }}</div>
              <div class="exchange-card-id">{{ ex._id }}</div>
            </div>
          </div>
          <span :class="['badge', isConnected(ex._id) ? 'badge-success' : 'badge-neutral']">{{ isConnected(ex._id) ? '● Connected' : '○ Offline' }}</span>
        </div>
        <div class="exchange-card-body">
          <div class="exchange-card-row">
            <span class="exchange-card-row-label">Mode</span>
            <span class="exchange-card-row-value">{{ ex.trading_mode || 'Spot' }}{{ ex.leverage && ex.leverage > 1 ? ' · ' + ex.leverage + 'x' : '' }}</span>
          </div>
          <div v-if="exchangeStatus[ex._id] && exchangeStatus[ex._id].balances" class="exchange-card-row">
            <span class="exchange-card-row-label">Balance</span>
            <span class="exchange-card-row-value" style="font-size:11px;">{{ formatBalance(exchangeStatus[ex._id].balances) }}</span>
          </div>
          <div class="exchange-symbols-row">
            <span v-for="sym in (ex.symbols || [])" :key="sym" class="symbol-badge">{{ sym }}</span>
            <span v-if="!ex.symbols || ex.symbols.length === 0" class="text-muted" style="font-size:11px;">No symbols</span>
          </div>
        </div>
        <div class="exchange-card-footer">
          <div class="exchange-card-footer-left">
            <button class="btn btn-sm" @click="configureExchange(ex)"><i class="fas fa-cog"></i> Configure</button>
            <button class="btn btn-sm" @click="manageSymbols(ex)"><i class="fas fa-list"></i> Symbols</button>
          </div>
          <div class="exchange-card-footer-right">
            <toggle v-model="ex.enabled" @update:modelValue="toggleEx(ex._id, $event)"></toggle>
          </div>
        </div>
      </div>
    </div>
    <div v-if="managingSymbols" class="symbols-manager" style="margin-top: 2rem; padding: 1.5rem; border: 1px solid var(--border); border-radius: var(--radius);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <h3><i class="fas fa-list"></i> Manage Symbols</h3>
        <button class="btn btn-sm" @click="closeSymbols()">Close</button>
      </div>
      <div class="form-group" style="margin-bottom: 1rem;">
        <input v-model="symbolSearch" type="text" placeholder="Search symbols (e.g. BTC)..." @input="searchSymbols()">
        <div v-if="symbolSearchResults.length > 0" style="margin-top: 0.5rem; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-sm); max-height: 200px; overflow-y: auto;">
          <div v-for="sym in symbolSearchResults.slice(0, 20)" :key="sym" @click="addSymbol(sym)" style="padding: 0.5rem; cursor: pointer; border-bottom: 1px solid var(--border-light); hover: {background: var(--bg-tertiary)};">{{ sym }}</div>
        </div>
      </div>
      <table class="plain-table" style="width: 100%;">
        <thead>
          <tr><th>Symbol</th><th>Action</th></tr>
        </thead>
        <tbody>
          <tr v-for="sym in (currentExchange && currentExchange.symbols || [])" :key="sym">
            <td><span class="symbol-badge">{{ sym }}</span></td>
            <td><button class="btn btn-sm btn-danger" @click="removeSymbol(sym)"><i class="fas fa-trash"></i> Remove</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>`,
  data() {
    return {
      managingSymbols: false,
      currentExchange: null,
      symbolSearch: '',
      symbolSearchResults: [],
      searchTimeout: null
    };
  },
  computed: {
    currentAccountName() {
      if (!store.currentAccountId) return '';
      const acc = store.accounts.find(a => a._id === store.currentAccountId);
      return acc ? acc.name : store.currentAccountId;
    },
    accountExchanges() {
      if (!store.currentAccountId) return [];
      return Object.values(store.exchanges).filter(ex => ex.account_id === store.currentAccountId);
    },
    exchangeStatus() {
      return store.exchangeStatus;
    }
  },
  methods: {
    goBack() {
      pushRoute('accounts');
    },
    isConnected(exId) {
      return store.exchangeStatus[exId] && store.exchangeStatus[exId].connected;
    },
    formatBalance(balances) {
      if (!balances) return '—';
      const parts = [];
      for (const [asset, bal] of Object.entries(balances)) {
        let total = typeof bal === 'object' ? (bal.total || bal.free || 0) : bal;
        if (total > 0) parts.push(`${asset}: ${parseFloat(total).toFixed(2)}`);
      }
      return parts.slice(0, 4).join(' · ') || '—';
    },
    configureExchange(ex) {
      const acc = store.accounts.find(a => a._id === store.currentAccountId);
      this.$root.$refs.exchangeModal.open(ex, acc);
    },
    manageSymbols(ex) {
      this.currentExchange = ex;
      this.managingSymbols = true;
      this.symbolSearch = '';
      this.symbolSearchResults = [];
    },
    closeSymbols() {
      this.managingSymbols = false;
      this.currentExchange = null;
    },
    async searchSymbols() {
      if (this.searchTimeout) clearTimeout(this.searchTimeout);
      if (!this.symbolSearch.trim()) {
        this.symbolSearchResults = [];
        return;
      }
      this.searchTimeout = setTimeout(async () => {
        this.symbolSearchResults = await api.searchMarketSymbols(this.currentExchange._id, this.symbolSearch);
      }, 300);
    },
    async addSymbol(sym) {
      if (!this.currentExchange.symbols) this.currentExchange.symbols = [];
      if (!this.currentExchange.symbols.includes(sym)) {
        this.currentExchange.symbols.push(sym);
        await api.saveSymbols(this.currentExchange._id, this.currentExchange.symbols);
        this.symbolSearch = '';
        this.symbolSearchResults = [];
      }
    },
    async removeSymbol(sym) {
      if (this.currentExchange.symbols) {
        this.currentExchange.symbols = this.currentExchange.symbols.filter(s => s !== sym);
        await api.saveSymbols(this.currentExchange._id, this.currentExchange.symbols);
      }
    },
    async toggleEx(exId, enabled) {
      await api.toggleExchange(exId, enabled);
    }
  }
};

const SymbolsRoutingPage = {
  template: `<div class="page-content">
    <div class="section-title">Symbols & Routing</div>
    <table class="routing-table">
      <thead>
        <tr><th>Exchange Account</th><th>Type</th><th>Environment</th><th>Symbols</th></tr>
      </thead>
      <tbody>
        <tr v-for="ex in allExchanges" :key="ex._id">
          <td>{{ ex._id }}</td>
          <td>{{ ex.type.toUpperCase() }}</td>
          <td>{{ ex.testnet ? 'Testnet' : (ex.paper_trading ? 'Paper' : 'Live') }}</td>
          <td><span v-for="sym in (ex.symbols || [])" :key="sym" class="symbol-badge">{{ sym }}</span></td>
        </tr>
      </tbody>
    </table>
    <div v-if="allExchanges.length === 0" class="empty-state">
      <i class="fas fa-route"></i>
      <p>No symbol routing configured yet</p>
    </div>
  </div>`,
  computed: {
    allExchanges() {
      return Object.values(store.exchanges);
    }
  }
};

const TradingSettingsPage = {
  template: `<div class="page-content">
    <div class="section-title">Trading Settings</div>
    <div style="max-width: 600px;">
      <div class="form-group">
        <label>Position Size</label>
        <div style="display: flex; gap: 1rem; align-items: center;">
          <input v-model.number="positionSize" type="range" min="5" max="100" style="flex: 1;">
          <span style="min-width: 60px; font-weight: bold;">{{ positionSize }}%</span>
        </div>
      </div>
      <div class="form-group">
        <label class="with-check">
          <input v-model="usePercentage" type="checkbox">
          Use Percentage (vs Fixed Amount)
        </label>
      </div>
      <div class="form-group">
        <label class="with-check">
          <input v-model="warnExisting" type="checkbox">
          Warn if Position Exists
        </label>
      </div>
      <button class="btn btn-primary" @click="saveTradingSettings()">Save</button>
    </div>
  </div>`,
  data() {
    return {
      positionSize: 20,
      usePercentage: true,
      warnExisting: true
    };
  },
  mounted() {
    this.positionSize = store.tradingSettings.position_size_percent || 20;
    this.usePercentage = store.tradingSettings.use_percentage !== false;
    this.warnExisting = store.tradingSettings.warn_existing_positions !== false;
  },
  methods: {
    async saveTradingSettings() {
      await api.saveTradingSettings({
        position_size_percent: this.positionSize,
        use_percentage: this.usePercentage,
        warn_existing_positions: this.warnExisting
      });
    }
  }
};

const RiskManagementPage = {
  template: `<div class="page-content">
    <div class="section-title">Risk Management</div>
    <div style="max-width: 600px;">
      <div class="form-group">
        <label>Stop Loss %</label>
        <input v-model.number="stopLoss" type="number" min="0.1" max="20" step="0.1">
      </div>
      <div class="alert alert-warning" style="margin: 2rem 0;">
        <i class="fas fa-info-circle"></i> After TP1, stop-loss automatically moves to entry price
      </div>
      <div class="form-group">
        <label>Take Profit Levels (read-only)</label>
        <table class="plain-table" style="width: 100%; margin-top: 1rem;">
          <thead>
            <tr><th>Level</th><th>Profit %</th><th>Close %</th></tr>
          </thead>
          <tbody>
            <tr><td>TP1</td><td>1%</td><td>10%</td></tr>
            <tr><td>TP2</td><td>2%</td><td>15%</td></tr>
            <tr><td>TP3</td><td>5%</td><td>35%</td></tr>
            <tr><td>TP4</td><td>6.5%</td><td>35%</td></tr>
            <tr><td>TP5 (Runner)</td><td>Variable</td><td>5%</td></tr>
          </tbody>
        </table>
      </div>
      <button class="btn btn-primary" @click="saveRiskManagement()">Save</button>
    </div>
  </div>`,
  data() {
    return {
      stopLoss: 5.0
    };
  },
  mounted() {
    this.stopLoss = store.riskManagement.stop_loss_percent || 5.0;
  },
  methods: {
    async saveRiskManagement() {
      await api.saveRiskManagement({
        stop_loss_percent: this.stopLoss
      });
    }
  }
};

const ActivityPage = {
  template: `<div class="page-content">
    <div class="section-title">Activity & Logs</div>
    <table class="signals-table">
      <thead>
        <tr><th>Time</th><th>Symbol</th><th>Signal</th><th>Price</th><th>Status</th></tr>
      </thead>
      <tbody>
        <tr v-for="sig in store.signals.slice(0, 50)" :key="sig.id">
          <td>{{ formatTime(sig.timestamp) }}</td>
          <td><strong>{{ sig.symbol }}</strong></td>
          <td><span :class="['sig-badge', sig.signal.toLowerCase()]">{{ sig.signal }}</span></td>
          <td>{{ sig.price ? sig.price.toFixed(4) : '—' }}</td>
          <td>✓ Received</td>
        </tr>
      </tbody>
    </table>
    <div v-if="store.signals.length === 0" class="empty-state">
      <i class="fas fa-inbox"></i>
      <p>No signals received</p>
    </div>
  </div>`
};

// ============================================================================
// ROOT APP
// ============================================================================

const App = {
  mixins: [componentMixin],
  components: {
    'stat-card': StatCard,
    'exchange-type-icon': ExchangeTypeIcon,
    'toggle': Toggle,
    'account-modal': AccountModal,
    'exchange-modal': ExchangeModal,
    'overview-page': OverviewPage,
    'accounts-page': AccountsPage,
    'exchanges-page': ExchangesPage,
    'symbols-routing-page': SymbolsRoutingPage,
    'trading-settings-page': TradingSettingsPage,
    'risk-management-page': RiskManagementPage,
    'activity-page': ActivityPage
  },
  template: `
    <div class="dashboard-container">
      <header class="dashboard-header">
        <h1><i class="fas fa-chart-line"></i> Trading Bot</h1>
        <div class="header-right">
          <div class="status-indicator">
            <span class="status-dot" :style="{background: isHealthy ? '#10b981' : '#ef4444'}"></span>
            <span>{{ isHealthy ? 'Operational' : 'Offline' }}</span>
          </div>
        </div>
      </header>
      <div class="dashboard-body">
        <nav class="dashboard-sidebar">
          <div class="sidebar-section-label">Navigation</div>
          <button v-for="page in navPages" :key="page.id" :class="['sidebar-item', {active: store.currentPage === page.id}]" @click="pushRoute(page.id)">
            <i :class="page.icon"></i><span>{{ page.label }}</span>
          </button>
          <div class="sidebar-divider"></div>
          <div class="sidebar-section-label">Config</div>
          <button :class="['sidebar-item', {active: store.currentPage === 'tradingSettings'}]" @click="pushRoute('tradingSettings')">
            <i class="fas fa-sliders-h"></i><span>Trading Settings</span>
          </button>
          <button :class="['sidebar-item', {active: store.currentPage === 'risk'}]" @click="pushRoute('risk')">
            <i class="fas fa-shield-alt"></i><span>Risk Management</span>
          </button>
          <div class="sidebar-divider"></div>
          <button :class="['sidebar-item', {active: store.currentPage === 'activity'}]" @click="pushRoute('activity')">
            <i class="fas fa-chart-bar"></i><span>Activity</span>
          </button>
        </nav>
        <div class="dashboard-main">
          <overview-page v-show="store.currentPage === 'overview'"></overview-page>
          <accounts-page v-show="store.currentPage === 'accounts'"></accounts-page>
          <exchanges-page v-show="store.currentPage === 'exchanges'"></exchanges-page>
          <symbols-routing-page v-show="store.currentPage === 'symbolsRouting'"></symbols-routing-page>
          <trading-settings-page v-show="store.currentPage === 'tradingSettings'"></trading-settings-page>
          <risk-management-page v-show="store.currentPage === 'risk'"></risk-management-page>
          <activity-page v-show="store.currentPage === 'activity'"></activity-page>
        </div>
      </div>
      <account-modal ref="accountModal"></account-modal>
      <exchange-modal ref="exchangeModal"></exchange-modal>
      <div v-if="store.toast.visible" class="toast" :class="'toast-' + store.toast.type">{{ store.toast.message }}</div>
    </div>
  `,
  data() {
    return {
      navPages: [
        { id: 'overview', label: 'Overview', icon: 'fas fa-home' },
        { id: 'accounts', label: 'Accounts', icon: 'fas fa-user' },
        { id: 'symbolsRouting', label: 'Symbols & Routing', icon: 'fas fa-route' }
      ]
    };
  },
  computed: {
    isHealthy() {
      return store.status && store.status.connected;
    }
  },
  async mounted() {
    // Load all data
    store.loading = true;
    const { page, accountId } = restoreFromURL();

    await Promise.all([
      api.loadAccounts(),
      api.loadAllExchanges(),
      api.loadTradingSettings(),
      api.loadRiskManagement(),
      api.loadSignals(),
      api.loadStatus(),
      api.loadExchangeStatus()
    ]);

    store.loading = false;

    // Restore page from URL
    if (page === 'exchanges' && accountId) {
      await api.loadExchangesForAccount(accountId);
      store.currentPage = page;
      store.currentAccountId = accountId;
    } else {
      store.currentPage = page;
    }

    const urlPath = pageToPath(store.currentPage, store.currentAccountId);
    history.replaceState({ page: store.currentPage, accountId: store.currentAccountId }, '', urlPath);

    // Refresh signals every 10s, exchange status every 30s
    setInterval(() => api.loadSignals(), 10000);
    setInterval(() => api.loadExchangeStatus(), 30000);
    setInterval(() => api.loadStatus(), 5000);
  }
};

// ============================================================================
// BOOT
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  const app = createApp(App);

  // Global properties
  app.config.globalProperties.$formatTime = formatTime;
  app.config.globalProperties.$escapeHtml = escapeHtml;
  app.config.globalProperties.$showToast = showToast;
  app.config.globalProperties.pushRoute = pushRoute;
  app.config.globalProperties.store = store;
  app.config.globalProperties.api = api;
  app.config.globalProperties.formatTime = formatTime;

  // Register components globally
  app.component('stat-card', StatCard);
  app.component('exchange-type-icon', ExchangeTypeIcon);
  app.component('toggle', Toggle);
  app.component('badge', Badge);
  app.component('account-modal', AccountModal);
  app.component('exchange-modal', ExchangeModal);
  app.component('overview-page', OverviewPage);
  app.component('accounts-page', AccountsPage);
  app.component('exchanges-page', ExchangesPage);
  app.component('symbols-routing-page', SymbolsRoutingPage);
  app.component('trading-settings-page', TradingSettingsPage);
  app.component('risk-management-page', RiskManagementPage);
  app.component('activity-page', ActivityPage);

  app.mount('#app');
  console.log('✅ Vue app mounted with all components');
});
