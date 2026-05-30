# Bibliography & framing — the AI investment cycle as concentrated financial risk

*Compiled 2026-05-29. Companion to `notes/methodology_financial_markets.md` and the
"Two Markets" synthesis (`notes/synthesis.md` §6). This file records the analytical
framing and the secondary literature for the argument that the AI buildout is a
concentrated, increasingly debt-financed, partly-subsidized investment cycle whose
financing cost is showing up in bond and credit markets.*

**Citation discipline (per CLAUDE.md):** these are FRAMING sources — use them for
interpretation, not as the data of record. The empirical claims must rest on the
`data/processed/` series. Each entry has a **[verify]** flag where the work is recent /
fast-moving / I am reconstructing details from memory; confirm title, date, and figures
against the primary source before quoting in published output.

---

## 0. The argument in one paragraph (for the report intro)

Rising long-term bond yields are widely misread as a recession warning. They are better
read as the price of a borrowing surge: a large federal deficit (Treasury supply) and a
fast-growing, highly concentrated wave of corporate borrowing to build AI data centers,
both competing for the world's finite savings and pushing up the *term premium*. The
equity market looks calm only because a handful of AI megacaps carry the index, and
investors are now paid almost nothing extra to hold stocks over safe bonds. The buildout
has not yet earned the revenue to justify its cost, is propped up by multiple subsidies
(tax, energy, an implicit national-security backstop), and is increasingly financed with
debt against assets (GPUs) that depreciate in a few years. The result is a single,
stacked, concentrated bet — the bond market, the equity market, and the AI cycle are
three views of the same wager.

---

## 1. "Is it a bubble AND a real revolution?" — the both/and frame

- **Carlota Pérez (2002)**, *Technological Revolutions and Financial Capital: The
  Dynamics of Bubbles and Golden Ages* (Edward Elgar). The key framework. Every great
  technological revolution (canals, rail, steel, mass production, ICT) passes through an
  "installation" period whose "frenzy" phase produces a financial bubble and a crash,
  *before* the productive "deployment"/golden age. **Application:** a crash would not
  prove AI is fake — it would be the genre-typical middle chapter. Lets us hold "real
  transformation" and "speculative excess" simultaneously.
- **Charles P. Kindleberger & Robert Aliber**, *Manias, Panics, and Crashes: A History
  of Financial Crises* (1978; later editions). The canonical anatomy: displacement →
  boom → euphoria → distress → revulsion. **Application:** template for staging where the
  AI cycle sits.
- **Historical analogues for capital destruction:**
  - UK **Railway Mania, 1840s** — see **Andrew Odlyzko**'s papers on the bubble and its
    collapse. [verify exact titles]
  - **Telecom/fiber glut, 1999–2002** — vast overbuild of fiber-optic capacity ("dark
    fiber"), most unused for years. **Contrast worth drawing:** fiber and rail lasted
    decades, so the assets were eventually useful; **GPUs depreciate in ~3–6 years**, so
    AI hardware can be obsolete before it pays off — a sharper risk than past overbuilds.

## 2. "Debt-financed investment is how stability becomes crisis"

- **Hyman P. Minsky**, "The Financial Instability Hypothesis" (1992, Levy Economics
  Institute Working Paper No. 74); *Stabilizing an Unstable Economy* (1986). Financing
  progresses from **hedge** (cash flow covers principal + interest) → **speculative**
  (covers interest, must roll principal) → **Ponzi** (must borrow to pay interest).
  "Stability breeds instability." **Application — directly testable in our data:** the
  shift we measured from cash-funded to debt-funded capex is Minsky's progression;
  CoreWeave (operating cash flow ≈ 0.30× capex) and Oracle (≈ 0.98×) sit in the
  speculative-to-Ponzi zone (`output/ai_financing.csv`).
- **Ray Dalio**, *Principles for Navigating Big Debt Crises* (2018); recent work on
  sovereign debt cycles [verify the 2025 title/edition]. The long debt-cycle lens on the
  fiscal (Treasury-supply) side of the term-premium story.

## 3. "Has AI actually paid off?" — the skeptics / the revenue gap

- **Daron Acemoglu (2024)**, "The Simple Macroeconomics of AI" (NBER Working Paper /
  *Economic Policy*). Argues the near-term aggregate productivity gain is modest — on the
  order of a fraction of a percent of TFP over ~10 years — far below popular hype. [verify
  the exact TFP figure, ~0.5–0.7% over a decade.] MIT; 2024 Nobel laureate. The strongest
  academic counterweight to "AI changes everything fast."
- **Goldman Sachs Global Macro Research (June 2024)**, "Gen AI: Too Much Spend, Too
  Little Benefit?" Features **Jim Covello** (GS Head of Global Equity Research) skeptical
  interview and Acemoglu. [verify issue no./date.] Directly on the capex-vs-payoff gap.
- **David Cahn (Sequoia Capital)**, "AI's $600B Question" (Sept 2024), following "AI's
  $200B Question" (2023). Frames the revenue needed to justify AI capex and the shortfall.
  **Application:** corroborates our report's existing revenue-gap / "the bet outruns
  revenue" finding (synthesis §2).

## 4. Concentration, private credit, depreciation accounting (current commentary)

*Fast-moving 2024–26 commentary — strongest on the specific plumbing, weakest on
permanence. Treat as leads to verify against primary filings/data.*

- **Torsten Sløk (Apollo Global Management, Chief Economist)** — frequent notes ("Apollo
  Daily" / "Daily Spark") on AI capex, S&P 500 concentration, private-credit financing of
  data centers, and (relevant here) market-concentration-vs-dot-com comparisons. [verify]
  Probably the most on-point current commentator for our datasets.
- **Jim Chanos** — short-seller; public skepticism on hyperscaler capital intensity and
  **depreciation/useful-life accounting**. [verify recent statements]
- **Michael Burry (Scion Asset Management)** — 2025 commentary alleging hyperscalers
  **understate depreciation by extending the useful life of servers/GPUs**, flattering
  earnings. [verify — this is the precise claim the depreciation analysis
  (`fetch_/analyze_hyperscaler_depreciation.py`) is built to test against 10-K data.]

## 5. The bond-market / fiscal side (the term-premium story)

- **Olivier Blanchard (2019)**, "Public Debt and Low Interest Rates" (AEA Presidential
  Address, *American Economic Review*). The r-vs-g debt-sustainability frame; essential
  for whether a high term premium / rising rates make the deficit path unstable.
- **Zoltan Pozsar** — dispatches on Treasury supply, collateral, and dealer balance-sheet
  capacity (e.g., the 2022 "Bretton Woods III" notes, formerly at Credit Suisse). [verify]
  Who actually absorbs Treasury issuance — the supply side of the term premium.
- **Michael Pettis (Carnegie / Peking University)**, *Trade Wars Are Class Wars* (2020,
  with Matthew C. Klein). Global savings imbalances — whose savings fund the US borrowing
  surge. Frames the "world's finite savings pool" claim.
- **Lawrence H. Summers** — "secular stagnation" thesis (2013–14) and its apparent
  reversal toward a higher neutral rate (r*); context for why the term premium normalized
  upward. [verify specific pieces]

## 6. Data-methodology citations (underpin our series — not framing)

- **Adrian, Tobias; Crump, Richard K.; Moench, Emanuel (2013)**, "Pricing the Term
  Structure with Linear Regressions," *Journal of Financial Economics*. The **ACM** model
  behind FRED `THREEFYTP10`, our term-premium series. Term premium is a MODEL ESTIMATE.
- **Kim, Don H.; Wright, Jonathan H. (2005)**, Federal Reserve FEDS paper — the
  alternative term-premium model; cite to show model dependence.
- **Sahm, Claudia (2019)** — the real-time Sahm-rule recession indicator (FRED
  `SAHMREALTIME`), used in `analyze_recession_signals.py`.
- **Robert J. Shiller** — CAPE / "CAPE 10" cyclically-adjusted P/E (Yale online dataset),
  basis of `data/processed/shiller_cape.csv` and the equity-risk-premium calculation.

---

## Status legend
- **[verify]** = recent, fast-moving, or reconstructed from memory; confirm bibliographic
  details and any quoted figures against the primary source before publication.
- Entries without a flag are established works with stable citations, but page/edition
  details should still be checked when formally cited.
