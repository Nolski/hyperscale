# Cross-cutting synthesis — the AI investment cycle and the autocolonial churn

*Working synthesis of the empirical findings (Q1–Q3) against the paper's
argument. Compiled 2026-05-15. Every figure here is traceable to a dataset in
`data/processed/` and a provenance entry in `notes/provenance.md`; the headline
numbers are collected in `output/synthesis_indicators.csv` and the integrating
figure is `output/fig_synthesis_dashboard.png`.*

This memo connects three empirical strands to the paper's three claims. It is
deliberate about where the data **supports** the argument and where it **cannot
reach** it — the second list matters as much as the first.

---

## 1. The investment cycle is real, macro-scale, and extraordinarily concentrated

Seven hyperscalers spent **$424B** on capital investment in 2025 (cash capex +
finance leases), up from roughly $20B a decade earlier and nearly double the 2024
figure. That single year is:

- **1.4%** of US GDP,
- **~10%** of *all* US private nonresidential fixed investment,
- **30.7%** of *all* US investment in IT equipment and software.

The paper frames AI as "hyperscaling" — an investment cycle, not merely a
technology. The capital accounts bear this out literally: a discrete, steep surge
in fixed-capital formation, concentrated in seven firms that now command close to
a third of the economy's information-technology investment. This is the
empirical content of "hyperscaling": the prefix is a description of the capital
intensity, and the concentration is its political-economic signature. Around the
spine sit a **$259B** global venture flow into AI firms (the financing layer) and
**$405B** of AI-chip revenue (the supply mirror) — separate accounts, not
additive, but each confirming the same concentration.

## 2. The forward bet outruns the revenue — which is where the "backstop" thesis lives

The projection work puts cumulative 2026–2030 capital investment for the seven US
hyperscalers at **$2.8T–$6.8T** (independent estimate, mid case $4.6T); the
global, all-operator third-party forecasts run **$6.7T** (McKinsey, data-center
capex) to **$7.6T** (Goldman, AI capex incl. chips and power).

The paper's provocative claim — "why is this bubble different? it is geopolitical
… the state has infinite money … valuations don't matter" — is not something the
data can *prove*. What the data can do is **size the gap the backstop thesis
points at**. Bain's finding (carried in the forecast catalogue) is that funding
this path needs roughly **$2T/yr of new revenue by 2030**, against an estimated
**~$800B funding shortfall**; Goldman itself flags its numbers as "baseline
estimates, extremely sensitive." A forward commitment of multiple trillions is
being made against a revenue base that, on these sources' own arithmetic, does not
yet exist. That structural gap — committed capex vs. revenue to service it — is
the empirically loadable core of the "geopolitically-backstopped cycle" argument.
The *backstop* itself (intent, guarantee, the state's role) is a claim the
financing data here cannot adjudicate; see §4.

## 3. The churn: the cycle's costs are displaced onto energy and labour

The paper's "autocolonial churn" names a dispossession turned inward — extraction
whose targets are domestic. Two cost systems measured here are consistent with
that framing, and notably **every cost series is a US-domestic one**.

**Energy.** US electricity demand was flat for thirteen years (−0.1%/yr,
2007–2020); it is now rising (+1.8%/yr, 2020–2025). Data centers were **4.4%** of
US electricity in 2023 and are projected at **9–17%** by 2030. Over 2001–2025
residential electricity prices **doubled** (8.6¢ → 17.3¢/kWh, nominal). The load
growth is corporate; a rising share of the bill is borne by households. The data
shows the *coincidence* of surging corporate load and rising household prices —
it does not by itself establish that the former *causes* the latter (see §4) —
but the distributional shape (private capital formation, socialised grid cost) is
exactly the "churn" the paper theorises.

**Labour.** The average US job has **~32%** of its tasks LLM-exposed
(employment-weighted); **23%** of employment sits in high-exposure occupations.
Crucially, exposure **rises with wage** — bottom wage decile ~0.20, deciles 7–10
around 0.42–0.50. Earlier automation waves hit manual, lower-wage work; this one
concentrates on cognitive, linguistic, white-collar tasks. The most-exposed large
occupations — customer-service representatives, sales representatives,
secretaries and administrative assistants — are the white-collar core, and they
are precisely the roles the paper's introduction flags. This is the labour-market
shadow of the paper's central claim about the **dispossession of cultural capital
(language, art, music, code)**: the tasks being absorbed are linguistic and
interpretive. "Language is leaving us" has a measurable occupational footprint.

**Capital allocation** is itself a third site of churn: directing ~31% of US IT
investment into seven firms' data centers reallocates the economy's investable
surplus toward the buildout — a crowding effect that the GDP-share figures make
visible.

## 4. What the data does NOT show — load-bearing caveats

The argument is strengthened, not weakened, by stating these plainly:

- **No clean AI/non-AI split.** Filings do not disaggregate AI capex; the $424B
  includes non-AI cloud. "AI investment" here is a scoped proxy, not a clean
  measure.
- **The buildout is larger and more opaque than measured.** Cash capex + finance
  leases still excludes operating-lease- and SPV/JV-financed capacity. The
  financing layer (private credit, off-balance-sheet vehicles) is not captured —
  and it is exactly where the "backstop" would operate.
- **The backstop is a thesis, not a finding.** The data sizes the revenue gap; it
  cannot show state intent, an implicit guarantee, or whether demand will
  materialise. Model collapse and demand realisation are unmeasured here.
- **Exposure is not displacement.** The Eloundou β measures task *exposure*, not
  job loss. The labour data shows what is exposed, not what has been automated;
  the paper should not let the two slide together. It is also *one* methodology —
  Anthropic's Economic Index and Frey & Osborne would bracket it.
- **Electricity-price causation is not established.** Prices rose for many
  reasons; attributing the rise to data centers needs the node-level / Dallas Fed
  work, not these aggregates.
- **Scope is US-primary.** The geopolitical-concentration strand — compute and
  capital concentrated across borders — is thinner here than the domestic strands.

## 5. Open questions / next data work

1. **Bracket the labour estimate** — add the Anthropic Economic Index (and
   Frey-Osborne) as second/third exposure methods; present a range.
2. **The financing layer** — pursue private-credit and SPV/JV disclosures; this
   is the missing evidence for or against the backstop thesis.
3. **Electricity-price attribution** — node-level / Dallas Fed analysis to move
   from coincidence to causation.
4. **Demand realisation** — track revenue against the forward bet; the gap in §2
   is the live empirical question.
5. **International concentration** — compute geography (chips, data-center siting)
   to firm up the geopolitical strand.

---

## 6. The Two Markets — why bonds "look like collapse" while equities don't

*Added 2026-05-29. This strand (methodology: `notes/methodology_financial_markets.md`)
addresses a question that sits one layer beneath the backstop thesis in §2: if the
buildout is a fiscally/geopolitically backstopped bet, what are the bond, credit and
equity markets actually pricing about it? Headline numbers live in
`output/{curve_decomposition, recession_signals, equity_concentration, ai_financing,
cross_asset}.csv`.*

**The apparent contradiction is mostly a category error.** "Bonds signal collapse"
conflates two opposite signals. An *inverted curve* prices a growth collapse; a rising
*long-end yield with a positive term premium* prices fiscal supply and a higher neutral
rate. As of 2026-05 the collapse battery is **benign** — 10y−3mo +0.76 (un-inverted),
12-mo recession prob 1.8%, Sahm 0.13, IG OAS 0.73% (0.6th percentile of its history),
HY OAS 2.72% (8.8th), VIX 15.7, NFCI/STLFSI loose. What is elevated is the **10y term
premium (+0.83, ACM)** — positive again after turning deeply negative in 2016–2021. The
10y decomposes cleanly into real 2.09% + breakeven 2.39%, and into a 3.65% expectations
component + the 0.83% term premium. The long end is heavy for **duration-supply**
reasons, not because a recession is being priced.

**The curve "cried wolf," on the record.** The 2022 inversion (T10Y2Y) ran **782 days —
the longest in the FRED series since 1976 — and un-inverted with no recession**, against
a historical median lead of ~18 months. Small-N (≈7 post-war recessions): suggestive,
not a law.

**The equity calm is partly compositional.** Since 2015 the cap-weighted S&P 500
(+344%) has beaten the equal-weighted index (+216%) by **1.41×** — gains concentrated in
the largest (AI) names, not the median stock. The Mag-7 are ~$23.9T of market cap
(~35% of the index by weight, external ref). And the **cyclically-adjusted equity risk
premium is ~0.5%** (CAPE earnings yield 2.6% − real 10y 2.1%): investors are paid almost
nothing extra to hold stocks over inflation-protected Treasuries. That is the quantified
form of "this doesn't seem rational."

**The hinge to the project thesis: the buildout is starting to bond-finance itself.**
The seven firms still out-earn their capex in aggregate (operating cash flow $683B vs
capex $395B, 1.73× coverage), but the *marginal* AI builders do not — **Oracle 0.98×,
CoreWeave 0.30×** — and the group reported **$77B of new long-term-debt issuance** in the
latest year (Meta $29.9B, Oracle $19.5B, Amazon $15.7B, CoreWeave $11.8B). That issuance
adds duration the market must absorb, the same supply pressure that keeps the term
premium positive. So the buoyant AI equities and the heavy long end are **the same
story from two ends**: an enormous, concentrated, increasingly debt-financed bet whose
financing cost is showing up in the term structure.

**What this strand cannot settle (carry the §4 discipline):**
- The term premium is **model-estimated**; at +0.83 it is elevated vs the post-GFC era
  but only ~54th percentile of its full 1990+ history — *normalizing*, not extreme.
- **One credit gauge dissents:** CCC OAS sits at the **72nd percentile** even as IG/HY
  are at record-low percentiles — the lowest-quality borrowers *are* showing strain.
  Don't over-tell the "everything is calm" story.
- **Financing → term-premium causation is a thesis, not a measurement** — hyperscaler
  issuance is small next to total Treasury supply; the claim is directional.
- Equity concentration/ERP lean on **Tier-2 inputs** (Yahoo prices, approximate Shiller
  CAPE); bond vol is a **realized-vol proxy** for the paywalled MOVE. Read trends and
  rank-orderings, not second decimals.

This connects back to §2's backstop thesis: the "backstop bill" may be becoming visible
not as an explicit guarantee but as **term premium and corporate issuance** — the price
the bond market charges to fund a bet it cannot yet see the revenue for.

---

## 7. The hardware substrate — what an AI chip is really worth, and who pays for it

*Added 2026-05-29. This strand (methodology: `notes/methodology_hardware_economics.md`;
bibliography: `notes/bibliography_hardware_economics.md`) goes beneath the capex numbers to
the unit economics of the accelerators themselves — how energy, efficiency, supply-chain
pricing power, and a collapsing output price jointly set a GPU's value and its true useful
life. Five models; headline numbers in `output/{gpu_tco, economic_obsolescence,
endogenous_price, cost_stack, token_economics, jevons_rebound}.csv`. All inputs are Tier-2
(vendor specs, analyst BOM estimates, API prices) — read proportions and directions, not
second decimals.*

**A GPU dies economically, not physically — and at US power, energy isn't what kills it.**
A chip should be retired when running it costs more per unit of work than a newer, more
efficient one. At ~9¢/kWh US industrial power, energy is only ~8–17% of a chip's total cost
of ownership, so an old chip's energy-only cost stays *below* a new chip's all-in cost: it's
rational to keep running it. Only ancient silicon strands at reachable prices (V100 ≈14¢/kWh,
A100 ≈32¢, but H100 ≈$1.00/kWh — implausible). So energy *cost* does **not** condemn the
6-year accounting life for modern hardware. The real refresh pressure is **power-capacity
opportunity cost** — compute delivered per scarce megawatt rose ~5.4× from V100 to B200 — an
opportunity cost, not a cash cost, which is why it doesn't translate cleanly into depreciation.

**Energy "looks cheap" only because the chip price is mostly Nvidia's margin.** Decomposing an
H100's full deployed cost: ~**60% vendor gross margin**, ~24% facility + cooling, ~8% lifetime
electricity, ~8% actual manufacturing (and HBM memory is ~41% of *that* — the bottleneck is
memory, not the logic die). NVIDIA's ~71% blended gross margin (SEC EDGAR) is the load-bearing
wall: it dwarfs energy, which is the whole reason the power bill looks like a rounding error.
Note that facility + cooling alone (~24%) exceeds the energy bill — the cooling/water build-out
is a first-class cost, not a PUE footnote.

**Inference is wildly profitable at the chip level — which is precisely why prices can keep
collapsing.** An H100's all-in cost is ~$0.24 per million tokens against a frontier API output
price of ~$15 (≈64×); it repays its margin-inflated capex in roughly a year, and the break-even
price is ~$0.32/Mtok — about 50× below list. So the GPU-level bet is *not* the fragile part.
The risks sit elsewhere: most capex funds **training** (no per-token revenue), utilisation may
not materialise, and the **price war** drags the sale price toward cost. The enormous cushion is
itself the mechanism that lets token prices fall ~70%/yr.

**The whole edifice rests on the margin holding — and that is what competition threatens.** If
Chinese competition (Huawei et al., thin-margin and fast-iterating) drags the frontier chip price
from ~$35k toward ~$10k, the stranding thresholds collapse proportionally: an A100 would strand at
~9¢/kWh — *today's US price* — and economic life would shorten toward the ~2-year generational
cadence, **reopening the depreciation/earnings-quality question** (it links to the financial-markets
thread: the debt-funded buildout rests on profits that a too-long asset life may flatter).
But the path is mediated: Nvidia's CUDA/interconnect moat, export-control market bifurcation, an
HBM supply floor, and — crucially — the **efficiency gap** (cheap Chinese chips are power-hungry,
so they win where power is cheap and abundant, i.e. China, and lose where power is the binding
constraint, i.e. the US grid). Price, energy, efficiency, and geopolitics are one system.

**Efficiency will not bound the energy footprint — it accelerates it.** Frontier perf/watt
improves ~23%/yr, but compute demand must grow ~40–57%/yr to reach LBNL's projected data-center
energy — about twice the efficiency rate. Total energy therefore *rises* (the Jevons paradox):
efficiency "saved" ~1,084 TWh by 2028, yet energy still roughly **tripled** from its 2023 base.
Cheaper, more efficient compute induces more of it. Efficiency is an accelerant of the grid
problem, not a brake.

**The integrating point — and the tie to the paper's thesis.** Energy is *not* the binding
constraint on the **firm's** economics (it's a small slice next to a ~60% margin), but it *is* the
binding constraint on the **system** — grid capacity, Jevons-driven demand, and the price rises and
water draw that land on the public. That asymmetry is the autocolonial churn in hardware form: the
**margin is privatised** (captured by a concentrated Nvidia/TSMC/HBM supply chain) while the
**energy, grid, and water costs are socialised** (externalised to ratepayers and local
environments). The supply-chain markup is simultaneously what makes the buildout look cheap to run,
what makes inference look profitable, and the single point of failure competition is aimed at — and
the global energy intensity of the whole enterprise turns on *where* the compute is built and under
*which* design philosophy.

**What this strand cannot settle:**
- **Physical longevity is unknown** — the models assume *economic*, not failure, retirement; if AI
  GPUs genuinely last 6 years the accounting life is defensible.
- **Vendor FLOPS are marketing** (dense vs sparse), and peak ≠ realised throughput; the token model's
  FLOP→tokens conversion is a compute-bound proxy (MLPerf would refine it) and is sensitive to model
  size and utilisation.
- **BOM, China specs, token prices, and cloud rents are Tier-2 estimates**; facility $/MW and the
  Jevons compute-growth rate are inferred/assumed, not measured.
- **Causation stays contested**: the demand→electricity-price link carries the IER null alongside the
  Dallas Fed model; the Jevons "induced demand" claim is interpretation of an identity, not proof.
- **Token revenue is best-case** (all output at list price, high utilisation) — an upper bound.
