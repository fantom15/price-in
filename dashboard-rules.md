# Dashboard Rules — the narrative logic spec
### Accumulated from daily practice. Each rule = one if/then that turns data into a plain-language sentence.
*Started 2026-08-04. This file IS the dashboard's future spec. Every day of manual practice adds or refines a rule. When the list is stable (~10-15 practice sessions), these become the code.*

---

## How this file works

Every rule has four parts so it can later become code AND stay transparent:
- **TRIGGER** — the exact data condition (`if ...`)
- **SAYS** — the plain sentence the dashboard prints (`then ...`)
- **MEANS** — what it tells the trader (why the sentence matters)
- **ORIGIN** — which practice day / event it came from (so we remember it was earned, not invented)

Golden principle: **transparency over magic.** Every sentence must trace to a rule you understand. No AI free-writing. If you can't state the rule, it doesn't go in.

---

## Layer 1 — Rates (the "is there a live event?" layer)

### R1 — Quiet window
- **TRIGGER:** no high-tier event (CB meeting / CPI / NFP) within 7 days
- **SAYS:** "Quiet window — no live event near. Today is noise, not signal."
- **MEANS:** most moves today lack a rate catalyst; default to no-trade; any big move needs a non-rate explanation.
- **ORIGIN:** 2026-08-04, EUR/USD — ECB meeting weeks away, confirmed by flat chart.

### R2 — Repricing severity (breeze vs slap)
- **TRIGGER:** `abs(path_12m_chg)` in one day: ≥3bp = breeze, ≥8bp = slap
- **SAYS:** "{BANK} path moved {X}bp — {breeze/slap}. Market is re-pricing the trajectory."
- **MEANS:** the priced path is shifting; a slap means a real driver hit (find it: data? oil? official speech?).
- **ORIGIN:** the July week — 3bp shifts were noise, 8-15bp days (CPI, Warsh) were real regime moves.

### R3 — Locked meeting (reverse)
- **TRIGGER:** next-meeting odds ≥90%
- **SAYS:** "{BANK} meeting {X}% priced — locked. The surprise is now the MISS, not the hit."
- **MEANS:** no trade on the decision; asymmetry flips — an unexpected hold/no-move is the violent outcome.
- **ORIGIN:** ECB Sep at 92%, Fed Sep at 76% — the migration weeks.

### R4 — Calendar tripwire
- **TRIGGER:** a high-tier event lands today or tomorrow
- **SAYS:** "⚑ {EVENT} today/tomorrow — quiet window ends. Signal day, stay alert."
- **MEANS:** you know the window is closing BEFORE vol moves; pre-position your attention.
- **ORIGIN:** 2026-08-04 lesson — the window can end from Layer 1 (a data release) before EUVL even reacts.

---

## Layer 2 — Vol (the "how worried, which way?" layer)

### R5 — Vol crush (calm after storm)
- **TRIGGER:** `CVOL_chg` clearly negative (e.g. ≤ -0.15) AND a major event just passed
- **SAYS:** "Vol crushing — event premium draining. Worry is fading."
- **MEANS:** the market sees no big threat ahead right now; confirms a quiet window from the vol side.
- **ORIGIN:** 2026-08-04 — EUVL 6.18 → 5.23 after the four-CB week.

### R6 — Skew as fear direction
- **TRIGGER:** read `skew` sign and level vs its own 1-year band
- **SAYS:** "Skew {X}: {put/call}-tilted, {extreme/moderate/normal} vs its own history — crash/melt-up insurance is {rich/cheap}."
- **MEANS:** negative = downside insurance richer (fear of a fall). Judge against ITS OWN normal, not zero. Near zero = fear fading; deep = fear building.
- **ORIGIN:** 2026-08-04 — skew -0.76 (war peak) → -0.43 (fading but still put-tilted).

### R7 — Vol jump = alarm, then check skew for address
- **TRIGGER:** `EUVL_chg` sharply positive (e.g. ≥ +0.40)
- **SAYS:** "⚑ Vol jumping — something is happening. [check skew: if more negative → downside threat; if flat → two-sided]."
- **MEANS:** EUVL is the alarm bell (something's coming); skew is the address (which side). One rings, the other locates.
- **ORIGIN:** 2026-08-04 lesson — a vol jump alone doesn't say the direction; skew does.

---

## Layer 3 — Positioning (the "who's crowded?" layer)

### R8 — Crowding = asymmetry, not direction
- **TRIGGER:** leveraged-funds percentile in red zone (<15 or >85)
- **SAYS:** "{PAIR} positioning at {X}th pctile — crowded {short/long}. Asymmetry: news AGAINST the boat = squeeze; news WITH it = muted."
- **MEANS:** does NOT predict direction (can stay crowded for weeks). Predicts which surprise is violent.
- **ORIGIN:** ECB week — 6E at 0th percentile short; the squeeze setup that never fired because no hawkish surprise reached it.

---

## Cross-layer — the synthesis rules (the most valuable ones)

### X1 — All three agree
- **TRIGGER:** all three layers point the same way (e.g. quiet Layer 1 + vol crush L2 + normal L3)
- **SAYS:** "All layers aligned: {picture}. Reliable read."
- **MEANS:** when the gauges agree, the context is trustworthy — low risk of a hidden force. (Chart should match; if it doesn't, investigate.)
- **ORIGIN:** 2026-08-04 — quiet window + vol crush + fading skew + ranging chart, all saying "calm after storm."

### X2 — Layers disagree = the golden signal
- **TRIGGER:** any two layers contradict (e.g. odds calm BUT vol jumping = false calm; or path hardening BUT price falling = channel conflict)
- **SAYS:** "⚑ DIVERGENCE: {layer A says X} but {layer B says Y}. The market is whispering something not yet in the headline."
- **MEANS:** disagreement is where the edge is — a hidden force is being priced. Investigate before it becomes obvious.
- **ORIGIN:** the frozen EUR/USD (rates up vs war down netting to zero); false-calm pattern (odds locked + IV rising).

### X3 — Chart vs context check
- **TRIGGER:** compare chart behavior to the context sentence
- **SAYS:** "Chart {matches/contradicts} context. {If contradicts: big move with no catalyst → find the driver or suspect a fade}."
- **MEANS:** the daily routine's core move — the chart is only trustworthy when it agrees with the measured context.
- **ORIGIN:** 2026-08-04 — ranging chart matched the quiet-window context → confirmed no-trade.

---

## The daily output shape (what the dashboard will print)

```
═══ CONTEXT — {date} — {PAIR} ═══

Layer 1 (rates):  {R1/R2/R3/R4 sentences}
Layer 2 (vol):    {R5/R6/R7 sentences}
Layer 3 (pos):    {R8 sentence}

⚑ CROSS-CHECK:    {X1/X2 — aligned or diverging?}

▶ CONTEXT SENTENCE: "{the one-paragraph synthesis}"
▶ CHART CHECK:      {does price match? — X3}
▶ VERDICT:          {noise day / signal day / divergence-investigate}
```

The VERDICT line is never "buy" or "sell" — it's "is this a day to act, and is my ground solid?" Direction stays with the trader's chart.

---

## Open questions (to resolve through more practice)

- Exact numeric thresholds: is skew "extreme" at -0.65 or -0.70? Needs the 1-year percentile band per ticker, not a fixed number.
- How to weight the layers when they mildly disagree (not full divergence)?
- Should the 7-day event window be per-pair (EUR watches ECB+Fed; CAD watches BoC+Fed)?
- Percentile data isn't in the daily sheet yet (weekly COT) — how does L3 enter the daily dashboard? (probably a slow-moving flag updated Saturdays)

*These get answered by doing the routine, not by guessing. Each practice session should either add a rule or sharpen a threshold.*
