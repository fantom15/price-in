# Context: the price-in platform

I'm building an event-driven macro data platform for FX trading. It has three
data layers, each answering one question about market expectations:

- Layer 1 (rates): what scenario is priced? → rateprobability odds/bps/12m-path
- Layer 2 (vol): how much fear, which direction? → CME CVOL levels + skew
- Layer 3 (positioning): who's crowded? → CFTC COT net + percentile

The platform's job is NOT to predict direction. It reports CONTEXT: is today a
signal day or noise, where is the positioning asymmetry, what to watch. Direction
stays with my chart reading.

# The data layer (collectors already built)

All collectors write to CSV with an archive-first pattern (raw snapshots kept,
CSVs rebuilt from them). Files:

- market_data.csv (project root) — the assembled daily sheet, built by
  build_sheet.py from cvol.csv + skew.csv + rates.csv. One row per date.
  Columns: date, CAVL, CAVL_chg, cavl_skew, EUVL, EUVL_chg, euvl_skew,
  S1VL, S1VL_chg, s1vl_skew, fed_odds_pct, fed_bps, fed_path_12m,
  ecb_odds, ecb_bps, ecb_path_12m, boc_odds, boc_bps, dxy, usdcad, eurusd, wti

- data/cot.csv — weekly, long format, one row per (report_date, symbol).
  Columns: report_date, symbol, instrument, dataset, spec_long, spec_short,
  comm_long, comm_short, net_spec, net_comm, open_interest.
  dataset=tff for FX (spec=leveraged funds). net_spec = precomputed long−short.
  History back to 2010, so 3-year (156-week) and 1-year (52-week) percentiles
  are computable.

- data/prices.csv — daily, long format, one row per (date, series).
  Columns: date, series, open, high, low, close, volume, source.
  series values: eurusd, usdcad, dxy, wti.

- data/calendar.csv — event-level. Columns: date, time, currency, impact,
  event, actual, forecast, previous, actual_val, forecast_val, previous_val,
  surprise, surprise_dir. impact ∈ {LOW, MEDIUM, HIGH}.

# What brief.py must do

brief.py is the NARRATIVE layer. It runs AFTER all collectors + build_sheet.py.
It reads today's data, compares to prior days, evaluates a set of if/then rules,
and prints a plain-language brief per traded pair. Structure per pair:

  ▌ EUR/USD
    rates:  [Layer 1 sentences]
    vol:    [Layer 2 sentences]
    pos:    [Layer 3 sentences]
    ▶ CONTEXT: [one-line synthesis]
    ▶ WATCH:   [where the asymmetry/risk is]
    ▶ VERDICT: [signal day / noise day / investigate — never "buy"/"sell"]

CRITICAL PRINCIPLE: transparency over magic. Every sentence must trace to an
explicit rule. NO free-form AI analysis. Only coded if/then rules, rendered as
text. The rules live in dashboard-rules.md — read that file and implement each
rule as a function that returns a sentence when its trigger fires.

# The rules (from dashboard-rules.md — implement each)

Layer 1:
- Quiet window: no HIGH-impact event within 7 days → "quiet window, noise day"
- Calendar tripwire: a HIGH event today/tomorrow → "⚑ event near, signal day"
- Locked meeting (reverse): odds ≥90% → "meeting locked, surprise is the miss"
- Repricing: |Δ 12m-path| ≥5bp = shift, ≥8bp = slap

Layer 2:
- Vol crush: CVOL falling ≥0.15 AND event just passed → "premium draining"
- Vol jump: CVOL rising ≥0.40 → "⚑ vol jumping, check skew for direction"
- Skew as fear: report sign + drift vs yesterday; judge against its OWN history
  (use the 1-year distribution of that skew column, NOT a fixed threshold)

Layer 3 (COT):
- Composition first: compare net_spec (leveraged) vs net_comm. If mirror →
  possibly structural; if same direction → real consensus. (Rule 13)
- Crowding: compute net_spec percentile vs 3y history. <15 or >85 = red zone.
  Crowding predicts ASYMMETRY not direction: "news against the boat = squeeze".
- Always note COT is a Tuesday snapshot (3-day lag).

Cross-layer:
- All layers agree → "aligned, reliable read"
- Layers disagree (e.g. odds calm but vol jumping) → "⚑ divergence — the golden
  signal, investigate"

# Pair → data mapping

- eurusd: banks=[ecb, fed], cvol=EUVL, skew=euvl_skew, cot symbol=<check
  data/cot.csv for the exact symbol string>, price=eurusd, filters=[dxy]
- usdcad: banks=[boc, fed], cvol=CAVL, skew=cavl_skew, cot symbol=<check>,
  price=usdcad, filters=[dxy, wti]

# Tasks

1. First, inspect the actual CSVs (head each file, and `cut -d, -f2 data/cot.csv
   | sort -u` to find the exact COT symbol strings for EUR and CAD). Don't assume
   column names or symbol strings — verify against the real files.
2. Implement/fix brief.py so every rule above is a clear function, each returning
   a sentence only when its trigger fires. Percentiles computed from the real COT
   history. Thresholds as named constants at the top so I can tune them.
3. Handle missing data gracefully: if a column/file is empty, say "no X data"
   rather than crashing or guessing (this is a hard rule — never fabricate).
4. Output the brief for the latest date in market_data.csv, for eurusd and usdcad.
5. Make it a reusable script: `python3 brief.py [--date YYYY-MM-DD] [--pair X]`.

Read dashboard-rules.md and the CSV files first, then implement. Show me the
output on the latest real data, and flag any rule where the data doesn't cleanly
support the sentence.