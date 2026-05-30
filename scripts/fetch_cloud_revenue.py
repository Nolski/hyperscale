#!/usr/bin/env python3
"""
fetch_cloud_revenue.py -- Acquisition step (manual-source loader).

Validates and tidies the revenue/usage inputs for the revenue-vs-payback model and writes:
  - data/processed/cloud_segments.csv     (cloud-segment revenue + operating income)
  - data/processed/ai_native_revenue.csv  (OpenAI/Anthropic ARR over time)
  - data/processed/token_volume.csv        (Google token-volume trajectory)

cloud_segments rows with verified=true are PRIMARY: captured from SEC EDGAR 10-K filings via
the sec-edgar `get_segment_data` MCP (accession recorded). They anchor the mature-cloud
operating MARGIN (AWS ~35%, MSFT Intelligent Cloud ~42%, Google Cloud ~24%) and the AWS
revenue RAMP (the steepest real precedent for a compute-infrastructure business). The AWS
pre-2025 ramp and all ai_native/token_volume rows are Tier-2 (verified=false), from
disclosures/press.

This script hits no network; it validates the hand-keyed CSVs and passes them through. To
refresh the primary cloud figures, re-run get_segment_data for AMZN/GOOGL/MSFT.

Re-runnable: reads data/raw/manual/, overwrites data/processed/. No network.
"""

import datetime as dt
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "data" / "raw" / "manual"
PROCESSED = ROOT / "data" / "processed"
RETRIEVED = dt.date.today().isoformat()


def load_checked(name: str, required: set, check) -> pd.DataFrame:
    path = MANUAL / name
    if not path.exists():
        sys.exit(f"ERROR: missing manual source {path.relative_to(ROOT)}")
    df = pd.read_csv(path, comment="#")
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"ERROR: {name} missing columns {sorted(missing)}")
    err = check(df)
    if err:
        sys.exit(f"ERROR: {name}: {err}")
    df["retrieved"] = RETRIEVED
    return df


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)

    # --- cloud segments ---
    def chk_cloud(df):
        aws25 = df[(df.provider == "AWS") & (df.year == 2025)]
        if aws25.empty or not (120e9 <= aws25.iloc[0]["revenue_usd"] <= 140e9):
            return "AWS 2025 revenue missing or out of range (~$129B)"
        if not df["revenue_usd"].between(1e9, 3e11).all():
            return "a revenue value is out of sane range"
        return None
    cloud = load_checked("cloud_segments.csv",
                         {"provider", "year", "revenue_usd", "operating_income_usd", "verified"},
                         chk_cloud)
    cloud["operating_margin"] = (cloud["operating_income_usd"] / cloud["revenue_usd"]).round(3)
    cloud.to_csv(PROCESSED / "cloud_segments.csv", index=False)

    # --- AI-native revenue ---
    def chk_native(df):
        a = df[(df.company == "Anthropic")]
        return None if not a.empty else "no Anthropic rows"
    native = load_checked("ai_native_revenue.csv",
                          {"company", "date", "arr_usd_billion", "verified"}, chk_native)
    native.to_csv(PROCESSED / "ai_native_revenue.csv", index=False)

    # --- token volume ---
    def chk_tok(df):
        g = df[df.provider == "Google"].sort_values("period")
        if g.empty or g.iloc[-1]["tokens_per_month"] < 1e15:
            return "Google latest token volume missing or < 1 quadrillion"
        return None
    tok = load_checked("token_volume.csv",
                       {"provider", "period", "tokens_per_month", "verified"}, chk_tok)
    tok.to_csv(PROCESSED / "token_volume.csv", index=False)

    # --- console summary ---
    print("Cloud segments (latest year, PRIMARY rows from SEC):")
    latest = cloud.sort_values("year").groupby("provider").tail(1)
    for _, r in latest.sort_values("revenue_usd", ascending=False).iterrows():
        m = f"{r['operating_margin']*100:.0f}% margin" if pd.notna(r["operating_margin"]) else "n/a"
        flag = "PRIMARY" if r["verified"] else "Tier-2"
        print(f"  {r['provider']:28s} {r['year']:.0f}: ${r['revenue_usd']/1e9:6.1f}B rev, {m:>10s}  [{flag}]")
    aws = cloud[cloud.provider == "AWS"].sort_values("year")
    print(f"\nAWS ramp: ${aws.iloc[0]['revenue_usd']/1e9:.0f}B ({aws.iloc[0]['year']:.0f}) "
          f"-> ${aws.iloc[-1]['revenue_usd']/1e9:.0f}B ({aws.iloc[-1]['year']:.0f}), "
          f"{len(aws)} yrs")
    print(f"\nAI-native ARR latest: " + ", ".join(
        f"{c} ${native[native.company==c].sort_values('date').iloc[-1]['arr_usd_billion']:.0f}B"
        for c in native["company"].unique()))
    g = tok[tok.provider == "Google"].sort_values("period").iloc[-1]
    print(f"Google token volume latest: {g['tokens_per_month']/1e15:.1f} quadrillion/month ({g['period']})")
    print(f"\nWrote 3 files -> data/processed/  (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
