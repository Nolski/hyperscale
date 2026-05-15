#!/usr/bin/env python3
"""
fetch_vc_ai.py -- Acquisition step (manual-source loader).

Loads venture-capital-into-AI figures and writes:
  - tidy panel -> data/processed/vc_ai.csv

This is the FINANCING layer of the AI-investment accounts -- equity into AI-native
firms (OpenAI, Anthropic, etc.). It is a separate flow from the real-investment
layer (hyperscaler capex); the two are NOT additive.

SOURCE IS MANUAL (Tier 3). OECD.AI hosts the data but exposes no download or API
-- the underlying Preqin data is paid. The figures are therefore hand-keyed into
  data/raw/manual/oecd_ai_vc.csv
from the OECD report "Venture capital investments in artificial intelligence
through 2025" (17 Feb 2026). This script validates and tidies that file; it does
not hit any API. To refresh, update the manual CSV from the next OECD release.

Re-runnable: reads the manual CSV, overwrites data/processed/. No network.
"""

import datetime as dt
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "data" / "raw" / "manual" / "oecd_ai_vc.csv"
PROCESSED = ROOT / "data" / "processed"
RETRIEVED = dt.date.today().isoformat()

REQUIRED_COLUMNS = {"year", "geography", "series", "value_usd_billion",
                    "share_of_total_vc_pct", "note"}


def main() -> None:
    if not MANUAL.exists():
        sys.exit(f"ERROR: manual source file missing: {MANUAL.relative_to(ROOT)}")

    df = pd.read_csv(MANUAL, comment="#")
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        sys.exit(f"ERROR: {MANUAL.name} missing columns: {sorted(missing)}")

    # Validation check: the 2025 global AI VC headline must be present and sane.
    world_2025 = df[(df.year == 2025) & (df.geography == "World") & (df.series == "ai_vc")]
    if world_2025.empty or not (200 <= world_2025.iloc[0]["value_usd_billion"] <= 320):
        sys.exit("ERROR: 2025 World ai_vc figure missing or out of expected range "
                 "(check data/raw/manual/oecd_ai_vc.csv against the OECD report).")

    df["source"] = "OECD (2026), VC investments in AI through 2025; data from Preqin"
    df["retrieved"] = RETRIEVED

    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / "vc_ai.csv"
    df.to_csv(out, index=False)

    print(f"Loaded manual source -> {out.relative_to(ROOT)}  ({len(df)} rows)")
    print(f"\n2025 AI venture capital (USD bn):")
    for _, r in df[(df.year == 2025) & (df.series == "ai_vc")].iterrows():
        share = f"  ({r['share_of_total_vc_pct']:.0f}% of global AI VC)" \
            if r["geography"] != "World" else "  (61% of all global VC)"
        val = f"${r['value_usd_billion']:.1f}B" if pd.notna(r["value_usd_billion"]) else "n/a"
        print(f"  {r['geography']:18s} {val:>9s}{share}")


if __name__ == "__main__":
    main()
