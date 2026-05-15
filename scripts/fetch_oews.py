#!/usr/bin/env python3
"""
fetch_oews.py -- Acquisition step (Question 3c, labor).

Pulls the BLS Occupational Employment and Wage Statistics (OEWS) national file
and writes:
  - raw zip           -> data/raw/bls_oesm24nat_<retrieval-date>.zip
  - tidy occupation panel -> data/processed/oews_occupations.csv

OEWS gives employment and wages for every detailed US occupation -- the base
the automation-exposure analysis weights by. Latest release: May 2024 estimates.

Source : BLS OEWS, https://www.bls.gov/oes/  (national file oesm24nat.zip)
No API key; BLS requires a descriptive User-Agent for file downloads.

Re-runnable: downloads the file, overwrites data/raw/ + data/processed/.
"""

import datetime as dt
import io
import os
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RETRIEVED = dt.date.today().isoformat()

URL = "https://www.bls.gov/oes/special-requests/oesm24nat.zip"


def user_agent() -> str:
    # BLS asks for a descriptive UA with contact info; reuse the SEC one.
    return os.environ.get("SEC_EDGAR_USER_AGENT", "").strip() or \
        "hyperscaling research (contact unset)"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    resp = requests.get(URL, headers={"User-Agent": user_agent()}, timeout=120)
    resp.raise_for_status()
    raw_path = RAW / f"bls_oesm24nat_{RETRIEVED}.zip"
    raw_path.write_bytes(resp.content)

    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        xlsx = [n for n in z.namelist() if n.lower().endswith((".xlsx", ".xls"))]
        if not xlsx:
            sys.exit(f"ERROR: no spreadsheet inside {URL}")
        with z.open(xlsx[0]) as f:
            raw = pd.read_excel(f, engine="openpyxl", dtype=str)

    # Detailed occupations only (O_GROUP == 'detailed'); 'total' is the all-jobs row.
    detailed = raw[raw["O_GROUP"] == "detailed"].copy()
    total_emp = pd.to_numeric(raw.loc[raw["O_GROUP"] == "total", "TOT_EMP"],
                              errors="coerce").iloc[0]

    df = pd.DataFrame({
        "soc_code": detailed["OCC_CODE"].str.strip(),
        "occupation": detailed["OCC_TITLE"].str.strip(),
        # OEWS suppresses some cells ('*', '**', '#'); coerce to numeric/NaN.
        "total_employment": pd.to_numeric(detailed["TOT_EMP"], errors="coerce"),
        "median_annual_wage": pd.to_numeric(detailed["A_MEDIAN"], errors="coerce"),
        "retrieved": RETRIEVED,
    }).dropna(subset=["total_employment"]).sort_values("soc_code")

    out = PROCESSED / "oews_occupations.csv"
    df.to_csv(out, index=False)

    covered = df["total_employment"].sum()
    print(f"Raw zip -> {raw_path.relative_to(ROOT)}  (retrieved {RETRIEVED})")
    print(f"Wrote {len(df)} detailed occupations -> {out.relative_to(ROOT)}")
    print(f"  total US employment (OEWS 'total' row): {total_emp:,.0f}")
    print(f"  covered by detailed occupations:        {covered:,.0f} "
          f"({covered / total_emp * 100:.1f}%)")
    print(f"  occupations missing a median wage: "
          f"{df['median_annual_wage'].isna().sum()}")
    big = df.nlargest(3, "total_employment")
    print("  largest occupations:")
    for _, r in big.iterrows():
        print(f"    {r['soc_code']}  {r['occupation'][:42]:42s} "
              f"{r['total_employment']:,.0f}")


if __name__ == "__main__":
    main()
