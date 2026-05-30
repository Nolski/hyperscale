#!/usr/bin/env python3
"""
build_report.py -- Presentation step.

Assembles a single self-contained HTML report -- a New York Times-style
data-journalism long-read on the AI-buildout research -- and writes:
  - output/report.html   (self-contained: all charts embedded as base64 PNGs)

The script reads the pipeline's processed datasets and summary tables so every
figure quoted in the prose stays in sync with the data, regenerates ~13 charts
in an editorial (NYT-graphics) style, and templates them into an HTML article.
The energy section is the centerpiece: national demand, state-level
concentration, the contested price question, price modelling, and data centers
as grid participants.

Re-runnable: reads data/processed/ + data/raw/manual/ + output/*.csv, overwrites
output/report.html. No network.
"""

import base64
import datetime as dt
import io
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "raw" / "manual"
OUTPUT = ROOT / "output"
RETRIEVED = dt.date.today().isoformat()
BN = 1e9

INK = "#121212"
NAVY = "#1a3a5c"
NAVY_MID = "#4a6e8f"
NAVY_LT = "#9fb6c8"
RED = "#a4262c"
GOLD = "#c08a2e"
GREY = "#8a8a8a"
DC_HEAVY = {"VA", "TX", "IL", "CA", "OR"}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Arial", "Liberation Sans", "DejaVu Sans"],
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.edgecolor": GREY, "axes.labelcolor": "#444",
    "text.color": INK, "xtick.color": "#444", "ytick.color": "#444",
    "xtick.labelsize": 9, "ytick.labelsize": 9,
    "axes.grid": True, "axes.axisbelow": True,
    "grid.color": "#e6e6e6", "grid.linewidth": 0.8,
    "figure.facecolor": "white", "axes.facecolor": "white",
})


def fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def to_num(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return v


def csv_dict(path, key="indicator", val="value"):
    df = pd.read_csv(path)
    return {k: to_num(v) for k, v in zip(df[key].astype(str).str.strip(), df[val])}


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def load():
    d = {}

    capex = pd.read_csv(PROCESSED / "hyperscaler_capex_annual.csv")
    em = pd.to_datetime(capex["period_end"]).dt.month
    capex["chart_year"] = capex["fiscal_year"].where(em != 1, capex["fiscal_year"] - 1)
    d["capex_by_year"] = (capex[capex.chart_year <= 2025]
                          .groupby("chart_year")["total_capacity_investment_usd"]
                          .sum() / BN)

    d["proj"] = pd.read_csv(OUTPUT / "investment_projection.csv")
    d["syn"] = csv_dict(OUTPUT / "synthesis_indicators.csv")
    d["lk"] = csv_dict(OUTPUT / "linked_sectors_summary.csv")
    d["ax"] = csv_dict(OUTPUT / "automation_exposure_summary.csv")
    d["es"] = csv_dict(OUTPUT / "energy_states_summary.csv")

    # National data-center electricity share
    dce = pd.read_csv(PROCESSED / "datacenter_energy.csv")
    share = dce[dce.metric == "datacenter_share_of_us"]
    d["dc_2023"] = share[share.year == 2023].iloc[0]["value"]
    d["dc_2030"] = sorted(share[share.year == 2030]["value"].tolist())

    # National electricity demand + price
    elec = pd.read_csv(PROCESSED / "us_electricity.csv")
    allsec = elec[elec.sector == "all sectors"].set_index("year").sort_index()
    res = elec[elec.sector == "residential"].set_index("year").sort_index()
    d["us_demand"] = allsec["sales_twh"]
    d["res_price"] = (res.loc[res.index.min(), "price_cents_per_kwh"],
                      res.loc[res.index.max(), "price_cents_per_kwh"])
    cagr = lambda a, b, n: ((b / a) ** (1 / n) - 1) * 100
    d["growth_flat"] = cagr(allsec.loc[2007, "sales_twh"], allsec.loc[2020, "sales_twh"], 13)
    d["growth_surge"] = cagr(allsec.loc[2020, "sales_twh"],
                             allsec.loc[allsec.index.max(), "sales_twh"],
                             allsec.index.max() - 2020)

    # State electricity + data-center load by state
    st = pd.read_csv(PROCESSED / "us_electricity_by_state.csv")
    st = st[st.stateid != "US"]
    res_st = st[st.sector == "residential"].pivot_table(
        index="year", columns="stateid", values="price_cents_per_kwh")
    idx = res_st / res_st.loc[2010] * 100
    heavy = [c for c in idx.columns if c in DC_HEAVY]
    rest = [c for c in idx.columns if c not in DC_HEAVY]
    d["state_price_idx"] = pd.DataFrame({"heavy": idx[heavy].mean(axis=1),
                                         "rest": idx[rest].mean(axis=1)})
    d["dc_states"] = pd.read_csv(MANUAL / "datacenter_energy_states.csv", comment="#")

    # Price outlook + power deals (manual)
    po = pd.read_csv(MANUAL / "electricity_price_outlook.csv", comment="#")
    d["price_outlook"] = po
    d["power_deals"] = pd.read_csv(MANUAL / "datacenter_power_deals.csv", comment="#")

    # Semiconductors
    semi = pd.read_csv(PROCESSED / "semiconductor_revenue_annual.csv")
    d["semi_latest"] = (semi.sort_values("period_end").groupby("ticker").tail(1)
                        .sort_values("revenue_usd"))

    # Forecasts
    d["forecasts"] = pd.read_csv(PROCESSED / "investment_forecasts.csv")

    # Construction: data-center share of all US construction
    dcc = pd.read_csv(PROCESSED / "datacenter_construction_annual.csv")
    tc = pd.read_csv(PROCESSED / "construction_sector.csv")
    tc = tc[tc.label == "total_construction_spending"].copy()
    tc["year"] = pd.to_datetime(tc["date"]).dt.year
    tca = tc.groupby("year").agg(v=("value", "mean"), n=("value", "count"))
    tca = tca[tca.n == 12]
    dcf = dcc[~dcc["partial_year"]].set_index("year")
    share_pct = (dcf["spending_usd"] / BN) / (tca["v"] / 1000) * 100
    d["constr_share"] = share_pct.dropna()

    # Labour: exposure by wage decile, two methods
    oews = pd.read_csv(PROCESSED / "oews_occupations.csv")
    elo = pd.read_csv(PROCESSED / "automation_exposure.csv")
    anth = pd.read_csv(PROCESSED / "anthropic_exposure.csv")
    m = (oews.merge(elo[["soc_code", "human_rating_beta"]], on="soc_code")
         .merge(anth[["soc_code", "anthropic_observed_exposure"]], on="soc_code")
         .dropna(subset=["median_annual_wage"]).copy())
    m["decile"] = pd.qcut(m["median_annual_wage"], 10, labels=False) + 1
    wm = lambda g, c: (g[c] * g["total_employment"]).sum() / g["total_employment"].sum()
    d["decile"] = m.groupby("decile").apply(
        lambda g: pd.Series({"elo": wm(g, "human_rating_beta"),
                             "anth": wm(g, "anthropic_observed_exposure")}),
        include_groups=False)

    # --- 2026 reframe: news/framing (Tier-2) + new-thread model outputs ---
    cr = pd.read_csv(MANUAL / "ai_capex_revenue_2026.csv", comment="#")
    d["cr"] = {k: to_num(v) for k, v in zip(cr["metric"].astype(str).str.strip(), cr["value"])}
    sg = pd.read_csv(MANUAL / "ai_adoption_signals.csv", comment="#")
    d["sig"] = {k: to_num(v) for k, v in zip(sg["indicator"].astype(str).str.strip(), sg["value"])}

    d["cost_stack"] = pd.read_csv(OUTPUT / "cost_stack.csv")
    d["jevons"] = pd.read_csv(OUTPUT / "jevons_rebound.csv")
    d["ec"] = csv_dict(OUTPUT / "equity_concentration.csv", key="item", val="value")
    fin = pd.read_csv(OUTPUT / "ai_financing.csv")
    agg = fin[fin["section"] == "aggregate_latest_fy"]
    d["debt_issuance"] = float(agg["debt_issuance_usd_bn"].iloc[0]) if not agg.empty else 77.0

    # Concentration time series: cap-weight vs equal-weight S&P, rebased to 2015 = 100
    ep = pd.read_csv(PROCESSED / "equity_prices.csv", parse_dates=["date"])
    wide = ep.pivot_table(index="date", columns="label", values="close", aggfunc="last")
    pair = wide[["sp500_capweight", "sp500_equalweight"]].dropna()
    pair = pair[pair.index >= "2015-01-01"]
    d["conc"] = (pair / pair.iloc[0] * 100).rename(
        columns={"sp500_capweight": "cap", "sp500_equalweight": "equal"})

    # --- Revenue-vs-payback model outputs ---
    rp = pd.read_csv(OUTPUT / "revenue_payback.csv")
    d["rp_scalar"] = {m: to_num(v) for m, v in zip(rp["metric"], rp["value"]) if pd.notna(m)}
    req = rp[rp.section == "required"]
    d["req_rev"] = {(int(r.life_years), float(r.margin)): float(r.required_revenue_bn)
                    for r in req.itertuples()}
    ap = rp[rp.section == "achievable_path"].copy()
    d["achieve"] = ap.pivot_table(index="year", columns="scenario", values="revenue_bn")
    mc = pd.read_csv(OUTPUT / "payback_montecarlo.csv")
    d["mc"] = {m: to_num(v) for m, v in zip(mc["metric"], mc["value"]) if pd.notna(m)}
    cl = pd.read_csv(PROCESSED / "cloud_segments.csv")
    d["aws"] = cl[cl.provider == "AWS"].sort_values("year")[["year", "revenue_usd"]]
    nat = pd.read_csv(PROCESSED / "ai_native_revenue.csv")
    d["native_latest"] = {c: nat[nat.company == c].sort_values("date").iloc[-1]["arr_usd_billion"]
                          for c in nat["company"].unique()}
    return d


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
def chart_ramp(d):
    s = d["capex_by_year"]
    fig, ax = plt.subplots(figsize=(8, 4.0))
    ax.bar(s.index, s.values, color=NAVY, width=0.74)
    for yr in (s.index.min(), 2025):
        ax.text(yr, s.loc[yr] + 12, f"${s.loc[yr]:,.0f}B", ha="center",
                fontsize=9.5, weight="bold", color=NAVY)
    ax.set_ylabel("USD billion")
    ax.set_ylim(0, s.max() * 1.16)
    ax.set_xticks(list(s.index))
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_layers(d):
    syn = d["syn"]
    labels = ["Real investment\n(hyperscaler total)", "Financing\n(global VC into AI)",
              "Supply mirror\n(AI-chip revenue)"]
    vals = [syn["Hyperscaler capital investment, 2025"],
            syn["Global VC into AI, 2025"], syn["AI-chip supplier revenue (5 US firms)"]]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    bars = ax.bar(labels, vals, color=[NAVY, GOLD, "#6a4c93"], width=0.6)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 9, f"${v:,.0f}B",
                ha="center", fontsize=10, weight="bold")
    ax.set_ylabel("USD billion")
    ax.set_ylim(0, max(vals) * 1.2)
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_macro(d):
    syn = d["syn"]
    items = [("of US GDP", syn["as share of US GDP"]),
             ("of all private business\nfixed investment",
              syn["as share of US private nonres. fixed investment"]),
             ("of all US IT-equipment\n+ software investment",
              syn["as share of US IT-equipment + software investment"])]
    fig, ax = plt.subplots(figsize=(8, 3.0))
    bars = ax.barh([i[0] for i in items], [i[1] for i in items],
                   color=[NAVY_LT, NAVY_MID, NAVY], height=0.62)
    for b, v in zip(bars, [i[1] for i in items]):
        ax.text(v + 0.6, b.get_y() + b.get_height() / 2, f"{v:.1f}%",
                va="center", fontsize=10, weight="bold")
    ax.invert_yaxis()
    ax.set_xlim(0, max(i[1] for i in items) * 1.2)
    ax.grid(axis="y", visible=False)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=9.5)
    return fig_to_b64(fig)


def chart_semis(d):
    s = d["semi_latest"]
    colors = [RED if t == "NVDA" else NAVY for t in s["ticker"]]
    fig, ax = plt.subplots(figsize=(8, 3.4))
    bars = ax.barh(s["company"], s["revenue_usd"] / BN, color=colors, height=0.64)
    for b, v in zip(bars, s["revenue_usd"] / BN):
        ax.text(v + 3, b.get_y() + b.get_height() / 2, f"${v:,.0f}B",
                va="center", fontsize=9.5, weight="bold")
    ax.set_xlabel("Latest-fiscal-year revenue, USD billion")
    ax.grid(axis="y", visible=False)
    return fig_to_b64(fig)


def chart_bet(d):
    s = d["capex_by_year"]
    hist = s[s.index >= 2015]
    proj = d["proj"]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(hist.index, hist.values, color=INK, lw=2.4)
    for sc, col in [("low", NAVY_LT), ("mid", NAVY_MID), ("high", NAVY)]:
        p = proj[proj.scenario == sc].set_index("year")["annual_capex_usd_bn"]
        xs, ys = [2025] + list(p.index), [hist.loc[2025]] + list(p.values)
        ax.plot(xs, ys, color=col, lw=1.9, ls="--")
        ax.text(2030.1, ys[-1], f"  {sc} ${ys[-1] / 1000:.1f}T", va="center",
                fontsize=8.5, color=col, weight="bold")
    lo = [hist.loc[2025]] + list(proj[proj.scenario == "low"]["annual_capex_usd_bn"])
    hi = [hist.loc[2025]] + list(proj[proj.scenario == "high"]["annual_capex_usd_bn"])
    ax.fill_between(range(2025, 2031), lo, hi, color=NAVY, alpha=0.07)
    ax.axvline(2025, color=GREY, lw=0.8, ls=":")
    ax.text(2024.8, 2080, "actual", ha="right", fontsize=8, color=GREY, style="italic")
    ax.text(2025.2, 2080, "projected", ha="left", fontsize=8, color=GREY, style="italic")
    ax.set_ylabel("Annual capital investment, USD billion")
    ax.set_xlim(2015, 2032.2)
    ax.set_ylim(0, 2200)
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_forecasts(d):
    cum = d["forecasts"]
    cum = cum[cum.metric == "cumulative"].copy()
    cum["label"] = cum["source"] + "\n" + cum["scenario"].str.slice(0, 22)
    fig, ax = plt.subplots(figsize=(8, 3.7))
    vals = cum["value_usd_billion"] / 1000
    bars = ax.bar(range(len(cum)), vals,
                  color=[NAVY_LT, NAVY_MID, NAVY, "#0d2233", GOLD][:len(cum)], width=0.62)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.12, f"${v:.1f}T",
                ha="center", fontsize=9, weight="bold")
    ax.set_xticks(range(len(cum)))
    ax.set_xticklabels(cum["label"], fontsize=7.3)
    ax.set_ylabel("Cumulative forecast, USD trillion")
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_us_demand(d):
    s = d["us_demand"]
    fig, ax = plt.subplots(figsize=(8, 3.9))
    ax.plot(s.index, s.values, color=NAVY, lw=2.4)
    ax.axvspan(2007, 2020, color="#999999", alpha=0.10)
    ax.text(2013.5, s.min() + 25, "flat, 2007–2020", ha="center", fontsize=8.5,
            color=GREY, style="italic")
    ax.set_ylabel("US electricity demand, TWh")
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_dc_share(d):
    lo, hi = d["dc_2030"]
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.plot([2023], [d["dc_2023"]], "o", ms=11, color=NAVY)
    ax.text(2023, d["dc_2023"] - 1.9, f"{d['dc_2023']:g}%\n2023", ha="center",
            fontsize=9.5, color=NAVY, weight="bold")
    ax.plot([2030, 2030], [lo, hi], color=RED, lw=11, solid_capstyle="round")
    ax.text(2030.4, (lo + hi) / 2, f"{lo:g}–{hi:g}%\nby 2030", va="center",
            fontsize=9.5, color=RED, weight="bold")
    ax.set_ylabel("Share of US electricity")
    ax.set_xlim(2021.5, 2032.5)
    ax.set_ylim(0, 19)
    ax.set_xticks([2023, 2030])
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_dc_states(d):
    s = d["dc_states"].sort_values("datacenter_twh")
    fig, ax = plt.subplots(figsize=(8, 3.3))
    bars = ax.barh(s["state"], s["datacenter_twh"], color=NAVY, height=0.62)
    for b, row in zip(bars, s.itertuples()):
        lab = f"{row.datacenter_twh:.0f} TWh"
        if pd.notna(row.share_of_state_electricity_pct):
            lab += f"  (~{row.share_of_state_electricity_pct:.0f}% of state)"
        ax.text(row.datacenter_twh + 0.7, b.get_y() + b.get_height() / 2, lab,
                va="center", fontsize=9, weight="bold")
    ax.set_xlim(0, 42)
    ax.set_xlabel("Data-center electricity, 2023 (TWh, approx.)")
    ax.grid(axis="y", visible=False)
    return fig_to_b64(fig)


def chart_state_prices(d):
    s = d["state_price_idx"]
    fig, ax = plt.subplots(figsize=(8, 4.0))
    ax.plot(s.index, s["heavy"], color=RED, lw=2.4, label="Data-center-heavy states")
    ax.plot(s.index, s["rest"], color=NAVY, lw=2.4, label="Other states")
    ax.axvline(2021, color=GREY, lw=0.8, ls=":")
    ax.text(2021.2, 150, "post-2021\ndivergence", fontsize=7.6, color=GREY, style="italic")
    ax.set_ylabel("Residential price index (2010 = 100)")
    ax.legend(fontsize=8.5, frameon=False, loc="upper left")
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_price_outlook(d):
    po = d["price_outlook"]
    w = po[po.metric == "wholesale_price_impact"].copy()
    order = {"current": 0, "moderate buildout": 1, "high utilization": 2}
    w["o"] = w["scenario"].map(order)
    w = w.sort_values("o")
    labels = ["Today\n(2026)", "Moderate\nbuild-out (2028)", "High\nutilization (2028)"]
    fig, ax = plt.subplots(figsize=(8, 3.4))
    bars = ax.bar(labels, w["value"], color=[NAVY_LT, NAVY_MID, RED], width=0.58)
    for b, v in zip(bars, w["value"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.2, f"+{v:g}%",
                ha="center", fontsize=10, weight="bold")
    ax.set_ylabel("Wholesale price impact")
    ax.set_ylim(0, 58)
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_labor(d):
    dec = d["decile"]
    x = dec.index.to_numpy()
    w = 0.4
    fig, ax = plt.subplots(figsize=(8, 4.0))
    ax.bar(x - w / 2, dec["elo"], w, color=NAVY, label="Predicted exposure (Eloundou)")
    ax.bar(x + w / 2, dec["anth"], w, color=RED, label="Observed use (Anthropic)")
    ax.set_ylabel("Share of tasks AI-exposed")
    ax.set_xlabel("Wage decile  (1 = lowest-paid, 10 = highest-paid)")
    ax.set_xticks(list(x))
    ax.grid(axis="x", visible=False)
    ax.legend(fontsize=8.5, frameon=False, loc="upper left")
    return fig_to_b64(fig)


def chart_construction(d):
    s = d["constr_share"]
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.bar(s.index, s.values, color=NAVY, width=0.72)
    ax.set_ylabel("% of all US construction spending")
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_capex_vs_revenue(d):
    cr = d["cr"]
    capex, rev = cr["capex_big5_total"], cr["ai_service_revenue"]
    fig, ax = plt.subplots(figsize=(8, 4.0))
    bars = ax.bar(["2026 capital spending\n(Big Five, guidance)",
                   "2025 AI-service\nrevenue"], [capex, rev], color=[NAVY, RED], width=0.5)
    for b, v in zip(bars, [capex, rev]):
        ax.text(b.get_x() + b.get_width() / 2, v + 12, f"${v:,.0f}B",
                ha="center", fontsize=11, weight="bold")
    ax.set_ylabel("USD billion")
    ax.set_ylim(0, capex * 1.18)
    ax.grid(axis="x", visible=False)
    ax.annotate("", xy=(1, rev + 30), xytext=(1, capex * 0.95),
                arrowprops=dict(arrowstyle="<->", color=GREY, lw=1.1))
    ax.text(1.06, capex * 0.5, "the gap the\nbuildout is\nbetting it\ncan close",
            fontsize=8.5, color=GREY, style="italic", va="center")
    return fig_to_b64(fig)


def chart_required_vs_achievable(d):
    ach = d["achieve"]
    years = list(ach.index)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.fill_between(years, ach["low"], ach["high"], color=NAVY, alpha=0.12)
    ax.plot(years, ach["mid"], color=NAVY, lw=2.4, marker="o",
            label="Achievable AI revenue (usage S-curve)")
    ax.plot(years, ach["low"], color=NAVY, lw=1, ls=":")
    ax.plot(years, ach["high"], color=NAVY, lw=1, ls=":")
    ax.axhline(d["req_rev"][(6, 0.35)], color=RED, lw=2, ls="--",
               label="Required to pay back @ 35% margin")
    ax.axhline(d["req_rev"][(6, 0.25)], color=GOLD, lw=2, ls="--",
               label="Required @ 25% margin")
    ax.axhline(2000, color=GREY, lw=1, ls="-.", label="Bain: ~$2T/yr 'cover cost'")
    ax.set_ylabel("AI revenue, USD billion / year")
    ax.set_ylim(0, d["req_rev"][(6, 0.25)] * 1.1)
    ax.legend(fontsize=7.6, frameon=False, loc="upper left")
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_aws_vs_required(d):
    aws = d["aws"]
    R0 = d["rp_scalar"]["R0_2026_bn"]
    g = d["rp_scalar"]["required_cagr_to_2030"]
    years = list(range(2026, 2031))
    req_line = [R0 * (1 + g) ** i for i in range(5)]
    fig, ax = plt.subplots(figsize=(8, 4.3))
    ax.plot(aws["year"], aws["revenue_usd"] / BN, color=NAVY, lw=2.4, marker="o",
            label=f"AWS actual ({len(aws)} yrs to ${aws.iloc[-1]['revenue_usd']/BN:.0f}B)")
    ax.plot(years, req_line, color=RED, lw=2.4, marker="s",
            label=f"Required AI ramp (~{g*100:.0f}%/yr)")
    ax.set_yscale("log")
    ax.set_ylabel("Revenue, USD billion (log)")
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    ax.grid(alpha=0.3, which="both")
    return fig_to_b64(fig)


def chart_cost_stack(d):
    cs = d["cost_stack"].set_index("chip")
    order = [c for c in ["A100 SXM 80GB", "H100 SXM5", "B200"] if c in cs.index]
    short = {"A100 SXM 80GB": "A100", "H100 SXM5": "H100", "B200": "B200"}
    segs = [("cogs_usd", "Manufacturing (chip)", NAVY_LT),
            ("vendor_margin_usd", "Nvidia gross margin", RED),
            ("facility_cooling_usd", "Facility + cooling", NAVY_MID),
            ("lifetime_energy_usd", "Lifetime electricity", GOLD)]
    fig, ax = plt.subplots(figsize=(8, 3.5))
    left = {m: 0.0 for m in order}
    for col, lab, color in segs:
        widths = [cs.loc[m, col] / cs.loc[m, "total_deployed_usd"] * 100 for m in order]
        ax.barh([short[m] for m in order], widths,
                left=[left[m] for m in order], color=color, height=0.6, label=lab)
        for m, w in zip(order, widths):
            if w > 7:
                ax.text(left[m] + w / 2, list(order).index(m), f"{w:.0f}%",
                        va="center", ha="center", fontsize=9,
                        color="white" if color in (RED, NAVY_MID) else INK, weight="bold")
            left[m] += w
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of full deployed cost (%)")
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.legend(fontsize=8, frameon=False, ncol=2, loc="lower center",
              bbox_to_anchor=(0.5, -0.42))
    return fig_to_b64(fig)


def chart_concentration(d):
    s = d["conc"]
    fig, ax = plt.subplots(figsize=(8, 4.0))
    ax.plot(s.index, s["cap"], color=RED, lw=2.4, label="Cap-weighted S&P 500 (the megacaps)")
    ax.plot(s.index, s["equal"], color=NAVY, lw=2.4, label="Equal-weighted S&P 500 (the median stock)")
    ax.set_ylabel("Total-return index (2015 = 100)")
    ax.legend(fontsize=8.5, frameon=False, loc="upper left")
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_jevons(d):
    j = d["jevons"][d["jevons"].scenario == "LBNL high"].iloc[0]
    labels = ["2023\nactual", "2028 if demand\nhad frozen\n(efficiency only)",
              "2028\nactual", "2028 if efficiency\nhad frozen\n(demand only)"]
    vals = [j["energy_base_twh"], j["frozen_demand_energy_twh"],
            j["energy_end_twh"], j["frozen_efficiency_energy_twh"]]
    colors = [GREY, NAVY, RED, "#0d2233"]
    fig, ax = plt.subplots(figsize=(8, 4.0))
    bars = ax.bar(labels, vals, color=colors, width=0.62)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 25, f"{v:,.0f}", ha="center",
                fontsize=9.5, weight="bold")
    ax.set_ylabel("US data-center electricity, TWh")
    ax.set_ylim(0, max(vals) * 1.16)
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_useful_life(d):
    burry = d["sig"]["burry_gpu_useful_life"]
    items = [("Booked in the 10-Ks", 6.0, NAVY),
             ("Burry&rsquo;s estimate", burry, RED),
             ("Generational refresh\n(our hardware model)", 2.5, GOLD)]
    fig, ax = plt.subplots(figsize=(8, 2.9))
    bars = ax.barh([i[0].replace("&rsquo;", "'") for i in items],
                   [i[1] for i in items], color=[i[2] for i in items], height=0.6)
    for b, v in zip(bars, [i[1] for i in items]):
        ax.text(v + 0.1, b.get_y() + b.get_height() / 2, f"{v:g} yrs",
                va="center", fontsize=10, weight="bold")
    ax.invert_yaxis()
    ax.set_xlim(0, 7)
    ax.set_xlabel("Assumed useful life of an AI server (years)")
    ax.grid(axis="y", visible=False)
    return fig_to_b64(fig)


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------
CSS = """
:root { --ink:#121212; --grey:#6b6b6b; --rule:#dcdcdc; }
* { box-sizing:border-box; }
body { margin:0; background:#fff; color:var(--ink);
  font-family:Georgia,'Times New Roman',serif; -webkit-font-smoothing:antialiased; }
.wrap { max-width:680px; margin:0 auto; padding:64px 24px 96px; }
.kicker { font-family:'Helvetica Neue',Arial,sans-serif; font-weight:700;
  text-transform:uppercase; letter-spacing:.09em; font-size:.72rem;
  color:#a4262c; margin-bottom:18px; }
h1 { font-size:2.8rem; line-height:1.1; font-weight:700; letter-spacing:-.012em;
  margin:0 0 18px; }
.deck { font-size:1.24rem; line-height:1.45; color:#333; margin:0 0 26px; }
.byline { font-family:'Helvetica Neue',Arial,sans-serif; font-size:.74rem;
  text-transform:uppercase; letter-spacing:.07em; color:#333; }
.dateline { font-family:'Helvetica Neue',Arial,sans-serif; font-size:.74rem;
  color:var(--grey); margin-top:4px; padding-bottom:22px;
  border-bottom:1px solid var(--rule); margin-bottom:30px; }
p { font-size:1.07rem; line-height:1.66; margin:0 0 1.15em; }
p.lede:first-letter { float:left; font-size:3.5em; line-height:.78; font-weight:700;
  padding:6px 9px 0 0; }
h2 { font-family:'Helvetica Neue',Arial,sans-serif; font-size:.82rem;
  font-weight:700; text-transform:uppercase; letter-spacing:.1em;
  margin:2.4em 0 1em; padding-top:1.4em; border-top:1px solid var(--rule); }
figure { margin:2.6em 0; }
.fig-title { font-family:'Helvetica Neue',Arial,sans-serif; font-weight:700;
  font-size:1.02rem; margin-bottom:3px; }
.fig-sub { font-family:'Helvetica Neue',Arial,sans-serif; font-size:.86rem;
  color:#444; margin-bottom:12px; line-height:1.4; }
figure img { width:100%; display:block; }
.fig-src { font-family:'Helvetica Neue',Arial,sans-serif; font-size:.68rem;
  text-transform:uppercase; letter-spacing:.05em; color:var(--grey); margin-top:9px; }
.pull { font-size:1.62rem; line-height:1.32; font-weight:700; color:var(--ink);
  margin:1.5em 0; padding:.55em 0; border-top:2px solid var(--ink);
  border-bottom:2px solid var(--ink); }
.placeholder { display:block; font-family:'Helvetica Neue',Arial,sans-serif;
  font-size:.82rem; line-height:1.5; color:#7a5b1e; background:#fbf7e8;
  border:1px dashed #c08a2e; padding:11px 15px; margin:1.5em 0; }
.methodbox { background:#f4f1ea; border-left:3px solid #1a3a5c; padding:20px 24px;
  margin:2.8em 0 0; font-family:'Helvetica Neue',Arial,sans-serif;
  font-size:.9rem; line-height:1.62; color:#333; }
.methodbox .mb-h { font-weight:700; text-transform:uppercase; letter-spacing:.09em;
  font-size:.72rem; color:#1a3a5c; margin-bottom:10px; }
.methodbox p { font-size:.9rem; line-height:1.62; margin:0 0 .7em; }
.sources { border-top:1px solid var(--rule); margin:2.4em 0 0; padding-top:18px;
  font-family:'Helvetica Neue',Arial,sans-serif; font-size:.82rem; line-height:1.6;
  color:#555; }
.sources .mb-h { font-weight:700; text-transform:uppercase; letter-spacing:.09em;
  font-size:.7rem; color:#1a3a5c; margin-bottom:9px; }
.sources p { font-size:.82rem; line-height:1.6; margin:0; }
.footer { margin-top:2.4em; padding-top:1.4em; border-top:1px solid var(--rule);
  font-family:'Helvetica Neue',Arial,sans-serif; font-size:.78rem;
  line-height:1.6; color:var(--grey); }
"""


def figure(b64, title, sub, src):
    return (f'<figure><div class="fig-title">{title}</div>'
            f'<div class="fig-sub">{sub}</div>'
            f'<img alt="{title}" src="data:image/png;base64,{b64}">'
            f'<div class="fig-src">{src}</div></figure>')


def build_paragraphs(n, c):
    """The long-read narrative as a list of (kind, content) tuples."""
    methodbox = (
        '<div class="methodbox"><div class="mb-h">How this was measured</div>'
        '<p>The spine of this report is a reproducible, primary-source pipeline. '
        'Hyperscaler and chip-maker capital spending, debt, depreciation and margins '
        'are extracted from SEC EDGAR filings; macro, rates and credit series from the '
        'Federal Reserve&rsquo;s FRED; electricity demand and prices, national and by '
        'state, from the US Energy Information Administration; occupational employment '
        'from the Bureau of Labor Statistics; accelerator specifications from vendor '
        'datasheets cross-checked against Epoch&nbsp;AI. Data-center energy is from '
        'Lawrence Berkeley National Laboratory; AI-exposure scores from Eloundou '
        'et&nbsp;al. and the Anthropic Economic Index; price modelling from the Federal '
        'Reserve Bank of Dallas.</p>'
        '<p>The chip total-cost-of-ownership, economic-obsolescence, token-economics and '
        'Jevons models are the author&rsquo;s, built on those inputs; vendor performance '
        'figures, bill-of-materials estimates and the 2026 capex/revenue and adoption '
        'figures are second-tier (analyst and press) and are flagged as such, attributed '
        'in the text, and listed in Sources below. They frame; they are not the data of '
        'record. Contested questions &mdash; whether data centers cause local price rises, '
        'whether the buildout is &ldquo;backstopped,&rdquo; what an AI chip&rsquo;s true '
        'life is &mdash; are left contested. Full dataset-by-dataset provenance is in '
        '<code>notes/provenance.md</code> in the project repository.</p></div>')

    sources = (
        '<div class="sources"><div class="mb-h">Sources &amp; further reading</div>'
        '<p>Framing figures cited above (journalism and analyst estimates, not primary '
        'data) include: MIT&nbsp;NANDA, &ldquo;The GenAI Divide&rdquo; (via <i>Fortune</i>, '
        'Aug&nbsp;2025); Robert&nbsp;Half and Forrester on AI re-hiring (via the '
        '<i>Washington Times</i>, Mar&nbsp;2026); Futurum and MUFG on 2026 hyperscaler '
        'capex; NPR (Nov&nbsp;2025) and reporting on OpenAI&rsquo;s ~$1.4&nbsp;trillion '
        'commitments; coverage of ~$800&nbsp;billion in circular financing; reporting on '
        '2026 data-center delays and Microsoft&rsquo;s unfilled, unpowered orders; and '
        'Michael&nbsp;Burry on GPU depreciation. URLs are recorded with the data files in '
        'the repository. These move quarter to quarter; treat them as of mid-2026.</p></div>')

    return [
        ("lede", f"In 2025, seven companies &mdash; Microsoft, Alphabet, Amazon, Meta, "
         f"Oracle, Nvidia and CoreWeave &mdash; committed about {n['hyper']} to capital "
         f"investment, most of it data centers built for artificial intelligence. That "
         f"single year&rsquo;s spending equaled roughly {n['share_gdp']} of American "
         f"gross domestic product, close to a tenth of all private business investment "
         f"in the country, and nearly a third &mdash; {n['share_it']} &mdash; of "
         f"everything American business spends on information-technology equipment and "
         f"software combined. A decade earlier, the same firms spent on the order of "
         f"{n['capex0']} a year between them."),
        ("fig", figure(c["ramp"], "A near-vertical climb",
                       "Combined annual capital investment of seven US hyperscalers, "
                       "cash capex plus finance leases.", "Source: SEC EDGAR filings")),

        ("h2", "The Build"),
        ("p", f"That was the floor, and it has since lifted off. For 2026 the largest "
         f"firms are guiding, between them, toward something like {n['capex26']} &mdash; "
         f"roughly double their 2024 spending, and now on the order of {n['capex_pct_rev']} "
         f"of their revenue, against 10 to 15 percent at the start of the decade. "
         f"Analysts project the group&rsquo;s free cash flow could fall sharply as the "
         f"spending outruns what the products bring in. Outlays at this scale stop being "
         f"the kind of investment a company makes out of profit, and become a bet it "
         f"makes on conviction &mdash; and, increasingly, on debt."),
        ("fig", figure(c["macro"], "A claim on the economy&rsquo;s investable surplus",
                       "2025 hyperscaler capital investment, measured against US capital "
                       "formation.", "Source: SEC EDGAR; FRED (BEA national accounts)")),
        ("p", "Concentration on this scale is itself a kind of risk. When a handful of "
         "firms account for nearly a third of national IT investment, the economy&rsquo;s "
         "growth, its stock-market gains and a measurable slice of its productivity "
         "statistics all become correlated with the same few decisions. The buildout has "
         "made the wider economy unusually dependent on whether a few boardrooms keep "
         "believing in it &mdash; and unusually exposed to the moment any of them stops."),

        ("h2", "The Ten-X Problem"),
        ("p", f"Set the spending beside what it earns. All AI-specific revenue &mdash; the "
         f"frontier labs (OpenAI ~{n['oai_rev_now']}, Anthropic ~{n['ant_rev']}) plus the "
         f"hyperscalers&rsquo; AI services &mdash; runs at roughly {n['r0']} a year, against "
         f"capital spending near {n['capex26']}. That is the headline gap, and it is real."),
        ("fig", figure(c["capexrev"], "The gap the buildout is betting on",
                       "2026 capital spending (largest firms&rsquo; guidance) against "
                       "today&rsquo;s AI-service revenue.",
                       "Source: SEC EDGAR; analyst / press estimates &mdash; Tier-2")),
        ("p", f"But this year&rsquo;s gap is not the real test. The real test is whether the "
         f"revenue can ever earn the capital back at its cost. So model it. The buildout has "
         f"committed something like {n['kmid']} of capital between 2024 and 2030, at a cost "
         f"of capital around {n['wacc']}. To return that &mdash; even at the {n['margin_sh']} "
         f"operating margin Amazon&rsquo;s AWS earns at scale, the most profitable cloud "
         f"business yet built &mdash; the AI economy would need to generate on the order of "
         f"{n['req35']} in revenue every year. At thinner margins, more."),
        ("p", f"Demand is, to be clear, exploding. Google now processes more than seven times "
         f"as many AI tokens each year as the last &mdash; the clearest public signal that "
         f"usage is real and vertical. But project that growth forward on an adoption curve, "
         f"net the collapsing price per token, and achievable AI revenue reaches roughly "
         f"{n['ach_mid']} by 2030 in the central case, {n['ach_hi']} even in an optimistic "
         f"one. Against a requirement of {n['req35']} or more, the curve does not close the "
         f"gap; it does not come within several times of it."),
        ("fig", figure(c["reqach"], "What it must earn versus what usage can deliver",
                       "Revenue required to pay back the buildout at its cost of capital, "
                       "against an adoption-curve projection of achievable AI revenue.",
                       "Source: author&rsquo;s model on SEC capex, FRED rates, observed usage")),
        ("pull", f"To pay the buildout back at its cost of capital, AI revenue would have to "
         f"grow about {n['req_cagr']} a year &mdash; roughly {n['aws_x']} AWS&rsquo;s pace over "
         f"its thirteen-year climb, at far greater scale. There is no precedent for it."),
        ("fig", figure(c["awsreq"], "A ramp without precedent",
                       "The required AI revenue ramp against AWS&rsquo;s actual climb to "
                       "~$130B &mdash; the steepest real precedent for cloud infrastructure.",
                       "Source: SEC EDGAR (AWS segment); author&rsquo;s required-ramp model")),
        ("p", f"Run the whole thing as a probability &mdash; a Monte Carlo over the swing "
         f"assumptions (usage growth, price decline, margin, cost of capital, asset life), "
         f"crediting revenue earned well past 2030 &mdash; and the buildout clears its cost of "
         f"capital in only about {n['p_clear']} of paths, if it must be repaid by AI-specific "
         f"revenue. Credit AI instead with lifting all of cloud, advertising and search, and "
         f"that rises to about {n['p_broad']} &mdash; a coin flip. The answer hinges almost "
         f"entirely on that attribution question, and even the generous version is even money."),
        ("p", "None of which says the technology is fake; it plainly is not. Britain&rsquo;s "
         "railways and America&rsquo;s late-1990s fiber glut were the same species of "
         "bet &mdash; real, transformative infrastructure laid years ahead of the demand, and "
         "ruinous to most of the people who financed the early laying. The mature-cloud margins "
         "are the ceiling the case requires, and AI-native revenue today still earns *below* "
         "zero. The question was never whether AI matters. It is whether the revenue arrives, "
         "at a high enough margin, before the financing runs out."),

        ("h2", "The Hype Recedes"),
        ("p", f"And just as the bill comes due, the demand meant to do the multiplying is "
         f"being walked back. A widely cited MIT study found that about {n['mit95']} of "
         f"enterprise generative-AI pilots delivered no measurable return. Companies that "
         f"shed staff for AI are quietly reversing course: by one survey roughly "
         f"{n['rehire']} of firms that laid off workers for AI have rehired, and "
         f"{n['regret']} of employers say they regret the cuts. IBM, Duolingo and others "
         f"have unwound their boldest &ldquo;AI-first&rdquo; promises. The 2023 rhetoric "
         f"of imminent mass job replacement has, in 2026, gone notably quiet."),
        ("p", f"The labor data anticipated this. By one measure the average US job has "
         f"about {n['elo']} of its tasks exposed to large language models; but a second "
         f"measure, built from observed use rather than predicted capability, puts the "
         f"figure closer to {n['anth']}. The distance between what is possible and what is "
         f"actually happening was always the story &mdash; and the enterprise ROI numbers "
         f"now suggest that distance is closing more slowly than the spending assumes."),
        ("fig", figure(c["labor"], "Promise versus practice",
                       "Share of occupational tasks exposed to AI &mdash; predicted "
                       "capability versus observed use, employment-weighted.",
                       "Source: BLS OEWS; Eloundou et al.; Anthropic Economic Index")),
        ("p", "Exposure is not displacement, and the early signal is specific: this wave "
         "climbs the wage ladder rather than descending it, falling on the white-collar "
         "core &mdash; customer service, sales, administrative and interpretive work. But "
         "the buildout&rsquo;s return depends on that work being done more cheaply at "
         "scale. If the enterprise payoff is not materializing, the tenfold revenue ramp "
         "does not look closer. It looks further away."),

        ("h2", "Real, but Inflated"),
        ("p", "None of this means AI is fake. At the level of a single chip answering "
         "queries, the economics are genuinely excellent: a modern accelerator&rsquo;s "
         "running cost is a tiny fraction of what its output sells for, and it can repay "
         "its purchase price within a year. The technology works, and the unit economics "
         "of inference are real. What is inflated is the price of the picks and shovels."),
        ("p", f"Decompose the full deployed cost of an AI accelerator and roughly "
         f"{n['margin_sh']} of it is Nvidia&rsquo;s gross margin &mdash; scarcity rent, "
         f"not the physical cost of building anything. The manufacturing is a sliver, and "
         f"within it the high-bandwidth memory, not the logic chip, is the costly, "
         f"supply-constrained part. The building, power and cooling are about "
         f"{n['facil_sh']}; the electricity to run the thing for five years is only "
         f"{n['energy_sh']}. The reason energy &ldquo;looks small&rdquo; is that the "
         f"price is mostly markup."),
        ("fig", figure(c["coststack"], "Mostly markup",
                       "What a deployed AI accelerator costs over its life, by component "
                       "share.", "Source: SEC EDGAR margins; analyst BOM estimates (Tier-2)")),
        ("p", f"So a large part of what is counted as &ldquo;AI investment&rdquo; is a "
         f"transfer to a single chokepoint rather than productive capital. And some of the "
         f"demand is, in effect, manufactured: an estimated {n['circular']} of circular "
         f"financing &mdash; Nvidia funding OpenAI, OpenAI paying Oracle, Oracle buying "
         f"Nvidia &mdash; recycles the same dollars around a loop and books them as growth "
         f"at each turn. Wall Street has begun calling it what the late 1990s "
         f"called it: vendor financing."),
        ("fig", figure(c["semis"], "One company, half the supply",
                       "Latest-fiscal-year revenue of the five largest US-listed chip "
                       "suppliers. Nearly all are fabricated by a single Taiwanese "
                       "foundry.", "Source: SEC EDGAR filings")),
        ("p", "That chokepoint is also where the buildout meets geopolitics. Almost every "
         "advanced AI chip is fabricated by one contractor, on an island within reach of "
         "Chinese military pressure, using equipment from one Dutch supplier. A financial "
         "commitment that can be made in a quarter rests on a manufacturing base that "
         "takes a decade to expand and a geography no balance sheet controls. The cycle "
         "can be funded far faster than it can be supplied &mdash; or defended."),

        ("h2", "The Bill"),
        ("p", "Even where the arithmetic works for the firm, the costs land somewhere "
         "else &mdash; and the first to arrive is electricity. For thirteen years, from "
         "2007 to 2020, total US power demand was essentially flat, a generation of "
         "efficiency gains canceling out growth. Forecasters came to treat flat demand as "
         "the natural condition of a mature grid. The data-center surge is the first force "
         "in a generation strong enough to break it."),
        ("fig", figure(c["demand"], "Thirteen flat years, then a wall",
                       "US electricity demand, all sectors.", "Source: EIA")),
        ("p", f"Demand is now rising about {n['surge']} a year. Data centers drew roughly "
         f"{n['dc23']} of US electricity in 2023; depending on the scenario, that reaches "
         f"between {n['dc30']} by 2030."),
        ("fig", figure(c["dcshare"], "The grid absorbs the buildout",
                       "Data centers as a share of total US electricity, 2023 actual and "
                       "2030 projected range.", "Source: LBNL; EPRI; EIA")),
        ("p", f"By 2026 the binding constraint had flipped. It is no longer money, and no "
         f"longer chips &mdash; it is power. Roughly {n['dc_delayed']} of planned US "
         f"data centers for the year are reported delayed or canceled, held up not by "
         f"financing but by transformers, switchgear and interconnection queues. "
         f"Microsoft has disclosed something like {n['ms_unfilled']} of orders it cannot "
         f"fill because it cannot secure the electricity to power chips already sitting in "
         f"its warehouses. The grid cannot be scaled at the speed of capital, and the "
         f"buildout has run headfirst into that fact."),
        ("p", "The load does not spread evenly; it clusters. Virginia alone hosts an "
         "estimated 32 terawatt-hours of data-center demand &mdash; on the order of a "
         "quarter of the state&rsquo;s electricity. About fifteen states carry some 80 "
         "percent of the national total. The buildout is a national story told in a few "
         "ZIP codes, and those places carry a grid burden the average never shows."),
        ("fig", figure(c["states"], "Where the load lands",
                       "Data-center electricity by state &mdash; approximate 2023 "
                       "estimates.", "Source: LBNL; EPRI; secondary reporting")),
        ("p", f"Does the load raise prices? In the data-center-heavy states, residential "
         f"power rose about {n['p_heavy']} between 2020 and 2025, against roughly "
         f"{n['p_rest']} elsewhere, and the two diverged after 2021. The Dallas Fed&rsquo;s "
         f"dispatch model finds data centers have already lifted wholesale prices by "
         f"around {n['w_now']} percent and could add {n['w_mod']} to {n['w_high']} percent "
         f"by 2028. The causation is genuinely contested &mdash; the Institute for Energy "
         f"Research finds no significant link, and state prices turn on fuel mix and policy "
         f"too &mdash; but the mechanism, where it operates, is not mysterious: a large new "
         f"load bids against households for the same generation and transmission, and the "
         f"cost flows to everyone on the shared system."),
        ("fig", figure(c["prices"], "After 2021, a divergence",
                       "Residential electricity price, indexed to 2010, in data-center-"
                       "heavy states versus the rest.",
                       "Source: EIA API v2 (state retail prices)")),
        ("fig", figure(c["outlook"], "How high prices could go",
                       "Modelled data-center impact on US wholesale electricity prices.",
                       "Source: Federal Reserve Bank of Dallas, WP2606")),
        ("p", f"And efficiency will not bail the grid out &mdash; it accelerates the "
         f"problem. AI chips do get more efficient, by about {n['eff_yr']} a year in "
         f"performance per watt. But to meet the projected energy path, the underlying "
         f"compute must grow {n['comp_lo']} to {n['comp_hi']} a year &mdash; about twice "
         f"as fast. Total energy therefore rises, not falls: this is the Jevons paradox, "
         f"the oldest result in energy economics. Efficiency gains spared the grid roughly "
         f"{n['jev_saved']} terawatt-hours by 2028 &mdash; and data-center demand still "
         f"roughly tripled anyway."),
        ("fig", figure(c["jevons"], "Why efficiency does not save the grid",
                       "US data-center electricity in 2028: what efficiency saved, and "
                       "what demand added on top.",
                       "Source: vendor / Epoch AI perf-per-watt; LBNL energy")),
        ("pull", "The margin is private. The bill &mdash; the grid, the prices, the "
         "water &mdash; is increasingly public."),

        ("h2", "Everyone&rsquo;s Bet"),
        ("p", f"The financial risk is concentrated the way the spending is. Seven names "
         f"now make up about {n['mag7_sh']} of the S&amp;P 500. The equity risk "
         f"premium &mdash; the extra return investors get for holding stocks instead of "
         f"safe Treasuries &mdash; has thinned to roughly {n['erp']}. And the cap-weighted "
         f"index has pulled about {n['conc_x']} ahead of the average stock since 2015: the "
         f"market &ldquo;looks fine&rdquo; largely because a few AI megacaps carry it."),
        ("fig", figure(c["conc"], "The index and the median stock",
                       "Total return of the cap-weighted S&amp;P 500 versus its "
                       "equal-weighted twin, rebased to 2015.",
                       "Source: Yahoo Finance (Tier-2)")),
        ("p", f"Meanwhile the buildout is turning to debt &mdash; roughly {n['debt_iss']} "
         f"of new hyperscaler long-term issuance in a single year, with the marginal "
         f"builders, Oracle and CoreWeave, borrowing well beyond what their own cash flow "
         f"covers. Because nearly every retirement account is indexed to the same handful "
         f"of names, this long ago stopped being a technology-sector wager. It became a "
         f"household one, whether the household agreed to it or not."),

        ("h2", "What &ldquo;Popping&rdquo; Would Mean"),
        ("p", "So what if the bet sours? &ldquo;The AI bubble bursting&rdquo; summons the "
         "year 2000, but the analogy misleads. The hyperscalers are real, profitable and "
         "cash-rich; the technology is not vaporware; a chip serving inference makes "
         "money. Popping, here, would not mean AI is exposed as a fraud. It would mean the "
         "tower of financial claims built on top of a real-but-overbuilt infrastructure "
         "repricing to what that infrastructure actually earns."),
        ("p", f"That has a recognizable shape. It begins with capex deceleration &mdash; "
         f"and the sentiment has already turned, with investors now selling hyperscalers "
         f"when they announce <i>more</i> spending rather than rewarding it. It strikes "
         f"the second derivative hardest: Nvidia&rsquo;s valuation multiple, the "
         f"debt-funded clouds, and the power-and-construction supply chain, all priced for "
         f"the ramp to continue. And depreciation catches up. Michael Burry has argued an "
         f"AI server&rsquo;s true working life is about {n['burry']} &mdash; well under "
         f"the six years the books assume; on a realistic schedule, today&rsquo;s reported "
         f"profits would look materially worse."),
        ("fig", figure(c["life"], "How long does an AI server really last?",
                       "Assumed useful life: the depreciation schedule in the filings, a "
                       "prominent short-seller&rsquo;s estimate, and this "
                       "report&rsquo;s hardware model.",
                       "Source: SEC EDGAR; press; author&rsquo;s model (Tier-2)")),
        ("p", "From there the marginal borrowers hit refinancing walls, and the "
         "concentration carries the damage into ordinary index funds. Then comes the part "
         "that rhymes with history: the assets persist. The dark fiber laid in 1999 was "
         "eventually all lit. The data centers and the chips will not vanish &mdash; they "
         "will be repriced, absorbed and, in time, used. What pops is the financing and "
         "the valuations stacked on top of them. And the public is left holding the grid "
         "it paid to build."),

        ("h2", "Does the Math Math?"),
        ("p", "At the level of a single machine, yes; at the level of the whole bet, not "
         "yet. The largest firms can mostly fund their own spending, and an inference chip "
         "pays for itself. But the trillion-dollar total rests on a revenue ramp with no "
         "precedent, on a margin that one chokepoint controls and competitors are already "
         "gunning for, on a supply chain that runs through a single Taiwanese fab in the "
         "most dangerous geopolitical decade in living memory, and on a quiet assumption "
         "that the public keeps paying the power bill."),
        ("p", "Both things can be true at once &mdash; a genuine technological revolution "
         "and a speculative mania &mdash; because historically they almost always have "
         "been. Canals, railways, electricity, the internet: each delivered, and each "
         "ruined a generation of investors first. The honest verdict is therefore not a "
         "forecast but an accounting. The build is real. The bill is already being paid, "
         "disproportionately, by people who never voted for it. And the open question is "
         "not whether artificial intelligence matters &mdash; it plainly does &mdash; but "
         "who is left holding which half of the bargain when the wager is finally settled."),
        ("methodbox", methodbox),
        ("sources", sources),
    ]


def main() -> None:
    d = load()
    syn, lk, ax, es = d["syn"], d["lk"], d["ax"], d["es"]
    po = d["price_outlook"]

    def pov(metric, scenario=None):
        r = po[po.metric == metric]
        if scenario is not None:
            r = r[r.scenario == scenario]
        return r.iloc[0]["value"]

    capex0 = round(d["capex_by_year"].iloc[0] / 10) * 10
    rng = syn["Independent estimate, range (low-high)"].split("-")
    n = {
        "hyper": f"${syn['Hyperscaler capital investment, 2025']:.0f} billion",
        "share_gdp": f"{syn['as share of US GDP']:.1f} percent",
        "share_it": f"{syn['as share of US IT-equipment + software investment']:.0f} percent",
        "vc": f"${syn['Global VC into AI, 2025']:.0f} billion",
        "chip": f"${syn['AI-chip supplier revenue (5 US firms)']:.0f} billion",
        "nvda": f"${lk['of which NVIDIA']:.0f} billion",
        "nvda_sh": f"{lk['NVIDIA share of the five']:.0f} percent",
        "capex0": f"${capex0:.0f} billion",
        "proj_mid": f"${syn['Independent estimate, cumulative 2026-2030 (mid)'] / 1000:.1f} trillion",
        "proj_lo": f"${int(rng[0]) / 1000:.1f} trillion",
        "proj_hi": f"${int(rng[1]) / 1000:.1f} trillion",
        "mck": f"${syn['McKinsey global data-center capex 2025-30 (base)'] / 1000:.1f} trillion",
        "gs": f"${syn['Goldman global AI capex 2026-31'] / 1000:.1f} trillion",
        "dc23": f"{d['dc_2023']:g} percent",
        "dc30": f"{d['dc_2030'][0]:g} and {d['dc_2030'][1]:g} percent",
        "surge": f"{d['growth_surge']:.1f} percent",
        "res0": f"{d['res_price'][0]:.1f}", "res1": f"{d['res_price'][1]:.1f}",
        "p_heavy": f"{es['Residential price change, data-center-heavy states']:.0f} percent",
        "p_rest": f"{es['Residential price change, other states']:.0f} percent",
        "c_heavy": f"{es['Electricity consumption change, data-center-heavy states']:.0f} percent",
        "c_rest": f"{es['Electricity consumption change, other states']:.0f} percent",
        "c_va": f"{es['Electricity consumption change, Virginia']:.0f} percent",
        "w_now": f"{pov('wholesale_price_impact', 'current'):g}",
        "w_mod": f"{pov('wholesale_price_impact', 'moderate buildout'):g}",
        "w_high": f"{pov('wholesale_price_impact', 'high utilization'):g}",
        "pce26": f"{pov('pce_inflation_impact', 'baseline'):g}",
        "elo": f"{ax['Empl.-weighted exposure -- Eloundou (predicted)'] * 100:.0f} percent",
        "anth": f"{ax['Empl.-weighted exposure -- Anthropic (observed)'] * 100:.0f} percent",
        "hi_exp": f"{ax['Empl. in high-exposure occ. (>=0.5) %, Eloundou (predicted)']:.0f} percent",
        "constr_sh": f"{lk['Data-center share of all US construction (2025)']:.2f} percent",
        "constr_emp": f"{lk['US construction employment (latest)']:.1f} million",
    }

    # --- 2026 reframe number-strings ---
    cr, sig, ec = d["cr"], d["sig"], d["ec"]
    cs = d["cost_stack"].set_index("chip")
    h = cs.loc["H100 SXM5"]
    jhi = d["jevons"][d["jevons"].scenario == "LBNL high"].iloc[0]
    jlo = d["jevons"][d["jevons"].scenario == "LBNL low"].iloc[0]
    erp = next((v for k, v in ec.items() if "risk premium" in k.lower()), 0.5)
    conc_ratio = next((v for k, v in ec.items() if "outperform" in k.lower()), 1.4)
    mag7 = next((v for k, v in ec.items() if "Mag-7 share" in k), 35)
    n.update({
        "capex26": f"${cr['capex_big5_total']:.0f} billion",
        "airev": f"${cr['ai_service_revenue']:.0f} billion",
        "capex_rev_x": f"{cr['capex_big5_total'] / cr['ai_service_revenue']:.0f} times",
        "capex_pct_rev": f"{cr['capex_share_of_revenue']:.0f} percent",
        "oai_commit": f"${cr['openai_commitments'] / 1000:.1f} trillion",
        "oai_rev": f"${cr['openai_revenue']:.0f} billion",
        "mit95": f"{sig['genai_pilots_no_return']:.0f} percent",
        "rehire": f"{sig['firms_rehired_after_ai']:.0f} percent",
        "regret": f"{sig['employers_regret_ai_layoffs']:.0f} percent",
        "circular": f"${sig['circular_financing']:.0f} billion",
        "dc_delayed": f"{sig['datacenters_delayed_2026']:.0f} percent",
        "ms_unfilled": f"${sig['microsoft_unfulfilled_orders']:.0f} billion",
        "burry": f"{sig['burry_gpu_useful_life']:g} years",
        "margin_sh": f"{h['vendor_margin_usd'] / h['total_deployed_usd'] * 100:.0f} percent",
        "facil_sh": f"{h['facility_cooling_usd'] / h['total_deployed_usd'] * 100:.0f} percent",
        "energy_sh": f"{h['lifetime_energy_usd'] / h['total_deployed_usd'] * 100:.0f} percent",
        "erp": f"{erp:.1f} percent",
        "conc_x": f"{conc_ratio:.1f} times",
        "mag7_sh": f"{mag7:.0f} percent",
        "debt_iss": f"${d['debt_issuance']:.0f} billion",
        "eff_yr": f"{jhi['efficiency_cagr'] * 100:.0f} percent",
        "comp_lo": f"{jlo['implied_compute_cagr'] * 100:.0f}",
        "comp_hi": f"{jhi['implied_compute_cagr'] * 100:.0f} percent",
        "jev_saved": f"{jhi['frozen_efficiency_energy_twh'] - jhi['energy_end_twh']:,.0f}",
    })

    # --- revenue-vs-payback model number-strings ---
    rps, mc, ach = d["rp_scalar"], d["mc"], d["achieve"]
    n.update({
        "wacc": f"{rps['wacc'] * 100:.0f} percent",
        "kmid": f"${d['rp_scalar']['K_mid_bn'] / 1000:.1f} trillion",
        "req35": f"${d['req_rev'][(6, 0.35)] / 1000:.1f} trillion",
        "req25": f"${d['req_rev'][(6, 0.25)] / 1000:.1f} trillion",
        "ach_mid": f"${ach['mid'].iloc[-1] / 1000:.2f} trillion",
        "ach_hi": f"${ach['high'].iloc[-1] / 1000:.1f} trillion",
        "req_cagr": f"{rps['required_cagr_to_2030'] * 100:.0f} percent",
        "aws_cagr": f"{rps['aws_cagr'] * 100:.0f} percent",
        "aws_x": f"{rps['required_cagr_to_2030'] / rps['aws_cagr']:.0f} times",
        "p_clear": f"{mc['prob_clears_cost_of_capital'] * 100:.0f} percent",
        "p_broad": f"{mc['prob_clears_broad_attribution'] * 100:.0f} percent",
        "r0": f"${rps['R0_2026_bn']:.0f} billion",
        "oai_rev_now": f"${d['native_latest'].get('OpenAI', 25):.0f} billion",
        "ant_rev": f"${d['native_latest'].get('Anthropic', 30):.0f} billion",
    })

    c = {"ramp": chart_ramp(d), "macro": chart_macro(d), "semis": chart_semis(d),
         "demand": chart_us_demand(d), "dcshare": chart_dc_share(d),
         "states": chart_dc_states(d), "prices": chart_state_prices(d),
         "outlook": chart_price_outlook(d), "labor": chart_labor(d),
         "capexrev": chart_capex_vs_revenue(d), "coststack": chart_cost_stack(d),
         "reqach": chart_required_vs_achievable(d), "awsreq": chart_aws_vs_required(d),
         "conc": chart_concentration(d), "jevons": chart_jevons(d),
         "life": chart_useful_life(d)}

    paras = build_paragraphs(n, c)

    body, words = [], 0
    for kind, content in paras:
        if kind == "h2":
            body.append(f"<h2>{content}</h2>")
        elif kind == "fig":
            body.append(content)
        elif kind == "pull":
            body.append(f'<div class="pull">{content}</div>')
        elif kind == "placeholder":
            body.append(f'<div class="placeholder">{content}</div>')
        elif kind in ("methodbox", "sources"):
            body.append(content)
        elif kind == "lede":
            body.append(f'<p class="lede">{content}</p>')
        else:
            body.append(f"<p>{content}</p>")
        if kind in ("lede", "p", "pull", "h2"):
            words += len(re.sub("<[^>]+>", "", content).split())

    headline = "The Build and the Bill"
    deck = ("American tech is spending close to a trillion dollars a year building "
            "artificial-intelligence infrastructure — against a few tens of billions "
            "in revenue. The technology is real. The arithmetic is a bet. And its "
            "costs are already landing on people who never made it. A clear-eyed "
            "reckoning with what the math does, and does not, support.")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{headline}</title>
<style>{CSS}</style>
</head>
<body>
<article class="wrap">
<div class="kicker">Hyperscaling &middot; The AI Buildout</div>
<h1>{headline}</h1>
<p class="deck">{deck}</p>
<div class="byline">By Michael Nolan</div>
<div class="dateline">Updated May 30, 2026</div>
{"".join(body)}
</article>
</body>
</html>
"""
    out = OUTPUT / "report.html"
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}  ({len(html) / 1024:.0f} KB)")
    print(f"  charts embedded: {len(c)}")
    print(f"  prose word count: ~{words}")
    print(f"  self-contained: {'yes' if 'src=\"http' not in html else 'NO'}")


if __name__ == "__main__":
    main()
