# price-in

Fetchers for the `market_data_template` sheet.

> **Keep this repository private.** `data/` is no longer tracked, but the
> initial commit contained CME licensed market data, so it remains in git
> history. Publishing this repo would still redistribute it. See
> [Licensing](#licensing) before changing visibility or sharing a clone.

## Setup

Both credentials come from the QuikStrike dashboard URL and **expire with the
browser session**. Reopen the dashboard and copy fresh ones when a fetch fails.

```
https://cmegroup-tools.quikstrike.net/User/QuikStrikeView.aspx?...&insid=<INSID>&qsid=<QSID>
                                                                          ^^^^^^^       ^^^^^^
export QS_INSID=<insid from the url>
export QS_QSID=<qsid from the url>
```

## Usage

```bash
python3 rates.py                                     # run DAILY - see below
python3 quikstrike.py --all-measures --outdir data   # refresh all 7 measures
python3 build_sheet.py --days 30 --out market_data.csv
```

`build_sheet.py` also takes `--start` / `--end` for an explicit date window.
`rates.py` needs no credentials; `quikstrike.py` needs the env vars above.

## What each script does

**`quikstrike.py`** — pulls CVOL index data for 36 products across 7 measures
(cvol, skew, atm, convexity, skewratio, upvar, downvar). Writes one long-format
CSV per measure: `ticker,series,date,value`.

**`rates.py`** — pulls market-implied policy-rate paths from
[rateprobability.com](https://rateprobability.com/) for 6 central banks (fed,
ecb, boe, boj, boc, rba). Public JSON API, no auth. Writes
`data/rates.csv` as `bank,as_of,meeting,implied_rate,prob_move_pct,is_cut,num_moves,change_bps,horizon`.

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
| `fed_*`, `ecb_*`, `boc_*` | done — rateprobability, but **sparse** until daily runs accumulate |
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

## What data is tracked

| Path | Tracked | Why |
|---|---|---|
| `data/raw/` | yes | Irreplaceable — rateprobability exposes only 5 dates, so a missed day is a permanent gap. Committing it is the backup. |
| `data/cot.csv` | yes | Small, and public CFTC data. Also re-fetchable via `--backfill`. |
| `data/*.csv` (cvol, skew, …) | no | ~22MB of CME licensed data, rewritten in full on every fetch. Re-fetchable from QuikStrike. |
| `market_data.csv`, `logs/` | no | Derived output and runtime noise. |

Because `data/raw/` is tracked, the VPS deploy (`git reset --hard`) will
overwrite it with whatever is on origin. The VPS is the machine that runs the
daily fetch, so **commit and push from the VPS**, or its snapshots are lost on
the next deploy.

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
