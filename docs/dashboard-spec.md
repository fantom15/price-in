# The Visual Dashboard — Complete Specification
### Brief + charts in one view. The text tells you what; the charts show you the path.
*Spec for a Streamlit dashboard that sits on top of the price-in platform's data.*

---

## Purpose & principle

The daily brief (brief.py) answers "what's the situation today" in words. But a
word like "skew easing toward zero" hides the *shape* of the move. The COT
experience proved it: raw COT text is confusing, but on a chart you instantly see
"asset managers buying, leveraged selling, mirror image." **The dashboard adds the
visual layer so the path of each data series is obvious at a glance.**

Governing rule (same as everything in this platform): **every chart must answer
one of the three questions, or it's clutter.** No decorative charts. Each visual
maps to a layer:
- Layer 1 (rates) → is the priced path hardening or softening over time?
- Layer 2 (vol) → is fear building or fading, and which direction (skew path)?
- Layer 3 (positioning) → who's crowded, and how extreme vs history? (the COT chart)

The dashboard does NOT add new logic or signals. It **reads the same CSVs** the
brief reads and **renders them**. The brief text sits at the top; charts sit below,
per pair. Text and picture complete each other.

---

## Technology

- **Streamlit** — a local Python web app. Run `streamlit run dashboard.py`, opens
  in the browser, re-reads data on refresh. Chosen because it's ~one afternoon to
  build, pure Python (David's stack), no server/deploy needed, and trivially
  re-runs as data updates.
- **Plotly** for charts — interactive (hover, zoom, toggle series), which matters
  for the COT-style multi-line charts where you want to isolate one line.
- Reads directly from the existing CSVs (`market_data.csv`, `data/cot.csv`,
  `data/prices.csv`, `data/calendar.csv`) — no new data layer.

---

## Layout

```
┌─────────────────────────────────────────────────────────┐
│  price-in — Daily Dashboard        [date picker: 2026-08-10] │
├─────────────────────────────────────────────────────────┤
│  ── DAILY BRIEF (text, from brief.py) ──                 │
│  ▌ EUR/USD   rates / vol / pos / cal / CONTEXT / WATCH / VERDICT │
│  ▌ USD/CAD   ...                                          │
├─────────────────────────────────────────────────────────┤
│  ── EUR/USD ──                        [pair tabs / sections] │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐     │
│  │ L1: rate path │ │ L2: vol+skew │ │ L3: COT+price │     │
│  │  (line)       │ │  (2-axis)    │ │  (COT-style)  │     │
│  └──────────────┘ └──────────────┘ └──────────────┘     │
│  ── USD/CAD ──                                            │
│  (same three charts)                                     │
└─────────────────────────────────────────────────────────┘
```

- **Top:** the brief text, rendered as-is (call brief.py's logic or import it).
- **Middle/bottom:** per pair, a row of three charts (one per layer).
- **Date picker:** lets you view any historical day, not just today. The brief and
  all charts update to that date (charts show history *up to* that date).
- **Sidebar:** pair selector (show all, or focus one), and a lookback selector
  (30/90/180 days / all) for the charts.

---

## The charts — exact specification

### Chart 1 — Layer 1: Rate Path Over Time (per pair)

**Question it answers:** is the market pricing a harder or softer path, and is it
moving?

- **Type:** line chart, x = date, y = 12-month path (bps).
- **Series:** the pair's two banks. For EUR/USD: `ecb_path_12m` and `fed_path_12m`.
  For USD/CAD: `boc_path_12m`... (note: boc_path may not be in the sheet yet — if
  missing, show fed only and label the gap).
- **Also plot:** the next-meeting odds as a secondary faint line or markers, so you
  see both "the whole path" and "the next decision."
- **Annotations:** mark days with a repricing "slap" (|Δpath| ≥ 8bp) with a dot, so
  big moves are visually flagged.
- **Why:** turns "path +3.8 vs prev" into a visible slope — you see the trend, not
  just today's delta.

### Chart 2 — Layer 2: Vol + Skew Over Time (per pair)

**Question it answers:** is fear building or fading, and which side?

- **Type:** dual-axis line chart, x = date.
  - Left axis: CVOL level (`EUVL` or `CAVL`) — the amount of fear.
  - Right axis: skew (`euvl_skew` or `cavl_skew`) — the direction of fear.
- **Key visual:** a horizontal zero line on the skew axis. Skew below zero =
  downside fear; the distance from zero and the slope tell the story. This is where
  "skew -0.76 → -0.31 easing toward zero" becomes an obvious upward-drifting line.
- **Shading (optional):** shade the skew area below zero red-ish, above zero
  green-ish, so put-tilt vs call-tilt is instant.
- **Why:** the single most important chart for reading fear dynamics — the text
  can't convey a multi-week easing as clearly as a rising line toward zero.

### Chart 3 — Layer 3: COT Net + Price (per pair) — the COT-style chart

**Question it answers:** who's crowded, how extreme vs history, and how does it
relate to price? (This is the chart David asked for by name.)

- **Type:** two stacked panels sharing an x-axis (date), exactly like the COT
  screenshots:
  - **Top panel:** price (the pair's close from `prices.csv`).
  - **Bottom panel:** net positions — `net_spec` (leveraged/fast money) and
    `net_comm` (commercial/slow money) as two lines.
- **Key visuals:**
  - A zero line on the net panel (above = net long, below = net short).
  - Highlight when net_spec is in the red zone (percentile <15 or >85) — e.g.
    shade those regions, so "2nd percentile extreme" is visible as the line sitting
    at its historical bottom.
  - Because fast and slow are both plotted, you *see* the composition (mirror vs
    aligned — Rule 13) exactly as David discovered it manually.
- **Lookback:** default to a long window (2-3 years) so percentile extremes are
  visually meaningful — a "record short" only reads as extreme against years.
- **Why:** this is the chart that made COT click for David. It shows crowding,
  composition, and price-context in one picture.

### Optional Chart 4 — Skew vs its own 1-year band (per pair)

- Show current skew as a dot against the distribution (or the 10th/90th percentile
  band) of its own trailing year. Makes "extreme vs its own history" literal.
- Nice-to-have; build after the core three if useful.

---

## Interaction & polish

- **Date picker** drives everything — pick any past day, see that day's brief +
  charts-up-to-that-day. Great for replay practice (study a past event day).
- **Hover tooltips** on all charts (Plotly default) — exact values on demand.
- **Toggle series** by clicking the legend (Plotly default) — isolate one COT line,
  exactly like the source site.
- **Lookback selector** in the sidebar — 30/90/180/all days.
- **Refresh** — re-reads CSVs (a button, or Streamlit's rerun).
- Keep it visually calm: muted colors, thin lines, clear zero-lines. This is an
  analysis tool, not a trading terminal — no flashing, no red/green noise beyond
  the meaningful shading.

---

## What the dashboard must NOT do

- No new signals or logic beyond what brief.py already computes. It visualizes; it
  doesn't decide.
- No buy/sell markers. Direction stays with the chart-reading, not the dashboard.
- No prediction overlays, no fitted trendlines projecting the future — that invites
  the fortune-telling trap. Show what happened, not what "will" happen.
- No browser storage / external calls — reads local CSVs only.

---

## Build order (so it's usable early, not all-or-nothing)

1. **Skeleton:** Streamlit app that loads the CSVs and renders the brief text at
   top (import brief.py's per-pair logic, or shell out to it and display output).
2. **Chart 3 first (COT + price)** — the one David explicitly wants, highest value.
3. **Chart 2 (vol + skew)** — second highest for reading fear.
4. **Chart 1 (rate path)** — completes the three layers.
5. **Date picker + lookback** — makes it a replay tool.
6. **Chart 4 (skew band)** + polish — optional.

Definition of done for v1: brief text + the three per-pair charts, a working date
picker, reading from the real CSVs, for EUR/USD and USD/CAD.

---

## Data-source reference (for the builder)

- `market_data.csv` (project root): date + CAVL/EUVL/S1VL (+_chg,_skew) +
  fed/ecb/boc odds/bps/path + dxy/usdcad/eurusd/wti. Daily. Source for L1 + L2.
- `data/cot.csv`: report_date, symbol, dataset, net_spec, net_comm, ... Weekly.
  Source for L3. Symbols for EUR/CAD: verify exact strings via the file.
- `data/prices.csv`: date, series (eurusd/usdcad/dxy/wti), OHLCV. Daily. Source for
  the price panel of Chart 3.
- `data/calendar.csv`: date, currency, impact, event, ... Source for event markers
  (optional: mark event dates as vertical lines on charts).
