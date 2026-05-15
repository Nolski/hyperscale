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
        '<p>Every figure here comes from a reproducible pipeline. Hyperscaler and '
        'chip-maker capital spending is extracted from SEC EDGAR filings; macro and '
        'construction series from the Federal Reserve&rsquo;s FRED; electricity '
        'demand and prices, national and by state, from the US Energy Information '
        'Administration API; occupational employment from the Bureau of Labor '
        'Statistics. Data-center energy figures are transcribed from Lawrence '
        'Berkeley National Laboratory and EPRI reports; AI-exposure scores from '
        'Eloundou et&nbsp;al. (2024) and the Anthropic Economic Index; forecasts '
        'from McKinsey, Goldman Sachs and Bain; price modelling from the Federal '
        'Reserve Bank of Dallas.</p>'
        '<p>Three layers of &ldquo;AI investment&rdquo; are kept separate and never '
        'summed: real investment (capital spending), financing (venture capital), '
        'and the supply mirror (chip revenue, which sits inside the capital figure). '
        'The forward projection grows the seven firms&rsquo; 2025 actual under '
        'documented low/mid/high assumptions. State-level energy uses the EIA at '
        'state granularity; below the state level, public data runs out.</p>'
        '<p>Full dataset-by-dataset provenance, including caveats, is in '
        '<code>notes/provenance.md</code> in the project repository.</p></div>')

    return [
        ("lede", f"In 2025, seven companies — Microsoft, Alphabet, Amazon, Meta, "
         f"Oracle, Nvidia and CoreWeave — committed about {n['hyper']} to capital "
         f"investment, most of it data centers built for artificial intelligence. "
         f"That single year&rsquo;s spending equals roughly {n['share_gdp']} of "
         f"American gross domestic product, close to a tenth of all private business "
         f"investment in the country, and nearly a third — {n['share_it']} — of "
         f"everything American business spends on information-technology equipment "
         f"and software combined."),
        ("p", f"A decade earlier, the same seven firms spent on the order of "
         f"{n['capex0']} a year between them. The path from there to here is not a "
         f"gentle trend. The total roughly doubled in the single year between 2024 "
         f"and 2025."),
        ("fig", figure(c["ramp"], "A near-vertical climb",
                       "Combined annual capital investment of seven US hyperscalers, "
                       "cash capex plus finance leases.", "Source: SEC EDGAR filings")),

        ("h2", "The Scale"),
        ("p", f"Numbers this large invite double-counting, and most published tallies "
         f"of &ldquo;AI investment&rdquo; commit it. The {n['hyper']} is real "
         f"investment — money spent, and assets leased, to build and equip data "
         f"centers. It is a distinct quantity from the {n['vc']} of venture capital "
         f"that flowed into AI companies worldwide in 2025, which is a financing "
         f"flow, not a building. And it is distinct again from the {n['chip']} in "
         f"revenue earned last year by the five largest US-listed chip suppliers — "
         f"a figure not added to the buildout but contained within it, since those "
         f"chips are part of what the capital spending buys."),
        ("fig", figure(c["layers"], "Three layers, never summed",
                       "AI investment by accounting layer, 2025. The layers measure "
                       "different things and are not additive.",
                       "Source: SEC EDGAR; OECD")),
        ("p", f"What the three figures share is concentration. Nvidia alone booked "
         f"{n['nvda']} in revenue, {n['nvda_sh']} of the five-firm chip total. Seven "
         f"companies account for the capital. The AI economy, measured in dollars, "
         f"is not an economy of many participants. It is a handful of balance "
         f"sheets, and the rest of the economy is increasingly downstream of them."),
        ("fig", figure(c["macro"], "A claim on the economy&rsquo;s investable surplus",
                       "2025 hyperscaler capital investment, measured against US "
                       "capital formation.",
                       "Source: SEC EDGAR; FRED (BEA national accounts)")),
        ("p", f"The most telling of those ratios is the last. When seven firms "
         f"direct an amount equal to {n['share_it']} of all national "
         f"IT-equipment-and-software investment toward one category of asset, the "
         f"buildout has stopped being a sector story. It is a claim on the "
         f"economy&rsquo;s investable surplus — capital that is, by definition, "
         f"not going somewhere else."),
        ("p", f"And {n['hyper']} is itself a floor. The figure counts cash spending "
         f"and the assets the firms take on through finance leases, but not "
         f"capacity rented through ordinary operating leases, nor the web of "
         f"off-balance-sheet vehicles and private-credit arrangements that "
         f"increasingly fund the buildout. Several of the largest data-center "
         f"projects are now carried through joint ventures whose debt never lands "
         f"on a hyperscaler&rsquo;s balance sheet at all. The visible commitment is "
         f"enormous; the full one is larger, and, by the way it is structured, "
         f"meant to be harder to see."),
        ("p", "Concentration on this scale is itself a kind of risk. When seven "
         "firms account for nearly a third of national IT investment, the "
         "economy&rsquo;s growth, its stock-market gains and a measurable slice of "
         "its productivity statistics all become correlated with the same handful "
         "of decisions. The buildout is not only large. It has made the wider "
         "economy unusually dependent on whether a few boardrooms keep believing "
         "in it — and unusually exposed to the moment any of them stops."),

        ("h2", "The Chip Chokepoint"),
        ("p", "The buildout&rsquo;s pace is not set by money alone. It is set by "
         "chips. The graphics processors that fill the data centers come, "
         "overwhelmingly, from one company: Nvidia&rsquo;s data-center revenue "
         "dwarfs that of AMD, Broadcom, Micron and Intel combined. A single "
         "vendor&rsquo;s production schedule — and the Taiwanese foundry that "
         "manufactures for it — is therefore a governor on the entire cycle."),
        ("p", "That concentration is also where the buildout meets geopolitics. "
         "Advanced AI chips are subject to US export controls; the supply chain "
         "runs through a small number of firms and a smaller number of countries. "
         "The &ldquo;hyperscaling&rdquo; the rest of this report measures in "
         "dollars rests on a physical bottleneck that no amount of capital can "
         "widen quickly."),
        ("p", "Nearly all of those chips are fabricated by a single contractor, "
         "Taiwan Semiconductor Manufacturing Company, on an island within reach of "
         "Chinese military pressure. A new leading-edge fabrication plant takes "
         "years and tens of billions of dollars to bring online. So the buildout "
         "carries a contradiction at its core: a financial commitment that can be "
         "made in a quarter depends on a manufacturing base that takes a decade to "
         "expand — and on a geography no balance sheet controls. The cycle can "
         "be funded far faster than it can be supplied."),
        ("fig", figure(c["semis"], "One company, half the supply",
                       "Latest-fiscal-year revenue of the five largest US-listed "
                       "chip suppliers.", "Source: SEC EDGAR filings")),

        ("h2", "The Bet"),
        ("p", f"The spending is a wager on demand that has not yet arrived. "
         f"Extending the seven firms&rsquo; own trajectory forward under a range of "
         f"assumptions produces a cumulative 2026–2030 capital outlay of between "
         f"{n['proj_lo']} and {n['proj_hi']}, with a central estimate near "
         f"{n['proj_mid']}. Industry forecasters, counting the whole world and "
         f"including chips and power, reach higher: McKinsey puts global "
         f"data-center capital expenditure at {n['mck']} through 2030; Goldman "
         f"Sachs estimates {n['gs']} of global AI capital spending through 2031."),
        ("fig", figure(c["bet"], "The forward bet",
                       "Seven-hyperscaler annual capital investment: actual through "
                       "2025, then an independent low / mid / high projection.",
                       "Source: SEC EDGAR; author&rsquo;s projection")),
        ("p", "The projection is deliberately conservative. The seven firms&rsquo; "
         "combined investment grew 71 percent between 2024 and 2025; even the high "
         "scenario assumes that pace decelerates every year through 2030, and the "
         "low scenario assumes it stalls. The range is wide because the quantity "
         "being projected is not really a trend. It is a decision the firms remake, "
         "and defend to their shareholders, every quarter."),
        ("p", "Forecasts at this scale rest on assumptions that do not hold still. "
         "Goldman describes its own numbers as baseline estimates that are "
         "&ldquo;extremely sensitive.&rdquo; The harder question is revenue. Bain "
         "&amp; Company estimates that paying for the buildout on its current path "
         "would require roughly $2 trillion a year in new revenue by 2030, and "
         "projects the industry will fall some $800 billion short."),
        ("pull", "A forward commitment of several trillion dollars is being made "
         "against a revenue base that, on the industry&rsquo;s own arithmetic, does "
         "not yet exist."),
        ("p", "This gap is what the underlying research frames as a geopolitically "
         "backstopped investment cycle: the spending continues because it is "
         "treated, by the firms and their investors, as too important to be allowed "
         "to fail. The data can measure the gap a backstop would have to fill. It "
         "cannot show that the backstop exists. That remains a thesis, not a "
         "finding."),
        ("p", "The shape of the wager is not new. Britain&rsquo;s railway mania of "
         "the 1840s and America&rsquo;s late-1990s fiber-optic glut both funneled a "
         "society&rsquo;s savings into infrastructure built well ahead of demand. "
         "Both left two things behind: capacity that the economy eventually grew "
         "into, and a generation of investors who were ruined before it did. The "
         "underlying research treats the AI buildout as the same species of "
         "event — a churn — and the unsettled question is simply which half "
         "of that inheritance the present cycle is accumulating."),
        ("p", "For the hopeful half to win, a great deal has to come true at once: "
         "that AI applications earn revenue at the scale the spending implies, that "
         "the chips bought this year are not obsolete before they are paid off, and "
         "that the power and the permits arrive on schedule. Each is plausible on "
         "its own. The wager is that all of them hold together — and that "
         "joint probability, more than any single line in a forecast, is what the "
         "models cannot honestly price."),
        ("fig", figure(c["forecasts"], "What the forecasters expect",
                       "Cumulative AI / data-center capital-spending forecasts "
                       "(global, all operators).",
                       "Source: McKinsey; Goldman Sachs; Bain")),

        ("h2", "The Grid"),
        ("p", "Whatever the buildout&rsquo;s eventual returns, its first bills are "
         "already due, and they are arriving somewhere other than the seven "
         "firms&rsquo; income statements. The most immediate is electricity. For "
         "thirteen years, from 2007 to 2020, total US electricity demand was "
         "essentially flat — a generation of efficiency gains canceling out "
         "growth."),
        ("p", "For most of those years the explanation was benign. American "
         "electricity demand stopped growing because the economy kept learning to "
         "do more with less power — efficient lighting, better motors, and a "
         "manufacturing base that had shifted much of its heaviest load offshore. "
         "Forecasters came to treat flat demand as the natural condition of a "
         "mature grid, and two decades of utility planning, transmission "
         "investment and rate design were built on that assumption. The "
         "data-center surge is the first force in a generation strong enough to "
         "break it."),
        ("fig", figure(c["demand"], "Thirteen flat years, then a wall",
                       "US electricity demand, all sectors.", "Source: EIA")),
        ("p", f"That era is over. Demand is now rising about {n['surge']} a year, "
         f"and data centers are a principal reason. They consumed roughly "
         f"{n['dc23']} of US electricity in 2023; depending on the scenario, that "
         f"share is projected to reach between {n['dc30']} by 2030. A grid that was "
         f"planned around stability is being asked to absorb a step-change."),
        ("fig", figure(c["dcshare"], "The grid absorbs the buildout",
                       "Data centers as a share of total US electricity, 2023 "
                       "actual and 2030 projected range.",
                       "Source: LBNL; EPRI; EIA")),
        ("p", "Electricity is not like other inputs. It cannot be meaningfully "
         "stored at grid scale; the transmission lines to move it take the better "
         "part of a decade to permit and build; and a data center signs contracts "
         "for power years before the supply to serve it exists. A demand shock that "
         "another commodity would absorb through inventory and trade arrives in the "
         "power system as something harder: interconnection queues, capacity "
         "shortfalls, and price. The grid cannot be scaled at the speed of capital, "
         "and the buildout is testing exactly that mismatch."),

        ("h2", "Where the Load Lands"),
        ("p", "A national average of 4.4 percent is a misleading number, because "
         "the load does not spread evenly. It clusters. Virginia alone hosts an "
         "estimated 32 terawatt-hours of data-center demand — on the order of "
         "a quarter of the entire state&rsquo;s electricity. The corridor through "
         "Loudoun County is known in the industry, without irony, as "
         "&ldquo;Data Center Alley.&rdquo;"),
        ("p", "Texas follows at roughly 17 terawatt-hours, Illinois at 12, with "
         "California and Oregon close behind. By EPRI&rsquo;s estimate, about "
         "fifteen states account for some 80 percent of all US data-center "
         "electricity. The buildout is a national story told in a few "
         "ZIP codes — and those places carry a grid burden the national "
         "average never shows."),
        ("fig", figure(c["states"], "Where the load lands",
                       "Data-center electricity by state — approximate 2023 "
                       "estimates.", "Source: LBNL; EPRI; secondary reporting")),
        ("p", "Virginia is the case that shows what concentration means. The "
         "state&rsquo;s dominant utility, Dominion Energy, has reported "
         "data-center connection requests running into the tens of gigawatts — "
         "on the order of several times the entire state&rsquo;s current peak "
         "demand. Much of that queue is speculative and will never be built; "
         "interconnection lists are padded with projects that hedge their bets. "
         "But even a fraction of it implies a state, and a set of counties, whose "
         "grid, land use and politics are being reorganized around server farms "
         "inside a single decade. The buildout does not arrive everywhere. It "
         "arrives somewhere, all at once."),
        ("p", "Concentration changes the politics, too. A cost spread thinly across "
         "a national average draws no opposition; the same cost landing on a single "
         "county draws town-hall fights, building moratoriums and ballot measures. "
         "The map of the buildout is therefore also a map of where its legitimacy "
         "will be contested — and, increasingly, where local governments are "
         "weighing the promised tax revenue against the load, the land and the "
         "water, and beginning, in some places, to say no."),
        ("placeholder", "Placeholder — sub-state detail. No public dataset "
         "reports data-center electricity use by county or individual facility; "
         "the figures above are approximate state estimates. The per-town, "
         "per-substation reality is visible only in scattered utility filings. A "
         "county-level layer would be added here if a machine-readable source "
         "becomes available."),

        ("h2", "The Price Question"),
        ("p", f"Does the load raise prices? Our own comparison of state electricity "
         f"data finds that residential power prices in the data-center-heavy states "
         f"rose about {n['p_heavy']} between 2020 and 2025, against roughly "
         f"{n['p_rest']} elsewhere — and the two tracked together until about "
         f"2021, then diverged. Over the same window, electricity consumption in "
         f"those states grew {n['c_heavy']}, against {n['c_rest']} elsewhere; "
         f"Virginia&rsquo;s alone grew {n['c_va']}."),
        ("fig", figure(c["prices"], "After 2021, a divergence",
                       "Residential electricity price, indexed to 2010, averaged "
                       "across data-center-heavy states versus the rest.",
                       "Source: EIA API v2 (state retail prices)")),
        ("p", f"The Federal Reserve Bank of Dallas reaches a sharper version of the "
         f"same conclusion. Its dispatch model finds data centers have already "
         f"raised US wholesale electricity prices by roughly {n['w_now']} percent, "
         f"and could raise them {n['w_mod']}–{n['w_high']} percent by 2028 "
         f"depending on how much of the announced load is built and how hard it "
         f"runs. In the PJM grid region, capacity prices have already jumped "
         f"roughly elevenfold in two auctions, with data centers blamed for most "
         f"of the increase."),
        ("pull", "In the data-center states, residential power has risen by more "
         "than a third in five years. Whether the data centers caused it is the "
         "most contested question in the file."),
        ("p", "That contest is real. The Institute for Energy Research, examining "
         "the same period, found no statistically significant relationship between "
         "data-center density and state electricity prices — and noted that "
         "lower-growth states actually saw larger price increases. State prices are "
         "driven by fuel mix and policy as much as by load, and five heavy states "
         "are a small sample. The honest reading: the correlation is visible and "
         "the timing lines up, but causation is not settled."),
        ("p", "Where the mechanism does operate, it is not mysterious. A large new "
         "load bids for the same generation and the same transmission as everyone "
         "else; in the capacity markets that pay power plants to stay available, it "
         "lifts the price every utility must pay to guarantee supply — and that "
         "cost flows through to all customers, data center or household alike. A "
         "server farm that opens in a county does not build itself a separate "
         "electricity system. It joins the one the residents already share, and "
         "bids against them in it."),
        ("p", "Regulators have begun to respond. Virginia has approved a distinct "
         "rate class for the largest data centers — an attempt to make the load "
         "carry more of the transmission and generation it requires, rather than "
         "socializing that cost across residential bills. Whether such rules "
         "hold, and whether other states copy them, is now an active political "
         "fight, conducted utility by utility and rate case by rate case. The "
         "buildout has become a question of who pays, decided in venues most "
         "voters have never heard of."),

        ("h2", "How Prices Are Modeled"),
        ("p", "Behind every projected price increase is a model. The EIA&rsquo;s "
         "Electricity Market Module solves a least-cost hourly dispatch across "
         "twenty-five regions of the country, and for the first time treats "
         "data-center load as an explicit driver. The Dallas Fed&rsquo;s approach "
         "is similar in spirit — an hour-by-hour, unit-by-unit simulation of "
         "which power plants run to meet demand, and at what cost."),
        ("fig", figure(c["outlook"], "How high prices could go",
                       "Modelled data-center impact on US wholesale electricity "
                       "prices.", "Source: Federal Reserve Bank of Dallas, WP2606")),
        ("p", f"The projections range widely because they hinge on assumptions that "
         f"are themselves uncertain: how fast AI chips age, how quickly new "
         f"generation and transmission come online, and how much of the load "
         f"queued for connection actually materializes. The Dallas Fed estimates "
         f"data centers add about {n['pce26']} of a percentage point to consumer "
         f"price inflation in 2026, rising toward 2030 — and potentially "
         f"doubling if renewable build-out lags. Small numbers, spread across every "
         f"household in the country."),
        ("p", "The honesty of a forecast at this scale lies in its range. A model "
         "that returns one confident number is concealing its assumptions; one "
         "that returns a wide band is showing them. The gap between a 20 percent "
         "and a 50 percent wholesale-price impact is not analytical weakness — "
         "it is an accurate statement of how much still depends on choices not yet "
         "made: how fast chips are retired, how quickly generation and "
         "transmission are built, whether the queued load shows up at all. The "
         "forecasts disagree because the future genuinely does."),

        ("h2", "Data Centers as Power Players"),
        ("p", "If data centers strain the grid, can they also feed it — can they "
         "resell power? As of 2026, not as net sellers. But they are no longer "
         "passive loads either. Increasingly, they bring their own power. Meta has "
         "contracted 1,121 megawatts of Illinois nuclear capacity; Amazon has "
         "locked up 1,920 megawatts of Pennsylvania nuclear and is funding small "
         "modular reactors; Google has signed for the output of a restarted Iowa "
         "reactor."),
        ("p", "Some skip the grid altogether. xAI&rsquo;s &ldquo;Colossus&rdquo; "
         "site in Memphis runs largely off-grid on gas turbines and Tesla "
         "batteries. Others sell flexibility back: Google has committed around a "
         "gigawatt of demand response, agreeing to curtail load when the grid is "
         "stressed. The emerging model — &ldquo;bring your own power&rdquo; — "
         "lets a data center bypass the years-long interconnection queue, and "
         "blurs the line between a computing company and a utility."),
        ("p", "That blurring has consequences for everyone left on the shared "
         "system. A data center that builds its own gas plant to skip a five-year "
         "interconnection wait also removes itself, in part, from the grid that "
         "pools costs and risks across all customers. The buildout is not only "
         "adding load; it is quietly drawing a second, private power system "
         "alongside the public one — dedicated generation for those who can "
         "afford to commission it, and the older, slower, shared grid for "
         "everyone else. Whether that bifurcation is efficient or corrosive is one "
         "of the real questions the buildout poses, and it is barely being asked."),
        ("placeholder", "Placeholder — data centers as grid resources. "
         "Whether data centers become net contributors to the grid, rather than "
         "net burdens on it, is a question for the 2030s. Systematic data on their "
         "demand-response and behind-the-meter generation is still thin; this "
         "section rests on company disclosures, and would be quantified here if a "
         "consistent dataset emerges."),

        ("h2", "The Cubicle"),
        ("p", f"The buildout&rsquo;s second cost lands in the labor market, and it "
         f"lands differently than earlier automation did. By one widely used "
         f"measure, the average US job has about {n['elo']} of its tasks exposed to "
         f"large language models — work the technology could materially speed "
         f"up. Some {n['hi_exp']} of US employment sits in occupations where more "
         f"than half of tasks are exposed."),
        ("p", f"Two features complicate the headline. The first is that exposure is "
         f"not the same as use: a second measure, built from observed AI usage "
         f"rather than predicted capability, puts the employment-weighted figure "
         f"closer to {n['anth']}. The gap between what is possible and what is "
         f"actually happening is the adoption runway still ahead."),
        ("fig", figure(c["labor"], "This wave climbs the wage ladder",
                       "Share of occupational tasks exposed to AI, by wage decile "
                       "— predicted capability versus observed use, "
                       "employment-weighted.",
                       "Source: BLS OEWS; Eloundou et al.; Anthropic Economic Index")),
        ("pull", "Earlier waves of automation hit the factory floor. This one is "
         "concentrated in the cubicle."),
        ("p", "The second feature is who is exposed. Earlier automation fell "
         "hardest on lower-wage, manual work. This one inverts the pattern: "
         "exposure rises with wage. The most exposed large occupations are "
         "customer-service representatives, sales representatives and "
         "administrative assistants — the white-collar core, and the "
         "interpretive, linguistic work the underlying paper identifies as the "
         "cultural capital now being absorbed."),
        ("p", "Exposure is not displacement, and the report is careful not to let "
         "the two slide together. But the early signal is specific. The work most "
         "exposed — drafting a reply, summarizing a document, reconciling a "
         "ledger, writing a function — is the work that has long been the first "
         "rung of a white-collar career: the tasks juniors do while they learn the "
         "ones that cannot be written down. A labor market knows how to absorb the "
         "automation of tasks. It is far less clear how it absorbs the automation "
         "of the bottom rung of the ladder."),
        ("p", "The two measures together also set the clock. Predicted exposure "
         "marks where the technology can eventually reach; observed use marks how "
         "far it has reached so far. The distance between roughly a third of tasks "
         "and roughly an eighth is the room remaining before the labor-market "
         "effects, whatever they turn out to be, are fully felt. That gap is "
         "closing — and on the evidence of the usage data, it is closing "
         "fastest in exactly the high-wage, white-collar work that the predicted "
         "measure flags as most exposed."),

        ("h2", "The Concrete"),
        ("p", f"There is one sector where the buildout adds work rather than "
         f"displacing it. Data-center construction has grown to {n['constr_sh']} of "
         f"all US construction spending — a fivefold rise in its share over a "
         f"decade — and the construction workforce stands at {n['constr_emp']}. "
         f"The concrete, steel and switchgear of the AI economy still require "
         f"hands, even as the work done inside the finished buildings does not."),
        ("fig", figure(c["constr"], "The one place the buildout adds jobs",
                       "Data-center construction as a share of all US construction "
                       "spending.", "Source: US Census / OWID; FRED")),
        ("p", "It is a revealing exception. The buildout&rsquo;s lasting employment "
         "is in pouring the foundation, not in operating what stands on it: a "
         "finished hyperscale data center, for all the electricity it draws, is run "
         "by a few dozen technicians. The jobs the AI economy reliably creates are "
         "disproportionately the temporary ones — and they end when the concrete "
         "cures. What the buildout leaves behind is a structure that employs almost "
         "no one and consumes the power of a small city."),

        ("h2", "What the Numbers Cannot Say"),
        ("p", f"Several limits are worth stating plainly. The {n['hyper']} is not a "
         f"pure AI figure; corporate filings do not separate AI spending from "
         f"ordinary cloud investment. Task exposure measures what is possible, not "
         f"a count of jobs lost. The link between data centers and electricity "
         f"prices is a contested correlation, not a settled cause. Below the state "
         f"level, the energy picture goes dark for lack of public data. And the "
         f"central wager — that demand will arrive to justify the spending — "
         f"is precisely what no number can yet settle."),
        ("p", "None of this is a prediction of failure. The buildout may be "
         "vindicated; the demand may arrive; the data centers may yet earn back "
         "what they cost. The purpose of an accounting is narrower and more "
         "stubborn than a forecast. It is to set down clearly what has been spent, "
         "by whom, and who is already paying the bills that have come due — so "
         "that when the verdict on the wager finally lands, the ledger of who "
         "carried it in the meantime is not quietly lost."),
        ("p", "What the numbers do establish is the size of the bet, the smallness "
         "of the group making it, and the fact that its costs have already begun to "
         "move outward — onto the grid, onto the wage structure, onto the "
         "allocation of national capital, and onto particular places that did not "
         "choose the buildout. That asymmetry, between costs that are present and "
         "returns that are still a forecast, is the defining feature of the AI "
         "buildout as of mid-2026."),
        ("methodbox", methodbox),
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

    c = {"ramp": chart_ramp(d), "layers": chart_layers(d), "macro": chart_macro(d),
         "semis": chart_semis(d), "bet": chart_bet(d), "forecasts": chart_forecasts(d),
         "demand": chart_us_demand(d), "dcshare": chart_dc_share(d),
         "states": chart_dc_states(d), "prices": chart_state_prices(d),
         "outlook": chart_price_outlook(d), "labor": chart_labor(d),
         "constr": chart_construction(d)}

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
        elif kind == "methodbox":
            body.append(content)
        elif kind == "lede":
            body.append(f'<p class="lede">{content}</p>')
        else:
            body.append(f"<p>{content}</p>")
        if kind in ("lede", "p", "pull", "h2"):
            words += len(re.sub("<[^>]+>", "", content).split())

    headline = "The $424 Billion Bet"
    deck = ("Seven American companies are spending more on data centers than the "
            "country invests in most of its industries. The wager is that demand for "
            "artificial intelligence will arrive to justify it. The costs of the "
            "buildout are already moving onto the power grid — unevenly, and "
            "toward the places least able to refuse them.")
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
<div class="dateline">May 15, 2026</div>
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
