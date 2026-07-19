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


def _fcov(d, company):
    """Latest-FY operating-cash-flow / capex coverage for one firm, from ai_financing."""
    r = d["funding"][d["funding"]["company"] == company]
    return float(r["coverage_ocf_over_capex"].iloc[0]) if not r.empty else float("nan")


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
    d["ocf_agg"] = float(agg["operating_cash_flow_usd_bn"].iloc[0]) if not agg.empty else 683.0
    d["cov_agg"] = float(agg["coverage_ocf_over_capex"].iloc[0]) if not agg.empty else 1.73
    d["funding"] = (fin[fin["section"] == "latest_fy_by_firm"]
                    .dropna(subset=["coverage_ocf_over_capex"])
                    .sort_values("coverage_ocf_over_capex"))

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

    circ = pd.read_csv(MANUAL / "circular_financing.csv", comment="#")
    d["circ"] = circ
    d["circ_edge"] = {(r.source, r.target): float(r.amount_usd_billion) for r in circ.itertuples()}
    d["oai_commit_sum"] = circ[circ.source == "OpenAI"]["amount_usd_billion"].sum()

    # --- Broadening layer: BEA macro-attribution + AI-industrial-complex footprint ---
    d["macro_attr"] = pd.read_csv(OUTPUT / "macro_attribution.csv")
    cx = pd.read_csv(OUTPUT / "ai_complex_summary.csv")
    d["complex"] = cx.sort_values("revenue_bn", ascending=False).reset_index(drop=True)
    # --- Systemic-financing / private-credit layer (primary SEC anchor + validated Tier-2) ---
    pcs = pd.read_csv(OUTPUT / "private_credit_summary.csv")
    d["pcredit"] = {m: to_num(v) for m, v in zip(pcs["metric"], pcs["value"])}
    d["eqfund"] = pd.read_csv(OUTPUT / "equity_funding_summary.csv")
    dbt = pd.read_csv(PROCESSED / "hyperscaler_debt.csv")
    d["debt_traj"] = (dbt.pivot_table(index="fiscal_year", columns="ticker",
                                      values="long_term_debt_usd", aggfunc="last") / 1e9)
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


def chart_gdp_attribution(d):
    ma = d["macro_attr"].copy()
    yr = ma["time_period"].str.slice(0, 4).astype(int)
    q = ma["time_period"].str.slice(5, 6).astype(int)
    ma["t"] = yr + (q - 1) / 4.0
    fig, ax = plt.subplots(figsize=(8, 3.4))
    ax.plot(ma["t"], ma["it_pct_of_gdp"], color=NAVY, linewidth=2.2)
    ax.fill_between(ma["t"], ma["it_pct_of_gdp"], color=NAVY, alpha=0.08)
    lo, hi = ma["it_pct_of_gdp"].iloc[0], ma["it_pct_of_gdp"].iloc[-1]
    ax.text(ma["t"].iloc[-1], hi, f"  {hi:.1f}%", va="center", ha="left",
            fontsize=10.5, weight="bold", color=NAVY)
    ax.text(ma["t"].iloc[0], lo, f"{lo:.1f}%  ", va="center", ha="right",
            fontsize=9.5, color=GREY)
    ax.set_ylabel("% of GDP")
    ax.set_ylim(0, hi * 1.22)
    ax.set_xlim(ma["t"].iloc[0] - 0.5, ma["t"].iloc[-1] + 2.2)
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_complex_footprint(d):
    cx = d["complex"]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    bars = ax.barh(cx["layer"], cx["revenue_bn"], color=NAVY, height=0.66)
    for b, v in zip(bars, cx["revenue_bn"]):
        ax.text(v + 2, b.get_y() + b.get_height() / 2, f"${v:,.0f}B",
                va="center", fontsize=9.5, weight="bold")
    ax.invert_yaxis()
    ax.set_xlabel("AI-exposed revenue, USD billion (upper bound, not AI-only)")
    ax.set_xlim(0, cx["revenue_bn"].max() * 1.18)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    return fig_to_b64(fig)


def chart_funding_sources(d):
    e = d["eqfund"].sort_values("coverage").copy()
    e["rev"] = e["coverage"].clip(upper=1.0) * 100
    e["out"] = 100 - e["rev"]
    y = list(range(len(e)))
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.barh(y, e["rev"], color=NAVY, height=0.6,
            label="Funded by operating cash flow (revenue)")
    ax.barh(y, e["out"], left=e["rev"], color=RED, height=0.6,
            label="Must come from debt / outside")
    for i, (rev, out) in enumerate(zip(e["rev"], e["out"])):
        if out > 3:
            ax.text(rev + out / 2, i, f"{out:.0f}%", va="center", ha="center",
                    color="white", fontsize=8.5, weight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels(e["company"])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of latest-year capital spending")
    ax.legend(loc="lower right", fontsize=7.5, frameon=False)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    return fig_to_b64(fig)


def chart_debt_trajectory(d):
    p = d["debt_traj"]
    p = p[p.index >= 2016]
    style = {
        "MSFT": (NAVY_LT, "Microsoft", 2.0), "NVDA": (GREY, "Nvidia", 1.6),
        "GOOGL": (RED, "Alphabet", 2.4), "META": (NAVY, "Meta", 2.4),
        "AMZN": (NAVY_MID, "Amazon", 1.8), "ORCL": (GOLD, "Oracle", 1.8),
        "CRWV": ("#6a4c93", "CoreWeave", 1.8),
    }
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for tk, (col, lab, lw) in style.items():
        if tk not in p.columns:
            continue
        s = p[tk].dropna()
        if s.empty:
            continue
        ax.plot(s.index, s.values, color=col, linewidth=lw, label=lab)
        ax.scatter([s.index[-1]], [s.values[-1]], color=col, s=16, zorder=3)
    ax.set_ylabel("Long-term debt, USD billion")
    ax.set_xlim(p.index.min(), p.index.max() + 0.4)
    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=2)
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_debt_financing(d):
    f = d["funding"].copy()
    f["dfs"] = pd.to_numeric(f["debt_funded_share"], errors="coerce").fillna(0.0) * 100
    f = f.sort_values("dfs")
    colors = [RED if v >= 50 else NAVY for v in f["dfs"]]
    fig, ax = plt.subplots(figsize=(8, 3.4))
    bars = ax.barh(f["company"], f["dfs"], color=colors, height=0.62)
    for b, v in zip(bars, f["dfs"]):
        ax.text(v + 1.5, b.get_y() + b.get_height() / 2, f"{v:.0f}%",
                va="center", fontsize=9.5, weight="bold")
    ax.set_xlabel("Share of latest-FY capital spending funded by new debt")
    ax.set_xlim(0, max(f["dfs"].max() * 1.16, 10))
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
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
            label="Achievable (usage S-curve)")
    ax.plot(years, ach["low"], color=NAVY, lw=1, ls=":")
    ax.plot(years, ach["high"], color=NAVY, lw=1, ls=":")
    ax.axhline(d["req_rev"][(6, 0.35)], color=RED, lw=2, ls="--",
               label="Required @ 35% margin")
    ax.axhline(d["req_rev"][(6, 0.25)], color=GOLD, lw=2, ls="--",
               label="Required @ 25% margin")
    ax.axhline(2000, color=GREY, lw=1, ls="-.", label="Bain ~$2T 'cover cost'")
    ax.set_ylabel("AI revenue, USD billion / year")
    ax.set_ylim(0, d["req_rev"][(6, 0.25)] * 1.1)
    ax.set_xticks(years)
    ax.legend(fontsize=8.5, frameon=False, loc="center left", bbox_to_anchor=(1.02, 0.5))
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


def chart_funding_coverage(d):
    f = d["funding"]
    cov = f["coverage_ocf_over_capex"].astype(float)
    names = f["company"]
    colors = [RED if c < 1 else NAVY for c in cov]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    bars = ax.barh(names, cov, color=colors, height=0.64)
    ax.axvline(1.0, color=INK, lw=1.4, ls="--")
    ax.text(1.02, -0.45, "self-funds →", fontsize=8, color=NAVY)
    ax.text(0.98, -0.45, "← needs outside money", fontsize=8, color=RED, ha="right")
    for b, c in zip(bars, cov):
        ax.text(c + 0.05, b.get_y() + b.get_height() / 2, f"{c:.2f}×",
                va="center", fontsize=9, weight="bold")
    ax.set_xlabel("Operating cash flow ÷ capex (latest fiscal year)")
    ax.set_xlim(0, max(cov) * 1.15)
    ax.grid(axis="y", visible=False)
    return fig_to_b64(fig)


def chart_circular(d):
    e = d["circ_edge"]
    fig, ax = plt.subplots(figsize=(8, 5.4))
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
    pos = {"NVIDIA": (5, 8.7), "OpenAI": (2.2, 2.6), "Oracle /\nCoreWeave": (7.8, 2.6),
           "Microsoft": (1.0, 7.4)}
    boxc = {"NVIDIA": RED, "OpenAI": NAVY, "Oracle /\nCoreWeave": NAVY_MID, "Microsoft": GREY}
    for name, (x, y) in pos.items():
        ax.text(x, y, name, ha="center", va="center", fontsize=10.5, weight="bold",
                color="white", bbox=dict(boxstyle="round,pad=0.5", fc=boxc[name], ec="none"))

    def arrow(a, b, label, rad, lab_xy, color=INK, lw=2.4):
        (x0, y0), (x1, y1) = pos[a], pos[b]
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, shrinkA=30,
                                    shrinkB=30, connectionstyle=f"arc3,rad={rad}"))
        ax.text(lab_xy[0], lab_xy[1], label, ha="center", va="center", fontsize=9,
                color=color, weight="bold")

    # clean clockwise triangle loop, arrows bowing OUTWARD
    arrow("NVIDIA", "OpenAI", f"invests\n~${e[('NVIDIA','OpenAI')]:.0f}B", rad=0.22, lab_xy=(2.9, 6.1))
    arrow("OpenAI", "Oracle /\nCoreWeave", f"~${e[('OpenAI','Oracle')]:.0f}B+ compute deals",
          rad=-0.25, lab_xy=(5, 1.0))
    arrow("Oracle /\nCoreWeave", "NVIDIA", "buy the GPUs", rad=0.22, lab_xy=(7.3, 6.1))
    # one satellite: Microsoft also funds OpenAI
    arrow("Microsoft", "OpenAI", "invests", rad=0.0, color=GREY, lw=1.4, lab_xy=(1.0, 4.9))
    ax.text(5, 9.7, "The money goes in a circle", ha="center", fontsize=12, weight="bold")
    ax.text(5, 0.2, "≈ $800B of commitments circulating — each lap booked as growth",
            ha="center", fontsize=8.8, style="italic", color=GREY)
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
:root { --ink:#121212; --grey:#6b6b6b; --rule:#dcdcdc; --link:#1a3a5c; }
a { color:var(--link); text-decoration:none; border-bottom:1px solid #c9c9c9; }
a:hover { border-bottom-color:var(--link); }
.sources a, .fig-src a { border-bottom-color:#cfcfcf; }
.cmp-wrap { overflow-x:auto; margin:1.7rem 0; }
table.cmp { width:100%; border-collapse:collapse; font-size:.92rem; min-width:33rem; }
table.cmp th, table.cmp td { text-align:left; vertical-align:top; padding:.55rem .8rem; border-bottom:1px solid var(--rule); }
table.cmp thead th { border-bottom:2px solid var(--ink); font-family:'Helvetica Neue',Arial,sans-serif; font-size:.72rem; letter-spacing:.05em; text-transform:uppercase; color:var(--grey); }
table.cmp td:first-child { color:var(--grey); width:47%; }
table.cmp tbody tr:last-child td { border-bottom:2px solid var(--ink); }
.watch { border:1px solid var(--rule); border-left:3px solid var(--ink); padding:1.15rem 1.35rem; margin:1.9rem 0; background:#fafafa; }
.watch .w-h { font-family:'Helvetica Neue',Arial,sans-serif; font-size:.74rem; letter-spacing:.05em; text-transform:uppercase; color:var(--grey); margin-bottom:.8rem; }
.watch .keystone { padding:.7rem .9rem; background:#fff; border:1px solid var(--rule); margin-bottom:.85rem; }
.watch ol { margin:0; padding-left:1.25rem; }
.watch li { margin:.5rem 0; padding-left:.15rem; }
.watch .meta { margin-top:1rem; font-style:italic; color:var(--grey); font-size:.93rem; }
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


def comparison_table():
    rows = [
        ("Cheap money and a global savings glut inflate housing",
         "Cheap global credit &mdash; yen carry, the zero-rate decade &mdash; inflates tech "
         "valuations"),
        ("Teaser-rate mortgages: affordable only if refinanced before they reset",
         "Labs and neoclouds: solvent only if refinanced at a higher valuation mark"),
        ("Refinancing works while house prices keep <i>rising</i>",
         "Refinancing works while valuations keep <i>stepping up</i>"),
        ("<b>Breaks when appreciation merely slows</b> &mdash; the refinancing door shuts",
         "<b>Breaks when capex and valuation growth merely slow</b> &mdash; the mark step-ups "
         "stall"),
        ("First defaults hit subprime borrowers &mdash; the fringe",
         "First cracks hit CoreWeave, Oracle and the labs &mdash; the fringe"),
        ("Securitization spreads the risk into &ldquo;safe&rdquo; AAA tranches held everywhere",
         "Private credit, GPU-backed notes and index funds spread it to insurers, pensions and "
         "savers"),
        ("The tranches rated &lsquo;safe&rsquo; were the ones that blew up",
         "The parts that look safe &mdash; hyperscaler bonds, index funds &mdash; are where the "
         "losses would land"),
        ("Lehman: a refinancing that could not be rolled froze the system",
         "The terminal refinance &mdash; an OpenAI down-round or failed IPO &mdash; that prices "
         "below the mark"),
    ]
    trs = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in rows)
    return ('<div class="cmp-wrap"><table class="cmp"><thead><tr>'
            '<th>The subprime cycle &middot; 2008</th>'
            '<th>The AI buildout &middot; 2026</th></tr></thead>'
            f'<tbody>{trs}</tbody></table></div>')


def watchlist():
    keystone = (
        '<div class="keystone"><b>The keystone &mdash; OpenAI&rsquo;s terminal refinance.</b> '
        'Its rounds now step up by less each time &mdash; the latest was $122&nbsp;billion at an '
        '$852&nbsp;billion valuation, and the IPO, targeted for late 2026 at about '
        '$1&nbsp;trillion, is already at risk of slipping to 2027. It is roughly half of both '
        'Microsoft&rsquo;s and Oracle&rsquo;s AI backlog, so if its valuation stops climbing '
        'the whole circle loses the ability to refinance. <b>The tell:</b> that IPO prices '
        'flat or down, slips again, or is pulled &mdash; the moment its valuation stops rising '
        'is the moment everything stacked on that one refinance comes undone.</div>')
    items = [
        ("The plumbing (already amber).",
         "AI bond order books have fallen from about five-times-covered to under two. Next: a "
         "pulled or sharply-repriced AI bond deal, or a data-center-securitization downgrade."),
        ("The reflexive flip.",
         "The first hyperscaler that <i>cuts</i> capex guidance and is <i>rewarded</i> by its "
         "stock. The day the market pays a CFO to stop building, the &ldquo;can&rsquo;t sit "
         "out&rdquo; logic that drives the whole overhang inverts, and the others follow."),
        ("The collateral.",
         "GPU rental and resale prices falling, or a hyperscaler shortening its server "
         "useful-life assumption or taking a write-down &mdash; &ldquo;house prices fall&rdquo; "
         "for the hardware now being securitized into AAA-rated notes."),
        ("The fuel.",
         "A sharp move higher in the yen or a hawkish Bank-of-Japan surprise &mdash; the carry "
         "unwind. Watch the yen strengthening from around 161 toward 145, and a regime shift in "
         "the volatility index."),
        ("The contagion confirm.",
         "Edge stress &mdash; the weakest borrowers already pay nearly ten points over "
         "Treasuries &mdash; dragging investment-grade and high-yield spreads wider, and the "
         "record calm finally cracking."),
    ]
    lis = "".join(f"<li><b>{a}</b> {b}</li>" for a, b in items)
    meta = (
        '<div class="meta">The rule underneath all of them: watch the rate of change, not the '
        'level. The warning sign is growth <i>slowing</i> while the numbers are still at '
        'records &mdash; capex still climbing but by less, valuations still rising but by less '
        '&mdash; and the cleanest place to see it is OpenAI&rsquo;s next valuation.</div>')
    return ('<div class="watch"><div class="w-h">What to watch &mdash; the precursors, in the '
            f'order they light up</div>{keystone}<ol>{lis}</ol>{meta}</div>')


def build_paragraphs(n, c):
    """The long-read narrative as a list of (kind, content) tuples."""
    methodbox = (
        '<div class="methodbox"><div class="mb-h">How this was measured</div>'
        '<p>The spine of this report is a reproducible, primary-source pipeline. '
        'Hyperscaler and chip-maker capital spending, debt, stock-based pay, buybacks, '
        'depreciation and margins '
        'are extracted from SEC EDGAR filings, and the wider supply-chain footprint from '
        'EDGAR company facts; macro, rates and credit series from the Federal '
        'Reserve&rsquo;s FRED; national-accounts investment and output, and household wealth '
        'distribution, from the Bureau of Economic Analysis and the Fed&rsquo;s Distributional '
        'Financial Accounts; electricity demand and prices, national and by '
        'state, from the US Energy Information Administration; occupational employment '
        'from the Bureau of Labor Statistics; accelerator specifications from vendor '
        'datasheets cross-checked against Epoch&nbsp;AI. Data-center energy is from '
        'Lawrence Berkeley National Laboratory; AI-exposure scores from Eloundou '
        'et&nbsp;al. and the Anthropic Economic Index; price modelling from the Federal '
        'Reserve Bank of Dallas.</p>'
        '<p>The chip total-cost-of-ownership, economic-obsolescence, token-economics and '
        'Jevons models are the author&rsquo;s, built on those inputs; vendor performance '
        'figures, bill-of-materials estimates, and the 2026 capex/revenue, adoption and '
        'systemic-financing figures (the latter including the FSB private-credit report and '
        'bank and dealer research) are second-tier (analyst and press) and are flagged as '
        'such, attributed '
        'in the text, and listed in Sources below. They frame; they are not the data of '
        'record. Contested questions &mdash; whether data centers cause local price rises, '
        'whether the buildout is &ldquo;backstopped,&rdquo; what an AI chip&rsquo;s true '
        'life is &mdash; are left contested. Full dataset-by-dataset provenance is in '
        '<code>notes/provenance.md</code> in the project repository.</p></div>')

    sources = (
        '<div class="sources"><div class="mb-h">Sources &amp; further reading</div>'
        '<p>Framing figures cited above are journalism and analyst estimates, not the '
        'primary-source pipeline; they are attributed inline and flagged Tier-2. They move '
        'quarter to quarter &mdash; treat them as of mid-2026 and confirm against the linked '
        'source before re-quoting. Full dataset-by-dataset provenance, including these URLs, '
        'is in <code>notes/provenance.md</code>.</p>'
        '<p><b>Adoption &amp; the hype reversal.</b> MIT&nbsp;NANDA, &ldquo;The GenAI '
        'Divide&rdquo; (95% of enterprise pilots show no P&amp;L return), via '
        '<a href="https://fortune.com/2025/08/18/mit-report-95-percent-generative-ai-pilots-at-companies-failing-cfo/">'
        '<i>Fortune</i>, Aug&nbsp;2025</a>; Robert&nbsp;Half and Forrester on post-AI '
        're-hiring, via the '
        '<a href="https://www.washingtontimes.com/news/2026/mar/10/ai-layoff-reversal-companies-rehire-customer-roles-eliminated/">'
        '<i>Washington Times</i>, Mar&nbsp;2026</a>.</p>'
        '<p><b>Capex, revenue &amp; circular financing.</b> 2026 hyperscaler capex guidance '
        '(Futurum, MUFG) and OpenAI&rsquo;s ~$1.4&nbsp;trillion in commitments; the '
        '~$800&nbsp;billion vendor-financing loop, via '
        '<a href="https://blockeden.xyz/blog/2026/03/06/ai-circular-financing-loop-vendor-financing/">'
        'BlockEden, Mar&nbsp;2026</a>; 2026 data-center delays, via '
        '<a href="https://tech-insider.org/us-ai-data-center-delays-cancellations-7gw-capacity-crisis-2026/">'
        'Tech&nbsp;Insider</a>; Microsoft&rsquo;s unfilled, unpowered Azure orders, via '
        '<a href="https://www.globaldatacenterhub.com/p/microsoft-q3-fy2026-the-190b-capex">'
        'Global&nbsp;Data&nbsp;Center&nbsp;Hub</a>.</p>'
        '<p><b>GPU depreciation &amp; useful life.</b> Michael&nbsp;Burry (posting as '
        '&ldquo;Cassandra&nbsp;Unchained&rdquo;) argues hyperscalers flatter earnings by '
        'booking a 5&ndash;6-year life on hardware whose real economic life is ~2&ndash;3 '
        'years &mdash; an estimated ~$176&nbsp;billion of understated depreciation across the '
        'sector for 2026&ndash;2028 &mdash; in '
        '<a href="https://x.com/michaeljburry/status/1987918650104283372">posts on&nbsp;X '
        '(Nov&nbsp;2025)</a> and his Substack, reported by '
        '<a href="https://www.cnbc.com/2025/11/11/big-short-investor-michael-burry-accuses-ai-hyperscalers-of-artificially-boosting-earnings.html">'
        'CNBC (Nov&nbsp;11, 2025)</a>. Burry disclosed put positions on Nvidia and Palantir. '
        'For the counter-view &mdash; that retired training GPUs find a long second life in '
        'inference &mdash; see '
        '<a href="https://siliconangle.com/2025/11/22/resetting-gpu-depreciation-ai-factories-bend-dont-break-useful-life-assumptions/">'
        'SiliconANGLE (Nov&nbsp;2025)</a>.</p>'
        '<p><b>Enron or telecom &mdash; which analogy?</b> The depreciation critique is often '
        'wrapped in the Enron story: Jim&nbsp;Chanos, who called Enron by reading the footnote '
        'everyone skipped, now reads the useful-life footnote the same way, and adds a seller-side '
        'twist &mdash; the same buildout dollar is booked as high-margin revenue by the chip-maker '
        '<i>now</i> while the buyer expenses it slowly over six years, so index-level earnings '
        'flatter the underlying economics until the spending stops. The mechanic is real, but the '
        'Enron label overreaches. Enron was <i>fraud</i> &mdash; debt hidden in off-balance-sheet '
        'vehicles, self-dealing, fabricated marks; hyperscaler useful-life extensions are '
        '<i>disclosed</i> judgments sitting in the 10-K, aggressive but legal, at firms that '
        'generate real cash. The tighter historical rhyme is the one Chanos himself reaches for '
        'when he calls Nvidia&rsquo;s investing-in-its-own-customers &ldquo;the most sophisticated '
        'vendor-financing scheme since Lucent&rdquo; &mdash; the <b>2000 telecom overbuild</b>: '
        'genuine demand overshoot, double- and triple-ordering of scarce gear, then cancellation, '
        'ending in Cisco&rsquo;s ~$2.2&nbsp;billion inventory writedown in 2001. That is an '
        '<i>overinvestment</i> failure, not a concealment one &mdash; and it is the more apt, and '
        'more sobering, template for an AI capex cycle whose returns are still a forecast. '
        '(Chanos&rsquo;s sharpest single data point: feeding CoreWeave&rsquo;s own ~2&ndash;3-year '
        'GPU-life estimate into the model implies roughly 0% return on invested capital.)</p>'
        '<p><b>The financing-cycle reading.</b> Two outside analyses reach this report&rsquo;s '
        'conclusion by different routes. An independent essay, '
        '<a href="https://www.groundbrkr.com/p/the-second-derivative-why-no-one">&ldquo;The '
        'Second Derivative&rdquo; (Groundbrkr, 2026)</a>, argues the AI boom is financed like '
        'the 2008 credit cycle rather than the 2000 tech cycle, and that a mere '
        '<i>deceleration</i> in capex and funding &mdash; not a reversal &mdash; is enough to '
        'break structures built for perpetual acceleration. Economists Michael&nbsp;Hudson and '
        'Radhika&nbsp;Desai, in '
        '<a href="https://www.nakedcapitalism.com/2026/07/michael-hudson-with-radhika-desai-were-headed-for-a-depression-worse-than-2008.html">'
        'Geopolitical Economy Hour&nbsp;#80 (Jul&nbsp;2026)</a>, read the same buildout as a '
        'credit-fuelled &ldquo;Ponzi capital-gains bubble&rdquo; led by seven unprofitable AI '
        'names and floated on cheap global carry &mdash; concentrating the gains in a few hands '
        'while socialising the cost. Both are polemical, prediction-forward framings, not '
        'primary data; this report borrows their <i>mechanism</i> (a rollover dependency a '
        'monetary slowdown can trip) while declining their <i>timing</i> calls.</p></div>')

    return [
        ("lede", f"It is the largest private capital bet in history. In 2025 seven "
         f"companies committed about {n['hyper']} to building artificial-intelligence "
         f"infrastructure; for 2026 the five biggest are guiding, between them, toward "
         f"something like {n['capex26']} &mdash; roughly double their 2024 spending &mdash; "
         f"and the buildout will have absorbed on the order of {n['kmid']} of capital by "
         f"2030. Set against that is the revenue it earns today: all the AI-specific "
         f"services in the economy, frontier labs included, run at roughly {n['r0']} a year. "
         f"The returns, in other words, are a forecast; the costs are already here. This "
         f"report follows that asymmetry all the way down &mdash; can a bet this size ever be "
         f"paid back, and if it can&rsquo;t, who is left holding it, and who is already paying "
         f"while the forecast plays out?"),
        ("fig", figure(c["ramp"], "A near-vertical climb",
                       "Combined annual capital investment of seven US hyperscalers, "
                       "cash capex plus finance leases.", "Source: SEC EDGAR filings")),
        ("p", f"A decade ago these firms spent on the order of {n['capex0']} a year between "
         f"them. The total roughly doubled in the single year to 2025, and a single "
         f"year&rsquo;s spending now equals close to a third &mdash; {n['share_it']} &mdash; "
         f"of everything American business invests in information-technology equipment and "
         f"software combined. This is no longer a sector story. It is a claim on the "
         f"economy&rsquo;s entire investable surplus, made by a handful of boardrooms."),
        ("fig", figure(c["macro"], "A claim on the economy&rsquo;s investable surplus",
                       "2025 hyperscaler capital investment, measured against US capital "
                       "formation.", "Source: SEC EDGAR; FRED (BEA national accounts)")),
        ("p", f"Widen the lens to the whole economy and it reads the same way. Real investment "
         f"in information-processing equipment and software has climbed from about "
         f"{n['it_gdp_lo']} of GDP in 2010 to roughly {n['it_gdp_hi']} in 2026 &mdash; and in "
         f"the first half of 2025, the growth in that one line was equal to about "
         f"{n['it_h1_share']} of all US GDP growth. Strip it out and the economy barely moved. "
         f"That is a contribution, not a proven cause &mdash; absent the boom, cheaper credit "
         f"or power would have offset part of the gap &mdash; but it means headline growth now "
         f"leans on this single category of spending to a degree with few precedents."),
        ("fig", figure(c["gdpattr"], "The economy leans on one line",
                       "US investment in information-processing equipment and software as a "
                       "share of GDP, 2010&ndash;2026.",
                       "Source: BEA NIPA (T50306 / T10106); Furman contribution method")),
        ("p", f"And it is not just those seven firms. The same buildout runs through a whole "
         f"supply chain &mdash; the memory makers, the chip-equipment firms, the networking and "
         f"cooling vendors, the power companies, and the &ldquo;neoclouds&rdquo; that rent out "
         f"GPUs. Add up the US-listed names across those layers and you get another "
         f"{n['complex_firms']} companies with something like {n['complex_rev']} of AI-linked "
         f"revenue behind them. The exact total isn&rsquo;t the point &mdash; much of that "
         f"revenue is only partly about AI &mdash; the reach is: the bet now pulls in a wide "
         f"slice of the industrial economy, not a tech niche."),
        ("fig", figure(c["complex"], "Beyond the seven",
                       "AI-exposed revenue by supply-chain layer, 18 US-listed firms. Exposure "
                       "is an upper bound, not AI-only revenue.",
                       "Source: SEC EDGAR (companyconcept) &mdash; Tier-2 exposure")),

        ("h2", "The Arithmetic"),
        ("p", f"Start with the version that looks impossible, because it is the honest "
         f"starting point. The buildout has committed roughly {n['kmid']} of capital. For a "
         f"bet that size to be worth making &mdash; to earn back more than it costs to "
         f"finance &mdash; the AI economy would have to bring in, every single year, on the "
         f"order of {n['req35']}, even at the fat {n['margin_sh']} profit margin of "
         f"Amazon&rsquo;s AWS, the most profitable cloud business ever built. Today it brings "
         f"in about {n['r0']}."),
        ("fig", figure(c["capexrev"], "The gap the buildout is betting on",
                       "2026 capital spending against today&rsquo;s AI-service revenue.",
                       "Source: SEC EDGAR; analyst / press estimates &mdash; Tier-2")),
        ("p", f"Demand is, to be clear, exploding: Google now processes more than seven "
         f"times as many AI tokens each year as the last. But run that growth forward on an "
         f"adoption curve, net the collapsing price per token, and achievable AI revenue "
         f"reaches roughly {n['ach_mid']} by 2030 in the central case &mdash; {n['ach_hi']} "
         f"even in an optimistic one. Against a requirement of {n['req35']} or more, the "
         f"curve does not close the gap. It does not come within several times of it."),
        ("fig", figure(c["reqach"], "What it must earn versus what usage can deliver",
                       "Revenue the buildout must earn to pay itself back, against a "
                       "projection of achievable AI revenue as adoption grows.",
                       "Source: author&rsquo;s model on SEC capex, FRED rates, observed usage")),
        ("pull", f"To pay the buildout back from AI revenue, that revenue would have to grow "
         f"about {n['req_cagr']} a year &mdash; roughly {n['aws_x']} AWS&rsquo;s pace over its "
         f"thirteen-year climb, at far greater scale. Nothing in the history of business has "
         f"done it."),
        ("fig", figure(c["awsreq"], "A ramp without precedent",
                       "The required AI revenue ramp against AWS&rsquo;s actual climb to "
                       "~$130B &mdash; the steepest real precedent for cloud infrastructure.",
                       "Source: SEC EDGAR (AWS segment); author&rsquo;s required-ramp model")),

        ("h2", "So Who Actually Pays?"),
        ("p", f"If the arithmetic is that bad, the buildout should have stopped. It has not, "
         f"and the reason is the hinge of this whole story: the giants are not paying for it "
         f"out of AI revenue. They are paying for it out of the monopolies they already own. "
         f"Microsoft, Alphabet, Amazon and Meta together throw off something like "
         f"{n['ocf_agg']} a year in operating cash flow &mdash; from Search ads, Office, "
         f"Windows, AWS and the ad machines &mdash; and across the group that cash still "
         f"covers their capital spending about {n['cov_agg']} over. They are spending Search "
         f"and advertising profits on AI data centers."),
        ("fig", figure(c["funding"], "Who can pay their own way &mdash; and who can&rsquo;t",
                       "Operating cash flow divided by capital spending, latest fiscal year. "
                       "Below 1.0× means the buildout is being financed from outside.",
                       "Source: SEC EDGAR filings")),
        ("p", f"That is why the giants are not in danger of insolvency, whatever happens to "
         f"AI revenue &mdash; their risk is wasted shareholder value, not bankruptcy. But "
         f"look at the firms below the line. Oracle&rsquo;s operating cash flow covers only "
         f"about {n['oracle_cov']}× its capital spending; CoreWeave&rsquo;s, about "
         f"{n['crwv_cov']}×. They cannot pay from earnings, so they pay with debt, equity "
         f"raises and contracted revenue."),
        ("p", f"And &ldquo;self-funding&rdquo; flatters even the giants. A chunk of that "
         f"operating cash flow is not cash at all: the group pays some {n['sbc_total']} of "
         f"compensation a year in stock rather than money &mdash; about {n['sbc_pct']} of its "
         f"combined cash flow &mdash; and because that is booked as a non-cash expense, it "
         f"quietly lifts the very figure their coverage is measured against. Count the stock "
         f"pay as the cost it is and the group&rsquo;s cushion narrows from about "
         f"{n['cov_raw']}× its capital spending to roughly {n['cov_adj']}×, with Amazon "
         f"slipping below the line. And in the same year they handed about "
         f"{n['buybacks_total']} back to shareholders in buybacks &mdash; cash spent holding "
         f"up the share price rather than building. The core is less self-funding than "
         f"valuation-<i>supported</i>: it leans on a rich, liquid stock to pay part of its "
         f"workforce and prop its own price, both of which rest on the cheap-money era "
         f"holding &mdash; the same era that funds the edge below it."),
        ("fig", figure(c["fundsrc"], "Who builds from revenue &mdash; and who must borrow",
                       "Share of each firm&rsquo;s latest-year capital spending its own "
                       "operating cash flow can cover, versus the share that must come from "
                       "debt or outside financing.", "Source: SEC EDGAR filings")),
        ("p", f"Follow the debt, and the seven split three ways. Microsoft and Nvidia are "
         f"actually paying theirs <i>down</i> &mdash; Microsoft&rsquo;s long-term debt has "
         f"fallen from about $76&nbsp;billion in 2017 to {n['msft_debt']}, and it funds the "
         f"build from cash. Oracle and CoreWeave sit at the other extreme: they cannot cover "
         f"capex from earnings, so new borrowing ran to {n['oracle_dfs']} of Oracle&rsquo;s "
         f"capital spending and {n['crwv_dfs']} of CoreWeave&rsquo;s. And in between is the "
         f"telling group &mdash; Alphabet, Meta and Amazon, whose cash flow <i>does</i> cover "
         f"capex, and which are issuing anyway. Alphabet quadrupled its long-term debt in a "
         f"single year, from about {n['googl_debt_prior']} to {n['googl_debt']}; Meta went "
         f"from essentially none in 2021 to {n['meta_debt']}. They do not need the money to "
         f"build &mdash; they are tapping cheap credit because it is there, largely alongside "
         f"the buybacks from the last section."),
        ("fig", figure(c["debttraj"], "Who is borrowing for the buildout &mdash; and who "
                       "isn&rsquo;t",
                       "Long-term debt on the balance sheet, by fiscal year. Microsoft and "
                       "Nvidia fall; Alphabet, Meta and the edge climb.",
                       "Source: SEC EDGAR filings")),
        ("p", f"Across the group that is about {n['ltd_7firm']} of long-term debt, with "
         f"{n['debt_issue_7firm']} added in the latest year alone &mdash; and the wave is "
         f"larger still beyond these balance sheets. AI-related debt issuance is on track for "
         f"about {n['ai_debt_2026']} in 2026, roughly four times the previous year&rsquo;s "
         f"pace, and more than {n['ai_pc_out']} of private-credit loans to AI companies are "
         f"already outstanding, with hundreds of billions more in the pipeline. A growing "
         f"share is moving off the public bond market into private credit and off-balance-"
         f"sheet vehicles &mdash; Meta&rsquo;s roughly $30&nbsp;billion Hyperion data-center "
         f"venture, funded by PIMCO and Blue&nbsp;Owl, is the template &mdash; where "
         f"disclosure and creditor protection are thinner."),
        ("p", f"The question that eventually gets asked is who is holding this debt when the "
         f"revenue is tested &mdash; and the answer, increasingly, is insurers, pension funds, "
         f"and big private-credit firms like Blackstone, Apollo and Ares, whose money now backs "
         f"long-term data-center loans and reaches ordinary people through their retirement and "
         f"mutual funds. In May 2026 the global body that watches for financial crises, the "
         f"Financial Stability Board, warned that this fast-growing corner of lending &mdash; "
         f"now a {n['pc_market']} market, tightly tangled up with banks and insurers &mdash; "
         f"&ldquo;has not been tested during a severe economic downturn.&rdquo; The "
         f"professionals see it too: by July, {n['bofa_ai']} of fund managers told Bank of "
         f"America that AI spending was the single most likely thing to set off a credit "
         f"crisis &mdash; the first time it topped their list of worries."),
        ("p", "That is the debt side of how the edge stays funded. The contracted-revenue side "
         "is stranger still &mdash; because a striking share of it turns out to be the same "
         "money going around in a circle."),

        ("h2", "The Circle"),
        ("p", f"By one estimate, about {n['circular']} of arrangements now loop capital "
         f"around a ring. Nvidia is putting up to {n['nvidia_oai']} into OpenAI. OpenAI has "
         f"committed something like {n['oai_commit']} over the next several years &mdash; "
         f"around {n['oai_oracle']} to Oracle, with hundreds of billions more pledged to "
         f"Microsoft, Broadcom, AMD and CoreWeave. And those providers, in turn, spend much "
         f"of it buying Nvidia&rsquo;s chips. Nvidia books the sales as revenue and takes "
         f"equity stakes in the very customers placing the orders &mdash; roughly 7 percent "
         f"of CoreWeave among them. Each lap around the ring is counted, somewhere, as growth."),
        ("fig", figure(c["circle"], "The money goes in a circle",
                       "Headline AI financing commitments among the chipmaker, the lab and "
                       "the clouds. Figures are multi-year announced commitments, not annual "
                       "revenue.", "Source: company announcements / press &mdash; Tier-2")),
        ("p", f"Set OpenAI&rsquo;s {n['oai_commit']} of commitments beside its roughly "
         f"{n['oai_rev_now']} of actual annual revenue and the structure gives itself away. "
         f"This is vendor financing: a supplier funding the customers who buy its product, so "
         f"that the purchases show up as independent demand. Wall Street has seen the movie "
         f"before &mdash; Lucent and Nortel booked loans to their own customers as equipment "
         f"sales right up to the 2000 telecom bust, when the customers turned out unable to pay."),
        ("p", "It is not pure illusion: real compute is delivered, real chips are installed, "
         "and the demand for tokens underneath is genuine. But the ring flatters apparent "
         "demand and concentrates the danger, because it runs on one input no balance sheet "
         "controls &mdash; fresh capital continuing to flow in. The day investors stop funding "
         "the next OpenAI round is the day Oracle&rsquo;s contracted revenue, "
         "CoreWeave&rsquo;s debt service and Nvidia&rsquo;s order book all wobble at once. The "
         "circle is a confidence machine; it spins beautifully until it doesn&rsquo;t."),
        ("p", "And there is a sharper version of that fragility &mdash; the one that actually "
         "ended the last credit cycle. The ring does not need investors to <i>stop</i> funding "
         "the next round; it only needs them to slow down. Subprime mortgages in 2008 were "
         "written to be refinanced before their teaser rates reset, and they detonated not "
         "when house prices fell but when prices merely stopped rising <i>faster</i> &mdash; "
         "the acceleration going into reverse while the level was still near its peak. The AI "
         "circle has the same shape: the labs at its center keep going only by raising each new "
         "round at a higher valuation than the last, so a valuation that merely <i>stops "
         "climbing</i>, rather than one that falls, is enough to seize the machinery. And the "
         "capital those "
         "marks run on is not free-standing AI enthusiasm; it is the same cheap, yield-seeking "
         "credit that has bid up every asset for a decade, some of it borrowed abroad at "
         "near-zero rates. That makes the trip-wire monetary as much as technological: a "
         "central bank tightening, or that cheap-funding trade unwinding, would slow the marks "
         "on its own &mdash; no failure of AI required."),

        ("h2", "They Know"),
        ("p", "The executives running these firms are not fooled by the arithmetic above; "
         "they can do the sums better than anyone. What looks irrational from outside is the "
         "rational move from inside, and their own stated logic is blunt: the risk of "
         "under-investing is greater than the risk of over-investing. Three things make that "
         "true for them even if the aggregate is a bubble."),
        ("p", "First, it is defensive insurance on a far larger franchise. If AI becomes the "
         "way people get answers, Google&rsquo;s search-ad business &mdash; the thing that "
         "actually pays for all this &mdash; is the thing most at risk; spending a hundred "
         "billion to defend a three-hundred-billion-a-year monopoly is rational at almost any "
         "ROI. Second, it is a winner-take-most option: if transformative AI has even a "
         "modest chance of being enormous, the expected value justifies enormous spending. "
         "Third, it is a trap of the prisoner&rsquo;s-dilemma kind &mdash; each firm builds "
         "because the others are building, and none can afford to be the one that sat out if "
         "AI turns out to matter. That is exactly how individually-rational actors "
         "manufacture a collective bubble."),
        ("fig", figure(c["semis"], "The bet&rsquo;s single point of failure",
                       "Latest-fiscal-year revenue of the five largest US-listed chip "
                       "suppliers &mdash; nearly all fabricated by one Taiwanese foundry.",
                       "Source: SEC EDGAR filings")),
        ("p", f"And underneath the defensiveness is a genuine bull case. If AI really does "
         f"become the way knowledge work gets done, its &ldquo;revenue&rdquo; stops being a "
         f"line of metered usage and becomes a cut of all the labor it replaces &mdash; a "
         f"slice of GDP measured in trillions. That is the world the spending implies. Model "
         f"it as a range of scenarios and the split is stark: if only AI&rsquo;s own revenue "
         f"counts, the bet pays for itself in about {n['p_clear']} of them; if you also credit "
         f"AI with lifting all of cloud, advertising and search, about {n['p_broad']}. The "
         f"whole thing hinges on which of those worlds arrives &mdash; and even the generous "
         f"one is a coin flip."),

        ("h2", "The Bill"),
        ("p", f"Here the asymmetry from the start of this piece turns concrete. The payback "
         f"is a forecast; the running costs are not a forecast at all. They are already being "
         f"paid &mdash; and increasingly by the public. The first is "
         f"electricity. US power demand was flat for thirteen years; it is now rising about "
         f"{n['surge']} a year, with data centers a principal cause, climbing from "
         f"{n['dc23']} of US electricity in 2023 toward {n['dc30']} by 2030."),
        ("fig", figure(c["demand"], "Thirteen flat years, then a wall",
                       "US electricity demand, all sectors.", "Source: EIA")),
        ("fig", figure(c["dcshare"], "The grid absorbs the buildout",
                       "Data centers as a share of total US electricity, 2023 actual and "
                       "2030 projected range.", "Source: LBNL; EPRI; EIA")),
        ("p", f"By 2026 power, not money or chips, had become the binding constraint: roughly "
         f"{n['dc_delayed']} of planned US data centers are delayed or canceled, and "
         f"Microsoft is sitting on something like {n['ms_unfilled']} of orders it cannot fill "
         f"because it cannot find the electricity to run chips already in its warehouses. Nor "
         f"will efficiency rescue the grid &mdash; it accelerates the strain. Chips get about "
         f"{n['eff_yr']} more efficient each year, but to meet the projected energy path "
         f"compute must grow {n['comp_lo']}&ndash;{n['comp_hi']} a year, roughly twice as "
         f"fast. Efficiency spared the grid perhaps {n['jev_saved']} terawatt-hours by "
         f"2028 &mdash; and demand still tripled. It is the oldest result in energy "
         f"economics, the Jevons paradox, playing out in real time."),
        ("fig", figure(c["jevons"], "Why efficiency does not save the grid",
                       "US data-center electricity in 2028: what efficiency saved, and what "
                       "demand added on top.",
                       "Source: vendor / Epoch AI perf-per-watt; LBNL energy")),
        ("p", f"The pattern repeats inside the machine. Decompose the full cost of a deployed "
         f"AI accelerator and only about {n['energy_sh']} is the electricity to run it; some "
         f"{n['facil_sh']} is the building and cooling; and fully {n['margin_sh']} is "
         f"Nvidia&rsquo;s gross margin &mdash; scarcity rent, not the cost of making anything. "
         f"In the data-center-heavy states, residential power has risen about {n['p_heavy']} "
         f"in five years against {n['p_rest']} elsewhere; whether the data centers caused it "
         f"is genuinely contested, but the mechanism, where it operates, is plain. The "
         f"margin, in other words, is privatised, and the bill is increasingly socialised."),
        ("fig", figure(c["coststack"], "Mostly markup",
                       "What a deployed AI accelerator costs over its life, by component "
                       "share.", "Source: SEC EDGAR margins; analyst BOM estimates (Tier-2)")),
        ("fig", figure(c["prices"], "After 2021, a divergence",
                       "Residential electricity price, indexed to 2010, in data-center-"
                       "heavy states versus the rest.",
                       "Source: EIA API v2 (state retail prices)")),
        ("pull", "The margin is private. The bill &mdash; the grid, the prices, the "
         "water &mdash; is public."),

        ("h2", "Is the Demand Even There?"),
        ("p", f"All of which assumes the revenue eventually shows up. The early evidence is "
         f"mixed, and the most-hyped version of it is receding. A widely cited MIT study found "
         f"that about {n['mit95']} of enterprise generative-AI pilots delivered no measurable "
         f"return; by one survey {n['rehire']} of firms that cut staff for AI have rehired, "
         f"and {n['regret']} of employers regret the cuts. Usage in tokens is vertical; usage "
         f"in dollars, and in delivered productivity, lags well behind it."),
        ("fig", figure(c["labor"], "Promise versus practice",
                       "Share of occupational tasks exposed to AI &mdash; predicted "
                       "capability versus observed use, employment-weighted.",
                       "Source: BLS OEWS; Eloundou et al.; Anthropic Economic Index")),
        ("p", "The gap between what AI can do and what it is paid to do is the adoption "
         "runway still ahead &mdash; and the buildout&rsquo;s entire case is that the runway "
         "gets crossed, at a high margin, before the financing runs out. That remains a "
         "wager on a future, not a description of the present."),

        ("h2", "What &ldquo;Popping&rdquo; Would Mean"),
        ("p", f"So suppose the wager sours &mdash; or merely stops accelerating fast enough to "
         f"fund the next round. &ldquo;The AI bubble bursting&rdquo; conjures the "
         f"year 2000, but the analogy misleads, because the people who actually owe the money "
         f"are not the ones who look most exposed. Popping would not mean AI is exposed as "
         f"fake. It would mean the leveraged claims stacked on top of a real-but-overbuilt "
         f"infrastructure repricing to what it truly earns &mdash; and that repricing lands "
         f"on the fringe, not the giants. The Oracles, CoreWeaves and labs hit refinancing "
         f"walls; Nvidia&rsquo;s valuation multiple compresses; and depreciation finally "
         f"catches up &mdash; the short-seller Michael Burry "
         f"<a href=\"https://www.cnbc.com/2025/11/11/big-short-investor-michael-burry-accuses-ai-hyperscalers-of-artificially-boosting-earnings.html\">"
         f"argues</a> an AI server&rsquo;s true working life is closer to two or three years "
         f"&mdash; about {n['burry']} at the midpoint &mdash; well under the six years the "
         f"books assume, which would gut reported profits if applied."),
        ("fig", figure(c["life"], "How long does an AI server really last?",
                       "Assumed useful life: the depreciation schedule in the filings, a "
                       "prominent short-seller&rsquo;s estimate, and this report&rsquo;s "
                       "hardware model.",
                       "Source: SEC EDGAR; press; author&rsquo;s model (Tier-2)")),
        ("p", "If not 2000, then what? The truer template is 2008 &mdash; not in mood but in "
         "machinery. The dot-com bust was an <i>equity</i> event: overvalued stocks fell and "
         "the losses mostly stopped where the shareholders stood. This buildout is wired like "
         "the <i>credit</i> cycle that produced the last crash, and it fails the same way. Lay "
         "the two side by side and the wiring matches, line for line."),
        ("table", comparison_table()),
        ("p", "Read down the table and the fuel is identical: cheap, borrowed money with "
         "nowhere better to go. A decade of near-zero rates &mdash; much of it carried out of "
         "Japan at under one percent &mdash; inflated the valuations that then became the "
         "collateral. The same rich stock lets a giant pay its staff in equity and buy back "
         "its own shares, and lets a lab refinance at an ever-higher mark. Overvaluation is "
         "not a side effect sitting beside the cheap credit; it is the wire between them. Cut "
         "the funding and both ends go dark at once."),
        ("p", "Which is why the thing to watch is not a demand miss or a single bankruptcy, "
         "but money getting more expensive &mdash; and in mid-2026 it already is. Japan, the "
         "source of much of that cheap borrowed money, has been raising interest rates: its "
         "central bank&rsquo;s rate is now one percent, the highest in thirty years, and still "
         "climbing. At the same time, investors are betting against the yen more heavily than at "
         "any point since 2017. That is the exact setup that, on a single day in August 2024, "
         "sent the yen sharply higher and the market&rsquo;s fear gauge above sixty. If it "
         "happens harder, those cheap loans turn expensive, the money flows back to Japan, and "
         "the ever-rising valuations the whole structure leans on stop rising &mdash; without AI "
         "itself having to fail at anything."),
        ("p", "And there is almost no cushion. The market&rsquo;s fear gauge sits near sixteen, "
         "and lenders are charging even risky companies close to the smallest premium on "
         "record &mdash; everything is priced as if the good times simply continue. The one "
         "place already cracking is the edge: the weakest borrowers pay far more to borrow than "
         "the rest, and demand for new AI bonds has cooled fast &mdash; deals that drew five "
         "times more orders than they needed in February drew barely two by summer. That is "
         "what a first domino looks like &mdash; not a crash, but a slowdown, showing up first "
         "where the structure is thinnest."),
        ("p", f"Because the bet has been indexed into everyone&rsquo;s savings &mdash; seven "
         f"names are now about {n['mag7_sh']} of the S&amp;P 500, and the premium for holding "
         f"stocks over safe bonds has thinned to roughly {n['erp']} &mdash; that repricing "
         f"would not stay contained to a few balance sheets; it would run straight through the "
         f"index funds in ordinary retirement accounts. And then the part that rhymes with "
         f"history: the assets persist. The dark fiber of 1999 was eventually all lit. The "
         f"data centers and chips will not vanish; they will be repriced, absorbed and, in "
         f"time, used &mdash; while Microsoft keeps printing Office money throughout."),
        ("fig", figure(c["conc"], "Everyone&rsquo;s bet now",
                       "Total return of the cap-weighted S&amp;P 500 versus its "
                       "equal-weighted twin, rebased to 2015.",
                       "Source: Yahoo Finance (Tier-2)")),
        ("watch", watchlist()),

        ("h2", "Does the Math Math?"),
        ("p", f"As a standalone investment &mdash; AI revenue paying back AI capital &mdash; "
         f"no. It pays for itself in only about {n['p_clear']} of plausible scenarios, even on "
         f"the most generous cloud-style profit margins, and the revenue ramp it needs has no "
         f"precedent. As something else &mdash; spend the franchise&rsquo;s monopoly profits "
         f"on a defensive option, push the fragile financing onto whoever is furthest out on "
         f"the limb, and let the public carry the grid and the prices &mdash; it pencils out "
         f"fine, for the giants. Both can be true at once: a genuine technological revolution "
         f"and a speculative mania. They almost always have been. Canals, railways, "
         f"electricity, the internet &mdash; each delivered, and each ruined a generation of "
         f"financiers first."),
        ("p", "The distributional ledger is the starkest form of the same asymmetry. Stock-"
         "market wealth in America is not widely held: the top tenth of households own about "
         "93 percent of all equities and the bottom half roughly one percent (Federal Reserve, "
         "2024), and over the past quarter-century the net worth of the top 1 percent has risen "
         "from about $10 trillion to more than $50 trillion (Fed Distributional Financial "
         "Accounts). So the upside of the buildout &mdash; the seven stocks, the concentrated "
         "gains &mdash; accrues to a narrow band that already owns the market, while its costs, "
         "from the power bill to a repricing that would run through every indexed retirement "
         "account, are borne broadly. The heterodox economists Michael Hudson and Radhika Desai "
         "read the whole episode this way, as a credit-fuelled bubble whose rewards and risks "
         "fall on different people; one need not share their forecast of an imminent depression "
         "to accept the incidence."),
        ("p", "The honest verdict is therefore not a forecast but an accounting, and it comes "
         "down to the asymmetry this report has tracked from its first lines. The returns are "
         "a forecast; the costs are already here &mdash; and the two do not fall on the same "
         "people. The profits concentrate at a handful of chokepoints &mdash; Nvidia&rsquo;s "
         "margin, a single Taiwanese foundry, a few cloud balance sheets. The costs spread "
         "outward: onto ratepayers and the grid, onto the leveraged firms at the edge of the "
         "circle, and onto everyone whose retirement is indexed to the same seven stocks. The "
         "companies know the arithmetic does not close on AI revenue alone, and they spend "
         "anyway, because for each of them it is the rational move &mdash; which is precisely "
         "how the overhang gets built. So the question was never whether artificial "
         "intelligence is real. It is real. The question is who is left holding the bet when "
         "its claims finally reprice to what the machines can actually earn &mdash; and, long "
         "before that reckoning, who is paying for it now."),
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
        "ocf_agg": f"${d['ocf_agg']:.0f} billion",
        "cov_agg": f"{d['cov_agg']:.1f} times",
        "oracle_cov": f"{_fcov(d, 'Oracle'):.2f}",
        "crwv_cov": f"{_fcov(d, 'CoreWeave'):.2f}",
        "nvidia_oai": f"${d['circ_edge'][('NVIDIA', 'OpenAI')]:.0f} billion",
        "oai_oracle": f"${d['circ_edge'][('OpenAI', 'Oracle')]:.0f} billion",
    })

    # --- Broadening-layer number-strings (BEA attribution + complex footprint) ---
    ma = d["macro_attr"]
    q4 = ma[ma.time_period == "2024Q4"].iloc[0]
    q2 = ma[ma.time_period == "2025Q2"].iloc[0]
    it_h1 = (q2["it"] - q4["it"]) / (q2["gdp"] - q4["gdp"]) * 100
    cx = d["complex"]
    n.update({
        "it_gdp_lo": f"{ma['it_pct_of_gdp'].iloc[0]:.1f} percent",
        "it_gdp_hi": f"{ma['it_pct_of_gdp'].iloc[-1]:.1f} percent",
        "it_h1_share": f"{it_h1:.0f} percent",
        "complex_rev": f"${cx['revenue_bn'].sum():.0f} billion",
        "complex_capex": f"${cx['capex_bn'].sum():.0f} billion",
        "complex_firms": f"{int(cx['firms'].sum())}",
    })

    pc = d["pcredit"]
    fund = d["funding"].set_index("company")["debt_funded_share"]
    n.update({
        "ltd_7firm": f"${pc['ltd_7firm']:.0f} billion",
        "debt_issue_7firm": f"${pc['debt_issuance_7firm']:.0f} billion",
        "crwv_dfs": f"{float(fund.get('CoreWeave', 0)) * 100:.0f} percent",
        "oracle_dfs": f"{float(fund.get('Oracle', 0)) * 100:.0f} percent",
        "ai_debt_2026": f"${pc['ai_debt_issuance_2026']:.0f} billion",
        "ai_pc_out": f"${pc['ai_private_credit_outstanding']:.0f} billion",
        "pc_market": "$1.5 to $2 trillion",
        "bofa_ai": f"{pc['bofa_ai_capex_systemic']:.0f} percent",
    })

    ef = d["eqfund"]
    sbc_t, ocf_t = ef["share_based_comp_usd"].sum(), ef["operating_cash_flow_usd"].sum()
    cap_t, bb_t = ef["capex_usd"].sum(), ef["buybacks_usd"].sum()
    n.update({
        "sbc_total": f"${sbc_t:.0f} billion",
        "sbc_pct": f"{sbc_t / ocf_t * 100:.0f} percent",
        "cov_raw": f"{ocf_t / cap_t:.1f}",
        "cov_adj": f"{(ocf_t - sbc_t) / cap_t:.1f}",
        "buybacks_total": f"${bb_t:.0f} billion",
    })

    dtj = d["debt_traj"]
    def _ltd(tk, yr):
        return dtj.loc[yr, tk] if (yr in dtj.index and tk in dtj.columns) else float("nan")
    g25, g24 = _ltd("GOOGL", 2025), _ltd("GOOGL", 2024)
    n.update({
        "googl_debt": f"${g25:.0f} billion",
        "googl_debt_prior": f"${g24:.0f} billion",
        "googl_add": f"${g25 - g24:.0f} billion",
        "meta_debt": f"${_ltd('META', 2025):.0f} billion",
        "msft_debt": f"${_ltd('MSFT', 2025):.0f} billion",
    })

    c = {"ramp": chart_ramp(d), "macro": chart_macro(d), "semis": chart_semis(d),
         "demand": chart_us_demand(d), "dcshare": chart_dc_share(d),
         "prices": chart_state_prices(d), "labor": chart_labor(d),
         "capexrev": chart_capex_vs_revenue(d), "coststack": chart_cost_stack(d),
         "reqach": chart_required_vs_achievable(d), "awsreq": chart_aws_vs_required(d),
         "funding": chart_funding_coverage(d), "circle": chart_circular(d),
         "conc": chart_concentration(d), "jevons": chart_jevons(d),
         "life": chart_useful_life(d), "gdpattr": chart_gdp_attribution(d),
         "complex": chart_complex_footprint(d), "debttraj": chart_debt_trajectory(d),
         "fundsrc": chart_funding_sources(d)}

    paras = build_paragraphs(n, c)

    body, words = [], 0
    for kind, content in paras:
        if kind == "h2":
            body.append(f"<h2>{content}</h2>")
        elif kind in ("fig", "table", "watch"):
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
    deck = ("American tech is spending the better part of a trillion dollars a year "
            "building artificial-intelligence infrastructure that AI revenue cannot come "
            "close to paying back. So who does pay — and who is left holding the bet when "
            "the math comes due? A clear-eyed reckoning, from the arithmetic down to who "
            "carries the bill.")
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
<div class="dateline">Updated {dt.date.today():%B %-d, %Y}</div>
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
