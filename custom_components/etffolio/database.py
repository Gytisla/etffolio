"""Database layer for ETFfolio — SQLite via aiosqlite."""

import logging
from datetime import datetime
from typing import Optional

import aiosqlite

_LOGGER = logging.getLogger(__name__)


class ETFfolioDB:
    """Async SQLite database wrapper for ETFfolio."""

    def __init__(self, db_path: str) -> None:
        """Initialize with path to SQLite database."""
        self._db_path = db_path

    async def _connect(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self._db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        return db

    async def init_db(self) -> None:
        """Create tables if they don't exist."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    shares REAL NOT NULL,
                    purchase_date TEXT NOT NULL,
                    purchase_price REAL NOT NULL,
                    brokerage_fee REAL DEFAULT 0,
                    stamp_duty REAL DEFAULT 0,
                    notes TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS etf_metadata (
                    ticker TEXT PRIMARY KEY,
                    name TEXT,
                    full_name TEXT,
                    isin TEXT,
                    exchange TEXT,
                    currency TEXT DEFAULT 'EUR',
                    ter REAL,
                    category TEXT,
                    last_updated TEXT
                );

                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL NOT NULL,
                    volume INTEGER,
                    UNIQUE(ticker, date)
                );

                CREATE TABLE IF NOT EXISTS splits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    ratio REAL NOT NULL,
                    UNIQUE(ticker, date)
                );

                CREATE TABLE IF NOT EXISTS price_fetch_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    fetched_at TEXT DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_price_history_ticker_date
                    ON price_history(ticker, date);
                CREATE INDEX IF NOT EXISTS idx_holdings_ticker
                    ON holdings(ticker);
            """)
            await db.commit()

            # Migrate: add fee columns if missing
            cursor = await db.execute("PRAGMA table_info(holdings)")
            cols = {row[1] for row in await cursor.fetchall()}
            if "brokerage_fee" not in cols:
                await db.execute(
                    "ALTER TABLE holdings ADD COLUMN brokerage_fee REAL DEFAULT 0"
                )
            if "stamp_duty" not in cols:
                await db.execute(
                    "ALTER TABLE holdings ADD COLUMN stamp_duty REAL DEFAULT 0"
                )
            await db.commit()

        _LOGGER.info("Database initialized at %s", self._db_path)

    # ─── Holdings CRUD ────────────────────────────────────────

    async def add_holding(
        self,
        ticker: str,
        shares: float,
        purchase_date: str,
        purchase_price: float,
        brokerage_fee: float = 0,
        stamp_duty: float = 0,
        notes: str = "",
    ) -> dict:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """INSERT INTO holdings
                   (ticker, shares, purchase_date, purchase_price,
                    brokerage_fee, stamp_duty, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticker.upper(),
                    shares,
                    purchase_date,
                    purchase_price,
                    brokerage_fee,
                    stamp_duty,
                    notes,
                ),
            )
            await db.commit()
            row = await (
                await db.execute(
                    "SELECT * FROM holdings WHERE id = ?", (cursor.lastrowid,)
                )
            ).fetchone()
            return dict(row)

    async def get_holdings(self) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    "SELECT * FROM holdings ORDER BY purchase_date DESC"
                )
            ).fetchall()
            return [dict(r) for r in rows]

    async def delete_holding(self, holding_id: int) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM holdings WHERE id = ?", (holding_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_holding(self, holding_id: int, **kwargs) -> Optional[dict]:
        allowed = {
            "ticker", "shares", "purchase_date", "purchase_price",
            "brokerage_fee", "stamp_duty", "notes",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return None

        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [holding_id]

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                f"UPDATE holdings SET {set_clause} WHERE id = ?", values
            )
            await db.commit()
            row = await (
                await db.execute(
                    "SELECT * FROM holdings WHERE id = ?", (holding_id,)
                )
            ).fetchone()
            return dict(row) if row else None

    # ─── Price History ────────────────────────────────────────

    async def upsert_prices(self, ticker: str, prices: list[dict]) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.executemany(
                """INSERT INTO price_history
                   (ticker, date, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(ticker, date) DO UPDATE SET
                       open=excluded.open, high=excluded.high,
                       low=excluded.low, close=excluded.close,
                       volume=excluded.volume""",
                [
                    (
                        ticker,
                        p["date"],
                        p.get("open"),
                        p.get("high"),
                        p.get("low"),
                        p["close"],
                        p.get("volume"),
                    )
                    for p in prices
                ],
            )
            await db.commit()

    async def get_prices(
        self,
        ticker: str,
        start_date: str = None,
        end_date: str = None,
    ) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM price_history WHERE ticker = ?"
            params: list = [ticker]
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            query += " ORDER BY date ASC"
            rows = await (await db.execute(query, params)).fetchall()
            return [dict(r) for r in rows]

    async def get_latest_price(self, ticker: str) -> Optional[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (
                await db.execute(
                    """SELECT * FROM price_history WHERE ticker = ?
                       ORDER BY date DESC LIMIT 1""",
                    (ticker,),
                )
            ).fetchone()
            return dict(row) if row else None

    async def get_price_on_date(
        self, ticker: str, target_date: str
    ) -> Optional[float]:
        async with aiosqlite.connect(self._db_path) as db:
            row = await (
                await db.execute(
                    """SELECT close FROM price_history
                       WHERE ticker = ? AND date <= ?
                       ORDER BY date DESC LIMIT 1""",
                    (ticker, target_date),
                )
            ).fetchone()
            return row[0] if row else None

    # ─── Splits ───────────────────────────────────────────────

    async def upsert_splits(self, ticker: str, splits: list[dict]) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.executemany(
                """INSERT INTO splits (ticker, date, ratio)
                   VALUES (?, ?, ?)
                   ON CONFLICT(ticker, date) DO UPDATE SET
                       ratio=excluded.ratio""",
                [(ticker, s["date"], s["ratio"]) for s in splits],
            )
            await db.commit()

    async def get_splits(self, ticker: str) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    "SELECT * FROM splits WHERE ticker = ? ORDER BY date ASC",
                    (ticker,),
                )
            ).fetchall()
            return [dict(r) for r in rows]

    async def get_adjusted_shares(
        self, ticker: str, shares: float, purchase_date: str
    ) -> float:
        splits = await self.get_splits(ticker)
        adjusted = shares
        for s in splits:
            if purchase_date <= s["date"]:
                adjusted *= s["ratio"]
        return adjusted

    # ─── ETF Metadata ─────────────────────────────────────────

    async def upsert_etf_metadata(self, ticker: str, **kwargs) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            fields = {k: v for k, v in kwargs.items() if v is not None}
            fields["ticker"] = ticker
            fields["last_updated"] = datetime.now().isoformat()

            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            updates = ", ".join(
                f"{k}=excluded.{k}" for k in fields if k != "ticker"
            )

            await db.execute(
                f"""INSERT INTO etf_metadata ({cols}) VALUES ({placeholders})
                    ON CONFLICT(ticker) DO UPDATE SET {updates}""",
                list(fields.values()),
            )
            await db.commit()

    async def get_etf_metadata(
        self, ticker: str = None
    ) -> list[dict] | dict | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            if ticker:
                row = await (
                    await db.execute(
                        "SELECT * FROM etf_metadata WHERE ticker = ?",
                        (ticker,),
                    )
                ).fetchone()
                return dict(row) if row else None
            rows = await (
                await db.execute("SELECT * FROM etf_metadata")
            ).fetchall()
            return [dict(r) for r in rows]

    # ─── Fetch Log ────────────────────────────────────────────

    async def log_fetch(
        self, ticker: str, source: str, status: str, message: str = ""
    ) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """INSERT INTO price_fetch_log
                   (ticker, source, status, message)
                   VALUES (?, ?, ?, ?)""",
                (ticker, source, status, message),
            )
            await db.commit()
