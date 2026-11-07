import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.picks import (
    DEFAULT_HEADER_MAP,
    Zone,
    distance,
    is_stale,
    load_header_map,
    load_picks,
    rank_long_term,
    zone,
)

FAKE = Path(__file__).parent.parent / "data" / "fake_picks.csv"


@pytest.fixture
def picks():
    return {p.ticker: p for p in load_picks(FAKE)}


def test_distance_matches_sheet_formula():
    # (level - price) / price; positive means price is below the level
    assert distance(110, 100) == pytest.approx(0.10)
    assert distance(80, 100) == pytest.approx(-0.20)
    assert distance(None, 100) is None


def test_parses_money_percent_and_dates(picks):
    a = picks["FAKEA"]
    assert a.exposure_pct == 4.0
    assert a.priority == 3
    assert a.updated == date(2026, 9, 1)


def test_long_term_filter(picks):
    assert picks["FAKEA"].is_long_term          # Infinity + flag
    assert picks["FAKEB"].is_long_term          # Trend but flagged Top LT
    assert picks["FAKED"].is_long_term          # Infinity, no flag
    assert not picks["FAKEE"].is_long_term      # plain Trend -> excluded


def test_tags(picks):
    assert picks["FAKEA"].tag == "Infinity + Top LT"
    assert picks["FAKEB"].tag == "Trend + Top LT"
    assert picks["FAKED"].tag == "Infinity"


@pytest.mark.parametrize(
    "ticker, expected",
    [
        ("FAKEA", Zone.ABOVE_FAIR),          # 200: fair 150 < price < too-expensive 300
        ("FAKEB", Zone.BELOW_FAIR),          # 50: cheap 45 < price <= fair 55
        ("FAKEC", Zone.DEEPLY_UNDERVALUED),  # 250 <= deeply 260
        ("FAKED", Zone.CHEAP),               # 10: deeply 8 < price <= cheap 12
        ("FAKEF", Zone.NA),                  # no valuations (like an ETF)
        ("FAKEG", Zone.TOO_EXPENSIVE),       # 300 >= too-expensive 280
    ],
)
def test_zones(picks, ticker, expected):
    assert zone(picks[ticker]) == expected


def test_stale_after_60_days(picks):
    today = date(2026, 10, 19)
    assert is_stale(picks["FAKEC"], today)       # 6/1 -> 140 days
    assert not is_stale(picks["FAKEB"], today)   # 9/20 -> 29 days


def test_ranking_priority_then_flag_then_exposure(picks):
    ranked = [p.ticker for p in rank_long_term(list(picks.values()))]
    # P3 + flag (by exposure: G 4.8 > A 4.0), P3 no flag (D),
    # P2 + flag (B), P2 no flag (C), P1 (F). FAKEE excluded (plain Trend).
    assert ranked == ["FAKEG", "FAKEA", "FAKED", "FAKEB", "FAKEC", "FAKEF"]


def test_missing_required_column_fails_loudly(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("Ticker,Price\nX,1\n")
    with pytest.raises(ValueError, match="missing required columns"):
        load_picks(bad)


def test_api_picks_and_health():
    client = TestClient(app)
    assert client.get("/healthz").json() == {"status": "ok"}
    body = client.get("/picks").json()
    assert [r["ticker"] for r in body][:2] == ["FAKEG", "FAKEA"]
    assert body[0]["rank"] == 1 and body[0]["zone"] == "Too expensive"


def test_docs_disabled_by_default():
    assert TestClient(app).get("/docs").status_code == 404


# --- header map (ConfigMap) ---------------------------------------------------

def _renamed_map(tmp_path, old, new):
    m = dict(DEFAULT_HEADER_MAP)
    m[new] = m.pop(old)
    f = tmp_path / "header-map.json"
    f.write_text(json.dumps(m))
    return f


def test_renamed_header_is_config_only(tmp_path):
    # His real sheet might call it "Price": only the map changes, not the code.
    csv_file = tmp_path / "sheet.csv"
    csv_file.write_text(FAKE.read_text().replace("Current Price", "Price", 1))
    hm = load_header_map(str(_renamed_map(tmp_path, "Current Price", "Price")))
    picks = {p.ticker: p for p in load_picks(csv_file, hm)}
    assert picks["FAKEA"].price == 200.0


def test_required_columns_follow_the_map(tmp_path):
    # Map says the price column is "Price", but the sheet still says "Current Price".
    hm = load_header_map(str(_renamed_map(tmp_path, "Current Price", "Price")))
    with pytest.raises(ValueError, match=r"missing required columns: \['Price'\]"):
        load_picks(FAKE, hm)


@pytest.mark.parametrize(
    "bad",
    [
        {"Ticker": "ticker"},                                   # fields missing
        {**DEFAULT_HEADER_MAP, "Shares": "shares"},             # unknown field
        {**DEFAULT_HEADER_MAP, "Price 2": "price"},             # field mapped twice
        ["not", "an", "object"],
    ],
)
def test_bad_header_map_fails_loudly(tmp_path, bad):
    f = tmp_path / "header-map.json"
    f.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_header_map(str(f))


def test_header_map_file_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HEADER_MAP_FILE", str(_renamed_map(tmp_path, "Ticker", "Symbol")))
    assert load_header_map()["Symbol"] == "ticker"
