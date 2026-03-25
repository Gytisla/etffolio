"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class HoldingCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20, description="ETF ticker symbol")
    shares: float = Field(..., gt=0, description="Number of shares/units")
    purchase_date: str = Field(..., description="Purchase date (YYYY-MM-DD)")
    purchase_price: float = Field(..., gt=0, description="Price per share at purchase")
    brokerage_fee: float = Field(default=0, ge=0, description="Brokerage fee")
    stamp_duty: float = Field(default=0, ge=0, description="Stamp duty / tax")
    notes: str = Field(default="", max_length=500)


class HoldingUpdate(BaseModel):
    ticker: Optional[str] = None
    shares: Optional[float] = Field(None, gt=0)
    purchase_date: Optional[str] = None
    purchase_price: Optional[float] = Field(None, gt=0)
    brokerage_fee: Optional[float] = Field(None, ge=0)
    stamp_duty: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None


class HoldingResponse(BaseModel):
    id: int
    ticker: str
    shares: float
    purchase_date: str
    purchase_price: float
    notes: str
    created_at: str
    updated_at: str
    # Computed fields (added by the API)
    adjusted_shares: Optional[float] = None
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    brokerage_fee: float = 0
    stamp_duty: float = 0
    cost_basis: Optional[float] = None
    total_cost: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    etf_name: Optional[str] = None
    category: Optional[str] = None


class PortfolioSummary(BaseModel):
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float
    day_change: float
    day_change_pct: float
    num_positions: int
    num_records: int
    last_updated: Optional[str] = None


class PricePoint(BaseModel):
    date: str
    close: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[int] = None


class PortfolioHistoryPoint(BaseModel):
    date: str
    value: float
    cost: float


class FetchResult(BaseModel):
    ticker: str
    source: Optional[str]
    prices_stored: int
    splits_stored: int
    error: Optional[str]
