# Layer 1 Data Sources — Reference
### Every source for policy-rate expectations, with URL, format, formula and gotchas.
*Compiled 2026-09-25, replacing rateprobability.com (blocked by anti-bot). This is the spec for the `rates.py` rebuild.*
*Corrected 2026-09-25 against live downloads while implementing it — see "Corrections" at the end.*

---

## Why this exists

rateprobability.com was a single point of failure: one third-party site translating
futures prices into odds. It blocked automated access and Layer 1 went dark for six
weeks.

The replacement uses **official sources only** — central banks and exchanges. Most
publish deliberately machine-readable data. The trade-off: we compute the odds
ourselves instead of reading someone's translation. That is an upgrade, not a
workaround — we now know exactly how every number is produced.

**Core formula (all banks):**
```
implied_rate  = 100 − futures_price
change_bps    = (implied_rate − current_policy_rate) × 100
odds_pct      = change_bps / 25 × 100
```
Record `change_bps` as the primary datum; `odds_pct` is a step-dependent
interpretation (Rule 5). A magnitude above 100% means more than one 25bp step is
priced — not an error.

---

## Automation status at a glance

| Bank | Current rate | Expectations | Automatable |
|---|---|---|---|
| Fed | NY Fed EFFR api ✅ (target band) | FedWatch | ⚠️ expectations manual (see notes) |
| ECB | ECB api ✅ (deposit facility rate) | ICE Euribor futures ✅ | ✅ full |
| BoC | BoC Valet ✅ | Montréal CSV ✅ | ✅ full |
| BoE | BoE database ✅ | BoE OIS zip ✅ | ✅ full |

**CME (Fed expectations) must stay manual.** Their Data Terms of Use prohibit
scripted access; the endpoints block non-browser requests. Download the FedWatch
file once a day, or use DataMine (paid, licensed) if full automation is required
later. The ECB no longer uses CME at all (see section 2).

---

## 1. Fed

### Current rate + expectations — CME FedWatch
- **Page:** `cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html`
- **History download:** FedWatch → Historical → **Downloads** → *"All upcoming meetings"*
  (blue icon) gives every future meeting in one CSV. Individual meeting files
  (green icons) are also available.
- **Export URL pattern (session-bound, expires):**
  `cmegroup-tools.quikstrike.net/User/Export/FedWatch/AllMeetings.aspx?insid=<ID>&qsid=<GUID>`
- **Format (as actually exported, `FedMeetingHistory_<YYYYMMDD>.csv`):**
  ```
  ,History for 28 Oct 2026 Fed meeting,,…,History for 9 Dec 2026 Fed meeting,…
  Date,(0-25),(25-50),…,(1525-1550),(0-25),(25-50),…
  9/23/2026,,,…,0.291429,0.708571,…
  ```
  One `Date` column (m/d/yyyy), then one block of bucket columns **per upcoming
  meeting** — the bucket list restarts at `(0-25)` for each block and block
  lengths differ. One row per trading day: a single download carries ~251 days
  of history for every meeting. Values are decimals (0.925 = 92.5%); empty =
  bucket/meeting not listed that day.
- **Truncation:** the 2026-09-25 export titles 10 meetings but has columns for
  only 9 — the last title (8 Dec 2027) has no data. Skip it.
- **Past meetings are omitted:** history rows only cover meetings still upcoming
  on the download date, so for older dates the first listed meeting is *not*
  the next meeting. Daily downloads fix this going forward.

**Deriving the sheet columns from the bucket distribution:**
```python
CUR = "(375-400)"                      # current target band (after the 2026-09-16 hike)
mid  = lambda b: sum(map(float, b.strip("()").split("-"))) / 2
hold = probs[CUR] * 100                                  # hold %
hike = sum(p for b,p in probs.items() if mid(b) > mid(CUR)) * 100   # fed_odds_pct
bps  = sum(p * (mid(b) - mid(CUR)) for b,p in probs.items())        # fed_bps
```
Verified: 2026-09-15 → hold 6.5%, hike 93.5%, +23.4bp against the band then in
force, (350-375). Matches the site.

### Current target band — NY Fed EFFR api (automated)
- **API:** `https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json?startDate=<YYYY-MM-DD>&endDate=<YYYY-MM-DD>`
- Free, no auth, JSON. `refRates[]`, one record per business day:
  `{"effectiveDate": "2026-09-23", "type": "EFFR", "percentRate": 3.88,
  "targetRateFrom": 3.75, "targetRateTo": 4.00, "volumeInBillions": 101, …}`
- **Use `targetRateFrom`/`targetRateTo`**, not `percentRate` (EFFR itself trades
  inside the band). The band midpoint is `CUR` above — per date, so a year of
  FedWatch history is measured against the band in force on each day.
- **Lag:** EFFR for day D is published on D+1. A decision is public the day it is
  made, so the band for D is the newest record on or before D; the morning after
  a hike the api may not have the new band yet — the next rebuild corrects it.
- The Fed hiked on 2026-09-16: band 3.50–3.75 → 3.75–4.00.

**Gotchas**
- `qsid`/`insid` expire — same pattern as `quikstrike.py` for CVOL.
- The current target band changes after each hike — **derive it from the NY Fed
  api above, don't hard-code it.**
- Scripted access to FedWatch violates CME's Data Terms of Use. Manual download only.

---

## 2. ECB — fully automatable (ICE Euribor futures)

**Replaced 2026-09-25.** The CME €STR serial contracts (ESR) had **zero volume
and no `last` price** on every expiry, and their `priorSettle` predated the
2026-09-16 hike — a stale futures price against a live rate. It priced a
−45.7bp "cut" days after the ECB hiked. Do not go back to them.

### Current rate — ECB deposit facility rate (DFR)
- **API:** `https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?startPeriod=<YYYY-MM-DD>&format=csvdata`
- Daily SDMX csv; read `TIME_PERIOD` / `OBS_VALUE` by name. No auth.
- The value on a date is the rate **in force** that day (a set rate, not a
  fixing — same day counts). Changes on file: 2.00 → 2.25 on 2026-06-17,
  2.25 → **2.50 on 2026-09-16**.
- This replaces the old "€STR + 0.31" constant: €STR (2.44) now sits ~6bp below
  the DFR, not 31bp — that spread was never fixed.

### Expectations — ICE Three-Month Euribor futures
- **All contracts, current prices (one call):**
  `https://www.ice.com/marketdata/api/productguide/charting/contract-data?productId=15275&hubId=17455`
  → JSON array, one object per contract:
  `{"marketId": 8820755, "marketStrip": "Oct26", "endDate": 1793419200000,
  "lastPrice": 97.24, "volume": 11434, "lastTime": "09/25/2026 11:34 AM GMT", "change": 0.036}`
  - `lastPrice` — this market trades (Dec26 ~137k contracts/day).
  - `volume` — real; the **liquidity guard** (below).
  - `lastTime` — source timestamp, GMT; recorded as `as_of_time`.
  - `marketStrip` — the contract month. **`endDate` is just the month end**
    (Oct26 → 31 Oct), not the expiry or the reference period — don't use it.
  - Quarterlies run to Sep31; serial months (Oct/Nov/Jan/Feb) are listed too
    and some are thin (2026-09-25: Jan27 395, Feb27 75).
- **Daily history per contract:**
  `https://www.ice.com/marketdata/api/productguide/charting/data/historical?marketId=<marketId>&historicalSpan=<n>`
  → `{"marketId": …, "bars": [["Fri Jun 26 00:00:00 2026", 97.475], …]}` (daily
  settlements, no volume). Spans tested on 2026-09-25 for Oct26:
  `1` → 65 bars (from 26 Jun), `2` → 119 bars (from 13 Apr), `3` → same as 2,
  `4`/`5` → empty. **Use `2`.** Older contracts return longer histories.
- No auth, no cookies, no special headers.
- **Contract → period:** reference period = 3rd Wednesday of the contract month
  → 3rd Wednesday three months later (`Oct26` = 21 Oct 2026 → 20 Jan 2027).
  `meeting` = period start, like the other futures here.

**Formula:** `implied = 100 − price`; `change_bps = (implied − DFR on as_of) × 100`.

**Liquidity guard:** a contract whose live `volume` is below **300** is skipped,
with a note on stderr — and its history too, since history bars carry no volume
and so can't be liquidity-checked on their own.

**Worked example (2026-09-25 ~12:07 GMT, DFR 2.50):**
| contract | price | implied | vs DFR |
|---|---|---|---|
| Oct26 | 97.240 | 2.760% | +26.0bp |
| Dec26 | 96.990 | 3.010% | +51.0bp |
| Mar27 | 96.655 | 3.345% | +84.5bp |
| Jun27 | 96.470 | 3.530% | +103.0bp |
| Sep27 | 96.385 | 3.615% | +111.5bp ← `ecb_path_12m` (period starts 15 Sep 2027) |

History check: Oct26 settled 97.475 on 26 Jun → 97.205 on 24 Sep, i.e. the
implied rate hardened +27bp over the summer.

**Gotcha 1 — Euribor is interbank, not the policy rate.** It carries a spread
over the DFR that is not constant. It is **not** subtracted; `rates.py` prints
`front implied − DFR` every run and writes it per date to `data/ecb_spread.csv`
so drift is visible. 2026-09-23/24: +29.5bp, 2026-09-25: +26.0bp (basis +
expectations for the ~2 decisions inside Oct26's window).

**Gotcha 2 — decisions take effect at the next reserve maintenance period, not
on the decision date.** The 10 Sep decision only reached the DFR/€STR on 16 Sep.
- **Decision dates:** from the ECB Governing Council calendar,
  `https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html` (HTML,
  fetchable; the decision is Day 2 of a two-day monetary policy meeting —
  e.g. 29 Oct 2026, 17 Dec 2026, 4 Feb 2027 …). Written to `data/cb_meetings.csv`.
- **Effective dates:** the ECB's *Indicative calendar of reserve maintenance
  periods* (`/press/calendars/reserve/html/index.en.html`) is filled in by a
  script and is **not available as data** (no SDMX series found either). So
  `banks/ecb.py` uses **decision + 6 days — an APPROXIMATION fitted to two
  observations** (11 Jun → 17 Jun, 10 Sep → 16 Sep). Every run re-checks it
  against each DFR change and reports `EFFECTIVE-DATE APPROXIMATION BROKE` if a
  change doesn't land 6 days after a decision. Replace it with the published
  calendar if one becomes machine-readable.
- **Odds:** `prob_move_pct` is kept only when exactly **one** decision takes
  effect between `as_of` and the end of the front contract's window. A 3-month
  window normally holds two (Oct26: 4 Nov and 23 Dec), so the ECB is normally
  **bps-only** — a probability applies to one meeting.

Other ECB series:
- €STR (`EST/B.EU000A2X2A25.WT`, same api, `TIME_PERIOD`/`OBS_VALUE`) — no longer
  used by `rates.py`; still the reference overnight rate.
- ECB's *yield curve* api (`data-api…/YC/…`) is built from **government bonds**,
  not OIS. Not for policy expectations; useful for the long end (section 5).

---

## 3. BoC — fully automatable

### Current rate — CORRA
- **API:** `https://www.bankofcanada.ca/valet/observations/group/CORRA/csv`
- **Params:** `?start_date=2026-01-01` or `?recent=30` (prefer `recent` for the
  daily run — the full file is 7299 rows).
- **Format:** ~20 lines of metadata, then a line reading `"OBSERVATIONS"`, then
  the header and data. **Skip everything up to and including `OBSERVATIONS`.**
- **Columns:** `date, AVG.INTWO` (= CORRA), plus percentile/transparency columns
  that aren't needed.
- **Latest verified:** 2026-09-14 → 2.28%; 2026-09-23 → 2.29%.

### Expectations — Montréal Exchange CORRA futures
- **COA (1-month, use for next-meeting odds):**
  `https://www.m-x.ca/en/trading/data/historical?symbol=COA&f=COA&from=<YYYY-MM-DD>&to=<YYYY-MM-DD>&dnld=1`
- **CRA (3-month, use for the 12m path):** same URL with `CRA` in both `symbol` and `f`
- **`f=<symbol>&dnld=1` are required** — without them the URL returns the HTML
  page, not the CSV (up to 6 months per download).
- **Contract month = start of the reference period:** `COAV26` = average CORRA
  over Oct 2026 (expires first business day after); `CRAU26` = the quarter from
  the Sep IMM date (3rd Wednesday) to the Dec IMM date.
- **Column to use:** `Settlement Price`. **Not** `Last Price` — it is 0 on days
  with no trades, while settlement is always populated.
- **Also useful:** `Expiry Date` column identifies which period each contract covers.
- `CORRA Rate` column in these files is 0 — get the rate from Valet instead.

### Optional: the ready-made probability page
`m-x.ca/en/trading/tools/canadian-interest-rate-expectations` computes odds
already (no download link, HTML table — try `pandas.read_html`).
**Gotcha:** its "Implied Probability" column can read >100% (e.g. 168.79%), which
means more than one 25bp step is priced. Always take `Post-meeting Implied CORRA
Change` (in %) and convert to bps yourself.

---

## 4. BoE — fully automatable

### Current rate — SONIA
- **URL:** `https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2020&Dateto=now&SeriesCodes=IUDSOIA&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N`
  (the `fromshowcolumns.asp` URL used originally now returns an HTML "search
  again" page, not data)
- **Series code:** `IUDSOIA`
- **Format:** `DATE,IUDSOIA`, no metadata with `CSVF=TN` (`CSVF=TT` adds a
  series-description block). Dates as `22 Sep 2026` — **needs parsing**, not ISO.
- **History:** from Jan 2020. Latest verified: 2026-09-14 → 3.7312%; 2026-09-22 → 3.7305%.
- **Publication lag:** the fixing for day D appears on D+1. Use the latest fixing
  dated *before* the curve date — that is what the worked example below does
  (3.7312 is the 09-14 fixing; 09-15 itself was 3.7302).
- Date range: `Datefrom=DD/Mon/YYYY`, `Dateto=now`.

### Expectations — OIS forward curve
- **Latest (updated continuously):**
  `https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/latest-yield-curve-data.zip`
  → extract `OIS daily data current month.xlsx`
- **Archive (one-time backfill):** "Archive yield curve data → Daily → *Daily
  overnight index swap curve*" → contains `OIS daily data_2025 to present.xlsx`
  (433 rows, Jan 2025 → Aug 2026) plus older files for 2009-2015 and 2016-2024.
- **Sheet:** `1. fwds, short end` — row = date, column = months ahead (1, 2, 3…60).
  Values are instantaneous forward rates in %. Dates are **Excel serial numbers**
  (46266 = 2026-09-01); the header row starting `months:` holds the horizons as
  floats (`1.0000000400000015`) — round them.
- **Readable without openpyxl:** an xlsx is a zip of XML (stdlib `zipfile` +
  `xml.etree`); `banks/common.py:xlsx_sheet` does this.
- **The archive and the current-month file don't overlap** — concatenate both.

**Worked example (2026-09-15, SONIA = 3.7312%):**
| months ahead | fwd | vs SONIA |
|---|---|---|
| 1 | 3.8035% | +7.2bp |
| 3 | 4.0902% | +35.9bp |
| 12 | 4.8666% | **+113.5bp** ← `boe_path_12m` |

**Gotcha:** the zip also contains GLC Nominal / Real / Inflation files — those are
**government bond** curves, not policy expectations. Only the OIS file is correct.

---

## 5. Other useful data found along the way

### Euro-area yield curve (for the long end)
`https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.<MATURITY>?format=csvdata`
- Maturities: `PY1Y`, `PY5Y`, `PY10Y`, `PY30Y` etc. History from 2004, daily ~12:00 CET.
- **Not for Layer 1.** This fixes a different gap: the Treasury-buyback day showed
  the system only sees the *short* end. Pair with US `^TNX`/`^TYX` in `prices.py`
  to build the DE−US 2y spread — the cleanest summary of the FX differential.

### CME FX options daily update (Layer 2 extension)
Emailed PDF: premium traded per currency, **broken down by expiry date**. Maps
directly to Rule 10 (the address of fear) — shows where money is clustering on the
time axis. Weekly review, not a daily column.
**Gotcha:** it is *premium traded*, mixing buys and sells — not a directional net.
And CME contracts are inverted vs the pairs traded: a **put on CAD** = USD/CAD up.

---

## Output contract (unchanged)

`rates.py` must keep producing `data/rates.csv` with the same schema, so
`build_sheet.py`, `brief.py` and `story.py` need no changes:

```
bank, as_of, as_of_time, meeting, implied_rate, prob_move_pct, is_cut,
num_moves, change_bps, horizon
```

Keep the archive-first pattern: save each raw fetch under `data/raw/<bank>/<date>.<ext>`
so new columns can be backfilled later without re-fetching. That design already paid
for itself once (the `as_of_time` patch).

---

## Corrections (2026-09-25, from live downloads)

| Item | Originally written | Actual |
|---|---|---|
| M-X CSV URL | `symbol/from/to` only | needs `f=<symbol>&dnld=1`, else HTML |
| BoE SONIA URL | `fromshowcolumns.asp` | `_iadb-fromshowcolumns.asp?csv.x=yes…` |
| SONIA dates | `14 Sep 26` | `22 Sep 2026` (parse both) |
| €STR csv | 3 columns | ~29 SDMX columns; `TIME_PERIOD`/`OBS_VALUE` |
| €STR level | 2.190 on 09-25 | 2.440 — ECB hiked, effective 09-16 |
| Fed band | `(350-375)` | 3.75–4.00 since the 09-16 hike; take it from NY Fed EFFR |
| ECB expectations | CME €STR (ESR) `priorSettle`, manual | dead (zero volume, pre-hike settle) → ICE Euribor, automated |
| ECB policy rate | €STR + 0.31 constant | official DFR series, 2.50 since 09-16 |
| FedWatch csv | `Date,(buckets)` single block | one block per meeting + title row; last title may have no data |

## Standing rules that apply here

- **Raw bps is primary; % is derived** (Rule 5). A >100% reading = multiple steps.
  A probability applies to ONE meeting: `prob_move_pct` is only set on the
  next-meeting row, and only if that row covers a single decision; further rows
  carry `change_bps` and `num_moves` only.
- **Expired rows:** a row is dropped only once its period has fully elapsed
  (`period_end < as_of`). An in-progress front contract is live and stays.
- **Name missing data, never guess** (Rule 7). ECB expectations have no free
  history source — that series starts accumulating from today forward.
- **Record the source timestamp with every snapshot.** FedWatch and the CME quotes
  are delayed (10 min) and update ~3×/day; a stale snapshot silently misleads.
- **Sign always** (Rule 8): `change_bps` negative = cut priced.
