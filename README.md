# price-in

Fetchers for the `market_data_template` sheet.

> **Keep this repository private.** `data/` is no longer tracked, but the
> initial commit contained CME licensed market data, so it remains in git
> history. Publishing this repo would still redistribute it. See
> [Licensing](#licensing) before changing visibility or sharing a clone.

## Daily report — everything, in order

**One command runs it all** (after the manual inputs in step 1):

```bash
python3 make_report.py                 # collect -> sheet -> report in English + Persian, saved
python3 make_report.py --lang fa       # Persian report only
python3 make_report.py --offline       # no fetching: rebuild from disk, then report
python3 make_report.py --no-story      # no Claude API call: printed brief.py only, nothing saved
```

The saved report is `story.py`'s output — it takes `brief.py`'s facts and
writes them as a readable story — one file per language:
`reports/<report date>/brief_en.txt` and `brief_fa.txt`. Each run makes one
Claude API call per language (needs `ANTHROPIC_API_KEY`). `brief.py` still runs
first and is printed as a quick check, not saved. The folder is named for the
date the report covers (the newest sheet date), which can lag today. `--pair`
output is printed only, never saved. If a report file already exists and the
new one differs (e.g. you edited it by hand), the old version is kept as
`<name>.<time>.bak` first. `reports/` is gitignored.

**To read them:** open `reports/index.html` in a browser — one entry per day.
`make_report.py` rebuilds it after each run; after editing a report by hand,
run `python3 reports_html.py` and reload the page.

A failing step doesn't stop the chain; the summary at the end lists what
failed. The steps it runs are below — run them by hand to debug one.

Run from the project root. Each step writes the file the next one reads.

### 0. One-time setup

| Need | For | How |
|---|---|---|
| Python 3.11, stdlib only | every script | nothing to install |
| Camoufox | `ff_calendar.py` (forexfactory 403s plain HTTP) | `pip install camoufox[geoip] && python3 -m camoufox fetch` |
| `.env` with `ANTHROPIC_API_KEY=...` | `story.py` | file in the project root (gitignored) |
| `.env` with `TG_TOKEN`, `TG_CHAT` | `run_daily.py` alerts only | same file |

QuikStrike needs no credentials: `quikstrike.py` provisions its own session.
Set `QS_INSID` / `QS_QSID` only to reuse a browser session you already have.

### 1. Manual input (by hand, every day — CME forbids scripted access)

| File | What to put there |
|---|---|
| `data/manual/fed/FedMeetingHistory_<YYYYMMDD>.csv` | cmegroup.com → FedWatch → Historical → Downloads → **All upcoming meetings**. Save as downloaded, don't edit. |

The ECB is fully automatic (ICE Euribor futures) — no manual input. If the
FedWatch file is missing or stale, `rates.py` says so on stderr, leaves those cells
empty and exits non-zero. Everything else still runs.

### 2. Collect

```bash
python3 rates.py                                    # -> data/rates.csv        (Layer 1: BoC/BoE/ECB fetched, Fed from step 1)
python3 quikstrike.py --all-measures --outdir data  # -> data/cvol.csv, skew.csv, atm.csv, ... (Layer 2)
python3 cot.py                                      # -> data/cot.csv          (Layer 3, weekly)
python3 prices.py                                   # -> data/prices.csv
python3 ff_calendar.py                              # -> data/calendar.csv     (needs Camoufox)
```

### 3. Assemble the sheet

```bash
python3 build_sheet.py --days 30                    # -> market_data.csv
```

The sheet has one row per CVOL date, so **run `quikstrike.py` first**: if
`data/cvol.csv` is stale, the sheet stops at that date and newer rates never
reach it.

### 4. Report

```bash
python3 brief.py                                    # rules-only brief, no API call
python3 story.py --lang en                          # plain-language story (Claude API)
python3 story.py --lang fa                          # same, in Persian
```

Both default to the latest sheet date and all pairs; `--date YYYY-MM-DD` and
`--pair eurusd` narrow them. `brief_explain.py` is the fully explained variant
of `brief.py`.

### Offline rebuild

Re-run steps 3–4 from what is already on disk: `python3 rates.py --no-fetch`
rebuilds `data/rates.csv` from the archive, then `build_sheet.py` and the
report as above. `run_daily.py` runs step 2 plus the sheet on the VPS (see
[Deployment](#deployment)); the report steps are run by hand.

### Known gap

Layer 1 sources publish with a lag (BoC settlement and FedWatch history end 1–2
days before today; the BoE curve ~2). The brief reads today's sheet row only,
so on most days the Fed/BoC/BoE rate lines read "missing" even though
yesterday's reading exists. Only the manual ECB input, dated today, lines up.

## What each script does

**`quikstrike.py`** — pulls CVOL index data for 36 products across 7 measures
(cvol, skew, atm, convexity, skewratio, upvar, downvar). Writes one long-format
CSV per measure: `ticker,series,date,value`.

<<<<<<< Updated upstream
**`rates.py`** — pulls market-implied policy-rate paths from
[rateprobability.com](https://rateprobability.com/) for 6 central banks (fed,
ecb, boe, boj, boc, rba). Public JSON API, no auth. Writes
`data/rates.csv` as `bank,as_of,meeting,implied_rate,prob_move_pct,is_cut,num_moves,change_bps,horizon`.
=======
**`rates.py`** — market-implied policy-rate paths from official sources (see
`rates-sources.md`): BoC (Valet CORRA + Montréal Exchange COA/CRA) and BoE
(SONIA + BoE OIS forward curve) and ECB (deposit rate + ICE Euribor futures)
fully automatic; Fed (FedWatch buckets + NY Fed target band) with expectations
entered by hand in `data/manual/fed/`, because CME's terms forbid scripted access. One
module per bank in `banks/`. Writes `data/rates.csv` as
`bank,as_of,as_of_time,meeting,implied_rate,prob_move_pct,is_cut,num_moves,change_bps,horizon`.
>>>>>>> Stashed changes

**`build_sheet.py`** — pivots those into the wide template layout, one row per
date, computing `_chg` as the day-over-day difference per ticker.

## Run `rates.py` daily

The rate API is a **snapshot, not a time series**. Each response carries today
plus exactly four backdated snapshots (1w/3w/6w/10w ago), and there is no way to
request an arbitrary date — `?date=`/`?as_of=` are ignored and other paths fall
through to the SPA shell.

So history is *accumulated*, not fetched. Every run archives the raw JSON to
`data/raw/<bank>/<as_of>.json` and rebuilds the CSV from every snapshot ever
collected. The first run seeds ~10 weeks of sparse history (5 dates per bank);
coverage becomes dense only for days you actually run it. Miss a day and that
day is gone permanently.

The archive keeps every field the API returns, not just the ones the sheet uses,
so new columns can be backfilled later from snapshots already on disk —
`python3 rates.py --no-fetch` rebuilds the CSV without hitting the network.

## Column coverage

| Columns | Status |
|---|---|
| `CAVL`, `EUVL`, `S1VL` + `_chg` + `_skew` | done — QuikStrike |
<<<<<<< Updated upstream
| `fed_*`, `ecb_*`, `boc_*` | done — rateprobability, but **sparse** until daily runs accumulate |
=======
| `boc_*` | done — Montréal Exchange, automatic |
| `ecb_*` | done — ICE Euribor, automatic (bps-only: a 3-month window spans ~2 decisions) |
| `fed_*` | done — needs the daily FedWatch download in `data/manual/fed/` |
| `boc_path_12m` | done — added as the last column |
>>>>>>> Stashed changes
| `dxy`, `usdcad`, `eurusd`, `wti` | **not built** — needs a market data source |

Unbuilt columns are emitted empty so the sheet keeps the template's shape. To
add more vol products, extend `VOL_TICKERS` in `build_sheet.py` — any of the 36
tickers in `data/cvol.csv` works. To add banks, extend `CB_COLS`; `boe`, `boj`
and `rba` are already being fetched and archived.

### Reading the central bank columns

* `<bank>_odds`/`_odds_pct` — signed probability of a move at the **next**
  meeting (negative = cut). `rates.py` restores the sign; the API reports
  magnitude plus a separate `prob_is_cut` flag.
* `<bank>_bps` — implied change at the next meeting.
* `<bank>_path_12m` — cumulative implied change at the meeting nearest 12 months
  out (rejected if no meeting falls within 60 days of that mark).

Note that a negative `_odds` can sit alongside a positive `_path_12m`: the odds
describe one meeting, the path is cumulative from today.

`rbnz`, `snb` and `srb` exist on the API but return
`401 "Pro subscription required"`, so they are excluded by default.

## Notes on the endpoint

The chart data is not served by a JSON API. It is embedded in the ASP.NET
partial-postback response as the `JSONSettings` property of the page's
Highcharts component, so the fetcher replays the postback and extracts it.

Two consequences worth remembering:

* **The dashboard is stateful.** The selected measure and product set persist
  server-side per session. Every request sets them explicitly, but concurrent
  requests against one `qsid` will interfere — keep pulls sequential.
* **Ticker suffixes encode the measure.** The same product is `CAVL` under
  CVOL and `CASK` under skew (`VY`/`SY` for Treasuries). `build_sheet.py`
  matches on the stem, via `root()`.

## Deployment

`.github/workflows/deploy.yml` deploys to the VPS on every push to `master`
(and via the manual "Run workflow" button). It syntax-checks the fetchers, then
SSHes in and does `git fetch` + `git reset --hard origin/master`.

Required repo secrets (Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `VPS_HOST` | hostname or IP |
| `VPS_USER` | ssh user |
| `VPS_SSH_KEY` | **private** key, full PEM including header/footer lines |
| `VPS_PATH` | path to the checkout, e.g. `/srv/price-in` |
| `VPS_PORT` | optional, defaults to 22 |

The VPS needs a clone at `VPS_PATH` before the first deploy:

```bash
git clone https://github.com/fantom15/price-in.git /srv/price-in
```

Note the deploy uses `reset --hard`: the VPS is a deploy target, not somewhere
to edit code — local changes there are discarded. `data/` is gitignored, so the
accumulated archive is never touched.

## Data on the VPS

`data/` and `market_data.csv` are **not tracked in git** — the fetched data
lives on the VPS only, and each machine keeps its own.

This matters most for `data/raw/`. Those rateprobability snapshots are
irreplaceable: the API exposes only today plus 1w/3w/6w/10w ago, so a day
without a run is a permanent gap that cannot be backfilled. Nothing in this
repo backs that directory up — arrange that on the VPS.

Deploying does not run anything. Scheduling the daily fetch on the VPS is a
separate step, still to be set up.

## Licensing

The CSVs under `data/` are **CME licensed market data**. They are gitignored
now, but the initial commit included them, so they persist in git history —
which is why this repo should stay **private**. Making it public, or sharing a
clone, redistributes licensed data. (Scrubbing history with `git filter-repo`
would be the fix if that ever needs to change.)

If this ever feeds something redistributed or commercial, pull from
[CME DataMine](https://datamine.cmegroup.com/#/datasets/volindx) instead, which
serves the same series under proper licensing.

`data/raw/` (rateprobability snapshots) has no such restriction — that API is
public and unauthenticated.
