"""Long-term pick rules: parse the sheet export, filter, rank, and classify valuation zones.

Pure functions only — no web framework, no I/O beyond reading the CSV — so every
rule is unit-testable. The rules are deterministic and use only the author's own
numbers; nothing here invents a score or an opinion.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path

# Sheet header -> internal field. Columns are matched by HEADER NAME, not position,
# so the real sheet can add/reorder columns without breaking us.
# (Moves to a ConfigMap in step 3.)
HEADER_MAP = {
    "Ticker": "ticker",
    "Exposure %": "exposure_pct",
    "Timeframe": "timeframe",
    "Priority Ranking": "priority",
    "Top Long Term Pick": "top_long_term",
    "Timely Buy Now": "timely_buy",
    "Current Price": "price",
    "Fair Value": "fair_value",
    "Cheap Valuation": "cheap",
    "Deeply Undervalued": "deeply_undervalued",
    "Too Expensive": "too_expensive",
    "Update Date": "updated",
}

STALE_AFTER_DAYS = 60


class Zone(str, Enum):
    DEEPLY_UNDERVALUED = "Deeply undervalued"
    CHEAP = "Cheap"
    BELOW_FAIR = "Below fair"
    ABOVE_FAIR = "Above fair"
    TOO_EXPENSIVE = "Too expensive"
    NA = "n/a"


@dataclass(frozen=True)
class Pick:
    ticker: str
    exposure_pct: float | None
    timeframe: str
    priority: int | None
    top_long_term: bool
    timely_buy: bool
    price: float | None
    fair_value: float | None
    cheap: float | None
    deeply_undervalued: float | None
    too_expensive: float | None
    updated: date | None

    @property
    def is_long_term(self) -> bool:
        return self.timeframe.lower() == "infinity" or self.top_long_term

    @property
    def tag(self) -> str:
        if self.timeframe.lower() == "infinity":
            return "Infinity + Top LT" if self.top_long_term else "Infinity"
        # Trend-timeframe pick that he also flags as a top long-term pick:
        # his trend stop still applies, so say so.
        return "Trend + Top LT" if self.top_long_term else self.timeframe


# --- parsing -----------------------------------------------------------------

def _num(raw: str) -> float | None:
    """'$117,246' -> 117246.0, '3.7%' -> 3.7, '' -> None."""
    s = raw.strip().replace("$", "").replace(",", "").replace("%", "")
    return float(s) if s else None


def _date(raw: str) -> date | None:
    s = raw.strip()
    return datetime.strptime(s, "%m/%d/%Y").date() if s else None


def parse_row(row: dict[str, str]) -> Pick:
    f = {field: (row.get(header) or "") for header, field in HEADER_MAP.items()}
    priority = _num(f["priority"])
    return Pick(
        ticker=f["ticker"].strip().upper(),
        exposure_pct=_num(f["exposure_pct"]),
        timeframe=f["timeframe"].strip(),
        priority=int(priority) if priority is not None else None,
        top_long_term=bool(f["top_long_term"].strip()),
        timely_buy=bool(f["timely_buy"].strip()),
        price=_num(f["price"]),
        fair_value=_num(f["fair_value"]),
        cheap=_num(f["cheap"]),
        deeply_undervalued=_num(f["deeply_undervalued"]),
        too_expensive=_num(f["too_expensive"]),
        updated=_date(f["updated"]),
    )


def load_picks(path: Path) -> list[Pick]:
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        missing = {"Ticker", "Timeframe", "Current Price"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"sheet is missing required columns: {sorted(missing)}")
        return [parse_row(r) for r in reader if (r.get("Ticker") or "").strip()]


# --- rules -------------------------------------------------------------------

def distance(level: float | None, price: float | None) -> float | None:
    """(level - price) / price, as the sheet computes it. Positive = price below level."""
    if level is None or not price:
        return None
    return (level - price) / price


def zone(p: Pick) -> Zone:
    if p.price is None or p.fair_value is None:
        return Zone.NA  # e.g. ETFs he doesn't value
    if p.deeply_undervalued is not None and p.price <= p.deeply_undervalued:
        return Zone.DEEPLY_UNDERVALUED
    if p.cheap is not None and p.price <= p.cheap:
        return Zone.CHEAP
    if p.price <= p.fair_value:
        return Zone.BELOW_FAIR
    if p.too_expensive is not None and p.price >= p.too_expensive:
        return Zone.TOO_EXPENSIVE
    return Zone.ABOVE_FAIR


def is_stale(p: Pick, today: date) -> bool:
    return p.updated is not None and (today - p.updated).days > STALE_AFTER_DAYS


def rank_long_term(picks: list[Pick]) -> list[Pick]:
    """Long-term picks only, by his conviction: Priority -> Top LT flag -> Exposure %."""
    return sorted(
        (p for p in picks if p.is_long_term),
        key=lambda p: (
            -(p.priority or 0),
            not p.top_long_term,
            -(p.exposure_pct or 0.0),
            p.ticker,
        ),
    )
