#!/usr/bin/env python3
"""
fetch_gpu_specs.py -- Acquisition step (manual-source loader).

Validates and tidies the hand-keyed AI-accelerator spec table and writes:
  - tidy panel -> data/processed/gpu_specs.csv

This is the backbone of the hardware-economics models (model_gpu_tco.py,
model_economic_obsolescence.py): TDP (watts), dense FLOPS by precision, memory, and
approximate price per accelerator vintage. It also carries the `country` column used by
the China-vs-US thread (NVIDIA/AMD = US; Huawei = China).

SOURCE IS MANUAL (Tier-2). Vendor datasheets + secondary reporting, hand-keyed into
  data/raw/manual/gpu_specs.csv
FLOPS are DENSE (not the headline sparse numbers); China (Huawei) rows are ESTIMATES and
flagged `verified=false`. This script validates ranges and passes the file through; it
hits no network. To refresh, edit the manual CSV.

Re-runnable: reads the manual CSV, overwrites data/processed/. No network.
"""

import datetime as dt
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "data" / "raw" / "manual" / "gpu_specs.csv"
PROCESSED = ROOT / "data" / "processed"
RETRIEVED = dt.date.today().isoformat()

REQUIRED = {"model", "vendor", "country", "year_released", "tdp_watts",
            "flops_dense_bf16_tflops", "memory_gb", "msrp_usd"}


def main() -> None:
    if not MANUAL.exists():
        sys.exit(f"ERROR: manual source file missing: {MANUAL.relative_to(ROOT)}")

    df = pd.read_csv(MANUAL, comment="#")
    missing = REQUIRED - set(df.columns)
    if missing:
        sys.exit(f"ERROR: {MANUAL.name} missing columns: {sorted(missing)}")

    # Range sanity checks (catch fat-finger errors in the hand-keyed file).
    if not df["tdp_watts"].between(100, 3000).all():
        bad = df.loc[~df["tdp_watts"].between(100, 3000), "model"].tolist()
        sys.exit(f"ERROR: TDP out of sane range (100-3000W): {bad}")
    if not df["flops_dense_bf16_tflops"].between(50, 10000).all():
        bad = df.loc[~df["flops_dense_bf16_tflops"].between(50, 10000), "model"].tolist()
        sys.exit(f"ERROR: bf16 TFLOPS out of sane range (50-10000): {bad}")
    if df["year_released"].between(2015, 2030).all() is False:
        sys.exit("ERROR: year_released out of range (2015-2030).")

    # Derived: perf-per-watt (dense bf16 TFLOPS per watt) — the efficiency metric.
    df["bf16_tflops_per_watt"] = (df["flops_dense_bf16_tflops"] / df["tdp_watts"]).round(4)

    df["retrieved"] = RETRIEVED
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / "gpu_specs.csv"
    df.to_csv(out, index=False)

    print(f"Loaded manual GPU specs -> {out.relative_to(ROOT)}  ({len(df)} accelerators)")
    print(f"\n{'Model':18s} {'ctry':5s} {'yr':>4s} {'TDP':>5s} {'bf16':>7s} {'TF/W':>6s}")
    for _, r in df.sort_values(["year_released", "model"]).iterrows():
        flag = "" if r["verified"] else "  (est)"
        print(f"  {r['model']:18s} {r['country']:5s} {int(r['year_released']):4d} "
              f"{int(r['tdp_watts']):4d}W {r['flops_dense_bf16_tflops']:6.0f} "
              f"{r['bf16_tflops_per_watt']:6.3f}{flag}")
    print("\nPerf/watt (bf16 dense) is the efficiency march; (est) = Tier-2 estimate.")


if __name__ == "__main__":
    main()
