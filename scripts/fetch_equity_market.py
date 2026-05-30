#!/usr/bin/env python3
"""
fetch_equity_market.py -- Acquisition step (one script = one step).

Pulls equity-market data needed to test whether the "stocks are fine" story is
real or a CONCENTRATION ILLUSION, and writes:
  - raw CSV (yfinance prices) -> data/raw/yf_equity_prices_<retrieval-date>.csv
  - tidy long price panel     -> data/processed/equity_prices.csv
  - Mag-7 market-cap snapshot -> data/processed/equity_market_caps.csv
  - Shiller CAPE (from manual) -> data/processed/shiller_cape.csv

Why these series:
  * SPY (cap-weighted S&P 500) vs RSP (EQUAL-weighted S&P 500) -- their return
    divergence is the cleanest price-only measure of concentration: when SPY beats
    RSP, the index's gains are coming from its largest names, not the median stock.
  * QQQ (Nasdaq-100), SMH (semiconductors) -- the AI-tilted indices.
  * The Magnificent 7 (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA) -- the megacaps
    that dominate the cap-weighted index; current market caps quantify how top-heavy
    the market is.
These feed analyze_equity_concentration.py, which also computes the equity risk
premium using the Shiller CAPE earnings yield vs the TIPS real 10y.

Sources:
  * Prices & market caps: Yahoo Finance via the `yfinance` package (no key).
    Yahoo data is convenience/secondary-grade -- fine for index-relative analysis,
    not a statistical-agency source. Flagged Tier-2 in notes/provenance.md.
  * Shiller CAPE: MANUAL, hand-keyed approximate values (data/raw/manual/shiller_cape.csv).

Re-runnable: hits Yahoo Finance + reads the manual CAPE file, overwrites outputs.
"""

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANUAL = ROOT / "data" / "raw" / "manual" / "shiller_cape.csv"
PROCESSED = ROOT / "data" / "processed"
RETRIEVED = dt.date.today().isoformat()

# ticker -> (label, role). RSP (equal-weight S&P 500) launched 2003-04.
INDEX_TICKERS = {
    "SPY": ("sp500_capweight",  "index"),
    "RSP": ("sp500_equalweight", "index"),
    "QQQ": ("nasdaq100",        "index"),
    "SMH": ("semiconductors",   "index"),
}
MAG7 = {
    "AAPL":  "Apple",
    "MSFT":  "Microsoft",
    "GOOGL": "Alphabet",
    "AMZN":  "Amazon",
    "NVDA":  "NVIDIA",
    "META":  "Meta Platforms",
    "TSLA":  "Tesla",
}


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    all_tickers = list(INDEX_TICKERS) + list(MAG7)

    # --- Daily adjusted closes (auto_adjust folds in splits/dividends) ---
    px = yf.download(all_tickers, start="2003-01-01", auto_adjust=True,
                     progress=False)["Close"]
    if isinstance(px, pd.Series):  # single-ticker safety
        px = px.to_frame()
    px = px.dropna(how="all")
    px.to_csv(RAW / f"yf_equity_prices_{RETRIEVED}.csv")

    # tidy long panel
    long = px.reset_index().melt(id_vars="Date", var_name="ticker", value_name="close")
    long = long.dropna(subset=["close"])
    label_map = {t: lab for t, (lab, _) in INDEX_TICKERS.items()}
    label_map.update({t: MAG7[t] for t in MAG7})
    role_map = {t: role for t, (_, role) in INDEX_TICKERS.items()}
    role_map.update({t: "mag7" for t in MAG7})
    long["label"] = long["ticker"].map(label_map)
    long["role"] = long["ticker"].map(role_map)
    long = long.rename(columns={"Date": "date"}).sort_values(["ticker", "date"])
    long["retrieved"] = RETRIEVED
    out_px = PROCESSED / "equity_prices.csv"
    long.to_csv(out_px, index=False)
    print(f"  prices: {len(long):,} rows, {long['ticker'].nunique()} tickers, "
          f"through {long['date'].max().date()} -> {out_px.relative_to(ROOT)}")

    # --- Current market caps for the Mag-7 (descriptive top-heaviness) ---
    cap_rows = []
    for tkr, name in MAG7.items():
        info = yf.Ticker(tkr).info
        mc = info.get("marketCap")
        cap_rows.append({"ticker": tkr, "company": name,
                         "market_cap_usd": mc, "retrieved": RETRIEVED})
        mc_str = f"${mc/1e12:.2f}T" if mc else "n/a"
        print(f"  {tkr:6s} {name:16s} market cap {mc_str}")
    caps = pd.DataFrame(cap_rows)
    out_caps = PROCESSED / "equity_market_caps.csv"
    caps.to_csv(out_caps, index=False)
    total = caps["market_cap_usd"].dropna().sum()
    print(f"  Mag-7 combined market cap ~ ${total/1e12:.2f}T -> {out_caps.relative_to(ROOT)}")

    # --- Shiller CAPE from the manual file (validate + pass through) ---
    if not MANUAL.exists():
        sys.exit(f"ERROR: manual CAPE file missing: {MANUAL.relative_to(ROOT)}")
    cape = pd.read_csv(MANUAL, comment="#")
    if not {"year", "cape"}.issubset(cape.columns):
        sys.exit("ERROR: shiller_cape.csv must have columns year,cape,note")
    latest_cape = cape.sort_values("year").iloc[-1]["cape"]
    if not (5 <= latest_cape <= 60):
        sys.exit(f"ERROR: latest CAPE {latest_cape} out of sane range (5-60).")
    cape["source"] = "Shiller online dataset (approximate, manual); Tier-2"
    cape["retrieved"] = RETRIEVED
    out_cape = PROCESSED / "shiller_cape.csv"
    cape.to_csv(out_cape, index=False)
    print(f"  Shiller CAPE: {len(cape)} yrs, latest ~{latest_cape:.1f} "
          f"-> {out_cape.relative_to(ROOT)}")

    print(f"\nDone (retrieved {RETRIEVED}). Yahoo data is Tier-2; CAPE is manual/approximate.")


if __name__ == "__main__":
    main()
