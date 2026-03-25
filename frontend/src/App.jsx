import { useState, useEffect, useCallback, useMemo, useRef, createContext, useContext } from "react";
import * as recharts from "recharts";
import { api } from "./api";

const {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar, CartesianGrid,
} = recharts;

// ─── FORMATTERS ──────────────────────────────────────────────
const eur = (n, currency = "EUR") =>
  n != null
    ? new Intl.NumberFormat("de-DE", { style: "currency", currency, minimumFractionDigits: 2 }).format(n)
    : "—";
const pct = (n) => (n != null ? `${n >= 0 ? "+" : ""}${n.toFixed(2)}%` : "—");
const num = (n) => (n != null ? new Intl.NumberFormat("de-DE", { maximumFractionDigits: 4 }).format(n) : "—");
const fDate = (d) =>
  new Date(d).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });

// ─── THEMES ──────────────────────────────────────────────────
const themes = {
  dark: {
    bg: "#06080d", l1: "#0c0f17", l2: "#111520", l3: "#171c2a",
    bd: "#1c2236", bdL: "#252d44",
    mint: "#34d399", mintD: "#34d39918", mintM: "#34d39950", mintG: "#34d39930",
    red: "#f87171", redD: "#f8717118",
    amber: "#fbbf24", sky: "#38bdf8", violet: "#a78bfa", rose: "#fb7185", teal: "#2dd4bf",
    t: "#e2e8f0", t2: "#94a3b8", t3: "#64748b", t4: "#1e293b",
    overlay: "rgba(0,0,0,.75)", shadow: "rgba(0,0,0,.4)",
  },
  light: {
    bg: "#f1f5f9", l1: "#e2e8f0", l2: "#ffffff", l3: "#f8fafc",
    bd: "#cbd5e1", bdL: "#94a3b8",
    mint: "#059669", mintD: "#05966918", mintM: "#05966950", mintG: "#05966930",
    red: "#dc2626", redD: "#dc262618",
    amber: "#d97706", sky: "#0284c7", violet: "#7c3aed", rose: "#e11d48", teal: "#0d9488",
    t: "#0f172a", t2: "#475569", t3: "#64748b", t4: "#cbd5e1",
    overlay: "rgba(0,0,0,.35)", shadow: "rgba(0,0,0,.1)",
  },
};
const PAL = ["#34d399", "#38bdf8", "#a78bfa", "#fbbf24", "#fb7185", "#2dd4bf", "#c084fc", "#fb923c", "#a3e635", "#67e8f9"];

const ThemeCtx = createContext(themes.dark);
const useTheme = () => useContext(ThemeCtx);

// ─── ICONS ───────────────────────────────────────────────────
const I = {
  plus: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>,
  trash: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>,
  chart: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>,
  grid: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>,
  donut: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21.21 15.89A10 10 0 118 2.83"/><path d="M22 12A10 10 0 0012 2v10z"/></svg>,
  edit: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>,
  refresh: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>,
  globe: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>,
  x: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
  bars: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>,
  sun: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>,
  moon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>,
  expand: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>,
  shrink: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/><line x1="14" y1="10" x2="21" y2="3"/><line x1="3" y1="21" x2="10" y2="14"/></svg>,
};

// ─── STAT CARD ───────────────────────────────────────────────
function Stat({ label, value, sub, accent, idx = 0 }) {
  const c = useTheme();
  const pos = sub && typeof sub === "string" && (sub.startsWith("+") || sub.includes("position"));
  const neg = sub && typeof sub === "string" && sub.startsWith("-");
  return (
    <div className={`fi d${idx + 1}`} style={{
      background: accent ? `linear-gradient(145deg,${c.mintD},${c.l2})` : c.l2,
      border: `1px solid ${accent ? c.mintM : c.bd}`,
      borderRadius: 16, padding: "20px 22px", flex: "1 1 200px", minWidth: 170,
      position: "relative", overflow: "hidden",
    }}>
      {accent && <div style={{ position: "absolute", top: -20, right: -20, width: 80, height: 80,
        background: `radial-gradient(circle,${c.mintG},transparent)`, borderRadius: "50%" }} />}
      <div style={{ fontFamily: "'Outfit'", fontSize: 12, fontWeight: 600, color: c.t3,
        textTransform: "uppercase", letterSpacing: ".1em", marginBottom: 8 }}>{label}</div>
      <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 24, fontWeight: 700,
        color: accent ? c.mint : c.t, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 13, fontWeight: 600,
        marginTop: 6, color: pos ? c.mint : neg ? c.red : c.t2 }}>{sub}</div>}
    </div>
  );
}

// ─── TABS ────────────────────────────────────────────────────
function Tabs({ tabs, active, onChange }) {
  const c = useTheme();
  return (
    <div style={{ display: "flex", gap: 4, background: c.l1, borderRadius: 14, padding: 4,
      border: `1px solid ${c.bd}`, width: "fit-content" }}>
      {tabs.map((t) => (
        <button key={t.key} onClick={() => onChange(t.key)} style={{
          fontFamily: "'Outfit'", fontSize: 15, fontWeight: 600, padding: "10px 24px",
          borderRadius: 11, border: "none", cursor: "pointer", transition: "all .25s",
          background: active === t.key ? c.mint : "transparent",
          color: active === t.key ? (c === themes.dark ? "#06080d" : "#fff") : c.t2,
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <span style={{ display: "flex", opacity: active === t.key ? 1 : 0.6 }}>{t.icon}</span>{t.label}
        </button>
      ))}
    </div>
  );
}

// ─── RANGE PILLS ─────────────────────────────────────────────
function Ranges({ active, onChange }) {
  const c = useTheme();
  return (
    <div style={{ display: "flex", gap: 4 }}>
      {["1D", "1W", "1M", "3M", "6M", "1Y", "ALL"].map((r) => (
        <button key={r} onClick={() => onChange(r)} style={{
          fontFamily: "'JetBrains Mono'", fontSize: 12, fontWeight: 700,
          padding: "7px 16px", borderRadius: 8, border: "none", cursor: "pointer", transition: "all .2s",
          background: active === r ? c.mint : c.l1,
          color: active === r ? (c === themes.dark ? "#06080d" : "#fff") : c.t2,
        }}>{r}</button>
      ))}
    </div>
  );
}

// ─── THEME TOGGLE ────────────────────────────────────────────
function ThemeToggle({ dark, onToggle }) {
  const c = useTheme();
  return (
    <button onClick={onToggle} title={dark ? "Switch to light mode" : "Switch to dark mode"}
      style={{
        display: "flex", alignItems: "center", justifyContent: "center",
        width: 42, height: 42, borderRadius: 12,
        border: `1px solid ${c.bd}`, background: c.l2, color: c.t2,
        cursor: "pointer", transition: "all .25s", flexShrink: 0,
      }}
      onMouseEnter={(e) => { e.currentTarget.style.borderColor = c.mint; e.currentTarget.style.color = c.mint; }}
      onMouseLeave={(e) => { e.currentTarget.style.borderColor = c.bd; e.currentTarget.style.color = c.t2; }}>
      {dark ? I.sun : I.moon}
    </button>
  );
}

// ─── SIDEBAR TOGGLE ──────────────────────────────────────────
function SidebarToggle() {
  const c = useTheme();
  const [hidden, setHidden] = useState(false);
  const [inHA, setInHA] = useState(false);

  const getHAElements = useCallback(() => {
    try {
      const pp = window.parent;
      if (!pp || pp === window) return null;
      const ha = pp.document.querySelector("home-assistant");
      const main = ha?.shadowRoot?.querySelector("home-assistant-main");
      const drawer = main?.shadowRoot?.querySelector("ha-drawer");
      // The toolbar lives inside the panel content area:
      // ha-drawer > [slot="appContent"] > ha-panel-iframe > shadowRoot > .toolbar / app-toolbar
      const panelIframe = drawer?.querySelector("ha-panel-iframe");
      const toolbar = panelIframe?.shadowRoot?.querySelector("div.header") 
        || panelIframe?.shadowRoot?.querySelector("app-toolbar")
        || panelIframe?.shadowRoot?.querySelector(".toolbar");
      return { drawer, toolbar };
    } catch { return null; }
  }, []);

  const setSidebar = useCallback((hide) => {
    const els = getHAElements();
    if (!els?.drawer) return;
    const { drawer, toolbar } = els;
    drawer.open = !hide;
    if (hide) {
      drawer.setAttribute("data-etffolio-hidden", "true");
      drawer.style.setProperty("--mdc-drawer-width", "0px");
      if (toolbar) toolbar.style.display = "none";
    } else {
      drawer.removeAttribute("data-etffolio-hidden");
      drawer.style.removeProperty("--mdc-drawer-width");
      if (toolbar) toolbar.style.display = "";
    }
    setHidden(hide);
  }, [getHAElements]);

  useEffect(() => {
    // HA shadow DOM may not be ready on first render — poll until found
    let attempts = 0;
    const check = () => {
      const els = getHAElements();
      if (els?.drawer) {
        setInHA(true);
        const params = new URLSearchParams(window.location.search);
        if (params.get("hide_sidebar") === "true" || params.get("kiosk") === "true") {
          setTimeout(() => setSidebar(true), 100);
        }
        return true;
      }
      return false;
    };
    if (check()) return;
    const iv = setInterval(() => {
      attempts++;
      if (check() || attempts > 20) clearInterval(iv);
    }, 250);
    return () => clearInterval(iv);
  }, [getHAElements, setSidebar]);

  if (!inHA) return null;

  return (
    <button onClick={() => setSidebar(!hidden)} title={hidden ? "Show sidebar" : "Hide sidebar"}
      style={{
        display: "flex", alignItems: "center", justifyContent: "center",
        width: 42, height: 42, borderRadius: 12,
        border: `1px solid ${c.bd}`, background: c.l2, color: c.t2,
        cursor: "pointer", transition: "all .25s", flexShrink: 0,
      }}
      onMouseEnter={(e) => { e.currentTarget.style.borderColor = c.mint; e.currentTarget.style.color = c.mint; }}
      onMouseLeave={(e) => { e.currentTarget.style.borderColor = c.bd; e.currentTarget.style.color = c.t2; }}>
      {hidden ? I.expand : I.shrink}
    </button>
  );
}

// ─── ADD MODAL ───────────────────────────────────────────────
function AddModal({ onAdd, onClose, knownTickers, editing }) {
  const c = useTheme();
  const [ticker, setTicker] = useState(editing?.ticker || "");
  const [shares, setShares] = useState(editing?.shares?.toString() || "");
  const [date, setDate] = useState(editing?.purchase_date || new Date().toISOString().split("T")[0]);
  const [price, setPrice] = useState(editing?.purchase_price?.toString() || "");
  const [brokerageFee, setBrokerageFee] = useState(editing?.brokerage_fee?.toString() || "");
  const [stampDuty, setStampDuty] = useState(editing?.stamp_duty?.toString() || "");
  const [notes, setNotes] = useState(editing?.notes || "");
  const [drop, setDrop] = useState(false);
  const [saving, setSaving] = useState(false);
  const isEdit = !!editing;
  const ref = useRef(null);
  useEffect(() => { ref.current?.focus(); }, []);

  const q = ticker.toUpperCase();
  const tickerKeys = Object.keys(knownTickers);
  const matches = useMemo(() => {
    if (!q) return tickerKeys.slice(0, 6);
    return tickerKeys.filter((k) =>
      k.includes(q) || knownTickers[k]?.toLowerCase().includes(ticker.toLowerCase())
    ).slice(0, 6);
  }, [q, ticker, tickerKeys, knownTickers]);

  const submit = async () => {
    const s = parseFloat(shares);
    const p = parseFloat(price);
    if (!q || !s || s <= 0 || !p || p <= 0) return;
    setSaving(true);
    await onAdd({
      ticker: q,
      shares: s,
      purchase_date: date,
      purchase_price: p,
      brokerage_fee: parseFloat(brokerageFee) || 0,
      stamp_duty: parseFloat(stampDuty) || 0,
      notes,
    });
    setSaving(false);
  };

  const inp = {
    fontFamily: "'JetBrains Mono'", fontSize: 14, padding: "11px 14px",
    background: c.l1, border: `1px solid ${c.bd}`, borderRadius: 8, color: c.t, outline: "none", width: "100%",
  };
  const lbl = {
    fontFamily: "'Outfit'", fontSize: 12, fontWeight: 700, color: c.t3,
    textTransform: "uppercase", letterSpacing: ".1em", marginBottom: 5, display: "block",
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: c.overlay,
      backdropFilter: "blur(12px)", display: "flex", alignItems: "center",
      justifyContent: "center", zIndex: 1000, padding: 16 }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{
        animation: "si .3s ease", background: c.l2, border: `1px solid ${c.bd}`,
        borderRadius: 20, padding: 28, width: 440, maxWidth: "100%",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 22 }}>
          <h3 style={{ fontFamily: "'Outfit'", fontSize: 20, fontWeight: 700, color: c.t,
            display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ color: c.mint }}>{isEdit ? I.edit : I.plus}</span> {isEdit ? "Edit Position" : "New Position"}
          </h3>
          <button onClick={onClose} style={{ background: "none", border: "none",
            color: c.t3, cursor: "pointer", padding: 4 }}>{I.x}</button>
        </div>

        <div style={{ marginBottom: 14, position: "relative" }}>
          <label style={lbl}>ETF Ticker</label>
          <input ref={ref} value={ticker} placeholder="EMIM, IWDA, VWCE..."
            onChange={(e) => { setTicker(e.target.value); setDrop(true); }}
            onFocus={() => setDrop(true)} onBlur={() => setTimeout(() => setDrop(false), 200)}
            disabled={isEdit}
            style={{ ...inp, textTransform: "uppercase", opacity: isEdit ? 0.6 : 1 }} />
          {drop && matches.length > 0 && !isEdit && (
            <div style={{ position: "absolute", top: "100%", left: 0, right: 0, zIndex: 10,
              background: c.l1, border: `1px solid ${c.bd}`, borderRadius: 10,
              maxHeight: 220, overflowY: "auto", marginTop: 4 }}>
              {matches.map((m) => (
                <div key={m} onClick={() => { setTicker(m); setDrop(false); }}
                  style={{ padding: "10px 14px", cursor: "pointer",
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    borderBottom: `1px solid ${c.bd}`, transition: "background .15s" }}
                  onMouseEnter={(e) => e.currentTarget.style.background = c.l3}
                  onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
                  <div>
                    <span style={{ fontFamily: "'JetBrains Mono'", fontWeight: 700, color: c.mint, fontSize: 14 }}>{m}</span>
                    <span style={{ fontFamily: "'Outfit'", fontSize: 12, color: c.t3, marginLeft: 10 }}>{knownTickers[m]}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ display: "flex", gap: 12, marginBottom: 14 }}>
          <div style={{ flex: 1 }}>
            <label style={lbl}>Shares / Units</label>
            <input value={shares} onChange={(e) => setShares(e.target.value)}
              placeholder="e.g. 30" type="number" step="0.0001" min="0" style={inp} />
          </div>
          <div style={{ flex: 1 }}>
            <label style={lbl}>Purchase Date</label>
            <input value={date} onChange={(e) => setDate(e.target.value)}
              type="date" max={new Date().toISOString().split("T")[0]} style={inp} />
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <label style={lbl}>Price per Unit</label>
          <input value={price} onChange={(e) => setPrice(e.target.value)}
            placeholder="e.g. 32.36" type="number" step="0.0001" style={inp} />
        </div>

        <div style={{ display: "flex", gap: 12, marginBottom: 14 }}>
          <div style={{ flex: 1 }}>
            <label style={lbl}>Brokerage Fee</label>
            <input value={brokerageFee} onChange={(e) => setBrokerageFee(e.target.value)}
              placeholder="0.00" type="number" step="0.01" min="0" style={inp} />
          </div>
          <div style={{ flex: 1 }}>
            <label style={lbl}>Stamp Duty</label>
            <input value={stampDuty} onChange={(e) => setStampDuty(e.target.value)}
              placeholder="0.00" type="number" step="0.01" min="0" style={inp} />
          </div>
        </div>

        <div style={{ marginBottom: 20 }}>
          <label style={lbl}>Notes (optional)</label>
          <input value={notes} onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g. Monthly DCA" maxLength={500} style={inp} />
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={onClose} style={{ flex: 1, padding: 12, borderRadius: 10,
            border: `1px solid ${c.bd}`, background: "transparent", color: c.t2,
            fontFamily: "'Outfit'", fontSize: 14, fontWeight: 600, cursor: "pointer" }}>Cancel</button>
          <button onClick={submit} disabled={saving} style={{ flex: 2, padding: 12, borderRadius: 10,
            border: "none", background: c.mint, color: "#fff", fontFamily: "'Outfit'", fontSize: 14,
            fontWeight: 700, cursor: "pointer", boxShadow: `0 4px 24px ${c.mintD}`,
            opacity: saving ? 0.6 : 1 }}>
            {saving ? "Saving..." : isEdit ? "Save Changes" : "Add Position"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── HOLDINGS TABLE ──────────────────────────────────────────
function HoldingsTable({ holdings, onDelete, onEdit }) {
  const c = useTheme();
  if (!holdings.length) return (
    <div style={{ textAlign: "center", padding: "60px 20px", fontFamily: "'Outfit'" }}>
      <div style={{ fontSize: 52, marginBottom: 14, opacity: 0.2 }}>📈</div>
      <div style={{ fontSize: 18, fontWeight: 600, color: c.t2, marginBottom: 6 }}>No positions yet</div>
      <div style={{ fontSize: 14, color: c.t3 }}>Click "Add Position" to start tracking</div>
    </div>
  );

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: "0 6px", fontFamily: "'Outfit'" }}>
        <thead><tr>
          {["ETF", "Units", "Avg Price", "Fees", "Current", "Value", "Total Cost", "P/L", "Return", ""].map((h) => (
            <th key={h} style={{ textAlign: h === "" ? "center" : "left", padding: "8px 14px",
              fontSize: 12, fontWeight: 700, color: c.t3, textTransform: "uppercase", letterSpacing: ".08em" }}>{h}</th>
          ))}
        </tr></thead>
        <tbody>
          {holdings.map((h, i) => {
            const adjShares = h.adjusted_shares ?? h.shares;
            const fees = (h.brokerage_fee || 0) + (h.stamp_duty || 0);
            const up = h.pnl != null ? h.pnl >= 0 : true;
            return (
              <tr key={h.id} className={`fi d${Math.min(i + 1, 4)}`}>
                <td style={{ padding: "14px", background: c.l1, borderRadius: "10px 0 0 10px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ width: 38, height: 38, borderRadius: 10,
                      background: `linear-gradient(135deg,${PAL[i % PAL.length]}20,${PAL[i % PAL.length]}08)`,
                      border: `1px solid ${PAL[i % PAL.length]}30`, display: "flex", alignItems: "center",
                      justifyContent: "center", fontFamily: "'JetBrains Mono'", fontSize: 11, fontWeight: 700,
                      color: PAL[i % PAL.length] }}>{h.ticker.slice(0, 2)}</div>
                    <div>
                      <div style={{ fontFamily: "'JetBrains Mono'", fontWeight: 700, color: c.t, fontSize: 15 }}>
                        {h.ticker}
                      </div>
                      <div style={{ fontSize: 12, color: c.t3 }}>{h.category || h.etf_name || "ETF"}</div>
                    </div>
                  </div>
                </td>
                <td style={{ padding: "14px", background: c.l1 }}>
                  <span style={{ fontFamily: "'JetBrains Mono'", fontSize: 14, color: c.t, fontWeight: 500 }}>{num(adjShares)}</span>
                  {adjShares !== h.shares && <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 11, color: c.t3 }}>orig: {num(h.shares)}</div>}
                </td>
                <td style={{ padding: "14px", background: c.l1 }}>
                  <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 14, color: c.t }}>{eur(h.purchase_price)}</div>
                  <div style={{ fontFamily: "'Outfit'", fontSize: 11, color: c.t3 }}>{fDate(h.purchase_date)}</div>
                </td>
                <td style={{ padding: "14px", background: c.l1 }}>
                  <span style={{ fontFamily: "'JetBrains Mono'", fontSize: 13, color: fees > 0 ? c.amber : c.t3 }}>
                    {fees > 0 ? eur(fees) : "—"}
                  </span>
                </td>
                <td style={{ padding: "14px", background: c.l1 }}>
                  <span style={{ fontFamily: "'JetBrains Mono'", fontSize: 14, color: c.t }}>{eur(h.current_price)}</span>
                </td>
                <td style={{ padding: "14px", background: c.l1 }}>
                  <span style={{ fontFamily: "'JetBrains Mono'", fontSize: 15, fontWeight: 700, color: c.t }}>{eur(h.current_value)}</span>
                </td>
                <td style={{ padding: "14px", background: c.l1 }}>
                  <span style={{ fontFamily: "'JetBrains Mono'", fontSize: 13, color: c.t2 }}>{eur(h.total_cost)}</span>
                </td>
                <td style={{ padding: "14px", background: c.l1 }}>
                  <span style={{ fontFamily: "'JetBrains Mono'", fontSize: 14, fontWeight: 600,
                    color: up ? c.mint : c.red }}>
                    {h.pnl != null ? `${h.pnl >= 0 ? "+" : ""}${eur(h.pnl)}` : "—"}
                  </span>
                </td>
                <td style={{ padding: "14px", background: c.l1 }}>
                  <span style={{ fontFamily: "'JetBrains Mono'", fontSize: 12, fontWeight: 700,
                    padding: "4px 12px", borderRadius: 20,
                    background: up ? c.mintD : c.redD, color: up ? c.mint : c.red }}>
                    {pct(h.pnl_pct)}
                  </span>
                </td>
                <td style={{ padding: "14px", background: c.l1, borderRadius: "0 10px 10px 0", textAlign: "center" }}>
                  <div style={{ display: "flex", gap: 2, justifyContent: "center" }}>
                    <button onClick={() => onEdit(h)}
                      style={{ background: "none", border: "none", color: c.t3, cursor: "pointer",
                        padding: 6, borderRadius: 6, transition: "color .2s" }}
                      onMouseEnter={(e) => e.currentTarget.style.color = c.sky}
                      onMouseLeave={(e) => e.currentTarget.style.color = c.t3}>{I.edit}</button>
                    <button onClick={() => { if (window.confirm(`Delete ${h.ticker} holding?`)) onDelete(h.id); }}
                      style={{ background: "none", border: "none", color: c.t3, cursor: "pointer",
                        padding: 6, borderRadius: 6, transition: "color .2s" }}
                      onMouseEnter={(e) => e.currentTarget.style.color = c.red}
                      onMouseLeave={(e) => e.currentTarget.style.color = c.t3}>{I.trash}</button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── PORTFOLIO CHART ─────────────────────────────────────────
function PortChart({ range }) {
  const c = useTheme();
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.getHistory(range).then((d) => {
      if (!cancelled) { setData(d); setLoading(false); }
    }).catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [range]);

  if (loading) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, color: c.t3,
      fontFamily: "'Outfit'", fontSize: 14 }}>Loading chart...</div>
  );
  if (!data.length) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, color: c.t3,
      fontFamily: "'Outfit'", fontSize: 14 }}>No history data yet. Add holdings and refresh prices.</div>
  );

  const first = data[0]?.value || 0;
  const last = data[data.length - 1]?.value || 0;
  const up = last >= first;
  const col = up ? c.mint : c.red;
  const ch = last - first;
  const chP = first > 0 ? ((last - first) / first) * 100 : 0;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 16, flexWrap: "wrap" }}>
        <span style={{ fontFamily: "'JetBrains Mono'", fontSize: 28, fontWeight: 700, color: c.t }}>{eur(last)}</span>
        <span style={{ fontFamily: "'JetBrains Mono'", fontSize: 15, fontWeight: 600, color: col }}>
          {ch >= 0 ? "+" : ""}{eur(ch)} ({pct(chP)})
        </span>
        <span style={{ fontFamily: "'Outfit'", fontSize: 12, color: c.t3 }}>
          {range === "ALL" ? "All time" : `Past ${range}`}
        </span>
      </div>
      <div style={{ width: "100%", height: 300 }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 5, right: 5, left: 5, bottom: 0 }}>
            <defs>
              <linearGradient id="gV" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={col} stopOpacity={0.25} />
                <stop offset="100%" stopColor={col} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gC" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={c.t3} stopOpacity={0.12} />
                <stop offset="100%" stopColor={c.t3} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={c.bd} strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: c.t3, fontSize: 11, fontFamily: "'JetBrains Mono'" }}
              axisLine={false} tickLine={false}
              tickFormatter={(v) => { const d = new Date(v); return `${d.getDate()}/${d.getMonth() + 1}`; }}
              interval={Math.max(1, Math.floor(data.length / 7))} />
            <YAxis tick={{ fill: c.t3, fontSize: 11, fontFamily: "'JetBrains Mono'" }}
              axisLine={false} tickLine={false} width={65}
              tickFormatter={(v) => `€${v >= 1000 ? (v / 1000).toFixed(1) + "k" : v.toFixed(0)}`} />
            <Tooltip contentStyle={{ background: c.l2, border: `1px solid ${c.bd}`, borderRadius: 10,
              fontFamily: "'JetBrains Mono'", fontSize: 13, boxShadow: `0 8px 32px ${c.shadow}` }}
              labelStyle={{ color: c.t2 }}
              formatter={(v, n) => [eur(v), n === "value" ? "Portfolio" : "Cost Basis"]} />
            <Area type="monotone" dataKey="cost" stroke={c.t3} strokeWidth={1} fill="url(#gC)" strokeDasharray="5 5" />
            <Area type="monotone" dataKey="value" stroke={col} strokeWidth={2.5} fill="url(#gV)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ─── ALLOCATION ──────────────────────────────────────────────
function Allocation({ holdings }) {
  const c = useTheme();
  const byTicker = useMemo(() => {
    const m = {};
    for (const h of holdings) {
      if (h.current_value != null) m[h.ticker] = (m[h.ticker] || 0) + h.current_value;
    }
    return Object.entries(m).map(([t, v]) => ({ ticker: t, value: Math.round(v * 100) / 100, name: t })).sort((a, b) => b.value - a.value);
  }, [holdings]);

  const byCategory = useMemo(() => {
    const m = {};
    for (const h of holdings) {
      if (h.current_value != null) {
        const cat = h.category || h.etf_name || "Other";
        m[cat] = (m[cat] || 0) + h.current_value;
      }
    }
    return Object.entries(m).map(([n, v]) => ({ name: n, value: Math.round(v * 100) / 100 })).sort((a, b) => b.value - a.value);
  }, [holdings]);

  if (!byTicker.length) return null;
  const total = byTicker.reduce((s, d) => s + d.value, 0);

  return (
    <div style={{ display: "flex", gap: 40, flexWrap: "wrap", justifyContent: "center", alignItems: "center" }}>
      <div>
        <div style={{ fontFamily: "'Outfit'", fontSize: 13, fontWeight: 700, color: c.t3,
          textTransform: "uppercase", letterSpacing: ".1em", textAlign: "center", marginBottom: 12 }}>By ETF</div>
        <div style={{ width: 200, height: 200 }}>
          <ResponsiveContainer>
            <PieChart><Pie data={byTicker} dataKey="value" nameKey="ticker" cx="50%" cy="50%"
              innerRadius={55} outerRadius={85} paddingAngle={3} strokeWidth={0}>
              {byTicker.map((_, i) => <Cell key={i} fill={PAL[i % PAL.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ background: c.l2, border: `1px solid ${c.bd}`, borderRadius: 8,
              fontFamily: "'JetBrains Mono'", fontSize: 13 }} formatter={(v) => eur(v)} /></PieChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div>
        <div style={{ fontFamily: "'Outfit'", fontSize: 13, fontWeight: 700, color: c.t3,
          textTransform: "uppercase", letterSpacing: ".1em", textAlign: "center", marginBottom: 12 }}>By Category</div>
        <div style={{ width: 200, height: 200 }}>
          <ResponsiveContainer>
            <PieChart><Pie data={byCategory} dataKey="value" nameKey="name" cx="50%" cy="50%"
              innerRadius={55} outerRadius={85} paddingAngle={3} strokeWidth={0}>
              {byCategory.map((_, i) => <Cell key={i} fill={PAL[(i + 3) % PAL.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ background: c.l2, border: `1px solid ${c.bd}`, borderRadius: 8,
              fontFamily: "'JetBrains Mono'", fontSize: 13 }} formatter={(v) => eur(v)} /></PieChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 220 }}>
        {byTicker.map((d, i) => (
          <div key={d.ticker} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 10, height: 10, borderRadius: 4, background: PAL[i % PAL.length], flexShrink: 0 }} />
            <span style={{ fontFamily: "'JetBrains Mono'", fontSize: 14, fontWeight: 700, color: c.t, width: 55 }}>{d.ticker}</span>
            <span style={{ fontFamily: "'JetBrains Mono'", fontSize: 13, color: c.t2, flex: 1 }}>{eur(d.value)}</span>
            <span style={{ fontFamily: "'JetBrains Mono'", fontSize: 12, color: c.t3,
              background: c.l1, padding: "3px 10px", borderRadius: 8 }}>{((d.value / total) * 100).toFixed(1)}%</span>
          </div>
        ))}
        <div style={{ borderTop: `1px solid ${c.bd}`, paddingTop: 10, marginTop: 4, display: "flex", justifyContent: "space-between" }}>
          <span style={{ fontFamily: "'Outfit'", fontSize: 13, fontWeight: 700, color: c.t2 }}>Total</span>
          <span style={{ fontFamily: "'JetBrains Mono'", fontSize: 14, fontWeight: 700, color: c.t }}>{eur(total)}</span>
        </div>
      </div>
    </div>
  );
}

// ─── PERFORMANCE BARS ────────────────────────────────────────
function PerfBars({ holdings }) {
  const c = useTheme();
  const data = useMemo(() => {
    const m = {};
    for (const h of holdings) {
      if (!m[h.ticker]) m[h.ticker] = { cost: 0, val: 0 };
      m[h.ticker].cost += h.total_cost || (h.shares * h.purchase_price);
      m[h.ticker].val += h.current_value || 0;
    }
    return Object.entries(m)
      .map(([t, d]) => ({ ticker: t, pnl: d.cost > 0 ? ((d.val - d.cost) / d.cost * 100) : 0 }))
      .sort((a, b) => b.pnl - a.pnl);
  }, [holdings]);

  if (!data.length) return null;
  return (
    <div style={{ width: "100%", height: Math.max(160, data.length * 52) }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 50, bottom: 5 }}>
          <CartesianGrid stroke={c.bd} strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tick={{ fill: c.t3, fontSize: 11, fontFamily: "'JetBrains Mono'" }}
            axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} />
          <YAxis type="category" dataKey="ticker"
            tick={{ fill: c.t, fontSize: 13, fontFamily: "'JetBrains Mono'", fontWeight: 700 }}
            axisLine={false} tickLine={false} width={55} />
          <Tooltip contentStyle={{ background: c.l2, border: `1px solid ${c.bd}`, borderRadius: 8,
            fontFamily: "'JetBrains Mono'", fontSize: 13 }} formatter={(v) => `${v.toFixed(2)}%`} />
          <Bar dataKey="pnl" radius={[0, 8, 8, 0]}>
            {data.map((d, i) => <Cell key={i} fill={d.pnl >= 0 ? c.mint : c.red} fillOpacity={0.75} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── POSITIONS DETAIL ─────────────────────────────────────────
const PERIOD_LABELS = [
  { key: "day", label: "Day" },
  { key: "week", label: "Week" },
  { key: "month", label: "Month" },
  { key: "3month", label: "3 Month" },
  { key: "6month", label: "6 Month" },
  { key: "year", label: "Year" },
];

function Positions({ positions, loading: posLoading }) {
  const c = useTheme();

  if (posLoading) return (
    <div style={{ textAlign: "center", padding: "40px", fontFamily: "'Outfit'", color: c.t3, fontSize: 14 }}>
      Loading positions...
    </div>
  );

  if (!positions.length) return (
    <div style={{ textAlign: "center", padding: "60px 20px", fontFamily: "'Outfit'" }}>
      <div style={{ fontSize: 52, marginBottom: 14, opacity: 0.2 }}>📊</div>
      <div style={{ fontSize: 18, fontWeight: 600, color: c.t2, marginBottom: 6 }}>No positions yet</div>
      <div style={{ fontSize: 14, color: c.t3 }}>Add holdings to see per-position performance</div>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {positions.map((pos, idx) => {
        const up = pos.total_pnl >= 0;
        return (
          <div key={pos.ticker} className={`fi d${Math.min(idx + 1, 4)}`}
            style={{ background: c.l2, border: `1px solid ${c.bd}`, borderRadius: 18,
              padding: "22px 24px", overflow: "hidden" }}>

            {/* Position header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start",
              marginBottom: 18, flexWrap: "wrap", gap: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ width: 44, height: 44, borderRadius: 12,
                  background: `linear-gradient(135deg,${PAL[idx % PAL.length]}20,${PAL[idx % PAL.length]}08)`,
                  border: `1px solid ${PAL[idx % PAL.length]}30`, display: "flex", alignItems: "center",
                  justifyContent: "center", fontFamily: "'JetBrains Mono'", fontSize: 13, fontWeight: 700,
                  color: PAL[idx % PAL.length] }}>{pos.ticker.slice(0, 2)}</div>
                <div>
                  <div style={{ fontFamily: "'JetBrains Mono'", fontWeight: 700, color: c.t, fontSize: 18 }}>
                    {pos.ticker}
                  </div>
                  <div style={{ fontSize: 13, color: c.t3, marginTop: 2 }}>
                    {pos.etf_name || pos.category || "ETF"}
                    {pos.num_lots > 1 && <span style={{ marginLeft: 8, color: c.t3,
                      fontFamily: "'JetBrains Mono'", fontSize: 11 }}>({pos.num_lots} lots)</span>}
                  </div>
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 22, fontWeight: 700, color: c.t }}>
                  {eur(pos.current_value)}
                </div>
                <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 12, color: c.t3, marginTop: 2 }}>
                  {num(pos.total_shares)} units @ {eur(pos.current_price)}
                </div>
              </div>
            </div>

            {/* P/L summary row */}
            <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
              <div style={{ padding: "12px 18px", borderRadius: 12,
                background: up ? c.mintD : c.redD, border: `1px solid ${up ? c.mintM : c.red}22`,
                flex: "1 1 160px", minWidth: 150 }}>
                <div style={{ fontFamily: "'Outfit'", fontSize: 11, fontWeight: 600, color: c.t3,
                  textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 4 }}>Total P/L</div>
                <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 20, fontWeight: 700,
                  color: up ? c.mint : c.red }}>
                  {pos.total_pnl >= 0 ? "+" : ""}{eur(pos.total_pnl)}
                </div>
                <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 13, fontWeight: 600,
                  color: up ? c.mint : c.red, marginTop: 2 }}>
                  {pct(pos.total_pnl_pct)}
                </div>
              </div>
              <div style={{ padding: "12px 18px", borderRadius: 12,
                background: c.l1, border: `1px solid ${c.bd}`,
                flex: "1 1 120px", minWidth: 120 }}>
                <div style={{ fontFamily: "'Outfit'", fontSize: 11, fontWeight: 600, color: c.t3,
                  textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 4 }}>Cost Basis</div>
                <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 16, fontWeight: 600, color: c.t }}>
                  {eur(pos.total_cost)}
                </div>
                {pos.total_fees > 0 && <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 11,
                  color: c.amber, marginTop: 2 }}>incl. {eur(pos.total_fees)} fees</div>}
              </div>
            </div>

            {/* Period change grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
              gap: 8 }}>
              {PERIOD_LABELS.map(({ key, label }) => {
                const ch = pos.changes?.[key];
                if (!ch) return (
                  <div key={key} style={{ padding: "10px 14px", borderRadius: 10,
                    background: c.l1, border: `1px solid ${c.bd}` }}>
                    <div style={{ fontFamily: "'Outfit'", fontSize: 11, fontWeight: 600, color: c.t3,
                      textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 4 }}>{label}</div>
                    <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 13, color: c.t3 }}>—</div>
                  </div>
                );
                const chUp = ch.value >= 0;
                return (
                  <div key={key} style={{ padding: "10px 14px", borderRadius: 10,
                    background: c.l1, border: `1px solid ${c.bd}` }}>
                    <div style={{ fontFamily: "'Outfit'", fontSize: 11, fontWeight: 600, color: c.t3,
                      textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 4 }}>{label}</div>
                    <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 14, fontWeight: 600,
                      color: chUp ? c.mint : c.red }}>
                      {chUp ? "+" : ""}{eur(ch.value)}
                    </div>
                    <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 11, fontWeight: 600,
                      color: chUp ? c.mint : c.red, marginTop: 1 }}>
                      {pct(ch.pct)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── TOAST ───────────────────────────────────────────────────
function Toasts({ toasts }) {
  const c = useTheme();
  if (!toasts.length) return null;
  return (
    <div style={{ position: "fixed", bottom: 20, right: 20, zIndex: 200, display: "flex", flexDirection: "column", gap: 8 }}>
      {toasts.map((t) => (
        <div key={t.id} style={{
          animation: "fi .2s ease", padding: "12px 20px", borderRadius: 10,
          fontFamily: "'JetBrains Mono'", fontSize: 13, fontWeight: 600,
          background: c.l2, border: `1px solid ${t.type === "error" ? c.red : t.type === "success" ? c.mint : c.bd}`,
          color: t.type === "error" ? c.red : t.type === "success" ? c.mint : c.t,
          boxShadow: `0 4px 16px ${c.shadow}`,
        }}>{t.message}</div>
      ))}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════
// MAIN APP
// ═════════════════════════════════════════════════════════════
export default function App() {
  const [holdings, setHoldings] = useState([]);
  const [positions, setPositions] = useState([]);
  const [posLoading, setPosLoading] = useState(false);
  const [summary, setSummary] = useState(null);
  const [knownTickers, setKnownTickers] = useState({});
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [tab, setTab] = useState("overview");
  const [range, setRange] = useState("1Y");
  const [refreshing, setRefreshing] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [dark, setDark] = useState(() => {
    try { return localStorage.getItem("etffolio-theme") !== "light"; } catch { return true; }
  });

  const c = dark ? themes.dark : themes.light;

  useEffect(() => {
    try { localStorage.setItem("etffolio-theme", dark ? "dark" : "light"); } catch {}
  }, [dark]);

  const toast = useCallback((message, type = "info") => {
    const id = Date.now();
    setToasts((t) => [...t, { id, message, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3000);
  }, []);

  const load = useCallback(async () => {
    try {
      const [h, s] = await Promise.all([api.getHoldings(), api.getSummary()]);
      setHoldings(h);
      setSummary(s);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const loadPositions = useCallback(async () => {
    setPosLoading(true);
    try {
      const p = await api.getPositions();
      setPositions(p);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setPosLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    load();
    loadPositions();
    api.getKnownTickers().then((d) => setKnownTickers(d.tickers || {})).catch(() => {});
  }, [load, loadPositions]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await api.fetchAll();
      await Promise.all([load(), loadPositions()]);
      toast("Prices updated", "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setRefreshing(false);
    }
  };

  const handleAdd = async (data) => {
    try {
      if (editing) {
        await api.updateHolding(editing.id, data);
        toast("Holding updated", "success");
      } else {
        await api.createHolding(data);
        toast("Holding added", "success");
      }
      setModal(false);
      setEditing(null);
      await Promise.all([load(), loadPositions()]);
    } catch (e) {
      toast(e.message, "error");
    }
  };

  const handleEdit = (holding) => { setEditing(holding); setModal(true); };

  const handleDelete = async (id) => {
    try {
      await api.deleteHolding(id);
      await Promise.all([load(), loadPositions()]);
      toast("Holding deleted", "success");
    } catch (e) {
      toast(e.message, "error");
    }
  };

  const stats = summary || { total_value: 0, total_cost: 0, total_pnl: 0, total_pnl_pct: 0,
    day_change: 0, day_change_pct: 0, num_positions: 0, num_records: 0, total_fees: 0, currency: "EUR" };

  if (loading) return (
    <div style={{ minHeight: "100vh", background: c.bg, display: "flex", alignItems: "center",
      justifyContent: "center", fontFamily: "'Outfit'", color: c.t2 }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>📊</div>
        Loading...
      </div>
    </div>
  );

  return (
    <ThemeCtx.Provider value={c}>
      <div style={{ minHeight: "100vh", background: c.bg, padding: "20px 24px",
        fontFamily: "'Outfit',sans-serif", color: c.t, transition: "background .3s, color .3s" }}>

        {/* HEADER */}
        <div className="fi" style={{ display: "flex", justifyContent: "space-between",
          alignItems: "center", marginBottom: 24, flexWrap: "wrap", gap: 14 }}>
          <div>
            <h1 style={{ fontSize: 26, fontWeight: 800, display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ display: "inline-flex", padding: 8,
                background: `linear-gradient(135deg,${c.mintD},${c.l2})`,
                borderRadius: 10, color: c.mint, border: `1px solid ${c.mintM}` }}>{I.chart}</span>
              <span>ETF<span style={{ color: c.mint }}>folio</span></span>
              <span style={{ fontFamily: "'JetBrains Mono'", fontSize: 11, fontWeight: 700,
                background: c.l1, color: c.t3, padding: "3px 10px", borderRadius: 6,
                border: `1px solid ${c.bd}`, marginLeft: 4 }}>{stats.currency || "EUR"}</span>
            </h1>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 5, fontSize: 13, color: c.t3, flexWrap: "wrap" }}>
              <span style={{ display: "flex" }}>{I.globe}</span>
              {stats.num_records} records · {stats.num_positions} ETFs
              {stats.total_fees > 0 && <>
                <span style={{ marginLeft: 4 }}>·</span>
                <span style={{ color: c.amber }}>{eur(stats.total_fees)} fees</span>
              </>}
              {stats.last_updated && <>
                <span style={{ marginLeft: 4 }}>·</span>
                <span>Updated {new Date(stats.last_updated).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</span>
              </>}
              {stats.update_interval_hours && <>
                <span style={{ marginLeft: 4 }}>·</span>
                <span>every {stats.update_interval_hours}h</span>
              </>}
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <SidebarToggle />
            <ThemeToggle dark={dark} onToggle={() => setDark((d) => !d)} />
            <button onClick={handleRefresh} disabled={refreshing} style={{
              display: "flex", alignItems: "center", gap: 8, padding: "11px 20px",
              borderRadius: 12, border: `1px solid ${c.bd}`, background: c.l2, color: c.t2,
              fontFamily: "'Outfit'", fontSize: 14, fontWeight: 600, cursor: "pointer",
              transition: "all .25s", opacity: refreshing ? 0.6 : 1,
            }} onMouseEnter={(e) => { if (!refreshing) e.currentTarget.style.borderColor = c.mint; }}
               onMouseLeave={(e) => { e.currentTarget.style.borderColor = c.bd; }}>
              <span style={{ display: "flex", animation: refreshing ? "spin 1s linear infinite" : "none" }}>{I.refresh}</span>
              {refreshing ? "Updating..." : "Refresh"}
            </button>
            <button onClick={() => setModal(true)} style={{
              display: "flex", alignItems: "center", gap: 8, padding: "11px 22px",
              borderRadius: 12, border: "none", background: c.mint, color: "#fff",
              fontFamily: "'Outfit'", fontSize: 14, fontWeight: 700, cursor: "pointer",
              boxShadow: `0 4px 24px ${c.mintG}`, transition: "all .25s",
            }} onMouseEnter={(e) => { e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = `0 8px 32px ${c.mintM}`; }}
               onMouseLeave={(e) => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = `0 4px 24px ${c.mintG}`; }}>
              {I.plus} Add Position
            </button>
          </div>
        </div>

        {/* STATS */}
        <div style={{ display: "flex", gap: 12, marginBottom: 22, flexWrap: "wrap" }}>
          <Stat label="Portfolio Value" value={eur(stats.total_value)} sub={pct(stats.total_pnl_pct) + " all time"} accent idx={0} />
          <Stat label="Total Invested" value={eur(stats.total_cost)} sub={`${stats.num_positions} position${stats.num_positions !== 1 ? "s" : ""}`} idx={1} />
          <Stat label="Total P/L" value={(stats.total_pnl >= 0 ? "+" : "") + eur(stats.total_pnl)} sub={pct(stats.total_pnl_pct)} idx={2} />
          <Stat label="Day Change" value={(stats.day_change >= 0 ? "+" : "") + eur(stats.day_change)} sub={pct(stats.day_change_pct)} idx={3} />
        </div>

        {/* TABS */}
        <div style={{ marginBottom: 20 }}>
          <Tabs tabs={[
            { key: "overview", label: "Overview", icon: I.chart },
            { key: "positions", label: "Positions", icon: I.bars },
            { key: "holdings", label: "Holdings", icon: I.grid },
            { key: "allocation", label: "Allocation", icon: I.donut },
          ]} active={tab} onChange={setTab} />
        </div>

        {tab === "overview" && (
          <div className="fi">
            <div style={{ background: c.l2, border: `1px solid ${c.bd}`, borderRadius: 18, padding: "20px 18px", marginBottom: 18 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
                <h3 style={{ fontSize: 16, fontWeight: 700 }}>Portfolio Performance</h3>
                <Ranges active={range} onChange={setRange} />
              </div>
              <PortChart range={range} />
            </div>
            {holdings.length > 0 && (
              <div style={{ background: c.l2, border: `1px solid ${c.bd}`, borderRadius: 18, padding: "20px 18px" }}>
                <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 14 }}>Individual Returns</h3>
                <PerfBars holdings={holdings} />
              </div>
            )}
          </div>
        )}

        {tab === "positions" && (
          <div className="fi">
            <Positions positions={positions} loading={posLoading} />
          </div>
        )}

        {tab === "holdings" && (
          <div className="fi" style={{ background: c.l2, border: `1px solid ${c.bd}`, borderRadius: 18, padding: 16 }}>
            <HoldingsTable holdings={holdings} onDelete={handleDelete} onEdit={handleEdit} />
          </div>
        )}

        {tab === "allocation" && (
          <div className="fi" style={{ background: c.l2, border: `1px solid ${c.bd}`, borderRadius: 18, padding: "24px 18px" }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20, textAlign: "center" }}>Portfolio Allocation</h3>
            <Allocation holdings={holdings} />
          </div>
        )}

        {modal && <AddModal onAdd={handleAdd} onClose={() => { setModal(false); setEditing(null); }} knownTickers={knownTickers} editing={editing} />}
        <Toasts toasts={toasts} />

        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    </ThemeCtx.Provider>
  );
}
