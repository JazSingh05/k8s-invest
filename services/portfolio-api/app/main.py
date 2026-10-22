"""portfolio-api: serves the author's long-term picks, ranked, with valuation zones."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from app.picks import Zone, distance, is_stale, load_picks, rank_long_term, zone

PICKS_CSV = Path(os.environ.get("PICKS_CSV", "data/fake_picks.csv"))
# Interactive docs are a map of the API; off unless explicitly enabled.
ENABLE_DOCS = os.environ.get("ENABLE_DOCS", "false").lower() == "true"

app = FastAPI(
    title="portfolio-api",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)


class RankedPick(BaseModel):
    rank: int
    ticker: str
    tag: str
    priority: int | None
    exposure_pct: float | None
    timely_buy: bool
    price: float | None
    zone: Zone
    to_fair_value: float | None
    to_cheap: float | None
    to_too_expensive: float | None
    stale: bool


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/picks", response_model=list[RankedPick])
def picks() -> list[RankedPick]:
    today = date.today()
    ranked = rank_long_term(load_picks(PICKS_CSV))
    return [
        RankedPick(
            rank=i,
            ticker=p.ticker,
            tag=p.tag,
            priority=p.priority,
            exposure_pct=p.exposure_pct,
            timely_buy=p.timely_buy,
            price=p.price,
            zone=zone(p),
            to_fair_value=distance(p.fair_value, p.price),
            to_cheap=distance(p.cheap, p.price),
            to_too_expensive=distance(p.too_expensive, p.price),
            stale=is_stale(p, today),
        )
        for i, p in enumerate(ranked, start=1)
    ]
