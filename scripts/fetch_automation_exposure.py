#!/usr/bin/env python3
"""
fetch_automation_exposure.py -- Acquisition step (Question 3c, labor).

Pulls occupation-level LLM-exposure scores and writes:
  - raw CSV          -> data/raw/gpts_occ_level_<retrieval-date>.csv
  - tidy SOC panel   -> data/processed/automation_exposure.csv

Source: Eloundou, Manning, Mishkin & Rock, "GPTs are GPTs: Labor market impact
potential of LLMs" (Science, 2024). Occupation-level exposure ratings, released
at github.com/openai/GPTs-are-GPTs (data/occ_level.csv). Machine-readable, free.

Exposure measures (share of an occupation's tasks that LLMs can materially speed
up): alpha = LLM alone; beta = alpha + tasks reachable with LLM-powered software;
gamma = a wider inclusive measure. `human_rating_*` are human-annotator scores,
`dv_rating_*` are GPT-4 scores. The analysis uses human_rating_beta as the
headline measure (cite the method explicitly -- it is one of several; see
notes/provenance.md for Anthropic Economic Index / Frey-Osborne as alternatives).

Codes are O*NET-SOC (e.g. 11-1011.00); this script maps them to 6-digit SOC
(11-1011) to join with BLS OEWS, averaging where several O*NET-SOC roll up to
one SOC code.

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

URL = "https://raw.githubusercontent.com/openai/GPTs-are-GPTs/main/data/occ_level.csv"
RATING_COLS = ["dv_rating_alpha", "dv_rating_beta", "dv_rating_gamma",
               "human_rating_alpha", "human_rating_beta", "human_rating_gamma"]


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    resp = requests.get(URL, timeout=60)
    resp.raise_for_status()
    raw_path = RAW / f"gpts_occ_level_{RETRIEVED}.csv"
    raw_path.write_bytes(resp.content)

    raw = pd.read_csv(raw_path)
    # O*NET-SOC (11-1011.00) -> 6-digit SOC (11-1011) for the OEWS join.
    raw["soc_code"] = raw["O*NET-SOC Code"].str.split(".").str[0]

    agg = (raw.groupby("soc_code")
           .agg(onet_occupations=("O*NET-SOC Code", "count"),
                **{c: (c, "mean") for c in RATING_COLS})
           .reset_index())
    agg["retrieved"] = RETRIEVED

    out = PROCESSED / "automation_exposure.csv"
    agg.to_csv(out, index=False)

    print(f"Raw CSV -> {raw_path.relative_to(ROOT)}  (retrieved {RETRIEVED})")
    print(f"Wrote {len(agg)} SOC occupations -> {out.relative_to(ROOT)}")
    print(f"  ({len(raw)} O*NET-SOC rows rolled up to 6-digit SOC)")
    print(f"  mean human_rating_beta across occupations: "
          f"{agg['human_rating_beta'].mean():.3f}")
    hi = agg.nlargest(3, "human_rating_beta")[["soc_code", "human_rating_beta"]]
    print("  highest-exposure SOC codes:")
    for _, r in hi.iterrows():
        print(f"    {r['soc_code']}  beta={r['human_rating_beta']:.2f}")


if __name__ == "__main__":
    main()
