#!/usr/bin/env python3
"""
model_payback_montecarlo.py -- Model step (pricing the gap probabilistically).

The required-vs-achievable snapshot (model_revenue_payback.py) compares a 2030 revenue level
to a steady-state bar. This is the fairer counterpart: a multi-year DCF that gives the buildout
CREDIT for revenue earned past 2030, run as a Monte Carlo over the swing assumptions, to answer
"what is the probability the AI buildout earns its cost of capital?"

For each of N draws, sample:
  K        -- capital deployed (cumulative ~2024-2030 buildout), triangular $3.5/5.3/7.4T
  R2030    -- AI revenue reached by 2030, triangular $0.29/0.73/1.44T (the achievable S-curve)
  margin   -- steady-state operating margin, triangular 15% / 27% / 42% (thin -> MSFT-best)
  wacc     -- triangular 8% / 10% / 12%
  g_post   -- post-2030 revenue growth, triangular 10% / 20% / 35%, decaying to 3% terminal
Then build revenue 2026->2030 (interp from the ~$80B base to R2030) and 2031..2040 (decaying
growth), take NOPAT = revenue * margin * (1 - tax) [margin is after-D&A; steady-state capex ~
D&A so FCFF ~ NOPAT], discount at WACC, add a Gordon terminal value, subtract K. NPV > 0 means
the buildout clears its cost of capital.

A one-at-a-time tornado shows which assumption moves NPV most.

Reads : output/revenue_payback.csv (base R0, K, WACC anchors)
Writes: output/payback_montecarlo.csv + 2 figures.

Caveats: probabilities are CONDITIONAL on the sampled ranges (themselves Tier-2 scenario
judgments) -- they express plausibility, not a market forecast. FCFF~NOPAT assumes
maintenance reinvestment ~ depreciation. Fixed seed -> reproducible.

Re-runnable: reads output/, overwrites output/. No network.
"""

import datetime as dt
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
RETRIEVED = dt.date.today().isoformat()
SRC = f"Monte Carlo over documented assumption ranges. Compiled {RETRIEVED}."

N = 50_000
TAX = 0.21
HORIZON = 10            # years of explicit forecast beyond 2026 (to 2036)
TERM_G = 0.03           # terminal growth
SEED = 42
R0 = 80.0              # 2026 AI revenue base, USD bn (from revenue_payback.csv)
# triangular(min, mode, max)
TRI = {"K":      (3500, 5300, 7400),     # USD bn capital deployed
       "R2030":  (290, 730, 1440),        # USD bn 2030 AI-SPECIFIC revenue (matches payback model)
       "margin": (0.15, 0.27, 0.42),
       "wacc":   (0.08, 0.10, 0.12),
       "g_post": (0.10, 0.20, 0.35)}
# Fairness sensitivity: a "broad attribution" view where AI also lifts cloud/ads/search
# revenue, not just metered API tokens. Same capital, wider revenue. (Generous: credits
# revenue that partly predates the bet.)
R2030_BROAD = (500, 1200, 2800)


def caption(ax):
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=6.8, color="grey")


def npv_of(K, R2030, margin, wacc, g_post, rng_free=True):
    """PV (as of 2026) of after-tax operating cash flow minus capital K. Vectorizable scalars."""
    # revenue path: 2026=R0 -> 2030=R2030 (geometric), then decay growth g_post -> TERM_G
    g_2630 = (R2030 / R0) ** (1 / 4) - 1
    rev = [R0]
    for _ in range(4):                       # 2027..2030
        rev.append(rev[-1] * (1 + g_2630))
    g = g_post
    for t in range(HORIZON - 4):             # 2031..2036
        rev.append(rev[-1] * (1 + g))
        g = g - (g - TERM_G) * 0.35          # decay toward terminal
    nopat = [r * margin * (1 - TAX) for r in rev[1:]]   # 2027.. (year 0 = 2026 base, no flow)
    pv = sum(cf / (1 + wacc) ** (i + 1) for i, cf in enumerate(nopat))
    # terminal value at end of explicit horizon
    tv = nopat[-1] * (1 + TERM_G) / (wacc - TERM_G)
    pv += tv / (1 + wacc) ** len(nopat)
    return pv - K


def tri(rng, key, n=None):
    a, m, b = TRI[key]
    return rng.triangular(a, m, b, n)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    K = tri(rng, "K", N); R2030 = tri(rng, "R2030", N); margin = tri(rng, "margin", N)
    wacc = tri(rng, "wacc", N); g_post = tri(rng, "g_post", N)
    npv = np.array([npv_of(K[i], R2030[i], margin[i], wacc[i], g_post[i]) for i in range(N)])
    p_clear = float((npv > 0).mean())

    # Fairness sensitivity: broad-attribution revenue (everything else identical).
    R2030b = rng.triangular(*R2030_BROAD, N)
    npv_broad = np.array([npv_of(K[i], R2030b[i], margin[i], wacc[i], g_post[i]) for i in range(N)])
    p_clear_broad = float((npv_broad > 0).mean())

    # --- tornado: vary each input low->high, others at mode ---
    mode = {k: TRI[k][1] for k in TRI}
    base = npv_of(mode["K"], mode["R2030"], mode["margin"], mode["wacc"], mode["g_post"])
    tornado = []
    for k in TRI:
        lo_args = dict(mode); lo_args[k] = TRI[k][0]
        hi_args = dict(mode); hi_args[k] = TRI[k][2]
        lo = npv_of(lo_args["K"], lo_args["R2030"], lo_args["margin"], lo_args["wacc"], lo_args["g_post"])
        hi = npv_of(hi_args["K"], hi_args["R2030"], hi_args["margin"], hi_args["wacc"], hi_args["g_post"])
        tornado.append({"driver": k, "npv_low": round(lo), "npv_high": round(hi),
                        "swing": round(abs(hi - lo))})
    tornado = sorted(tornado, key=lambda d: d["swing"], reverse=True)

    out = pd.concat([
        pd.DataFrame([{"section": "result", "metric": "prob_clears_cost_of_capital", "value": round(p_clear, 3)},
                      {"section": "result", "metric": "prob_clears_broad_attribution", "value": round(p_clear_broad, 3)},
                      {"section": "result", "metric": "median_npv_bn", "value": round(float(np.median(npv)))},
                      {"section": "result", "metric": "p10_npv_bn", "value": round(float(np.percentile(npv, 10)))},
                      {"section": "result", "metric": "p90_npv_bn", "value": round(float(np.percentile(npv, 90)))},
                      {"section": "result", "metric": "base_case_npv_bn", "value": round(base)},
                      {"section": "result", "metric": "n_draws", "value": N},
                      {"section": "result", "metric": "seed", "value": SEED}]),
        pd.DataFrame(tornado).assign(section="tornado"),
    ], ignore_index=True)
    out["retrieved"] = RETRIEVED
    out.to_csv(OUTPUT / "payback_montecarlo.csv", index=False)

    # --- console ---
    print("=" * 78)
    print(f"MONTE CARLO: does the AI buildout earn its cost of capital?  (N={N:,}, seed {SEED})")
    print("=" * 78)
    print(f"  Probability NPV > 0 (clears WACC):     {p_clear*100:5.1f}%  (AI-specific revenue)")
    print(f"  ... under BROAD attribution (AI lifts all cloud/ads): {p_clear_broad*100:5.1f}%")
    print(f"  Median NPV:                            ${np.median(npv)/1000:+.1f}T")
    print(f"  P10 / P90 NPV:                         ${np.percentile(npv,10)/1000:+.1f}T  /  "
          f"${np.percentile(npv,90)/1000:+.1f}T")
    print(f"  Base case (all assumptions at mode):   ${base/1000:+.1f}T")
    print(f"\n  Sensitivity (NPV swing, low->high of each driver):")
    for t in tornado:
        print(f"    {t['driver']:8s}  ${t['npv_low']/1000:+5.1f}T -> ${t['npv_high']/1000:+5.1f}T  "
              f"(swing ${t['swing']/1000:.1f}T)")
    print("-" * 78)
    print(f"  Read: even crediting revenue earned well past 2030 and a terminal value, the bet")
    print(f"  clears its cost of capital in only ~{p_clear*100:.0f}% of draws. It pencils out ONLY")
    print(f"  with top-of-range margins, long life, and sustained extraordinary growth together.")
    print(f"  The dominant swing factor is {tornado[0]['driver']}. Probabilities are conditional on")
    print(f"  the assumption ranges (Tier-2 judgments) -- plausibility, not a forecast.")
    print("=" * 78)

    NAVY, RED, GREY = "#1a3a5c", "#a4262c", "#8a8a8a"

    # --- Fig 1: NPV distribution ---
    fig, ax = plt.subplots(figsize=(8, 4.4))
    ax.hist(npv / 1000, bins=70, color=NAVY, alpha=0.85)
    ax.axvline(0, color=RED, lw=2, ls="--")
    ax.text(0, ax.get_ylim()[1]*0.92,
            f"  {p_clear*100:.0f}% of draws clear the cost of capital\n"
            f"  ({p_clear_broad*100:.0f}% if AI is credited with lifting all cloud)",
            fontsize=8.5, color=RED, va="top")
    ax.set_xlabel("Buildout NPV, USD trillion (PV of after-tax AI profits minus capital deployed)")
    ax.set_ylabel("draws")
    ax.set_title("Most paths do not earn the cost of capital, even crediting profits past 2030")
    ax.grid(axis="x", visible=False)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_payback_distribution.png", dpi=150)
    plt.close(fig)

    # --- Fig 2: tornado ---
    fig, ax = plt.subplots(figsize=(8, 3.8))
    names = [t["driver"] for t in tornado][::-1]
    lows = [t["npv_low"]/1000 for t in tornado][::-1]
    highs = [t["npv_high"]/1000 for t in tornado][::-1]
    b = base/1000
    for i, (lo, hi) in enumerate(zip(lows, highs)):
        ax.barh(i, hi - lo, left=min(lo, hi), color=NAVY, height=0.55)
    ax.axvline(b, color=GREY, lw=1.5, ls=":")
    ax.text(b, len(names)-0.3, " base", fontsize=8, color=GREY)
    ax.axvline(0, color=RED, lw=1.5, ls="--")
    ax.set_yticks(range(len(names))); ax.set_yticklabels(names)
    ax.set_xlabel("Buildout NPV, USD trillion")
    ax.set_title("What moves the answer most (one-at-a-time, low→high)")
    ax.grid(axis="y", visible=False)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_payback_tornado.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/payback_montecarlo.csv + 2 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
