#!/usr/bin/env python3
"""
fetch_anthropic_economic_index.py -- Acquisition step (Question 3c, labor).

Pulls occupation-level AI-exposure scores from the Anthropic Economic Index and
writes:
  - raw CSV        -> data/raw/anthropic_job_exposure_<retrieval-date>.csv
  - tidy SOC panel -> data/processed/anthropic_exposure.csv

This is the SECOND labor-exposure method (the first is Eloundou et al., see
fetch_automation_exposure.py). The two measure different things and together
bracket the estimate:
  - Eloundou beta      -- PREDICTED exposure: share of an occupation's tasks an
                          LLM could materially speed up (expert/model judgement).
  - Anthropic observed -- OBSERVED exposure: built from actual Claude.ai usage,
                          i.e. how much AI is *currently being used* for the
                          occupation's work. Sparser, and a lower bound on
                          potential -- it reflects adoption, not capability.

Source: Anthropic Economic Index, huggingface.co/datasets/Anthropic/EconomicIndex
        -> labor_market_impacts/job_exposure.csv (CC-BY). Free, no key.
        occ_code is already 6-digit SOC -- joins directly to BLS OEWS.

Re-runnable: downloads the CSV, overwrites data/raw/ + data/processed/.
"""

import datetime as dt
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RETRIEVED = dt.date.today().isoformat()

URL = ("https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/"
       "labor_market_impacts/job_exposure.csv")


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    resp = requests.get(URL, timeout=60)
    resp.raise_for_status()
    raw_path = RAW / f"anthropic_job_exposure_{RETRIEVED}.csv"
    raw_path.write_bytes(resp.content)

    raw = pd.read_csv(raw_path)
    df = pd.DataFrame({
        "soc_code": raw["occ_code"].str.strip(),
        "occupation": raw["title"].str.strip(),
        "anthropic_observed_exposure": raw["observed_exposure"].astype(float),
        "retrieved": RETRIEVED,
    }).sort_values("soc_code")

    out = PROCESSED / "anthropic_exposure.csv"
    df.to_csv(out, index=False)

    print(f"Raw CSV -> {raw_path.relative_to(ROOT)}  (retrieved {RETRIEVED})")
    print(f"Wrote {len(df)} SOC occupations -> {out.relative_to(ROOT)}")
    print(f"  mean observed exposure: {df['anthropic_observed_exposure'].mean():.3f}")
    print(f"  occupations with zero observed usage: "
          f"{(df['anthropic_observed_exposure'] == 0).sum()}")
    hi = df.nlargest(3, "anthropic_observed_exposure")
    print("  highest observed exposure:")
    for _, r in hi.iterrows():
        print(f"    {r['anthropic_observed_exposure']:.2f}  {r['occupation']}")


if __name__ == "__main__":
    main()
