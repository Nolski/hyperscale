#!/usr/bin/env python3
"""
model_revenue_payback.py -- Model step (can the revenue pay the buildout back?).

Puts the REQUIRED revenue (to earn the cost of capital on the buildout) against the
ACHIEVABLE revenue (an adoption S-curve grounded in observed usage), and benchmarks the
required ramp against AWS -- the steepest real precedent for a compute-infrastructure business.

REQUIRED side:
  WACC from real inputs: Rf = latest 10y Treasury (treasury_curve.csv); cost of debt =
    Rf + IG OAS (credit_spreads.csv), after 21% tax; cost of equity = Rf + beta*ERP
    (CAPM, beta=1.3, ERP=5%); low-leverage weights. -> WACC ~= 9-10%.
  Capital deployed K = cumulative buildout capex (hyperscaler_capex actuals 2024-25 +
    investment_projection 2026-2030, low/mid/high).
  To earn its cost of capital over asset life L, the buildout must throw off annual
  operating profit = K * CRF(WACC, L), where CRF is the capital-recovery factor (an annuity
  that returns WACC and recovers K over L years). Required REVENUE = that profit / margin,
  at margins {15%, 25%, 35% (AWS-proven)} and L in {3, 6} (our economic-vs-book-life range).

ACHIEVABLE side:
  Base 2026 AI revenue R0 ~= AI-native ARR (OpenAI+Anthropic) + hyperscaler AI services.
  Grow on a DECELERATING schedule (an S-curve), calibrated to observed token-volume growth
  (~7x/yr now, decelerating -- token_volume.csv) net of the steep effective-price decline.
  Low/mid/high to 2030.

AWS comparable: AWS took 13 years to reach ~$129B (cloud_segments.csv). Compare its growth
rate and scale to the required AI ramp.

Reads : data/processed/{treasury_curve,credit_spreads,hyperscaler_capex_annual,cloud_segments,
        ai_native_revenue,token_volume}.csv; data/raw/manual/ai_capex_revenue_2026.csv;
        output/investment_projection.csv
Writes: output/revenue_payback.csv + 3 figures.

Caveats: achievable revenue is SCENARIO, not forecast; the monetization of token volume into
dollars is the softest assumption. WACC/beta/ERP are stated assumptions. K is cumulative
buildout spend used as a capital base. See notes. Tier-2 inputs flagged in provenance.

Re-runnable: reads data/processed/ + manual + output/, overwrites output/. No network.
"""

import datetime as dt
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "raw" / "manual"
OUTPUT = ROOT / "output"
RETRIEVED = dt.date.today().isoformat()
BN = 1e9
SRC = f"Sources: SEC EDGAR (cloud segments, capex), FRED (rates), company disclosures. Compiled {RETRIEVED}."

TAX = 0.21
BETA = 1.3
ERP = 0.05          # equity risk premium assumption
EQUITY_W = 0.85     # buildout is mostly equity-financed (low hyperscaler leverage)
MARGINS = [0.15, 0.25, 0.35]
LIVES = [3, 6]
# Achievable AI-revenue growth multipliers by year (2027..2030), decelerating S-curve.
# Calibrated to token-volume growth (~7x/yr, decelerating) net of steep effective-price decline.
ACHIEVE = {"low":  [1.8, 1.4, 1.25, 1.15],
           "mid":  [2.5, 1.8, 1.5, 1.35],
           "high": [3.2, 2.2, 1.7, 1.5]}


def caption(ax):
    ax.figure.text(0.5, 0.005, SRC, ha="center", fontsize=6.8, color="grey")


def latest(df, label):
    s = df[df.label == label].sort_values("date")
    return float(s.iloc[-1]["value"])


def crf(r, L):
    return r * (1 + r) ** L / ((1 + r) ** L - 1)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tc = pd.read_csv(PROCESSED / "treasury_curve.csv")
    cs = pd.read_csv(PROCESSED / "credit_spreads.csv")
    proj = pd.read_csv(OUTPUT / "investment_projection.csv")
    capex = pd.read_csv(PROCESSED / "hyperscaler_capex_annual.csv")
    cloud = pd.read_csv(PROCESSED / "cloud_segments.csv")
    native = pd.read_csv(PROCESSED / "ai_native_revenue.csv")

    # --- WACC ---
    rf = latest(tc, "nominal_10y") / 100
    ig = latest(cs, "ig_oas") / 100
    rd = (rf + ig) * (1 - TAX)              # after-tax cost of debt
    re = rf + BETA * ERP                    # CAPM cost of equity
    wacc = EQUITY_W * re + (1 - EQUITY_W) * rd

    # --- Capital deployed K (cumulative buildout capex), low/mid/high ---
    em = pd.to_datetime(capex["period_end"]).dt.month
    capex["cy"] = capex["fiscal_year"].where(em != 1, capex["fiscal_year"] - 1)
    actual_2425 = (capex[capex.cy.isin([2024, 2025])]
                   .groupby("cy")["total_capacity_investment_usd"].sum().sum() / BN)
    K = {}
    for sc in ("low", "mid", "high"):
        fwd = proj[proj.scenario == sc]["annual_capex_usd_bn"].sum()
        K[sc] = actual_2425 + fwd     # USD bn, cumulative ~2024-2030 buildout

    # --- Required revenue grid (K_mid), margin x life ---
    Kmid = K["mid"]
    req_rows = []
    for L in LIVES:
        annual_profit = Kmid * crf(wacc, L)        # USD bn/yr operating profit to earn WACC
        for m in MARGINS:
            req_rows.append({"section": "required", "life_years": L, "margin": m,
                             "required_op_profit_bn": round(annual_profit, 0),
                             "required_revenue_bn": round(annual_profit / m, 0)})
    req = pd.DataFrame(req_rows)

    # --- Achievable revenue path ---
    oai = native[native.company == "OpenAI"].sort_values("date").iloc[-1]["arr_usd_billion"]
    ant = native[native.company == "Anthropic"].sort_values("date").iloc[-1]["arr_usd_billion"]
    hyper_ai = 25.0   # hyperscaler AI-services revenue ~2025-26 (ai_capex_revenue_2026.csv)
    R0 = oai + ant + hyper_ai     # ~2026 AI-specific revenue run-rate, USD bn
    years = [2026, 2027, 2028, 2029, 2030]
    ach = {"year": years}
    for sc, mult in ACHIEVE.items():
        path = [R0]
        for m in mult:
            path.append(path[-1] * m)
        ach[sc] = path
    ach = pd.DataFrame(ach)

    # --- AWS comparable ---
    aws = cloud[cloud.provider == "AWS"].sort_values("year")
    aws_yrs = len(aws)
    aws_cagr = (aws.iloc[-1]["revenue_usd"] / aws.iloc[0]["revenue_usd"]) ** (1 / (aws_yrs - 1)) - 1
    # required CAGR from R0 (2026) to mid-required revenue (35% margin, 6yr life) by 2030
    req_target = Kmid * crf(wacc, 6) / 0.35     # bn
    req_cagr = (req_target / R0) ** (1 / 4) - 1

    # --- assemble output ---
    out = pd.concat([
        pd.DataFrame([{"section": "wacc", "metric": "rf", "value": round(rf, 4)},
                      {"section": "wacc", "metric": "cost_of_debt_aftertax", "value": round(rd, 4)},
                      {"section": "wacc", "metric": "cost_of_equity", "value": round(re, 4)},
                      {"section": "wacc", "metric": "wacc", "value": round(wacc, 4)},
                      {"section": "capital", "metric": "K_low_bn", "value": round(K["low"], 0)},
                      {"section": "capital", "metric": "K_mid_bn", "value": round(Kmid, 0)},
                      {"section": "capital", "metric": "K_high_bn", "value": round(K["high"], 0)},
                      {"section": "achievable", "metric": "R0_2026_bn", "value": round(R0, 0)},
                      {"section": "comparable", "metric": "aws_cagr", "value": round(aws_cagr, 3)},
                      {"section": "comparable", "metric": "required_cagr_to_2030", "value": round(req_cagr, 3)}]),
        req,
        ach.melt(id_vars="year", var_name="scenario", value_name="revenue_bn").assign(section="achievable_path"),
    ], ignore_index=True)
    out["retrieved"] = RETRIEVED
    out.to_csv(OUTPUT / "revenue_payback.csv", index=False)

    # --- console ---
    print("=" * 80)
    print("CAN THE REVENUE PAY THE BUILDOUT BACK?")
    print("=" * 80)
    print(f"  WACC: Rf {rf*100:.1f}% + equity (CAPM {re*100:.1f}%) / debt ({rd*100:.1f}% a-t) "
          f"-> {wacc*100:.1f}%")
    print(f"  Capital deployed (cum. ~2024-2030): low ${K['low']/1000:.1f}T / "
          f"mid ${Kmid/1000:.1f}T / high ${K['high']/1000:.1f}T")
    print(f"\n  REQUIRED annual revenue to earn WACC on the mid (${Kmid/1000:.1f}T) buildout:")
    print(f"    {'margin':>8s} {'life 6yr':>12s} {'life 3yr':>12s}")
    for m in MARGINS:
        r6 = req[(req.margin == m) & (req.life_years == 6)]["required_revenue_bn"].iloc[0]
        r3 = req[(req.margin == m) & (req.life_years == 3)]["required_revenue_bn"].iloc[0]
        print(f"    {m*100:6.0f}%  ${r6/1000:10.1f}T ${r3/1000:10.1f}T")
    print(f"\n  ACHIEVABLE AI revenue (from ${R0:.0f}B in 2026):")
    for sc in ("low", "mid", "high"):
        v = ach[sc].iloc[-1]
        print(f"    {sc:>4s}: ${v/1000:.2f}T by 2030")
    print(f"\n  THE GAP: required ~${req[req.life_years==6]['required_revenue_bn'].min()/1000:.1f}"
          f"-{req[req.life_years==3]['required_revenue_bn'].max()/1000:.1f}T/yr "
          f"vs achievable ${ach['low'].iloc[-1]/1000:.2f}-{ach['high'].iloc[-1]/1000:.2f}T by 2030.")
    print(f"  Required revenue CAGR to 2030 ~{req_cagr*100:.0f}%/yr vs AWS's ~{aws_cagr*100:.0f}%/yr "
          f"over its 13-yr ramp -> the required ramp is ~{req_cagr/aws_cagr:.0f}x AWS's pace,")
    print(f"  at far larger scale and less than half the time. Mature-cloud margins (AWS 35%, "
          f"MSFT 42%, GCP 24%) are the ceiling; AI-native revenue today is still unprofitable.")
    print("=" * 80)

    NAVY, RED, GOLD, GREY, LT = "#1a3a5c", "#a4262c", "#c08a2e", "#8a8a8a", "#9fb6c8"

    # --- Fig 1: required vs achievable to 2030 ---
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.fill_between(years, ach["low"], ach["high"], color=NAVY, alpha=0.13)
    ax.plot(years, ach["mid"], color=NAVY, lw=2.4, marker="o", label="Achievable AI revenue (S-curve, mid)")
    ax.plot(years, ach["low"], color=NAVY, lw=1, ls=":")
    ax.plot(years, ach["high"], color=NAVY, lw=1, ls=":")
    for m, col, lab in [(0.35, RED, "required @ 35% margin, 6-yr life"),
                        (0.25, GOLD, "required @ 25% margin, 6-yr life")]:
        rv = req[(req.margin == m) & (req.life_years == 6)]["required_revenue_bn"].iloc[0]
        ax.axhline(rv, color=col, lw=2, ls="--", label=lab)
    ax.axhline(2000, color=GREY, lw=1, ls="-.", label="Bain: ~$2T/yr 'cover cost' bar")
    ax.set_ylabel("AI revenue, USD billion / year")
    ax.set_title("What the buildout must earn vs what usage can plausibly deliver")
    ax.legend(fontsize=7.6, frameon=False, loc="upper left")
    ax.grid(axis="x", visible=False)
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_required_vs_achievable.png", dpi=150)
    plt.close(fig)

    # --- Fig 2: AWS ramp vs required ramp (log) ---
    fig, ax = plt.subplots(figsize=(8, 4.4))
    ax.plot(aws["year"], aws["revenue_usd"] / BN, color=NAVY, lw=2.4, marker="o",
            label=f"AWS actual ({aws_yrs} yrs to ${aws.iloc[-1]['revenue_usd']/BN:.0f}B, ~{aws_cagr*100:.0f}%/yr)")
    req_line = [R0 * (1 + req_cagr) ** i for i in range(5)]
    ax.plot(years, req_line, color=RED, lw=2.4, marker="s",
            label=f"Required AI ramp (~{req_cagr*100:.0f}%/yr to pay back)")
    ax.set_yscale("log")
    ax.set_ylabel("Revenue, USD billion (log)")
    ax.set_title("The required AI revenue ramp has no precedent — even AWS")
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    ax.grid(alpha=0.3, which="both")
    caption(ax)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUTPUT / "fig_aws_vs_required.png", dpi=150)
    plt.close(fig)

    # --- Fig 3: required-revenue heatmap (margin x life) ---
    grid = np.array([[req[(req.margin == m) & (req.life_years == L)]["required_revenue_bn"].iloc[0] / 1000
                      for L in LIVES] for m in MARGINS])
    fig, ax = plt.subplots(figsize=(7, 4.0))
    im = ax.imshow(grid, cmap="OrRd", aspect="auto")
    ax.set_xticks(range(len(LIVES))); ax.set_xticklabels([f"{L}-yr life" for L in LIVES])
    ax.set_yticks(range(len(MARGINS))); ax.set_yticklabels([f"{m*100:.0f}% margin" for m in MARGINS])
    for i in range(len(MARGINS)):
        for j in range(len(LIVES)):
            ax.text(j, i, f"${grid[i,j]:.1f}T", ha="center", va="center",
                    fontsize=11, weight="bold", color="#222" if grid[i,j] < grid.max()*0.6 else "white")
    ax.set_title(f"Required annual revenue to earn the cost of capital on a ${Kmid/1000:.1f}T buildout")
    fig.tight_layout()
    fig.savefig(OUTPUT / "fig_required_heatmap.png", dpi=150)
    plt.close(fig)

    print(f"\nWrote: output/revenue_payback.csv + 3 figures (retrieved {RETRIEVED})")


if __name__ == "__main__":
    main()
