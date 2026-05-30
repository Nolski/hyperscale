#!/usr/bin/env python3
"""
fetch_epoch_hardware.py -- Acquisition step.

Pulls Epoch AI's machine-learning hardware database and writes:
  - raw CSV     -> data/raw/epoch_ml_hardware_<retrieval-date>.csv
  - tidy panel  -> data/processed/epoch_hardware.csv

Epoch's database (≈300 accelerators) is the broad external corroboration of the hand-keyed
gpu_specs.csv and the source for the EFFICIENCY MARCH (perf/watt over release date) used by
the hardware-economics models. We keep release date, price, Tensor-FP16/BF16 & FP8 FLOP/s,
memory, TDP, and process node, and compute bf16 TFLOP/s per watt.

Source : Epoch AI, https://epoch.ai/data/ml_hardware.csv  (no key; CC-BY).
Fallback: if the download fails, fall back to a hand-keyed data/raw/manual/epoch_hardware.csv
(if present) with a logged warning; otherwise exit with a clear message.

Re-runnable: hits the network (with manual fallback), overwrites data/raw/ + data/processed/.
"""

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANUAL_FALLBACK = ROOT / "data" / "raw" / "manual" / "epoch_hardware.csv"
PROCESSED = ROOT / "data" / "processed"
RETRIEVED = dt.date.today().isoformat()
URL = "https://epoch.ai/data/ml_hardware.csv"

# Epoch column -> our short name.
COLS = {
    "Hardware name": "hardware",
    "Manufacturer": "manufacturer",
    "Type": "type",
    "Release date": "release_date",
    "Release price (USD)": "release_price_usd",
    "Tensor-FP16/BF16 performance (FLOP/s)": "bf16_flops",
    "FP8 performance (FLOP/s)": "fp8_flops",
    "Memory (bytes)": "memory_bytes",
    "Memory bandwidth (byte/s)": "memory_bw_bytes_s",
    "TDP (W)": "tdp_watts",
    "Process size (nm)": "process_nm",
}


def load_source() -> tuple[pd.DataFrame, str]:
    """Return (raw_dataframe, provenance_string), preferring the live download."""
    try:
        resp = requests.get(URL, timeout=60)
        resp.raise_for_status()
        (RAW / f"epoch_ml_hardware_{RETRIEVED}.csv").write_bytes(resp.content)
        from io import StringIO
        return pd.read_csv(StringIO(resp.text)), f"Epoch AI live download ({URL})"
    except Exception as e:  # network/parse failure -> manual fallback
        print(f"WARNING: Epoch download failed ({e}); trying manual fallback.", file=sys.stderr)
        if MANUAL_FALLBACK.exists():
            return pd.read_csv(MANUAL_FALLBACK, comment="#"), f"manual fallback ({MANUAL_FALLBACK.name})"
        sys.exit("ERROR: Epoch download failed and no manual fallback present "
                 f"({MANUAL_FALLBACK.relative_to(ROOT)}). Create it to proceed offline.")


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    raw, prov = load_source()
    have = {c: n for c, n in COLS.items() if c in raw.columns}
    if "Tensor-FP16/BF16 performance (FLOP/s)" not in have or "TDP (W)" not in have:
        sys.exit("ERROR: Epoch schema changed (missing BF16 perf or TDP column).")

    df = raw[list(have)].rename(columns=have).copy()
    df = df[df["bf16_flops"].notna() & df["tdp_watts"].notna()]  # ML accelerators with both

    # Derived efficiency metric + a tidy release year.
    df["bf16_tflops"] = df["bf16_flops"] / 1e12
    df["bf16_tflops_per_watt"] = (df["bf16_tflops"] / df["tdp_watts"]).round(4)
    df["release_year"] = pd.to_datetime(df["release_date"], errors="coerce").dt.year
    df["source"] = prov
    df["retrieved"] = RETRIEVED

    out = PROCESSED / "epoch_hardware.csv"
    df.sort_values("release_date").to_csv(out, index=False)

    print(f"Loaded {len(df)} ML accelerators from {prov}")
    print(f"Wrote -> {out.relative_to(ROOT)}")
    # Show the perf/watt frontier by year (corroborates gpu_specs.csv).
    recent = df[df["release_year"] >= 2017].dropna(subset=["release_year"])
    if not recent.empty:
        best = recent.sort_values("bf16_tflops_per_watt").groupby("release_year").tail(1)
        print("\nBest bf16 TFLOP/s-per-watt by year (efficiency frontier):")
        for _, r in best.sort_values("release_year").iterrows():
            print(f"  {int(r['release_year'])}  {r['hardware'][:28]:28s} "
                  f"{r['bf16_tflops_per_watt']:6.3f} TF/W  ({r['manufacturer']})")


if __name__ == "__main__":
    main()
