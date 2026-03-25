# ETFfolio — Home Assistant Add-on

A self-hosted ETF portfolio tracker that runs as a Home Assistant add-on.
Track purchases, monitor performance, and visualize trends — all with automatic price updates.

## Features

- **Manual position tracking** — Add ETF purchases with date, shares, and price
- **Automatic price updates** — yfinance (primary) + Alpha Vantage (fallback)
- **Split handling** — Automatically detects and adjusts for ETF splits
- **Performance analytics** — P/L, day change, time-range charts (1D → ALL)
- **Portfolio allocation** — By ETF and by category
- **European UCITS support** — EMIM, IWDA, VWCE, and more out of the box
- **EUR base currency** — Configurable to USD/GBP/CHF
- **HA Ingress** — Embedded in your Home Assistant sidebar

## Architecture

```
┌─────────────────────────────────────────────┐
│  Home Assistant Supervisor                   │
│  ┌───────────────────────────────────────┐  │
│  │  ETFfolio Docker Container            │  │
│  │                                       │  │
│  │  ┌─────────┐    ┌──────────────────┐  │  │
│  │  │ FastAPI  │───▶│ SQLite (WAL)     │  │  │
│  │  │ :8099   │    │ /data/etffolio.db │  │  │
│  │  └────┬────┘    └──────────────────┘  │  │
│  │       │                               │  │
│  │  ┌────┴────────────────────────────┐  │  │
│  │  │ Static Frontend (Vite build)    │  │  │
│  │  │ React SPA served by FastAPI     │  │  │
│  │  └─────────────────────────────────┘  │  │
│  │                                       │  │
│  │  ┌─────────────────────────────────┐  │  │
│  │  │ APScheduler (background)        │  │  │
│  │  │ → yfinance / Alpha Vantage      │  │  │
│  │  └─────────────────────────────────┘  │  │
│  └───────────────────────────────────────┘  │
│         ▲ Ingress (port 8099)               │
└─────────┴───────────────────────────────────┘
```

## Config Options (auto-generated UI in HA)

| Option | Default | Description |
|---|---|---|
| `price_source` | `yfinance` | `yfinance`, `alpha_vantage`, or `both` |
| `alpha_vantage_api_key` | _(empty)_ | Required if using Alpha Vantage |
| `update_interval_hours` | `6` | Price fetch frequency (1-24h) |
| `currency` | `EUR` | Display currency |
| `log_level` | `info` | Logging verbosity |

## API Endpoints

### Holdings
- `GET /api/holdings` — List all holdings with computed P/L
- `POST /api/holdings` — Add a new position
- `PUT /api/holdings/{id}` — Update a position
- `DELETE /api/holdings/{id}` — Remove a position

### Portfolio
- `GET /api/portfolio/summary` — Aggregate stats (value, P/L, day change)
- `GET /api/portfolio/history?range=1Y` — Daily value/cost for charting

### Prices
- `GET /api/prices/{ticker}` — Full price history
- `GET /api/prices/{ticker}/latest` — Current price
- `POST /api/fetch/{ticker}` — Manual refresh for one ticker
- `POST /api/fetch` — Refresh all tickers

### ETFs
- `GET /api/etfs` — All known ETF metadata
- `GET /api/etfs/known` — Ticker autocomplete map
- `GET /api/splits/{ticker}` — Split history

## Pre-configured European UCITS ETFs

| Ticker | Yahoo | Name |
|---|---|---|
| EMIM | EMIM.AS | iShares Core MSCI EM IMI |
| IWDA | IWDA.AS | iShares Core MSCI World |
| VWCE | VWCE.DE | Vanguard FTSE All-World |
| IUSN | IUSN.DE | iShares MSCI World Small Cap |
| CSPX | CSPX.L | iShares Core S&P 500 |
| AGGH | AGGH.AS | iShares Core Global Agg Bond |

Add any ETF by ticker — yfinance resolves it automatically.

## Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
DB_PATH=./dev.db uvicorn main:app --reload --port 8099

# Frontend
cd frontend
npm install
npm run dev
```

## License

MIT
