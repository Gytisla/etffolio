// Detect if running inside Home Assistant (custom component panel)
const isHA = window.location.pathname.startsWith('/etffolio_panel')
  || window.location.pathname.startsWith('/etffolio');
const BASE = isHA ? '/api/etffolio' : '';
const API_PREFIX = isHA ? '' : '/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  getHoldings: () => request(`${API_PREFIX}/holdings`),
  createHolding: (data) => request(`${API_PREFIX}/holdings`, { method: 'POST', body: JSON.stringify(data) }),
  updateHolding: (id, data) => request(`${API_PREFIX}/holdings/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteHolding: (id) => request(`${API_PREFIX}/holdings/${id}`, { method: 'DELETE' }),

  getSummary: () => request(`${API_PREFIX}/portfolio/summary`),
  getPositions: () => request(`${API_PREFIX}/portfolio/positions`),
  getHistory: (range = '1Y') => request(`${API_PREFIX}/portfolio/history?range=${range}`),

  getKnownTickers: () => request(`${API_PREFIX}/etfs/known`),
  fetchAll: () => request(`${API_PREFIX}/fetch`, { method: 'POST' }),
  fetchTicker: (ticker) => request(`${API_PREFIX}/fetch/${ticker}`, { method: 'POST' }),
};
