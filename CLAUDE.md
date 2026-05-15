# CLAUDE.md — Hyperscaling Research

## Project

Political-economy / critical-theory research project: **"Hyperscaling, AI, and the
Autocolonial Churn."** The working paper (`Theorizing Hyperscaling and Colonialism.odt`)
theorizes how the form, function, and political economy of AI drive dispossession of
cultural capital (language, art, music, code), and frames the AI buildout as a
geopolitically-backstopped investment cycle.

Claude is used here for two things:
1. **Data acquisition** — pulling economic data on the US tech/AI sector, the energy
   sector, data centers, and labor/automation exposure.
2. **Analysis** — writing scripts that process, analyze, and visualize that downloaded data.

The empirical questions the data needs to support: scale of hyperscaler capex; data-center
electricity demand and its share of grid load; the AI investment cycle vs. historical
bubbles; occupational automation exposure; geopolitical concentration of compute.

## Working principles for data work

- **Always record provenance.** For every dataset, note the source, the exact URL or API
  call, the retrieval date, and the data *vintage* (release date / reference period).
  Macro series get revised — a number is only meaningful with its vintage.
- **Save raw downloads unmodified** in `data/raw/`. Never edit raw files; transform into
  `data/processed/` via a script so the pipeline is reproducible.
- **Prefer primary sources** (statistical agencies, company filings) over secondary
  reporting. Use journalism and think-tank pieces for framing, not as the data of record.
- **Cite the methodology**, not just the number — especially for projections (e.g.
  data-center demand forecasts vary wildly by assumption) and automation-risk estimates.
- **Distinguish nominal vs. real**, and note the base year / deflator used.
- When a source paywalls or rate-limits, say so rather than substituting a weaker number.

## MCP data connectors (configured)

Two MCP servers are wired up in `.mcp.json` (Docker-based, version-pinned, audited):

- **`fred`** — FRED time series via `stefanoamorelli/fred-mcp-server`, pinned by image
  digest (`sha256:35d1900d…`, the Aug 2025 `latest` build; the repo only publishes
  `:latest`, so a digest is the only immutable pin). Tools: `fred_browse`, `fred_search`,
  `fred_get_series`. Prefer this over hand-rolled FRED API calls.
- **`sec-edgar`** — SEC EDGAR filings via `stefanoamorelli/sec-edgar-mcp:1.0.8`. Structured
  financial statements, filings, insider data. Use for hyperscaler capex extraction.

Requirements: `podman` must be available (this environment uses podman, not docker, with
fully-qualified `docker.io/` image names). `FRED_API_KEY` and `SEC_EDGAR_USER_AGENT` come
from `.claude/settings.local.json` (see API keys section below). To update a pin, re-audit
the new release first, then bump the digest/tag in `.mcp.json`. EIA and Census still use
direct API scripts (no MCP server).

## Primary data sources

### US macro & sector economics
- **FRED** (Federal Reserve, St. Louis) — `fred.stlouisfed.org`. Best first stop. Free
  API key. GDP, private fixed investment, sector output, interest rates. Good for
  information-processing equipment & software investment series.
- **BEA** — Bureau of Economic Analysis. GDP-by-industry, fixed-asset tables, private
  fixed investment by type. Free API key.
- **BLS** — Bureau of Labor Statistics. Employment, OEWS occupational employment & wages
  (key for automation-exposure analysis), productivity, PPI. Free API (registration).
- **Census Bureau** — Annual Capital Expenditures Survey (ACES), Economic Census,
  Business Dynamics Statistics, monthly Construction Spending (data-center construction).
  Free API key.
- **SEC EDGAR** — 10-K/10-Q filings for hyperscaler capex and AI disclosures (Microsoft,
  Alphabet, Amazon, Meta, Nvidia, Oracle, CoreWeave). Full-text search + `data.sec.gov`
  JSON API (`companyfacts`, `companyconcept`). No key needed; set a `User-Agent`.

### Energy & data centers
- **EIA** — US Energy Information Administration. `eia.gov`. Free API key. Electricity
  generation, consumption, prices; forms EIA-861 (utility sales) and EIA-923.
- **LBNL** — Lawrence Berkeley National Lab. The canonical *US Data Center Energy Usage*
  reports (2024 report is the reference for DC electricity share of US load).
- **IEA** — International Energy Agency. *Electricity* reports and data-center / AI energy
  analyses (international comparison; some content paywalled).
- **FERC** + **grid operators** (PJM, ERCOT, MISO, SPP) — interconnection queues and load
  forecasts; large-load / data-center interconnection requests are a leading indicator.

### AI & semiconductor sector
- **Stanford HAI AI Index** — annual report with downloadable underlying data.
- **Epoch AI** — `epochai.org`. Compute trends, training-run costs, model database.
- **SIA** — Semiconductor Industry Association; **BIS** (Commerce) for export controls.
- **OECD.AI** — policy observatory and cross-country indicators.

### Labor & automation
- **BLS OEWS** for occupational structure; pair with automation-exposure methodologies
  (Frey & Osborne; Webb; recent LLM-exposure papers) — cite the method explicitly.
- **WEF Future of Jobs** for survey-based projections (framing, not ground truth).

### International / geopolitical
- **World Bank** and **IMF** APIs for cross-country macro and investment data.

## Analysis scripts

- Language: **Python 3**. Use `pandas` for tabular work, `requests` for API pulls,
  `matplotlib` for figures. Add deps to `requirements.txt` as introduced.
- One script = one clear step. Keep acquisition (`scripts/fetch_*.py`) separate from
  analysis (`scripts/analyze_*.py`) so re-running analysis doesn't re-hit APIs.
- Scripts must be re-runnable: read from `data/raw/`, write to `data/processed/` or
  `output/`, and not depend on manual steps.
- Store API keys in a `.env` file (gitignored); never hardcode them in scripts.
- Label every figure/table with source and retrieval date.

## Suggested layout

```
data/raw/         # untouched downloads, named with source + date
data/processed/   # cleaned, script-generated derivatives
scripts/          # fetch_*.py (acquisition), analyze_*.py (analysis)
output/           # figures, tables, exports for the paper
notes/            # source notes, methodology notes, data provenance log
```

## API keys

All keys are free (FRED, BEA, BLS, EIA, Census; World Bank / IMF / SEC EDGAR need none).
They live in the `env` block of `.claude/settings.local.json` — the directory-local,
non-shared Claude Code settings file (`chmod 600`). Claude Code loads these into the
session environment automatically when launched in this directory: that resolves the
`${FRED_API_KEY}` references in `.mcp.json`, and propagates the keys to fetch scripts run
via the Bash tool (they read from `os.environ`). No `source` step is needed.

To add or rotate a key, edit `.claude/settings.local.json` and restart Claude Code.
Never commit this file; if the dir becomes a git repo, add it to `.gitignore`.
