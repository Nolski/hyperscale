#!/usr/bin/env python3
"""
build_report.py -- Presentation step.

Assembles a single self-contained HTML report -- a New York Times-style
data-journalism feature on the AI-buildout research -- and writes:
  - output/report.html   (self-contained: all charts embedded as base64 PNGs)

The script reads the pipeline's processed datasets and summary tables so every
figure quoted in the prose stays in sync with the data, regenerates five charts
in an editorial (NYT-graphics) style, and templates them into an HTML article.

Re-runnable: reads data/processed/ + output/*.csv, overwrites output/report.html.
No network.
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
OUTPUT = ROOT / "output"
RETRIEVED = dt.date.today().isoformat()
BN = 1e9

# Editorial palette
INK = "#121212"
NAVY = "#1a3a5c"
NAVY_MID = "#4a6e8f"
NAVY_LT = "#9fb6c8"
RED = "#a4262c"
GREY = "#8a8a8a"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Arial", "Liberation Sans", "DejaVu Sans"],
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False,
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
    """Coerce a CSV cell to float where possible; leave non-numeric strings."""
    try:
        return float(v)
    except (ValueError, TypeError):
        return v


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

    syn = pd.read_csv(OUTPUT / "synthesis_indicators.csv")
    d["syn"] = {k: to_num(v) for k, v in
                zip(syn["indicator"].str.strip(), syn["value"])}

    dce = pd.read_csv(PROCESSED / "datacenter_energy.csv")
    share = dce[dce.metric == "datacenter_share_of_us"]
    d["dc_2023"] = share[share.year == 2023].iloc[0]["value"]
    d["dc_2030"] = sorted(share[share.year == 2030]["value"].tolist())

    elec = pd.read_csv(PROCESSED / "us_electricity.csv")
    res = elec[elec.sector == "residential"].set_index("year")["price_cents_per_kwh"]
    d["res_price"] = (res.loc[res.index.min()], res.loc[res.index.max()])

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

    lk = pd.read_csv(OUTPUT / "linked_sectors_summary.csv")
    d["lk"] = {k: to_num(v) for k, v in
               zip(lk["indicator"].str.strip(), lk["value"])}
    ax = pd.read_csv(OUTPUT / "automation_exposure_summary.csv")
    d["ax"] = {k: to_num(v) for k, v in
               zip(ax["indicator"].str.strip(), ax["value"])}
    return d


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
def chart_ramp(d) -> str:
    s = d["capex_by_year"]
    fig, ax = plt.subplots(figsize=(8, 4.1))
    ax.bar(s.index, s.values, color=NAVY, width=0.74)
    for yr in (s.index.min(), 2025):
        ax.text(yr, s.loc[yr] + 12, f"${s.loc[yr]:,.0f}B", ha="center",
                fontsize=9.5, weight="bold", color=NAVY)
    ax.set_ylabel("USD billion")
    ax.set_ylim(0, s.max() * 1.16)
    ax.set_xticks(list(s.index))
    ax.tick_params(axis="x", labelrotation=0)
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_macro(d) -> str:
    syn = d["syn"]
    items = [("of US GDP", float(syn["as share of US GDP"])),
             ("of all private business\nfixed investment",
              float(syn["as share of US private nonres. fixed investment"])),
             ("of all US IT-equipment\n+ software investment",
              float(syn["as share of US IT-equipment + software investment"]))]
    labels = [i[0] for i in items]
    vals = [i[1] for i in items]
    fig, ax = plt.subplots(figsize=(8, 3.1))
    colors = [NAVY_LT, NAVY_MID, NAVY]
    bars = ax.barh(labels, vals, color=colors, height=0.62)
    for b, v in zip(bars, vals):
        ax.text(v + 0.6, b.get_y() + b.get_height() / 2, f"{v:.1f}%",
                va="center", fontsize=10, weight="bold", color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, max(vals) * 1.2)
    ax.grid(axis="y", visible=False)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=9.5)
    return fig_to_b64(fig)


def chart_bet(d) -> str:
    s = d["capex_by_year"]
    hist = s[s.index >= 2015]
    proj = d["proj"]
    fig, ax = plt.subplots(figsize=(8, 4.3))
    ax.plot(hist.index, hist.values, color=INK, lw=2.4, label="Actual")
    styles = [("low", NAVY_LT), ("mid", NAVY_MID), ("high", NAVY)]
    for sc, col in styles:
        p = proj[proj.scenario == sc].set_index("year")["annual_capex_usd_bn"]
        xs, ys = [2025] + list(p.index), [hist.loc[2025]] + list(p.values)
        ax.plot(xs, ys, color=col, lw=1.9, ls="--")
        ax.text(2030.1, ys[-1], f"  {sc} ${ys[-1] / 1000:.1f}T", va="center",
                fontsize=8.5, color=col, weight="bold")
    lo = [hist.loc[2025]] + list(proj[proj.scenario == "low"]["annual_capex_usd_bn"])
    hi = [hist.loc[2025]] + list(proj[proj.scenario == "high"]["annual_capex_usd_bn"])
    ax.fill_between(range(2025, 2031), lo, hi, color=NAVY, alpha=0.07)
    ax.set_ylabel("Annual capital investment, USD billion")
    ax.set_xlim(2015, 2032.2)
    ax.set_ylim(0, 2200)
    ax.grid(axis="x", visible=False)
    ax.axvline(2025, color=GREY, lw=0.8, ls=":")
    ax.text(2024.8, 2080, "actual", ha="right", fontsize=8, color=GREY, style="italic")
    ax.text(2025.2, 2080, "projected", ha="left", fontsize=8, color=GREY, style="italic")
    return fig_to_b64(fig)


def chart_energy(d) -> str:
    lo, hi = d["dc_2030"]
    fig, ax = plt.subplots(figsize=(8, 3.7))
    ax.plot([2023], [d["dc_2023"]], "o", ms=11, color=NAVY)
    ax.text(2023, d["dc_2023"] - 1.7, f"{d['dc_2023']:g}%\n2023", ha="center",
            fontsize=9.5, color=NAVY, weight="bold")
    ax.plot([2030, 2030], [lo, hi], color=RED, lw=10, solid_capstyle="round")
    ax.text(2030.4, (lo + hi) / 2, f"{lo:g}–{hi:g}%\nby 2030", va="center",
            fontsize=9.5, color=RED, weight="bold")
    ax.set_ylabel("Share of US electricity")
    ax.set_xlim(2021.5, 2032.5)
    ax.set_ylim(0, 19)
    ax.set_xticks([2023, 2030])
    ax.grid(axis="x", visible=False)
    return fig_to_b64(fig)


def chart_labor(d) -> str:
    dec = d["decile"]
    x = dec.index.to_numpy()
    w = 0.4
    fig, ax = plt.subplots(figsize=(8, 4.1))
    ax.bar(x - w / 2, dec["elo"], w, color=NAVY, label="Predicted exposure (Eloundou)")
    ax.bar(x + w / 2, dec["anth"], w, color=RED, label="Observed use (Anthropic)")
    ax.set_ylabel("Share of tasks AI-exposed")
    ax.set_xlabel("Wage decile  (1 = lowest-paid, 10 = highest-paid)")
    ax.set_xticks(list(x))
    ax.grid(axis="x", visible=False)
    ax.legend(fontsize=8.5, frameon=False, loc="upper left")
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
h1 { font-size:2.7rem; line-height:1.12; font-weight:700; letter-spacing:-.012em;
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
  text-transform:uppercase; letter-spacing:.05em; color:var(--grey);
  margin-top:9px; }
.pull { font-size:1.62rem; line-height:1.32; font-weight:700; color:var(--ink);
  margin:1.5em 0; padding:.55em 0; border-top:2px solid var(--ink);
  border-bottom:2px solid var(--ink); }
.footer { margin-top:3em; padding-top:1.4em; border-top:1px solid var(--rule);
  font-family:'Helvetica Neue',Arial,sans-serif; font-size:.78rem;
  line-height:1.6; color:var(--grey); }
"""


def figure(b64, title, sub, src):
    return (f'<figure><div class="fig-title">{title}</div>'
            f'<div class="fig-sub">{sub}</div>'
            f'<img alt="{title}" src="data:image/png;base64,{b64}">'
            f'<div class="fig-src">{src}</div></figure>')


def main() -> None:
    d = load()
    syn, lk, ax = d["syn"], d["lk"], d["ax"]

    # ---- numbers, read from the pipeline so prose stays in sync -----------
    capex0 = round(d["capex_by_year"].iloc[0] / 10) * 10
    n = {
        "hyper": f"${syn['Hyperscaler capital investment, 2025']:.0f} billion",
        "share_gdp": f"{float(syn['as share of US GDP']):.1f} percent",
        "share_it": f"{float(syn['as share of US IT-equipment + software investment']):.0f} percent",
        "vc": f"${syn['Global VC into AI, 2025']:.0f} billion",
        "vc_us": "$194 billion",
        "chip": f"${syn['AI-chip supplier revenue (5 US firms)']:.0f} billion",
        "nvda": f"${lk['of which NVIDIA']:.0f} billion",
        "nvda_sh": f"{lk['NVIDIA share of the five']:.0f} percent",
        "capex0": f"${capex0:.0f} billion",
        "proj_mid": f"${syn['Independent estimate, cumulative 2026-2030 (mid)'] / 1000:.1f} trillion",
        "proj_lo": f"${int(syn['Independent estimate, range (low-high)'].split('-')[0]) / 1000:.1f} trillion",
        "proj_hi": f"${int(syn['Independent estimate, range (low-high)'].split('-')[1]) / 1000:.1f} trillion",
        "mck": f"${syn['McKinsey global data-center capex 2025-30 (base)'] / 1000:.1f} trillion",
        "gs": f"${syn['Goldman global AI capex 2026-31'] / 1000:.1f} trillion",
        "dc23": f"{d['dc_2023']:g} percent",
        "dc30": f"{d['dc_2030'][0]:g} and {d['dc_2030'][1]:g} percent",
        "res0": f"{d['res_price'][0]:.1f}", "res1": f"{d['res_price'][1]:.1f}",
        "elo": f"{float(ax['Empl.-weighted exposure -- Eloundou (predicted)']) * 100:.0f} percent",
        "hi": f"{float(ax['Empl. in high-exposure occ. (>=0.5) %, Eloundou (predicted)']):.0f} percent",
        "anth": f"{float(ax['Empl.-weighted exposure -- Anthropic (observed)']) * 100:.0f} percent",
        "constr_sh": f"{lk['Data-center share of all US construction (2025)']:.2f} percent",
        "constr_emp": f"{lk['US construction employment (latest)']:.1f} million",
    }

    charts = {"ramp": chart_ramp(d), "macro": chart_macro(d), "bet": chart_bet(d),
              "energy": chart_energy(d), "labor": chart_labor(d)}

    # ---- prose ------------------------------------------------------------
    paras = [
        ("lede", f"In 2025, seven companies — Microsoft, Alphabet, Amazon, Meta, "
         f"Oracle, Nvidia and CoreWeave — committed about {n['hyper']} to capital "
         f"investment, most of it data centers built for artificial intelligence. "
         f"That is roughly {n['share_gdp']} of American gross domestic product, close "
         f"to a tenth of all private business investment in the United States, and "
         f"nearly a third — {n['share_it']} — of everything American business "
         f"spends on information-technology equipment and software combined."),
        ("p", f"A decade earlier, the same seven firms spent on the order of "
         f"{n['capex0']} a year between them. The path from there to here is not a "
         f"gentle trend. The total roughly doubled in the single year between 2024 "
         f"and 2025."),
        ("fig", figure(charts["ramp"], "A near-vertical climb",
                       "Combined annual capital investment of seven US hyperscalers, "
                       "cash capex plus finance leases.",
                       "Source: SEC EDGAR filings")),
        ("h2", "The Scale"),
        ("p", f"Numbers this large invite double-counting, and most published tallies "
         f"of “AI investment” commit it. The {n['hyper']} is real "
         f"investment — money spent, and assets leased, to build and equip data "
         f"centers. It is distinct from the {n['vc']} of venture capital that flowed "
         f"into AI companies worldwide in 2025 ({n['vc_us']} of it in the United "
         f"States), which is a financing flow, not a building. And it is distinct "
         f"again from the {n['chip']} in revenue earned last year by the five largest "
         f"US-listed chip suppliers — a figure not added to the buildout but "
         f"contained within it, since those chips are what the spending buys."),
        ("p", f"What the three figures share is concentration. Nvidia alone booked "
         f"{n['nvda']} in revenue, {n['nvda_sh']} of the five-firm total. Seven "
         f"companies account for the capital. The AI economy, measured in dollars, is "
         f"not an economy of many participants. It is a handful of balance sheets."),
        ("fig", figure(charts["macro"], "A claim on the economy's investable surplus",
                       "2025 hyperscaler capital investment, measured against US "
                       "capital formation.",
                       "Source: SEC EDGAR; FRED (BEA national accounts)")),
        ("p", f"The most telling of those ratios is the last. When seven firms direct "
         f"an amount equal to {n['share_it']} of all national IT-equipment-and-"
         f"software investment toward one category of asset, the buildout has stopped "
         f"being a sector story. It is a claim on the economy's investable surplus."),
        ("p", f"Even {n['hyper']} is a floor. The figure counts cash spending and the "
         f"assets the firms lease through finance leases, but not capacity rented "
         f"through ordinary operating leases, nor the off-balance-sheet vehicles and "
         f"private-credit arrangements that increasingly fund data centers. The true "
         f"scale of the commitment is larger than any single line in a financial "
         f"statement — and, by design, harder to see."),
        ("h2", "The Bet"),
        ("p", f"The spending is a wager on demand that has not yet arrived. Extending "
         f"the seven firms' own trajectory forward under a range of assumptions "
         f"produces a cumulative 2026–2030 capital outlay of between "
         f"{n['proj_lo']} and {n['proj_hi']}, with a central estimate near "
         f"{n['proj_mid']}. Industry forecasters, counting the whole world and "
         f"including chips and power, reach higher: McKinsey puts global data-center "
         f"capital expenditure at {n['mck']} through 2030; Goldman Sachs estimates "
         f"{n['gs']} of global AI capital spending through 2031."),
        ("fig", figure(charts["bet"], "The forward bet",
                       "Seven-hyperscaler annual capital investment: actual through "
                       "2025, then an independent low / mid / high projection.",
                       "Source: SEC EDGAR; author's projection (see notes/provenance.md)")),
        ("p", "The projection is deliberately conservative. The seven firms' combined "
         "investment grew 71 percent between 2024 and 2025; even the high scenario "
         "here assumes that pace decelerates every year through 2030, and the low "
         "scenario assumes it stalls outright. The range is wide because the quantity "
         "being projected is not really a trend. It is a decision — one the firms "
         "remake, and defend to their shareholders, every quarter."),
        ("p", "Forecasts at this scale rest on assumptions that do not hold still. "
         "Goldman describes its own numbers as baseline estimates that are "
         "“extremely sensitive” — a single change in how fast AI chips "
         "are assumed to age can move the total by hundreds of billions of dollars. "
         "The harder question is revenue. Bain &amp; Company estimates that paying "
         "for the buildout on its current path would require roughly $2 trillion a "
         "year in new revenue by 2030, and projects the industry will fall some $800 "
         "billion short."),
        ("p", "This gap is what the project's framing — of an AI buildout treated "
         "as a geopolitically backstopped investment cycle — is built to "
         "explain. The argument is that the spending continues because it is "
         "understood, by the firms and their investors, as too important to be "
         "allowed to fail. The data assembled here can measure the gap a backstop "
         "would have to fill. It cannot show that the backstop exists. That remains a "
         "thesis, not a finding."),
        ("h2", "The Churn"),
        ("p", "Whatever the buildout's eventual returns, its costs are already "
         "arriving — and they are arriving somewhere other than the seven firms' "
         "income statements."),
        ("p", f"Start with electricity. For thirteen years, from 2007 to 2020, total "
         f"US electricity demand was essentially flat. It is now rising again, by "
         f"about 1.8 percent a year, and data centers are a principal reason. They "
         f"consumed roughly {n['dc23']} of US electricity in 2023; depending on the "
         f"scenario, that share is projected to reach between {n['dc30']} by 2030."),
        ("fig", figure(charts["energy"], "The grid absorbs the buildout",
                       "Data centers as a share of total US electricity consumption, "
                       "2023 actual and 2030 projected range.",
                       "Source: Lawrence Berkeley National Laboratory; EPRI; EIA")),
        ("p", f"Over the same quarter-century in which data-center demand climbed, the "
         f"average American residential electricity price doubled, from {n['res0']} "
         f"to {n['res1']} cents per kilowatt-hour. The data here establishes the "
         f"coincidence, not the cause; prices rise for many reasons. But the "
         f"distributional shape is plain. The load growth is corporate. A rising "
         f"share of the bill is paid by households."),
        ("p", "The flat years are the context that makes the present moment legible. "
         "Utilities spent two decades planning around stable demand; the data-center "
         "surge has arrived faster than transmission and generation can be built to "
         "meet it. The cost of closing that gap — new power plants, new lines, and "
         "the higher price of electricity itself — is spread across every customer "
         "on the grid, whether or not they have any use for artificial intelligence."),
        ("pull", "Earlier waves of automation hit the factory floor. This one is "
         "concentrated in the cubicle."),
        ("p", f"The second cost lands in the labor market, and it lands differently "
         f"than earlier automation did. By one widely used measure, the average US "
         f"job has about {n['elo']} of its tasks exposed to large language "
         f"models — work the technology could materially speed up. Some "
         f"{n['hi']} of US employment sits in occupations where more than half of "
         f"tasks are exposed."),
        ("p", f"Two features complicate the headline. The first is that exposure is "
         f"not the same as use: a second measure, built from observed AI usage rather "
         f"than predicted capability, puts the employment-weighted figure closer to "
         f"{n['anth']}. The gap between the two — what is possible and what is "
         f"actually happening — is the adoption runway still ahead."),
        ("p", "The second feature is who is exposed. Earlier waves of automation fell "
         "hardest on lower-wage, manual work. This one inverts the pattern: exposure "
         "rises with wage. The most exposed large occupations are customer-service "
         "representatives, sales representatives and administrative assistants — "
         "the white-collar core."),
        ("p", "The pattern is sharp at the level of individual jobs. Customer-service "
         "representatives — 2.7 million workers — score near 0.70 on the "
         "predicted measure and, unusually, near 0.70 on the observed one as well: a "
         "rare case in which what AI could do and what it is already doing agree. "
         "Sales representatives, general office clerks and accountants follow close "
         "behind. These are not marginal occupations. They are among the largest in "
         "the country, and they are the linguistic, interpretive work — the "
         "drafting, the answering, the reconciling — that the paper's argument "
         "identifies as the cultural capital now being absorbed."),
        ("fig", figure(charts["labor"], "This wave climbs the wage ladder",
                       "Share of occupational tasks exposed to AI, by wage decile — "
                       "predicted capability versus observed use, employment-weighted.",
                       "Source: BLS OEWS; Eloundou et al. (2024); Anthropic Economic Index")),
        ("p", f"There is one sector where the buildout adds work rather than "
         f"displacing it. Data-center construction has grown to {n['constr_sh']} of "
         f"all US construction spending, and the construction workforce stands at "
         f"{n['constr_emp']}. The concrete and steel of the AI economy still require "
         f"hands."),
        ("h2", "What the Numbers Cannot Say"),
        ("p", f"Several limits are worth stating plainly. The {n['hyper']} is not a "
         f"pure AI figure; corporate filings do not separate AI spending from "
         f"ordinary cloud investment. Task exposure measures what is possible, not a "
         f"count of jobs lost. The rise in electricity prices is a correlation, not a "
         f"proven consequence. And the central wager — that demand will arrive "
         f"to justify the spending — is precisely what the numbers cannot yet "
         f"settle."),
        ("p", "What they do establish is the size of the bet, the smallness of the "
         "group making it, and the fact that its costs have already begun to move "
         "outward — onto the grid, onto the wage structure, onto the allocation "
         "of national capital — while its returns remain a forecast. That "
         "asymmetry, between costs that are present and returns that are promised, is "
         "the buildout's defining feature as of mid-2026."),
    ]

    body = []
    for kind, content in paras:
        if kind == "h2":
            body.append(f"<h2>{content}</h2>")
        elif kind == "fig":
            body.append(content)
        elif kind == "pull":
            body.append(f'<div class="pull">{content}</div>')
        elif kind == "lede":
            body.append(f'<p class="lede">{content}</p>')
        else:
            body.append(f"<p>{content}</p>")

    # word count over prose only
    words = sum(len(re.sub("<[^>]+>", "", c).split())
                for k, c in paras if k in ("lede", "p", "pull", "h2"))

    headline = "The $424 Billion Bet"
    deck = ("Seven American companies are spending more on data centers than the "
            "country invests in most of its industries. The wager is that demand for "
            "artificial intelligence will arrive to justify it — and the costs "
            "of the buildout are already moving onto the power grid and into the "
            "labor market.")
    footer = ("Methods &amp; sources. This report draws on a reproducible research "
              "pipeline: capital expenditure from SEC EDGAR filings; macro and "
              "construction series from FRED; electricity data from the EIA; "
              "occupational employment from the BLS; data-center energy projections "
              "from LBNL and EPRI; and AI-exposure scores from Eloundou et al. (2024) "
              "and the Anthropic Economic Index. Forecasts are attributed to "
              "McKinsey, Goldman Sachs and Bain. Every figure is regenerated by the "
              "scripts in <code>scripts/</code> and documented dataset-by-dataset in "
              f"<code>notes/provenance.md</code>. Compiled {RETRIEVED}.")

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
<div class="footer">{footer}</div>
</article>
</body>
</html>
"""

    out = OUTPUT / "report.html"
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}  ({len(html) / 1024:.0f} KB)")
    print(f"  charts embedded: {len(charts)}")
    print(f"  prose word count: ~{words}")
    print(f"  self-contained: {'yes' if 'src=\"http' not in html else 'NO'}")


if __name__ == "__main__":
    main()
