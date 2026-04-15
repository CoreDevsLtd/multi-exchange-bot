/**
 * Trading Bot Dashboard — Vue 3 SPA
 *
 * Architecture:
 *  - Single reactive store (no duplicates)
 *  - Centralised API layer with proper error handling
 *  - Clean path-based router
 *  - provide/inject for modal access (no store.modals hacks)
 *  - Polling intervals cleaned up on unmount
 *  - No manual XSS escaping — Vue templates handle this
 */

'use strict';

const { createApp, reactive, computed, watch, onMounted, onUnmounted } = Vue;

/* ============================================================
   CONSTANTS
   ============================================================ */

const EXCHANGE_TYPES = ['bybit', 'mexc', 'alpaca', 'ibkr'];

const EXCHANGE_ABBR = { bybit: 'BY', mexc: 'MX', alpaca: 'AL', ibkr: 'IB' };

const BASE_URL_DEFAULTS = {
  bybit:  'https://api.bybit.com',
  mexc:   'https://api.mexc.com',
  alpaca: 'https://paper-api.alpaca.markets',
  ibkr:   '', // Not used for IBKR (uses Gateway/TWS direct connection)
};

/* ============================================================
   STORE — single source of truth
   ============================================================ */

const store = reactive({
  page:              'overview',
  accountId:         null,   // reused as symbol in portfolio context
  exchangeAccountId: null,   // exchange_account_id for portfolio context
  tradeId:           null,
  accounts:          [],
  exchanges:         {},   // keyed by exchange._id
  exStatus:          {},   // keyed by exchange._id
  settings:          {},
  risk:              {},
  signals:           [],
  webhookLogs:       [],
  status:            {},
  demoMode:          false,
  demoStats:         {},
  portfolio:         [],   // Milestone 3: Portfolio page data
  portfolioFilters:  { startDate: '', endDate: '' },
  loading:           true,
  toast: { msg: '', type: 'info', visible: false, _t: null },
});

/* ============================================================
   TOAST
   ============================================================ */

function toast(msg, type = 'info') {
  if (store.toast._t) clearTimeout(store.toast._t);
  Object.assign(store.toast, { msg, type, visible: true });
  store.toast._t = setTimeout(() => { store.toast.visible = false; }, 4000);
}

/* ============================================================
   API — centralised fetch with unified error handling
   ============================================================ */

const api = {
  async _req(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const r = await fetch(url, opts);
    const raw = await r.text();
    let payload = null;
    if (raw) {
      try { payload = JSON.parse(raw); } catch { payload = { message: raw }; }
    }
    if (!r.ok) {
      const backendError = payload?.error;
      const backendMessage = payload?.message;
      const msg = (backendError && backendError.toLowerCase() !== 'connection failed')
        ? backendError
        : (backendMessage || backendError || `${method} ${url} → HTTP ${r.status}`);
      const err = new Error(msg);
      err.status = r.status;
      err.payload = payload;
      throw err;
    }
    return payload ?? {};
  },
  get:    (url)       => api._req('GET',    url),
  post:   (url, body) => api._req('POST',   url, body),
  delete: (url)       => api._req('DELETE', url),

  /* --- Accounts --- */
  async loadAccounts() {
    const d = await api.get('/api/accounts').catch(console.error);
    if (d) store.accounts = d.accounts ?? [];
  },

  async saveAccount(data) {
    const r = await api.post('/api/accounts', data).catch(() => null);
    if (r?.status === 'success') { await api.loadAccounts(); toast('Account saved', 'success'); return true; }
    toast(r?.error ?? 'Failed to save account', 'error');
    return false;
  },

  async deleteAccount(id) {
    const r = await api.delete(`/api/accounts/${id}`).catch(() => null);
    if (r?.status === 'success') {
      store.accounts = store.accounts.filter(a => a._id !== id);
      Object.keys(store.exchanges).forEach(k => {
        if (store.exchanges[k].account_id === id) delete store.exchanges[k];
      });
      toast('Account deleted', 'success');
      return true;
    }
    toast(r?.error ?? 'Failed to delete account', 'error');
    return false;
  },

  async toggleAccount(id, enabled) {
    await api.post('/api/accounts', { _id: id, enabled }).catch(console.error);
  },

  /* --- Exchanges --- */
  async loadExchangesForAccount(accountId) {
    const d = await api.get(`/api/accounts/${accountId}/exchanges`).catch(() => null);
    (d?.exchanges ?? []).forEach(ex => { store.exchanges[ex._id] = { ...ex, account_id: accountId }; });
    return d?.exchanges ?? [];
  },

  async loadAllExchanges() {
    for (const ac of store.accounts) {
      await api.loadExchangesForAccount(ac._id);
    }
  },

  async saveExchange(accountId, data) {
    const r = await api.post(`/api/accounts/${accountId}/exchanges`, data).catch(() => null);
    if (r?.status === 'success') { await api.loadExchangesForAccount(accountId); toast('Exchange saved', 'success'); return true; }
    toast(r?.error ?? 'Failed to save exchange', 'error');
    return false;
  },

  async updateExchange(exchangeId, data) {
    const r = await api.post(`/api/exchanges/${exchangeId}`, data).catch(() => null);
    if (r?.status === 'success') { Object.assign(store.exchanges[exchangeId] ?? {}, data); toast('Exchange updated', 'success'); return true; }
    toast(r?.error ?? 'Failed to update exchange', 'error');
    return false;
  },

  async deleteExchange(id) {
    const r = await api.delete(`/api/exchanges/${id}`).catch(() => null);
    if (r?.status === 'success') { delete store.exchanges[id]; toast('Exchange deleted', 'success'); return true; }
    toast(r?.error ?? 'Failed to delete exchange', 'error');
    return false;
  },

  async toggleExchange(id, enabled) {
    const r = await api.post(`/api/exchanges/${id}/toggle`, { enabled }).catch(() => null);
    if (r?.status === 'success' && store.exchanges[id]) {
      store.exchanges[id].enabled = enabled;
      toast(enabled ? 'Exchange enabled' : 'Exchange disabled', 'success');
    }
  },

  async loadExStatus() {
    const d = await api.get('/api/exchanges/status').catch(() => null);
    if (d) store.exStatus = d;
  },

  async testConnection(id, body) {
    try {
      const r = await api.post(`/api/test-connection/${id}`, body);
      if (r?.status === 'success') toast('Connection successful!', 'success');
      else toast(r?.error ?? r?.message ?? 'Connection failed', 'error');
      return r;
    } catch (err) {
      const msg = err?.payload?.message || err?.payload?.error || err?.message || 'Connection failed';
      toast(msg, 'error');
      return { status: 'error', error: msg };
    }
  },

  /* --- IBKR ibeam Container Management --- */
  async ibkrSetup(exchangeId, user, pass, paper) {
    const r = await api.post('/api/ibkr/setup', {
      exchange_id: exchangeId,
      ibkr_user: user,
      ibkr_pass: pass,
      paper_trading: paper
    }).catch(() => null);
    if (r?.port) {
      toast(`ibeam container started on port ${r.port}`, 'success');
      return r;
    } else {
      toast(r?.error ?? 'Failed to start ibeam container', 'error');
      return null;
    }
  },

  async ibkrStop(exchangeId) {
    const r = await api._req('DELETE', `/api/ibkr/stop/${exchangeId}`).catch(() => null);
    if (r?.status === 'stopped') {
      toast('ibeam container stopped', 'success');
      return true;
    } else {
      toast(r?.error ?? 'Failed to stop container', 'error');
      return false;
    }
  },

  async ibkrContainerStatus(exchangeId) {
    const r = await api.get(`/api/ibkr/status/${exchangeId}`).catch(() => null);
    return r;
  },

  /* --- Symbols (single symbol per exchange) --- */
  async loadSymbols(id) {
    const d = await api.get(`/api/exchanges/${id}/symbols`).catch(() => null);
    if (d && store.exchanges[id]) store.exchanges[id].symbol = d.symbol ?? null;
    return d?.symbol ?? null;
  },

  async saveSymbols(id, symbol) {
    const r = await api.post(`/api/exchanges/${id}/symbols`, { symbol }).catch(() => null);
    if (r?.status === 'success') {
      if (store.exchanges[id]) store.exchanges[id].symbol = r.symbol ?? symbol;
      toast('Symbol saved', 'success');
      return true;
    }
    toast(r?.error ?? 'Failed to save symbol', 'error');
    return false;
  },

  async searchSymbols(id, q, draft = null) {
    const url = `/api/exchanges/${id}/market-symbols?q=${encodeURIComponent(q)}`;
    const d = draft
      ? await api.post(url, draft).catch(() => null)
      : await api.get(url).catch(() => null);
    return d?.symbols ?? [];
  },

  /* --- Settings --- */
  async loadSettings() {
    const [s, r] = await Promise.all([
      api.get('/api/trading-settings').catch(() => null),
      api.get('/api/risk-management').catch(() => null),
    ]);
    if (s) store.settings = s;
    if (r) store.risk = r;
  },

  async saveSettings(data) {
    const r = await api.post('/api/trading-settings', data).catch(() => null);
    if (r?.status === 'success') { store.settings = data; toast('Settings saved', 'success'); return true; }
    toast(r?.error ?? 'Failed', 'error');
    return false;
  },

  async saveRisk(data) {
    const r = await api.post('/api/risk-management', data).catch(() => null);
    if (r?.status === 'success') { store.risk = r.risk ?? data; toast('Risk settings saved', 'success'); return true; }
    toast(r?.error ?? 'Failed', 'error');
    return false;
  },

  /* --- Portfolio (Milestone 3) --- */
  async loadPortfolio(params = {}) {
    const q = new URLSearchParams();
    if (params.start_date) q.set('start_date', params.start_date);
    if (params.end_date) q.set('end_date', params.end_date);
    const url = q.toString() ? `/api/portfolio?${q}` : '/api/portfolio';
    const d = await api.get(url).catch(() => null);
    if (d) store.portfolio = d.tickers ?? [];
    return d;
  },

  async loadTickerDetail(symbol, exchangeAccountId, params = {}) {
    const q = new URLSearchParams();
    if (params.start_date) q.set('start_date', params.start_date);
    if (params.end_date) q.set('end_date', params.end_date);
    const qs = q.toString();
    const url = `/api/portfolio/${encodeURIComponent(symbol)}/${encodeURIComponent(exchangeAccountId)}${qs ? `?${qs}` : ''}`;
    const d = await api.get(url).catch(() => null);
    if (d) return d;
    return null;
  },

  async loadTradeDetail(symbol, exchangeAccountId, tradeId) {
    const d = await api.get(`/api/portfolio/${encodeURIComponent(symbol)}/${encodeURIComponent(exchangeAccountId)}/trade/${encodeURIComponent(tradeId)}`).catch(() => null);
    if (d) return d;
    return null;
  },

  async checkPosition(exchangeId, symbol) {
    const d = await api.get(`/api/exchanges/${encodeURIComponent(exchangeId)}/check-position/${encodeURIComponent(symbol)}`).catch(() => null);
    return d;
  },

  /* --- Status & Signals --- */
  async loadSignals() {
    const d = await api.get('/api/signals/recent?limit=100&hours=24').catch(() => null);
    if (d) store.signals = d.signals ?? [];
  },

  async loadWebhookLogs(limit = 100, status = '', symbol = '') {
    const params = new URLSearchParams({ limit });
    if (status) params.set('status', status);
    if (symbol) params.set('symbol', symbol);
    const d = await api.get(`/api/webhook-logs?${params}`).catch(() => null);
    if (d?.logs) store.webhookLogs = d.logs;
  },

  async loadStatus() {
    const [s, ss] = await Promise.all([
      api.get('/api/status').catch(() => null),
      api.get('/api/signals/status').catch(() => null),
    ]);
    if (s)  store.status = { ...store.status, ...s };
    if (ss) store.status = { ...store.status, ...ss };
    store.demoMode = !!store.status.demo_mode;
  },

  async loadDemoData() {
    if (!store.demoMode) return;
    const d = await api.get('/api/demo/stats').catch(() => null);
    if (d) store.demoStats = d.stats ?? {};
  },
};

/* ============================================================
   ROUTER
   ============================================================ */

const ROUTES = {
  '/':                 { page: 'overview' },
  '/accounts':         { page: 'accounts' },
  '/symbols-routing':  { page: 'symbolsRouting' },
  '/trading-settings': { page: 'tradingSettings' },
  '/risk-management':  { page: 'risk' },
  '/activity':         { page: 'activity' },
  '/portfolio':        { page: 'portfolio' },  // Milestone 3: Portfolio page
};

function parsePath(pathname) {
  if (ROUTES[pathname]) return { ...ROUTES[pathname], accountId: null, exchangeAccountId: null };
  const m = pathname.match(/^\/exchanges\/(.+)$/);
  if (m) return { page: 'exchanges', accountId: decodeURIComponent(m[1]), exchangeAccountId: null };
  // /portfolio/<symbol>/<exchangeAccountId>/trade/<tradeId>
  const trade = pathname.match(/^\/portfolio\/([^/]+)\/([^/]+)\/trade\/(.+)$/);
  if (trade) return { page: 'tradeDetail', accountId: decodeURIComponent(trade[1]), exchangeAccountId: decodeURIComponent(trade[2]), tradeId: decodeURIComponent(trade[3]) };
  // /portfolio/<symbol>/<exchangeAccountId>
  const ticker = pathname.match(/^\/portfolio\/([^/]+)\/([^/]+)$/);
  if (ticker) return { page: 'tickerDetail', accountId: decodeURIComponent(ticker[1]), exchangeAccountId: decodeURIComponent(ticker[2]) };
  return { page: 'overview', accountId: null, exchangeAccountId: null };
}

function buildPath(page, accountId = null, exchangeAccountId = null, tradeId = null) {
  if (page === 'exchanges' && accountId) return `/exchanges/${encodeURIComponent(accountId)}`;
  if (page === 'tradeDetail' && accountId && exchangeAccountId && tradeId)
    return `/portfolio/${encodeURIComponent(accountId)}/${encodeURIComponent(exchangeAccountId)}/trade/${encodeURIComponent(tradeId)}`;
  if (page === 'tickerDetail' && accountId && exchangeAccountId)
    return `/portfolio/${encodeURIComponent(accountId)}/${encodeURIComponent(exchangeAccountId)}`;
  return Object.entries(ROUTES).find(([, v]) => v.page === page)?.[0] ?? '/';
}

function navigate(page, accountId = null, replace = false, tradeId = null, exchangeAccountId = null) {
  store.page = page;
  store.accountId = accountId;
  store.exchangeAccountId = exchangeAccountId;
  store.tradeId = tradeId;
  const url = buildPath(page, accountId, exchangeAccountId, tradeId);
  replace ? history.replaceState({ page, accountId, exchangeAccountId, tradeId }, '', url)
           : history.pushState({ page, accountId, exchangeAccountId, tradeId }, '', url);
}

window.addEventListener('popstate', async e => {
  const { page, accountId, exchangeAccountId, tradeId } = e.state ?? parsePath(location.pathname);
  store.page = page;
  store.accountId = accountId;
  store.exchangeAccountId = exchangeAccountId ?? null;
  store.tradeId = tradeId;
  if (page === 'exchanges' && accountId) await api.loadExchangesForAccount(accountId);
});

/* ============================================================
   UTILITIES
   ============================================================ */

function fmtTime(iso) {
  if (!iso) return 'Never';
  return new Date(iso).toLocaleString();
}

function fmtTimeSince(sec) {
  if (!sec) return '—';
  const s = Math.floor(sec), m = Math.floor(s / 60), h = Math.floor(m / 60);
  if (h > 0) return `${h}h ${m % 60}m ago`;
  if (m > 0) return `${m}m ${s % 60}s ago`;
  return `${s}s ago`;
}

function fmtBalance(bals) {
  if (!bals || typeof bals !== 'object') return '—';
  return Object.entries(bals)
    .map(([a, b]) => {
      const v = parseFloat(typeof b === 'object' ? (b.total ?? b.free ?? 0) : b) || 0;
      return v > 0 ? `${a}: ${v >= 1 ? v.toFixed(2) : v.toFixed(4)}` : null;
    })
    .filter(Boolean).slice(0, 4).join(' · ') || '—';
}

function exchangeAbbr(type) {
  return EXCHANGE_ABBR[(type ?? '').toLowerCase()] ?? (type ?? '?').slice(0, 2).toUpperCase();
}

function formatExchangeDisplay(exchangeId) {
  const id = String(exchangeId ?? '').trim();
  if (!id) return '—';
  const ex = store.exchanges?.[id];
  if (!ex) return id;
  const account = store.accounts.find(a => a._id === ex.account_id);
  const accountName = (account?.name || ex.account_id || 'Unknown Account').trim();
  const exType = (ex.type || '').toUpperCase() || 'EXCHANGE';
  return `${accountName} - ${exType} - ${id}`;
}

function formatExchangeList(ids) {
  if (!Array.isArray(ids) || !ids.length) return '—';
  return ids.map(formatExchangeDisplay).join(', ');
}

/* ============================================================
   SHARED MIXIN — injected into every component
   ============================================================ */

const mixin = {
  data() { return { store, api }; },
  methods: { toast, navigate, fmtTime, fmtTimeSince, fmtBalance, exchangeAbbr, formatExchangeDisplay, formatExchangeList },
};

/* ============================================================
   ATOMIC COMPONENTS
   ============================================================ */

/** Toggle switch */
const CToggle = {
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: `
    <label class="c-toggle">
      <input type="checkbox" :checked="modelValue"
             @change="$emit('update:modelValue', $event.target.checked)">
      <span class="c-toggle-track"></span>
    </label>`,
};

/** Exchange type icon */
const CExIcon = {
  props: ['type'],
  computed: { abbr() { return exchangeAbbr(this.type); } },
  template: `<div :class="['ex-icon', (type || '').toLowerCase()]">{{ abbr }}</div>`,
};

/* ============================================================
   ACCOUNT MODAL
   ============================================================ */

const AccountModal = {
  data: () => ({
    open:    false,
    saving:  false,
    isEdit:  false,
    form:    { _id: '', name: '', enabled: true },
  }),
  template: `
    <teleport to="body">
      <transition name="modal">
        <div v-if="open" class="modal-backdrop" @mousedown.self="close">
          <div class="modal-box">
            <div class="modal-head">
              {{ isEdit ? 'Edit Account' : 'New Account' }}
              <button class="modal-close" @click="close">×</button>
            </div>
            <div class="modal-body">
              <div class="field-group">
                <label>Account Name</label>
                <input v-model.trim="form.name" type="text" placeholder="e.g. Main Account" autofocus>
              </div>
              <label class="check-row">
                <input v-model="form.enabled" type="checkbox"> Enabled
              </label>
            </div>
            <div class="modal-foot">
              <button class="btn" @click="close">Cancel</button>
              <button class="btn btn-primary" @click="save" :disabled="saving">
                {{ saving ? 'Saving…' : 'Save Account' }}
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>`,
  methods: {
    show(account = null) {
      this.isEdit = !!account;
      this.form   = account
        ? { _id: account._id, name: account.name ?? account._id, enabled: account.enabled !== false }
        : { _id: '', name: '', enabled: true };
      this.saving = false;
      this.open   = true;
    },
    close() { this.open = false; },
    async save() {
      if (!this.form.name) { toast('Name is required', 'error'); return; }
      this.saving = true;
      const data = { name: this.form.name, enabled: this.form.enabled };
      if (this.form._id) data._id = this.form._id;
      const ok = await api.saveAccount(data);
      this.saving = false;
      if (ok) this.close();
    },
  },
};

/* ============================================================
   EXCHANGE MODAL
   ============================================================ */

const ExchangeModal = {
  components: { CToggle },
  data: () => ({
    open:           false,
    saving:         false,
    testing:        false,
    isCreate:       false,
    exchangeId:     null,
    accountId:      null,
    type:           'bybit',
    secretHasValue: false,
    form: {
      enabled: true, api_key: '', api_secret: '', base_url: '',
      trading_mode: 'spot', leverage: 1,
      paper_trading: false, use_sub_account: false, sub_account_id: '', proxy: '',
      symbol: null,
    },
    symbolResults: [],
    symbolQuery: '',
    symbolTimer: null,
    ibkrUser: '',
    ibkrPass: '',
    ibkrSetting: false,
    ibkrContainerRunning: false,
    positionWarning: null,
    originalLeverage: 1,
  }),
  computed: {
    isIbkr()          { return this.type === 'ibkr'; },
    isBybit()         { return this.type === 'bybit'; },
    isMexc()          { return this.type === 'mexc'; },
    isAlpaca()        { return this.type === 'alpaca'; },
    baseUrlPlaceholder() { return BASE_URL_DEFAULTS[this.type] ?? ''; },
  },
  template: `
    <teleport to="body">
      <transition name="modal">
        <div v-if="open" class="modal-backdrop" @mousedown.self="close">
          <div class="modal-box modal-box--wide">
            <div class="modal-head">
              {{ isCreate ? 'Add Exchange' : 'Configure ' + type.toUpperCase() }}
              <button class="modal-close" @click="close">×</button>
            </div>
            <div class="modal-body">

              <div v-if="isCreate" class="field-group">
                <label>Exchange Type</label>
                <select v-model="type">
                  <option value="bybit">Bybit</option>
                  <option value="mexc">MEXC</option>
                  <option value="alpaca">Alpaca</option>
                  <option value="ibkr">Interactive Brokers</option>
                </select>
              </div>

              <label class="check-row">
                <input v-model="form.enabled" type="checkbox"> Enable this exchange
              </label>

              <template v-if="!isIbkr">
                <div class="field-group">
                  <label>API Key</label>
                  <input v-model.trim="form.api_key" type="text" placeholder="API Key" autocomplete="off">
                </div>
                <div class="field-group">
                  <label>API Secret</label>
                  <input v-model="form.api_secret" type="password"
                         :placeholder="secretHasValue ? '(unchanged — type to replace)' : 'API Secret'"
                         autocomplete="new-password">
                </div>
              </template>

              <template v-if="isBybit">
                <div class="field-group">
                  <label>Trading Environment</label>
                  <select v-model="form.paper_trading">
                    <option :value="false">Live</option>
                    <option :value="true">Paper</option>
                  </select>
                </div>
                <div class="field-row">
                  <div class="field-group">
                    <label>Trading Mode</label>
                    <select v-model="form.trading_mode">
                      <option value="spot">Spot</option>
                      <option value="futures">Futures</option>
                    </select>
                  </div>
                  <div v-if="form.trading_mode === 'futures'" class="field-group">
                    <label>Leverage</label>
                    <input v-model.number="form.leverage" type="number" min="1" max="100">
                  </div>
                </div>

                <div v-if="positionWarning" style="padding:12px; background:#fff3cd; border:1px solid #ffc107; border-radius:4px; margin:12px 0; color:#856404;">
                  <div style="font-weight:bold; margin-bottom:8px;">⚠️ WARNING: Open Position Detected</div>
                  <div>{{ positionWarning.warning }}</div>
                  <div style="margin-top:8px; font-size:12px;">
                    <button @click="confirmLeverageChange" style="padding:4px 8px; background:#dc3545; color:white; border:none; border-radius:3px; cursor:pointer; margin-right:4px;">Confirm & Change Leverage</button>
                    <button @click="positionWarning = null" style="padding:4px 8px; background:#6c757d; color:white; border:none; border-radius:3px; cursor:pointer;">Cancel</button>
                  </div>
                </div>

                <div class="field-group">
                  <label>Symbol</label>
                  <div style="position: relative; z-index: 100;">
                    <input v-model="symbolQuery" type="text" placeholder="Search symbol (e.g. BTC)…"
                           @input="onSymbolSearch" autocomplete="off" style="width: 100%;">
                    <div v-if="symbolResults.length" style="position: absolute; top: calc(100% + 2px); left: 0; right: 0; background: var(--bg-2); border: 1px solid var(--bd); border-radius: var(--r-sm); max-height: 200px; overflow-y: auto; z-index: 1000; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                      <div v-for="s in symbolResults.slice(0, 20)" :key="s"
                           @mousedown.prevent="form.symbol = s.toUpperCase(); symbolResults = []; symbolQuery = ''"
                           style="padding: 8px 12px; cursor: pointer; border-bottom: 1px solid var(--bd); transition: background 0.1s; user-select: none;"
                           @mouseover="$event.target.style.background = 'var(--bg-hover)'"
                           @mouseout="$event.target.style.background = 'transparent'">
                        {{ s }}
                      </div>
                    </div>
                  </div>
                </div>
                <div v-if="form.symbol" style="display: flex; align-items: center; gap: 8px; margin-top: 8px; margin-bottom: 16px;">
                  <span class="symbol-badge">{{ form.symbol }}</span>
                  <button class="btn btn-sm btn-danger" type="button" @click="form.symbol = null">
                    <i class="fas fa-trash"></i> Clear
                  </button>
                </div>

                <div class="field-group">
                  <label>Proxy URL <span class="field-hint">(optional)</span></label>
                  <input v-model.trim="form.proxy" type="text" placeholder="http://proxy:port">
                </div>
              </template>

              <template v-if="isMexc">
                <div class="field-group">
                  <label>Base URL <span class="field-hint">(leave blank for default)</span></label>
                  <input v-model.trim="form.base_url" type="text" :placeholder="baseUrlPlaceholder">
                </div>
                <label class="check-row">
                  <input v-model="form.use_sub_account" type="checkbox"> Use Sub-Account
                </label>
                <div v-if="form.use_sub_account" class="field-group">
                  <label>Sub-Account ID</label>
                  <input v-model.trim="form.sub_account_id" type="text" placeholder="Sub-account ID">
                </div>

                <div class="field-group">
                  <label>Symbol</label>
                  <div style="position: relative; z-index: 100;">
                    <input v-model="symbolQuery" type="text" placeholder="Search symbol (e.g. BTC)…"
                           @input="onSymbolSearch" autocomplete="off" style="width: 100%;">
                    <div v-if="symbolResults.length" style="position: absolute; top: calc(100% + 2px); left: 0; right: 0; background: var(--bg-2); border: 1px solid var(--bd); border-radius: var(--r-sm); max-height: 200px; overflow-y: auto; z-index: 1000; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                      <div v-for="s in symbolResults.slice(0, 20)" :key="s"
                           @mousedown.prevent="form.symbol = s.toUpperCase(); symbolResults = []; symbolQuery = ''"
                           style="padding: 8px 12px; cursor: pointer; border-bottom: 1px solid var(--bd); transition: background 0.1s; user-select: none;"
                           @mouseover="$event.target.style.background = 'var(--bg-hover)'"
                           @mouseout="$event.target.style.background = 'transparent'">
                        {{ s }}
                      </div>
                    </div>
                  </div>
                </div>
                <div v-if="form.symbol" style="display: flex; align-items: center; gap: 8px; margin-top: 8px; margin-bottom: 16px;">
                  <span class="symbol-badge">{{ form.symbol }}</span>
                  <button class="btn btn-sm btn-danger" type="button" @click="form.symbol = null">
                    <i class="fas fa-trash"></i> Clear
                  </button>
                </div>

                <div class="alert alert-warning">
                  <i class="fas fa-exclamation-triangle"></i>
                  Sub-account trading requires additional MEXC permissions.
                </div>
              </template>

              <template v-if="isAlpaca">
                <div class="field-group">
                  <label>Trading Environment</label>
                  <select v-model="form.paper_trading">
                    <option :value="true">Paper</option>
                    <option :value="false">Live</option>
                  </select>
                </div>

                <div class="field-group">
                  <label>Symbol</label>
                  <div style="position: relative;">
                    <input v-model="symbolQuery" type="text" placeholder="Search symbol (e.g. AAPL)…"
                           @input="onSymbolSearch" autocomplete="off">
                    <div v-if="symbolResults.length" style="position: absolute; top: 100%; left: 0; right: 0; background: var(--bg-2); border: 1px solid var(--bd); border-radius: var(--r-sm); max-height: 200px; overflow-y: auto; z-index: 10;">
                      <div v-for="s in symbolResults.slice(0, 20)" :key="s"
                           @click="form.symbol = s.toUpperCase(); symbolResults = []; symbolQuery = ''"
                           style="padding: 8px 12px; cursor: pointer; border-bottom: 1px solid var(--bd-light); hover:background var(--bg-hover);">
                        {{ s }}
                      </div>
                    </div>
                  </div>
                </div>
                <div v-if="form.symbol" style="display: flex; align-items: center; gap: 8px; margin-top: 8px; margin-bottom: 16px;">
                  <span class="symbol-badge">{{ form.symbol }}</span>
                  <button class="btn btn-sm btn-danger" type="button" @click="form.symbol = null">
                    <i class="fas fa-trash"></i> Clear
                  </button>
                </div>
              </template>

              <template v-if="isIbkr">
                <label class="check-row">
                  <input v-model="form.paper_trading" type="checkbox"> Paper Trading (Demo Account)
                </label>

                <!-- ibeam Setup Section -->
                <div v-if="!ibkrContainerRunning" class="field-group">
                  <label>IBKR Username</label>
                  <input v-model.trim="ibkrUser" type="text" placeholder="your@ibkr.com">
                </div>
                <div v-if="!ibkrContainerRunning" class="field-group">
                  <label>IBKR Password</label>
                  <input v-model="ibkrPass" type="password" placeholder="••••••••">
                </div>

                <div style="display:flex; gap:8px; align-items:center; margin-bottom:12px; flex-wrap:wrap">
                  <button v-if="!ibkrContainerRunning" class="btn btn-primary" type="button"
                          @click="setupIbeam" :disabled="ibkrSetting">
                    <i class="fas fa-play"></i> {{ ibkrSetting ? 'Starting…' : 'Start ibeam' }}
                  </button>
                  <button v-if="ibkrContainerRunning" class="btn btn-danger" type="button"
                          @click="stopIbeam" :disabled="ibkrSetting">
                    <i class="fas fa-stop"></i> {{ ibkrSetting ? 'Stopping…' : 'Stop Container' }}
                  </button>
                  <span v-if="ibkrContainerRunning" style="color:#4ade80;font-size:13px;display:flex;align-items:center;gap:6px">
                    <i class="fas fa-circle"></i> Running on port {{ form.gateway_port }}
                  </span>
                </div>

                <!-- Gateway config (shown only when container is running) -->
                <template v-if="ibkrContainerRunning">
                  <div class="field-row">
                    <div class="field-group">
                      <label>Gateway Host</label>
                      <input v-model.trim="form.gateway_host" type="text" placeholder="127.0.0.1">
                    </div>
                    <div class="field-group" style="max-width:130px">
                      <label>Gateway Port</label>
                      <input v-model.number="form.gateway_port" type="number" disabled>
                    </div>
                    <div class="field-group" style="max-width:100px">
                      <label>Client ID</label>
                      <input v-model.number="form.client_id" type="number" min="1" max="999" placeholder="1">
                    </div>
                  </div>
                </template>
              </template>

            </div>
            <div class="modal-foot">
              <button class="btn btn-ghost" type="button" @click="testConn" :disabled="testing">
                <i class="fas fa-plug"></i> {{ testing ? 'Testing…' : 'Test' }}
              </button>
              <button class="btn" @click="close">Cancel</button>
              <button class="btn btn-primary" @click="save" :disabled="saving">
                {{ saving ? 'Saving…' : 'Save' }}
              </button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>`,
  methods: {
    showCreate(accountId) {
      Object.assign(this, {
        isCreate: true, exchangeId: null, accountId,
        type: 'bybit', secretHasValue: false, saving: false, testing: false,
        symbolQuery: '', symbolResults: [],
        form: { enabled: true, api_key: '', api_secret: '', base_url: '',
                trading_mode: 'spot', leverage: 1, paper_trading: false,
                use_sub_account: false, sub_account_id: '', proxy: '', symbol: null,
                gateway_host: '127.0.0.1', gateway_port: 7497, client_id: 1 },
      });
      this.open = true;
    },
    showEdit(exchange) {
      const creds = exchange.credentials ?? {};
      const origLeverage = exchange.leverage ?? 1;
      const editType = (exchange.type ?? exchange._id).toLowerCase();
      Object.assign(this, {
        isCreate: false, exchangeId: exchange._id,
        accountId: exchange.account_id,
        type: editType,
        secretHasValue: !!(creds.api_secret ?? exchange.api_secret),
        saving: false, testing: false,
        symbolQuery: '', symbolResults: [],
        positionWarning: null,
        originalLeverage: origLeverage,
        form: {
          enabled:         exchange.enabled !== false,
          api_key:         creds.api_key ?? exchange.api_key ?? '',
          api_secret:      '',
          base_url:        exchange.base_url ?? '',
          trading_mode:    exchange.trading_mode ?? 'spot',
          leverage:        origLeverage,
          use_sub_account: !!exchange.use_sub_account,
          sub_account_id:  exchange.sub_account_id ?? '',
          proxy:           exchange.proxy ?? '',
          symbol:          exchange.symbol ?? null,
          gateway_host:    exchange.gateway_host ?? '127.0.0.1',
          gateway_port:    exchange.gateway_port ?? 7497,
          client_id:       exchange.client_id ?? 1,
          paper_trading:   (editType === 'bybit')
                            ? !!exchange.testnet
                            : (editType === 'alpaca')
                              ? (exchange.paper_trading ?? exchange.use_paper ?? true)
                              : (exchange.paper_trading !== false),
        },
      });
      // Check if IBKR container is running
      if (this.type === 'ibkr') {
        api.ibkrContainerStatus(exchange._id).then(status => {
          this.ibkrContainerRunning = status?.running ?? false;
          if (status?.port) this.form.gateway_port = status.port;
        });
      }
      this.open = true;
    },
    close() { this.open = false; },
    payload() {
      let baseUrl = this.form.base_url;
      if (this.isAlpaca && !baseUrl) {
        baseUrl = this.form.paper_trading ? 'https://paper-api.alpaca.markets' : 'https://api.alpaca.markets';
      }
      const p = {
        type:     this.type,
        enabled:  this.form.enabled,
        api_key:  this.form.api_key,
        symbol:   this.form.symbol,
      };
      if (this.isMexc) p.base_url = baseUrl;
      if (this.form.api_secret) p.api_secret = this.form.api_secret;
      if (this.isBybit)  { p.paper_trading = this.form.paper_trading; p.trading_mode = this.form.trading_mode; p.leverage = this.form.leverage; if (this.form.proxy) p.proxy = this.form.proxy; }
      if (this.isMexc)   { p.use_sub_account = this.form.use_sub_account; p.sub_account_id = this.form.sub_account_id; }
      if (this.isAlpaca) { p.paper_trading = this.form.paper_trading; }
      if (this.isIbkr)   { p.gateway_host = this.form.gateway_host; p.gateway_port = parseInt(this.form.gateway_port); p.client_id = parseInt(this.form.client_id); p.paper_trading = this.form.paper_trading; }
      return p;
    },
    async onSymbolSearch() {
      clearTimeout(this.symbolTimer);
      if (!this.symbolQuery.trim()) { this.symbolResults = []; return; }
      this.symbolTimer = setTimeout(async () => {
        this.symbolResults = await api.searchSymbols(
          this.exchangeId || `${this.accountId}_${this.type}`,
          this.symbolQuery,
          this.payload()
        );
      }, 250);
    },
    async testConn() {
      this.testing = true;
      const id = this.exchangeId ?? `${this.accountId}_${this.type}`;
      await api.testConnection(id, this.payload());
      this.testing = false;
    },
    async setupIbeam() {
      if (!this.ibkrUser.trim() || !this.ibkrPass.trim()) {
        toast('Enter IBKR username and password', 'error');
        return;
      }
      this.ibkrSetting = true;
      const id = this.exchangeId ?? `${this.accountId}_${this.type}`;
      const res = await api.ibkrSetup(id, this.ibkrUser, this.ibkrPass, this.form.paper_trading);
      if (res?.port) {
        this.form.gateway_port = res.port;
        this.form.gateway_host = '127.0.0.1';
        this.ibkrContainerRunning = true;
        this.ibkrUser = '';
        this.ibkrPass = '';
      }
      this.ibkrSetting = false;
    },
    async stopIbeam() {
      this.ibkrSetting = true;
      const id = this.exchangeId ?? `${this.accountId}_${this.type}`;
      const ok = await api.ibkrStop(id);
      if (ok) {
        this.ibkrContainerRunning = false;
        this.form.gateway_port = this.form.paper_trading ? 7497 : 7496;
      }
      this.ibkrSetting = false;
    },
    async checkPositionBeforeLeverage() {
      // Check if leverage changed on Bybit and warn if position exists
      if (!this.isBybit || this.isCreate || this.form.leverage === this.originalLeverage) {
        return true; // No change, proceed
      }

      // Check for open position
      const symbol = this.form.symbol;
      if (!symbol) {
        return true; // No symbol assigned, no position possible
      }

      const result = await api.checkPosition(this.exchangeId, symbol);
      if (result?.has_position) {
        this.positionWarning = result;
        return false; // Block save
      }
      return true; // No position, proceed
    },

    async save() {
      // Check position before saving leverage change
      const canSave = await this.checkPositionBeforeLeverage();
      if (!canSave) {
        toast('⚠️  Cannot change leverage on open position. Close position first or confirm you understand the risk.', 'warn');
        return;
      }

      this.saving = true;
      const p = this.payload();
      let ok;
      if (this.isCreate) {
        p._id = `${this.accountId}_${this.type}`;
        ok = await api.saveExchange(this.accountId, p);
      } else {
        ok = await api.updateExchange(this.exchangeId, p);
      }
      this.saving = false;
      if (ok) {
        this.positionWarning = null;
        this.close();
      }
    },

    confirmLeverageChange() {
      // User confirms they want to change leverage despite open position
      this.positionWarning = null;
      this.save();
    },
  },
  watch: {
    type(nextType) {
      if (!this.isCreate) return;
      if (nextType === 'bybit') this.form.paper_trading = false;
      if (nextType === 'alpaca' || nextType === 'ibkr') this.form.paper_trading = true;
      if (nextType === 'ibkr') this.form.gateway_port = this.form.paper_trading ? 7497 : 7496;
    },
    'form.paper_trading'(paper) {
      if (this.type === 'ibkr') this.form.gateway_port = paper ? 7497 : 7496;
    },
  },
};

/* ============================================================
   SYMBOL MANAGER (inline panel)
   ============================================================ */

const SymbolManager = {
  mixins: [mixin],
  props: ['exchangeId'],
  emits: ['close'],
  data: () => ({ q: '', results: [], timer: null }),
  computed: {
    exchange() { return store.exchanges[this.exchangeId] ?? {}; },
    symbol()   { return this.exchange.symbol ?? null; },
  },
  mounted() { api.loadSymbols(this.exchangeId); },
  template: `
    <div class="symbol-panel">
      <div class="symbol-panel-head">
        <span><i class="fas fa-list"></i> Symbol — {{ (exchange.type || exchangeId).toUpperCase() }}</span>
        <button class="btn btn-sm" @click="$emit('close')">✕ Close</button>
      </div>
      <div class="symbol-search-wrap">
        <i class="fas fa-search symbol-search-icon"></i>
        <input class="symbol-search-input" v-model="q" type="text"
               placeholder="Search symbol (e.g. BTC)…"
               @input="onInput" @keydown.enter.prevent="selectFromInput"
               autocomplete="off">
        <div v-if="results.length" class="symbol-dropdown">
          <div v-for="s in results.slice(0, 25)" :key="s"
               class="symbol-dropdown-item" @mousedown.prevent="select(s)">{{ s }}</div>
        </div>
      </div>
      <div class="symbol-current">
        <div v-if="symbol" class="symbol-row">
          <span class="symbol-badge">{{ symbol }}</span>
          <button class="btn btn-sm btn-danger btn-icon" @click="clear">
            <i class="fas fa-trash"></i> Clear
          </button>
        </div>
        <div v-else class="empty-inline">No symbol configured yet.</div>
      </div>
    </div>`,
  methods: {
    onInput() {
      clearTimeout(this.timer);
      if (!this.q.trim()) { this.results = []; return; }
      this.timer = setTimeout(async () => {
        this.results = await api.searchSymbols(this.exchangeId, this.q);
      }, 250);
    },
    async select(sym) {
      const s = sym.trim().toUpperCase();
      if (!s) return;
      await api.saveSymbols(this.exchangeId, s);
      this.q = ''; this.results = [];
    },
    selectFromInput() { if (this.q.trim()) this.select(this.q); },
    async clear() {
      await api.saveSymbols(this.exchangeId, null);
    },
  },
};

/* ============================================================
   EXCHANGE CARD
   ============================================================ */

const ExchangeCard = {
  mixins: [mixin],
  components: { CToggle, CExIcon },
  props: ['exchangeId'],
  emits: ['configure'],
  data: () => ({}),
  computed: {
    ex()        { return store.exchanges[this.exchangeId] ?? {}; },
    status()    { return store.exStatus[this.exchangeId] ?? {}; },
    type()      { return (this.ex.type ?? this.exchangeId).toLowerCase(); },
    connected() { return !!this.status.connected; },
    enabled()   { return this.ex.enabled !== false; },
    symbol()    { return this.ex.symbol ?? null; },
    modeLabel() {
      const m = this.ex.trading_mode;
      const env = (this.type === 'alpaca')
        ? ((this.ex.paper_trading ?? this.ex.use_paper) ? 'Paper' : 'Live')
        : (this.ex.paper_trading ? 'Paper' : this.ex.testnet ? 'Paper' : 'Live');
      if (this.type === 'bybit') {
        const tradingMode = m ? m.charAt(0).toUpperCase() + m.slice(1) : 'Spot';
        return `${tradingMode} · ${env}`;
      }
      if (m) return m.charAt(0).toUpperCase() + m.slice(1);
      return env;
    },
  },
  template: `
    <div :class="['ex-card', enabled ? 'ex-card--on' : 'ex-card--off']">
      <div class="ex-card-head">
        <div class="ex-card-title">
          <c-ex-icon :type="type"></c-ex-icon>
          <div>
            <div class="ex-card-name">{{ (ex.type || exchangeId).toUpperCase() }}</div>
            <div class="ex-card-id">{{ exchangeId }}</div>
          </div>
        </div>
        <span :class="['badge', connected ? 'badge-success' : 'badge-neutral']">
          {{ connected ? '● Live' : '○ Offline' }}
        </span>
      </div>
      <div class="ex-card-body">
        <div class="ex-row">
          <span class="ex-label">Mode</span>
          <span class="ex-val">{{ modeLabel }}{{ ex.leverage > 1 ? ' · ' + ex.leverage + 'x' : '' }}</span>
        </div>
        <div v-if="connected && status.balances" class="ex-row">
          <span class="ex-label">Balance</span>
          <span class="ex-val ex-val--mono">{{ fmtBalance(status.balances) }}</span>
        </div>
        <div v-if="symbol" class="ex-symbol">
          <span class="symbol-badge">{{ symbol }}</span>
        </div>
      </div>
      <div class="ex-card-foot">
        <div class="ex-card-foot-l">
          <button class="btn btn-sm" @click="$emit('configure', exchangeId)">
            <i class="fas fa-cog"></i> Configure
          </button>
          <button class="btn btn-sm btn-danger btn-icon" @click="del">
            <i class="fas fa-trash"></i>
          </button>
        </div>
        <c-toggle :model-value="enabled" @update:model-value="toggle"></c-toggle>
      </div>
    </div>`,
  methods: {
    toggle(v) { api.toggleExchange(this.exchangeId, v); },
    async del() {
      if (!confirm(`Delete exchange ${this.exchangeId}? This cannot be undone.`)) return;
      await api.deleteExchange(this.exchangeId);
    },
  },
};

/* ============================================================
   PAGES
   ============================================================ */

const OverviewPage = {
  mixins: [mixin],
  computed: {
    exchanges()     { return Object.values(store.exchanges); },
    enabledCount()  { return this.exchanges.filter(e => e.enabled !== false).length; },
    signalCount()   { return store.signals.length; },
    isConnected()   { return store.status?.webhook_status === 'connected'; },
    lastSignal()    { return fmtTime(store.status?.last_signal_datetime); },
    timeSince()     { return fmtTimeSince(store.status?.time_since_last_signal); },
    recentSignals() { return store.signals.slice(0, 20); },
  },
  methods: {
    executionCounts(sig) {
      const execs = Array.isArray(sig.executions) ? sig.executions : [];
      const total = execs.length;
      const ok = execs.filter(e => !!e.success).length;
      const fail = total - ok;
      return { total, ok, fail };
    },
    statusText(sig) {
      const { total, ok, fail } = this.executionCounts(sig);
      if (total > 0) {
        if (ok > 0 && fail > 0) return 'Partial';
        if (ok > 0) return 'Executed';
        return 'Failed';
      }
      if (sig.executed) return 'Executed';
      if (sig.error) return 'Failed';
      return 'Failed';
    },
    statusClass(sig) {
      const { total, ok, fail } = this.executionCounts(sig);
      if (total > 0) {
        if (ok > 0 && fail > 0) return 'warn';
        if (ok > 0) return 'ok';
        return 'fail';
      }
      if (sig.executed) return 'ok';
      if (sig.error) return 'fail';
      return 'fail';
    },
    exchangeSummary(sig) {
      const matches = Array.isArray(sig.matched_exchanges) ? sig.matched_exchanges : [];
      if (!matches.length) return '—';
      const { total, ok, fail } = this.executionCounts(sig);
      if (total > 0) return `${ok}/${total} success${fail > 0 ? `, ${fail} fail` : ''}`;
      return `${matches.length} matched`;
    },
  },
  template: `
    <div class="page">
      <div class="stat-strip">
        <div class="stat-card">
          <div class="stat-label">Accounts</div>
          <div class="stat-val">{{ store.accounts.length }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Exchanges</div>
          <div class="stat-val">{{ exchanges.length }}</div>
        </div>
        <div class="stat-card stat-card--success">
          <div class="stat-label">Enabled</div>
          <div class="stat-val">{{ enabledCount }}</div>
        </div>
        <div class="stat-card stat-card--blue">
          <div class="stat-label">Signals 24h</div>
          <div class="stat-val">{{ signalCount }}</div>
        </div>
      </div>

      <div class="signal-hero">
        <div class="signal-hero-head">
          <div class="signal-hero-title">
            <i class="fas fa-satellite-dish"></i> TradingView Signal Monitor
          </div>
          <div class="conn-pill" :class="isConnected ? 'conn-pill--on' : ''">
            <span class="conn-dot"></span>
            {{ isConnected ? 'Connected' : 'Waiting' }}
          </div>
        </div>
        <div class="signal-stat-grid">
          <div class="signal-stat-box">
            <div class="signal-stat-ttl">Webhook</div>
            <div class="signal-stat-row">
              <span>Status</span>
              <strong :class="isConnected ? 'clr-success' : 'clr-muted'">
                {{ isConnected ? 'Active' : 'Idle' }}
              </strong>
            </div>
            <div class="signal-stat-row"><span>Last signal</span><strong>{{ lastSignal }}</strong></div>
            <div class="signal-stat-row"><span>Time since</span><strong>{{ timeSince }}</strong></div>
          </div>
          <div class="signal-stat-box">
            <div class="signal-stat-ttl">Statistics</div>
            <div class="signal-stat-row">
              <span>Total received</span><strong>{{ store.status.total_signals || 0 }}</strong>
            </div>
            <div class="signal-stat-row">
              <span>Executed</span>
              <strong class="clr-success">{{ store.status.successful_trades || 0 }}</strong>
            </div>
            <div class="signal-stat-row">
              <span>Failed</span>
              <strong class="clr-error">{{ store.status.failed_trades || 0 }}</strong>
            </div>
          </div>
        </div>
        <div class="signal-table-wrap">
          <table class="signal-table">
            <thead>
              <tr><th>Time</th><th>Symbol</th><th>Signal</th><th>Price</th><th>Exchanges</th><th>Status</th></tr>
            </thead>
            <tbody>
              <tr v-if="!recentSignals.length">
                <td colspan="6" class="td-empty">No signals in the last 24 hours</td>
              </tr>
              <tr v-for="sig in recentSignals" :key="sig.id ?? sig.timestamp">
                <td class="td-time">
                  {{ new Date(sig.datetime ?? sig.timestamp).toLocaleTimeString() }}
                  <br><span class="td-date">{{ new Date(sig.datetime ?? sig.timestamp).toLocaleDateString() }}</span>
                </td>
                <td><strong>{{ sig.symbol || '—' }}</strong></td>
                <td><span :class="['sig-badge', (sig.signal || '').toLowerCase()]">{{ sig.signal || '—' }}</span></td>
                <td>{{ sig.price ? sig.price.toFixed(2) : '—' }}</td>
                <td class="text-muted" style="font-size:12px">{{ exchangeSummary(sig) }}</td>
                <td>
                  <span :class="['sig-badge', statusClass(sig)]">
                    {{ statusText(sig) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>`,
};

/* ---- Accounts Page ---- */
const AccountsPage = {
  mixins: [mixin],
  components: { CToggle },
  inject: ['showAccountModal'],
  template: `
    <div class="page">
      <div class="page-head">
        <h2><i class="fas fa-user"></i> Accounts</h2>
        <button class="btn btn-primary" @click="showAccountModal()">
          <i class="fas fa-plus"></i> New Account
        </button>
      </div>
      <div v-if="!store.accounts.length" class="empty-state">
        <i class="fas fa-user-plus"></i>
        <div class="empty-title">No accounts yet</div>
        <p>Create your first account to get started.</p>
      </div>
      <div v-else class="accounts-grid">
        <div v-for="ac in store.accounts" :key="ac._id"
             :class="['account-card', ac.enabled !== false ? 'account-card--on' : '']">
          <div class="account-card-head">
            <div>
              <div class="account-card-name">{{ ac.name || ac._id }}</div>
              <div class="account-card-id">{{ ac._id }}</div>
            </div>
            <span :class="['badge', ac.enabled !== false ? 'badge-success' : 'badge-neutral']">
              {{ ac.enabled !== false ? 'Enabled' : 'Disabled' }}
            </span>
          </div>
          <div class="account-card-foot">
            <div style="display:flex;gap:5px;flex-wrap:wrap">
              <button class="btn btn-sm" @click="navigate('exchanges', ac._id)">
                <i class="fas fa-list"></i> Exchanges
              </button>
              <button class="btn btn-sm" @click="showAccountModal(ac)">
                <i class="fas fa-edit"></i> Edit
              </button>
              <button class="btn btn-sm btn-danger btn-icon" @click="del(ac._id)">
                <i class="fas fa-trash"></i>
              </button>
            </div>
            <c-toggle :model-value="ac.enabled !== false"
                      @update:model-value="toggle(ac._id, $event)">
            </c-toggle>
          </div>
        </div>
      </div>
    </div>`,
  methods: {
    toggle(id, enabled) {
      const ac = store.accounts.find(a => a._id === id);
      if (ac) ac.enabled = enabled;
      api.toggleAccount(id, enabled);
    },
    async del(id) {
      if (!confirm('Delete this account and all its exchanges?')) return;
      await api.deleteAccount(id);
    },
  },
};

/* ---- Exchanges Page ---- */
const ExchangesPage = {
  mixins: [mixin],
  components: { ExchangeCard },
  inject: ['showExchangeModal'],
  computed: {
    accountName() {
      return store.accounts.find(a => a._id === store.accountId)?.name ?? store.accountId ?? '';
    },
    exchangeIds() {
      if (!store.accountId) return [];
      return Object.keys(store.exchanges).filter(id => store.exchanges[id].account_id === store.accountId);
    },
  },
  watch: {
    'store.accountId': {
      immediate: true,
      handler(id) { if (id) api.loadExchangesForAccount(id); },
    },
  },
  template: `
    <div class="page">
      <div class="page-head">
        <h2>
          <i class="fas fa-exchange-alt"></i>
          Exchanges<span v-if="accountName"> — {{ accountName }}</span>
        </h2>
        <div style="display:flex;gap:8px">
          <button class="btn" @click="navigate('accounts')">
            <i class="fas fa-arrow-left"></i> Accounts
          </button>
          <button v-if="store.accountId" class="btn btn-primary"
                  @click="showExchangeModal(null, store.accountId)">
            <i class="fas fa-plus"></i> Add Exchange
          </button>
        </div>
      </div>
      <div v-if="!exchangeIds.length" class="empty-state">
        <i class="fas fa-plug"></i>
        <div class="empty-title">No exchanges yet</div>
        <p>Add an exchange account to get started.</p>
      </div>
      <div v-else class="exchange-grid">
        <exchange-card v-for="id in exchangeIds" :key="id"
                       :exchange-id="id"
                       @configure="id => showExchangeModal(id)">
        </exchange-card>
      </div>
    </div>`,
};

/* ---- Symbols & Routing Page ---- */
const SymbolsRoutingPage = {
  computed: {
    rows() {
      return Object.entries(store.exchanges).map(([id, ex]) => {
        const sym = ex.symbol ?? null;
        const type = (ex.type ?? id).toLowerCase();
        const env = (type === 'alpaca')
          ? ((ex.paper_trading ?? ex.use_paper) ? 'Paper' : 'Live')
          : (ex.paper_trading ? 'Paper' : ex.testnet ? 'Paper' : 'Live');
        return { id, type, env, sym };
      });
    },
  },
  template: `
    <div class="page">
      <div class="page-head"><h2><i class="fas fa-route"></i> Symbols &amp; Routing</h2></div>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr><th>Exchange Account</th><th>Type</th><th>Environment</th><th>Symbol</th></tr>
          </thead>
          <tbody>
            <tr v-if="!rows.length">
              <td colspan="4" class="td-empty">No symbols configured yet</td>
            </tr>
            <tr v-for="(r, i) in rows" :key="i">
              <td style="font-family:var(--mono);font-size:11px">{{ r.id }}</td>
              <td><span :class="['badge', 'badge-' + r.type]">{{ r.type.toUpperCase() }}</span></td>
              <td>{{ r.env }}</td>
              <td>
                <span v-if="r.sym" class="symbol-badge">{{ r.sym }}</span>
                <span v-else class="text-muted" style="font-style:italic;font-size:11px">None configured</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>`,
};

/* ---- Trading Settings Page ---- */
const TradingSettingsPage = {
  mixins: [mixin],
  data: () => ({ warnExisting: true, saving: false }),
  mounted() {
    this.warnExisting = store.settings.warn_existing_positions !== false;
  },
  template: `
    <div class="page">
      <div class="page-head"><h2><i class="fas fa-sliders-h"></i> Trading Settings</h2></div>
      <div class="settings-card">
        <label class="check-row">
          <input v-model="warnExisting" type="checkbox">
          Warn when an open position already exists for the symbol
        </label>
        <div class="form-actions">
          <button class="btn btn-primary" @click="save" :disabled="saving">
            {{ saving ? 'Saving…' : 'Save Settings' }}
          </button>
        </div>
      </div>
    </div>`,
  methods: {
    async save() {
      this.saving = true;
      await api.saveSettings({
        warn_existing_positions:  this.warnExisting,
      });
      this.saving = false;
    },
  },
};

/* ---- Risk Management Page ---- */
const RiskManagementPage = {
  mixins: [mixin],
  data: () => ({
    bybitStopLoss: 5.0,
    bybitPositionSize: 20.0,
    bybitFixedSize: '',
    bybitUsePct: true,
    bybitTpMode: 'ladder',
    saving: false,
    bybitTp1: 1.0,
    bybitTp2: 2.0,
    bybitTp3: 5.0,
    bybitTp4: 6.5,
    bybitTp5: 8.0,
    alpacaStopLoss: 5.0,
    alpacaTakeProfit: 5.0,
    alpacaPositionSize: 20.0,
    alpacaFixedSize: '',
    alpacaUsePct: true,
    alpacaTpMode: 'single',
  }),
  mounted() {
    const bybit = store.risk.bybit ?? {};
    const alpaca = store.risk.alpaca ?? {};
    this.bybitStopLoss = bybit.stop_loss_percent ?? 5.0;
    this.bybitPositionSize = bybit.position_size_percent ?? 20.0;
    this.bybitFixedSize = bybit.position_size_fixed ?? '';
    this.bybitUsePct = bybit.use_percentage !== false;
    this.bybitTpMode = bybit.tp_mode ?? 'ladder';
    this.bybitTp1 = bybit.tp1_target ?? 1.0;
    this.bybitTp2 = bybit.tp2_target ?? 2.0;
    this.bybitTp3 = bybit.tp3_target ?? 5.0;
    this.bybitTp4 = bybit.tp4_target ?? 6.5;
    this.bybitTp5 = bybit.tp5_target ?? 8.0;
    this.alpacaStopLoss = alpaca.stop_loss_percent ?? 5.0;
    this.alpacaTakeProfit = alpaca.take_profit_percent ?? 5.0;
    this.alpacaPositionSize = alpaca.position_size_percent ?? 20.0;
    this.alpacaFixedSize = alpaca.position_size_fixed ?? '';
    this.alpacaUsePct = alpaca.use_percentage !== false;
    this.alpacaTpMode = alpaca.tp_mode ?? 'single';
  },
  template: `
    <div class="page">
      <div class="page-head"><h2><i class="fas fa-shield-alt"></i> Risk Management</h2></div>
      <div class="settings-card">
        <h3 style="margin:0 0 12px 0;">Bybit (Ladder TP)</h3>
        <div class="field-group">
          <label>Stop Loss (%)</label>
          <input v-model.number="bybitStopLoss" type="number" min="0.1" max="20" step="0.1">
        </div>
        <div class="field-group">
          <label>Position Size (%)</label>
          <input v-model.number="bybitPositionSize" type="number" min="1" max="100" step="0.1" :disabled="!bybitUsePct">
        </div>
        <div class="field-group">
          <label>Fixed Position Size (USDT)</label>
          <input v-model.number="bybitFixedSize" type="number" min="0" step="0.01" placeholder="Used when percentage is disabled" :disabled="bybitUsePct">
        </div>
        <label class="check-row">
          <input v-model="bybitUsePct" type="checkbox">
          Use percentage-based sizing
        </label>
        <div class="field-group">
          <label>TP Mode</label>
          <select v-model="bybitTpMode">
            <option value="ladder">Ladder</option>
            <option value="none">None</option>
          </select>
        </div>

        <div class="field-group">
          <label>TP1: 1% (Close 10%)</label>
          <input v-model.number="bybitTp1" type="number" min="0.1" step="0.1">
        </div>

        <div class="field-group">
          <label>TP2: 2% (Close 15%)</label>
          <input v-model.number="bybitTp2" type="number" min="0.1" step="0.1">
        </div>

        <div class="field-group">
          <label>TP3: 5% (Close 35%)</label>
          <input v-model.number="bybitTp3" type="number" min="0.1" step="0.1">
        </div>

        <div class="field-group">
          <label>TP4: 6.5% (Close 35%)</label>
          <input v-model.number="bybitTp4" type="number" min="0.1" step="0.1">
        </div>

        <div class="field-group">
          <label>TP5: 8% (Close 50% of remaining)</label>
          <input v-model.number="bybitTp5" type="number" min="0.1" step="0.1">
        </div>

        <div style="border-top:1px solid #ddd; margin:16px 0; padding-top:16px;">
          <h3 style="margin:0 0 12px 0;">Alpaca (Single TP)</h3>
          <div class="field-group">
            <label>Stop Loss (%)</label>
            <input v-model.number="alpacaStopLoss" type="number" min="0.1" max="20" step="0.1">
          </div>
          <div class="field-group">
            <label>Take Profit (%)</label>
            <input v-model.number="alpacaTakeProfit" type="number" min="0.1" max="50" step="0.1">
          </div>
          <div class="field-group">
            <label>Position Size (%)</label>
            <input v-model.number="alpacaPositionSize" type="number" min="1" max="100" step="0.1" :disabled="!alpacaUsePct">
          </div>
          <div class="field-group">
            <label>Fixed Position Size (USD)</label>
            <input v-model.number="alpacaFixedSize" type="number" min="0" step="0.01" placeholder="Used when percentage is disabled" :disabled="alpacaUsePct">
          </div>
          <label class="check-row">
            <input v-model="alpacaUsePct" type="checkbox">
            Use percentage-based sizing
          </label>
          <div class="field-group">
            <label>TP Mode</label>
            <select v-model="alpacaTpMode">
              <option value="single">Single TP</option>
              <option value="none">None</option>
            </select>
          </div>
        </div>

        <div class="alert alert-info">
          <i class="fas fa-info-circle"></i>
          Bybit keeps ladder TP behavior. Alpaca uses single-TP mode for exchange compatibility.
        </div>

        <div class="form-actions">
          <button class="btn btn-primary" @click="save" :disabled="saving">
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
        </div>
      </div>
    </div>`,
  methods: {
    async save() {
      this.saving = true;
      await api.saveRisk({
        bybit: {
          stop_loss_percent: this.bybitStopLoss,
          position_size_percent: this.bybitPositionSize,
          position_size_fixed: (this.bybitFixedSize === '' || this.bybitFixedSize === null || this.bybitFixedSize === undefined) ? null : this.bybitFixedSize,
          use_percentage: this.bybitUsePct,
          tp_mode: this.bybitTpMode,
          tp1_target: this.bybitTp1,
          tp2_target: this.bybitTp2,
          tp3_target: this.bybitTp3,
          tp4_target: this.bybitTp4,
          tp5_target: this.bybitTp5,
        },
        alpaca: {
          stop_loss_percent: this.alpacaStopLoss,
          take_profit_percent: this.alpacaTakeProfit,
          position_size_percent: this.alpacaPositionSize,
          position_size_fixed: (this.alpacaFixedSize === '' || this.alpacaFixedSize === null || this.alpacaFixedSize === undefined) ? null : this.alpacaFixedSize,
          use_percentage: this.alpacaUsePct,
          tp_mode: this.alpacaTpMode,
        },
      });
      this.saving = false;
    },
  },
};

/* ---- Activity Page ---- */
const ActivityPage = {
  mixins: [mixin],
  data: () => ({
    filterStatus: 'all',
    filterSignal: 'all',
    filterSymbol: '',
    sortDesc: true,
    selectedLog: null,
  }),
  computed: {
    filtered() {
      let list = store.webhookLogs.slice();
      if (this.filterStatus !== 'all') list = list.filter(log => log.status === this.filterStatus);
      if (this.filterSignal !== 'all') list = list.filter(log => (log.signal ?? '').toLowerCase() === this.filterSignal.toLowerCase());
      if (this.filterSymbol) {
        const q = this.filterSymbol.toUpperCase();
        list = list.filter(log => (log.symbol ?? '').toUpperCase().includes(q));
      }
      list.sort((a, b) => this.sortDesc
        ? new Date(b.timestamp ?? 0) - new Date(a.timestamp ?? 0)
        : new Date(a.timestamp ?? 0) - new Date(b.timestamp ?? 0));
      return list;
    },
  },
  methods: {
    statusBadgeClass(status) {
      switch(status) {
        case 'success': return 'ok';
        case 'failed':  return 'fail';
        case 'skipped': return 'warn';
        case 'error':   return 'fail';
        default:        return 'skip';
      }
    },
    getStatusLabel(status) {
      return (status ?? '—').charAt(0).toUpperCase() + (status ?? '—').slice(1);
    },
    getDetail(log) {
      if (log.error) return log.error;
      if (log.failure_reason) return log.failure_reason;
      if (log.executions && log.executions.length > 0) {
        const ok = log.executions.filter(exec => !!exec.success).length;
        const total = log.executions.length;
        const fail = total - ok;
        return `${ok}/${total} succeeded${fail ? `, ${fail} failed` : ''}`;
      }
      return '—';
    },
    showDetail(log) {
      this.selectedLog = log;
    },
    closeDetail() {
      this.selectedLog = null;
    },
  },
  async mounted() {
    // Ensure webhook logs are loaded when Activity page is displayed
    await api.loadWebhookLogs();
  },
  template: `
    <div class="page">
      <div class="page-head"><h2><i class="fas fa-chart-bar"></i> Activity</h2></div>
      <div class="filter-bar">
        <div class="filter-field">
          <label>Status</label>
          <select v-model="filterStatus">
            <option value="all">All</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="skipped">Skipped</option>
            <option value="error">Error</option>
          </select>
        </div>
        <div class="filter-field">
          <label>Signal</label>
          <select v-model="filterSignal">
            <option value="all">All</option>
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
            <option value="close">Close</option>
          </select>
        </div>
        <div class="filter-field filter-field--grow">
          <label>Symbol</label>
          <input v-model="filterSymbol" type="text" placeholder="Filter symbol…">
        </div>
      </div>
      <div v-if="store.webhookLogs.length === 0" style="padding:20px; text-align:center; color:#999;">
        <p><i class="fas fa-spinner fa-spin"></i> Loading webhook logs...</p>
      </div>
      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr><th>Time</th><th>Symbol</th><th>Signal</th><th>Status</th><th>Matched Exchanges</th><th>Detail</th></tr>
          </thead>
          <tbody>
            <tr v-if="!filtered.length">
              <td colspan="6" class="td-empty">No webhook logs match your filters</td>
            </tr>
            <tr v-for="log in filtered" :key="log._id ?? log.timestamp">
              <td class="td-time">
                {{ new Date(log.timestamp).toLocaleTimeString() }}
                <br><span class="td-date">{{ new Date(log.timestamp).toLocaleDateString() }}</span>
              </td>
              <td><strong>{{ log.symbol || '—' }}</strong></td>
              <td><span :class="['sig-badge', (log.signal || '').toLowerCase()]">{{ (log.signal || '—').toUpperCase() }}</span></td>
              <td>
                <span :class="['sig-badge', statusBadgeClass(log.status)]">
                  {{ getStatusLabel(log.status) }}
                </span>
              </td>
              <td style="font-size:12px">
                <span v-if="log.matched_exchanges && log.matched_exchanges.length" class="text-muted">
                  {{ formatExchangeList(log.matched_exchanges) }}
                </span>
                <span v-else class="text-muted">—</span>
              </td>
              <td class="td-detail">
                <button v-if="log.failure_reason || log.error || (log.executions && log.executions.length)"
                        @click="showDetail(log)"
                        style="background:none; border:none; cursor:pointer; text-decoration:underline; color:inherit; padding:0;">
                  <span :class="log.status === 'success' ? 'clr-success' : log.status === 'failed' || log.status === 'error' ? 'clr-error' : ''">
                    {{ getDetail(log) }}
                  </span>
                </button>
                <span v-else :class="log.status === 'success' ? 'clr-success' : log.status === 'failed' || log.status === 'error' ? 'clr-error' : ''">
                  {{ getDetail(log) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <transition name="modal">
        <div v-if="selectedLog" class="modal-backdrop" @mousedown.self="closeDetail">
          <div class="modal-box">
            <div class="modal-head">
              <i class="fas fa-exclamation-circle"></i> {{ selectedLog.symbol }} — {{ getStatusLabel(selectedLog.status) }}
              <button class="modal-close" @click="closeDetail">×</button>
            </div>
            <div class="modal-body" style="max-height:60vh; overflow-y:auto; color:#333;">
              <div class="field-group">
                <label>Signal</label>
                <input type="text" :value="selectedLog.signal" disabled style="background:#f5f5f5; color:#333; border:1px solid #ddd; padding:8px; border-radius:4px;">
              </div>
              <div class="field-group">
                <label>Time</label>
                <input type="text" :value="new Date(selectedLog.timestamp).toLocaleString()" disabled style="background:#f5f5f5; color:#333; border:1px solid #ddd; padding:8px; border-radius:4px;">
              </div>
              <div class="field-group">
                <label>Status</label>
                <input type="text" :value="getStatusLabel(selectedLog.status)" disabled style="background:#f5f5f5; color:#333; border:1px solid #ddd; padding:8px; border-radius:4px;">
              </div>
              <div v-if="selectedLog.matched_exchanges && selectedLog.matched_exchanges.length" class="field-group">
                <label>Matched Exchanges</label>
                <input type="text" :value="formatExchangeList(selectedLog.matched_exchanges)" disabled style="background:#f5f5f5; color:#333; border:1px solid #ddd; padding:8px; border-radius:4px;">
              </div>
              <div v-if="selectedLog.failure_reason" class="field-group">
                <label style="color:#dc3545; font-weight:bold;">Failure Reason</label>
                <textarea :value="selectedLog.failure_reason" disabled style="background:#f5f5f5; color:#333; border:1px solid #ddd; padding:8px; border-radius:4px; min-height:80px; font-family:monospace; font-size:12px;"></textarea>
              </div>
              <div v-if="selectedLog.error" class="field-group">
                <label style="color:#dc3545; font-weight:bold;">Error</label>
                <textarea :value="selectedLog.error" disabled style="background:#f5f5f5; color:#333; border:1px solid #ddd; padding:8px; border-radius:4px; min-height:80px; font-family:monospace; font-size:12px;"></textarea>
              </div>
              <div v-if="selectedLog.executions && selectedLog.executions.length" class="field-group">
                <label>Execution Details</label>
                <div style="background:#f5f5f5; padding:12px; border-radius:4px; max-height:300px; overflow-y:auto; color:#333; border:1px solid #ddd;">
                  <div v-for="(exec, idx) in selectedLog.executions" :key="idx" style="margin-bottom:12px; padding-bottom:12px; border-bottom:1px solid #ddd;">
                    <div><strong>Exchange:</strong> {{ formatExchangeDisplay(exec.exchange_id || exec.exchange) }}</div>
                    <div><strong>Success:</strong> <span :style="{color: exec.success ? '#28a745' : '#dc3545'}">{{ exec.success ? '✓ YES' : '✗ NO' }}</span></div>
                    <div v-if="exec.error"><strong style="color:#dc3545;">Error:</strong> {{ exec.error }}</div>
                    <div v-if="exec.order_id"><strong>Order ID:</strong> <code style="background:#fff; padding:2px 6px; border-radius:3px; font-size:11px;">{{ exec.order_id }}</code></div>
                    <div v-if="exec.order_response"><strong>Response:</strong> <pre style="margin:4px 0; font-size:11px; overflow-x:auto; background:#fff; padding:8px; border-radius:3px;">{{ JSON.stringify(exec.order_response, null, 2) }}</pre></div>
                  </div>
                </div>
              </div>
            </div>
            <div class="modal-foot" style="padding:12px; border-top:1px solid #ddd; text-align:right;">
              <button @click="closeDetail" class="btn btn-primary">Close</button>
            </div>
          </div>
        </div>
      </transition>
    </div>`,
};

/* ---- Portfolio Page (Milestone 3) ---- */
const PortfolioPage = {
  mixins: [mixin],
  data: () => ({
    startDate: '',
    endDate: '',
    loading: false,
  }),
  computed: {
    sortedTickers() {
      return (store.portfolio || []).slice().sort((a, b) => {
        const aDate = new Date(a.last_trade || 0);
        const bDate = new Date(b.last_trade || 0);
        return bDate - aDate;
      });
    },
  },
  methods: {
    _todayIso() {
      return new Date().toISOString().slice(0, 10);
    },
    _daysAgoIso(days) {
      const d = new Date();
      d.setDate(d.getDate() - days);
      return d.toISOString().slice(0, 10);
    },
    async applyDateRange() {
      this.loading = true;
      store.portfolioFilters = {
        startDate: this.startDate,
        endDate: this.endDate,
      };
      await api.loadPortfolio({
        start_date: this.startDate,
        end_date: this.endDate,
      });
      this.loading = false;
    },
    async resetLast30Days() {
      this.startDate = this._daysAgoIso(30);
      this.endDate = this._todayIso();
      await this.applyDateRange();
    },
    navigateToTicker(ticker) {
      navigate('tickerDetail', ticker.symbol, false, null, ticker.exchange_account_id);
    },
    formatDate(dateStr) {
      if (!dateStr) return '—';
      const d = new Date(dateStr);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
    },
  },
  async mounted() {
    const savedStart = store.portfolioFilters?.startDate;
    const savedEnd = store.portfolioFilters?.endDate;
    this.startDate = savedStart || this._daysAgoIso(30);
    this.endDate = savedEnd || this._todayIso();
    await this.applyDateRange();
  },
  template: `
    <div class="page">
      <div class="page-head"><h2><i class="fas fa-chart-pie"></i> Portfolio</h2></div>
      <div class="settings-card" style="margin-bottom:16px;">
        <div style="display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap;">
          <div class="field-group" style="margin:0;">
            <label>Start Date</label>
            <input v-model="startDate" type="date" style="max-width:180px;">
          </div>
          <div class="field-group" style="margin:0;">
            <label>End Date</label>
            <input v-model="endDate" type="date" style="max-width:180px;">
          </div>
          <button class="btn btn-primary" @click="applyDateRange" :disabled="loading">
            {{ loading ? 'Loading…' : 'Apply' }}
          </button>
          <button class="btn" @click="resetLast30Days" :disabled="loading">
            Last 30 Days
          </button>
        </div>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr><th>Symbol</th><th>Exchange</th><th>Trades</th><th>Last Trade</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-if="!sortedTickers.length">
              <td colspan="5" class="td-empty">No trades in selected date range</td>
            </tr>
            <tr v-for="ticker in sortedTickers" :key="ticker.symbol + '_' + ticker.exchange_account_id">
              <td><strong>{{ ticker.symbol }}</strong></td>
              <td><span style="font-size:12px; background:#e9ecef; padding:2px 8px; border-radius:12px;">{{ ticker.exchange_label || '—' }}</span></td>
              <td>{{ ticker.trade_count }}</td>
              <td class="td-date">{{ formatDate(ticker.last_trade) }}</td>
              <td style="text-align:right">
                <button @click="navigateToTicker(ticker)" class="btn-link">View Details →</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>`,
};

/* ---- Ticker Detail Page (Milestone 3) ---- */
const TickerDetailPage = {
  mixins: [mixin],
  data: () => ({
    tickerData: null,
    loading: false,
  }),
  computed: {
    symbol() {
      return store.accountId;
    },
    exchangeAccountId() {
      return store.exchangeAccountId;
    },
  },
  methods: {
    async loadTickerData() {
      if (!this.symbol || !this.exchangeAccountId) return;
      this.loading = true;
      const data = await api.loadTickerDetail(this.symbol, this.exchangeAccountId, {
        start_date: store.portfolioFilters?.startDate || '',
        end_date: store.portfolioFilters?.endDate || '',
      });
      if (data) {
        this.tickerData = data;
      } else {
        toast('Failed to load ticker details', 'error');
      }
      this.loading = false;
    },
    backToPortfolio() {
      navigate('portfolio');
    },
    formatDate(dateStr) {
      if (!dateStr) return '—';
      const d = new Date(dateStr);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
    },
    formatPrice(price) {
      return price ? parseFloat(price).toFixed(2) : '—';
    },
    navigateToTrade(tradeId) {
      navigate('tradeDetail', this.symbol, false, tradeId, this.exchangeAccountId);
    },
  },
  async mounted() {
    await this.loadTickerData();
  },
  template: `
    <div class="page">
      <div class="page-head">
        <button @click="backToPortfolio" style="margin-right:12px; padding:0; border:none; background:none; cursor:pointer; font-size:18px;">←</button>
        <div>
          <h2 v-if="tickerData" style="margin:0;"><i class="fas fa-chart-line"></i> {{ tickerData.symbol }}</h2>
          <h2 v-else style="margin:0;"><i class="fas fa-spinner fa-spin"></i> Loading…</h2>
          <div v-if="tickerData && tickerData.exchange_label" style="font-size:13px; color:#888; margin-top:2px;">{{ tickerData.exchange_label }}</div>
        </div>
      </div>

      <div v-if="tickerData" style="display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:16px; margin-bottom:24px;">
        <div class="stat-card">
          <div class="stat-label">ROI</div>
          <div class="stat-val" :class="tickerData.roi_percent >= 0 ? 'clr-success' : 'clr-error'">
            {{ tickerData.roi_percent }}%
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Win Rate</div>
          <div class="stat-val">{{ tickerData.win_rate_percent }}%</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Total P&L</div>
          <div class="stat-val" :class="tickerData.total_pnl >= 0 ? 'clr-success' : 'clr-error'">
            {{ '$' + tickerData.total_pnl }}
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Trades</div>
          <div class="stat-val">{{ tickerData.winning_trades }}/{{ tickerData.total_trades }}</div>
        </div>
      </div>

      <div class="table-wrap" v-if="tickerData">
        <table class="data-table">
          <thead>
            <tr><th>Time</th><th>Direction</th><th>Entry</th><th>Exit</th><th>P&L</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-if="!tickerData.trades.length">
              <td colspan="6" class="td-empty">No trades for this symbol</td>
            </tr>
            <tr v-for="trade in tickerData.trades" :key="trade._id">
              <td class="td-time">
                {{ formatDate(trade.timestamp_open) }}
              </td>
              <td>
                <span :class="['sig-badge', (trade.direction || '').toLowerCase()]">
                  {{ (trade.direction || '—').toUpperCase() }}
                </span>
              </td>
              <td>{{ formatPrice(trade.entry_price) }}</td>
              <td>{{ formatPrice(trade.exit_price) }}</td>
              <td :class="trade.result_usd >= 0 ? 'clr-success' : 'clr-error'">
                {{ '$' + (trade.result_usd || 0).toFixed(2) }}
              </td>
              <td style="text-align:right">
                <button @click="navigateToTrade(trade._id)" class="btn-link">Details →</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>`,
};

/* ---- Trade Detail Page (Milestone 3) ---- */
const TradeDetailPage = {
  mixins: [mixin],
  data: () => ({
    tradeData: null,
    loading: false,
  }),
  computed: {
    symbol() {
      return store.accountId;
    },
    tradeId() {
      return store.tradeId;
    },
    exchangeAccountId() {
      return store.exchangeAccountId;
    },
  },
  methods: {
    async loadTradeData() {
      if (!this.symbol || !this.tradeId || !this.exchangeAccountId) return;
      this.loading = true;
      const data = await api.loadTradeDetail(this.symbol, this.exchangeAccountId, this.tradeId);
      if (data) {
        this.tradeData = data;
      } else {
        toast('Failed to load trade details', 'error');
      }
      this.loading = false;
    },
    backToTicker() {
      navigate('tickerDetail', this.symbol, false, null, this.exchangeAccountId);
    },
    formatDate(dateStr) {
      if (!dateStr) return '—';
      const d = new Date(dateStr);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
    },
    formatPrice(price) {
      return price ? parseFloat(price).toFixed(8) : '—';
    },
    formatResult(val, isPercent = false) {
      if (val === null || val === undefined) return '—';
      const formatted = parseFloat(val).toFixed(isPercent ? 2 : 2);
      return formatted;
    },
    getTpLabel(idx) {
      if (idx === 4) return 'TP5 (Runner)';
      return `TP${idx + 1}`;
    },
  },
  async mounted() {
    await this.loadTradeData();
  },
  template: `
    <div class="page">
      <div class="page-head">
        <button @click="backToTicker" style="margin-right:12px; padding:0; border:none; background:none; cursor:pointer; font-size:18px;">←</button>
        <h2 v-if="tradeData"><i class="fas fa-receipt"></i> Trade: {{ tradeData.symbol }}</h2>
        <h2 v-else><i class="fas fa-spinner fa-spin"></i> Loading…</h2>
      </div>

      <!-- Row 1: Symbol, Direction, Entry, Exit, Stop Loss -->
      <div v-if="tradeData" style="display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:16px; margin-bottom:16px;">
        <div class="stat-card">
          <div class="stat-label">Symbol</div>
          <div class="stat-val" style="font-size:1.1em; font-weight:700;">{{ tradeData.symbol || '—' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Direction</div>
          <div class="stat-val">
            <span :class="['sig-badge', (tradeData.direction || '').toLowerCase()]">
              {{ tradeData.direction === 'BUY' ? 'LONG' : tradeData.direction === 'SELL' ? 'SHORT' : (tradeData.direction || '—').toUpperCase() }}
            </span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Entry Price</div>
          <div class="stat-val">{{ formatPrice(tradeData.entry_price) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Exit Price</div>
          <div class="stat-val">{{ formatPrice(tradeData.exit_price) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Stop Loss</div>
          <div class="stat-val">{{ formatPrice(tradeData.stop_loss) }}</div>
        </div>
      </div>

      <!-- Row 2: P&L, R-Multiple, Duration, Max Profit, Max Drawdown -->
      <div v-if="tradeData" style="display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:16px; margin-bottom:16px;">
        <div class="stat-card">
          <div class="stat-label">Result (USD)</div>
          <div class="stat-val" :class="tradeData.result_usd >= 0 ? 'clr-success' : 'clr-error'">
            {{ '$' + formatResult(tradeData.result_usd) }}
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Result (%)</div>
          <div class="stat-val" :class="tradeData.result_percent >= 0 ? 'clr-success' : 'clr-error'">
            {{ formatResult(tradeData.result_percent) }}%
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">R-Multiple</div>
          <div class="stat-val">{{ tradeData.r_multiple !== null && tradeData.r_multiple !== undefined ? tradeData.r_multiple + 'R' : '—' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Trade Duration</div>
          <div class="stat-val">{{ tradeData.trade_duration || '—' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Max Profit</div>
          <div class="stat-val clr-success">
            {{ tradeData.max_profit_pct !== null && tradeData.max_profit_pct !== undefined ? '+' + formatResult(tradeData.max_profit_pct) + '%' : '—' }}
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Max Drawdown</div>
          <div class="stat-val clr-error">
            {{ tradeData.max_drawdown_pct !== null && tradeData.max_drawdown_pct !== undefined ? '-' + formatResult(tradeData.max_drawdown_pct) + '%' : '—' }}
          </div>
        </div>
      </div>

      <!-- Take Profit Hits -->
      <div v-if="tradeData" class="settings-card" style="margin-bottom:16px;">
        <div class="field-group" style="margin-bottom:0;">
          <label>Take Profit Hits</label>
          <div style="display:grid; grid-template-columns:repeat(5,1fr); gap:8px; margin-top:8px;">
            <div v-for="(hit, idx) in tradeData.tp_hits" :key="idx"
                 :style="{padding:'10px 8px', background: hit ? '#d4edda' : '#f5f5f5', borderRadius:'4px', textAlign:'center', border: hit ? '1px solid #28a745' : '1px solid #ddd'}">
              <div style="font-size:11px; color:#666; margin-bottom:4px;">{{ getTpLabel(idx) }}</div>
              <div style="font-weight:bold;" :style="{color: hit ? '#155724' : '#999'}">{{ hit ? '✓ YES' : '✗ NO' }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Exit Reason & Timestamps -->
      <div v-if="tradeData" class="settings-card">
        <div class="field-group">
          <label>Exit Reason</label>
          <input type="text" :value="tradeData.exit_reason || '—'" disabled style="background:#f5f5f5;">
        </div>
        <div class="field-group">
          <label>Opened</label>
          <input type="text" :value="formatDate(tradeData.timestamp_open)" disabled style="background:#f5f5f5;">
        </div>
        <div class="field-group">
          <label>Closed</label>
          <input type="text" :value="formatDate(tradeData.timestamp_close)" disabled style="background:#f5f5f5;">
        </div>
      </div>
    </div>`,
};

/* ============================================================
   ROOT APP
   ============================================================ */

const App = {
  mixins: [mixin],
  components: {
    AccountModal, ExchangeModal,
    OverviewPage, AccountsPage, ExchangesPage,
    SymbolsRoutingPage, TradingSettingsPage, RiskManagementPage, ActivityPage, PortfolioPage, TickerDetailPage, TradeDetailPage,
  },

  /** provide modal openers via inject — no store.modals hacks */
  provide() {
    return {
      showAccountModal:  (account)              => this.$refs.accountModal.show(account),
      showExchangeModal: (exchangeId, accountId) => {
        if (exchangeId) {
          const ex = store.exchanges[exchangeId];
          if (ex) this.$refs.exchangeModal.showEdit(ex);
        } else {
          this.$refs.exchangeModal.showCreate(accountId);
        }
      },
    };
  },

  data: () => ({
    navItems: [
      { id: 'overview',        icon: 'fas fa-home',       label: 'Overview' },
      { id: 'accounts',        icon: 'fas fa-user',       label: 'Accounts' },
      { id: 'symbolsRouting',  icon: 'fas fa-route',      label: 'Symbols & Routing' },
      { id: 'tradingSettings', icon: 'fas fa-sliders-h',  label: 'Trading Settings' },
      { id: 'risk',            icon: 'fas fa-shield-alt', label: 'Risk Management' },
      { id: 'portfolio',       icon: 'fas fa-chart-pie',  label: 'Portfolio' },
      { id: 'activity',        icon: 'fas fa-chart-bar',  label: 'Activity' },
    ],
    _intervals: [],
  }),

  computed: {
    enabledCount() { return Object.values(store.exchanges).filter(e => e.enabled !== false).length; },
    totalCount()   { return Object.keys(store.exchanges).length; },
    isHealthy()    { return this.enabledCount > 0; },
    statusLabel()  {
      if (this.enabledCount > 0) return `${this.enabledCount}/${this.totalCount} Active`;
      return this.totalCount > 0 ? 'None Enabled' : 'No Exchanges';
    },
  },

  template: `
    <div class="shell">
      <header class="topbar">
        <div class="topbar-brand">
          <i class="fas fa-chart-line"></i> Trading Bot
        </div>
        <div class="topbar-right">
          <span v-if="store.demoMode" class="demo-badge">DEMO</span>
          <div class="status-pill" :class="isHealthy ? 'status-pill--on' : ''">
            <span class="status-dot"></span>
            {{ statusLabel }}
          </div>
        </div>
      </header>

      <nav class="sidebar">
        <div class="sidebar-label">Navigation</div>
        <button v-for="item in navItems" :key="item.id"
                :class="['sidebar-btn', store.page === item.id ? 'sidebar-btn--active' : '']"
                @click="navigate(item.id)">
          <i :class="item.icon"></i>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <main class="main-content">
        <div v-if="store.loading" class="loading-overlay">
          <i class="fas fa-spinner fa-spin"></i> Loading…
        </div>
        <template v-else>
          <overview-page         v-show="store.page === 'overview'"></overview-page>
          <accounts-page         v-show="store.page === 'accounts'"></accounts-page>
          <exchanges-page        v-show="store.page === 'exchanges'"></exchanges-page>
          <symbols-routing-page  v-show="store.page === 'symbolsRouting'"></symbols-routing-page>
          <trading-settings-page v-show="store.page === 'tradingSettings'"></trading-settings-page>
          <risk-management-page  v-show="store.page === 'risk'"></risk-management-page>
          <portfolio-page        v-show="store.page === 'portfolio'"></portfolio-page>
          <ticker-detail-page    v-show="store.page === 'tickerDetail'"></ticker-detail-page>
          <trade-detail-page     v-show="store.page === 'tradeDetail'"></trade-detail-page>
          <activity-page         v-show="store.page === 'activity'"></activity-page>
        </template>
      </main>

      <account-modal  ref="accountModal"></account-modal>
      <exchange-modal ref="exchangeModal"></exchange-modal>

      <transition name="toast">
        <div v-if="store.toast.visible" :class="['toast', 'toast--' + store.toast.type]">
          {{ store.toast.msg }}
        </div>
      </transition>
    </div>`,

  async mounted() {
    /* Restore page from URL */
    const { page, accountId, exchangeAccountId, tradeId } = parsePath(location.pathname);
    navigate(page, accountId, true, tradeId, exchangeAccountId);

    /* Initial data load — parallel where possible */
    await Promise.all([
      api.loadAccounts(),
      api.loadSettings(),
      api.loadSignals(),
      api.loadWebhookLogs(),
      api.loadStatus(),
      api.loadExStatus(),
      api.loadPortfolio(),
    ]);

    /* Load exchanges for every account */
    await api.loadAllExchanges();

    /* If opened directly on exchanges page, load that account's data */
    if (page === 'exchanges' && accountId) {
      await api.loadExchangesForAccount(accountId);
    }

    store.loading = false;

    /* Polling — stored so we can clear them on unmount */
    this._intervals = [
      setInterval(() => api.loadSignals(),     10_000),
      setInterval(() => api.loadWebhookLogs(), 15_000),
      setInterval(() => api.loadStatus(),      10_000),
      setInterval(() => api.loadExStatus(),    30_000),
      setInterval(() => api.loadDemoData(),    10_000),
    ];
  },

  unmounted() {
    /* Always clean up intervals */
    this._intervals.forEach(clearInterval);
  },
};

/* ============================================================
   BOOT
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  createApp(App).mount('#app');
  console.log('✅ Trading Bot Dashboard mounted');
});
