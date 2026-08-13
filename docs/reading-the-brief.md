# How to Read the Daily Brief — A Complete Guide
### Your manual for turning the brief's output into understanding
*Keep this next to the brief. Re-read it whenever a line doesn't click. Over time you'll need it less — that's the point.*

---

## Part 0 — What the brief is, in one paragraph

The brief is your desk analyst. Every day it reads your three layers of data
(rates, vol, positioning) plus the calendar, and tells you three things: **is
today a day to act or a day to wait, where is the danger, and what should you
watch.** It never says "buy" or "sell" — direction is your job, from the chart.
The brief only tells you whether the ground you're standing on is solid or mined.

If you remember nothing else: **the brief's most valuable output is "NOISE DAY —
no trade." That sentence, obeyed, is what fixes overtrading.**

---

## Part 1 — The overall shape

Every day, for each pair you trade, you get a block like this:

```
▌ EUR/USD
  rates: [Layer 1 — what's priced, is an event near]
  vol  : [Layer 2 — how much fear, which direction]
  pos  : [Layer 3 — who's crowded]
  cal  : [upcoming events, • = relevant to this pair]
  ▶ CONTEXT: [one-line summary of the situation]
  ▶ WATCH:   [where the asymmetry / danger is]
  ▶ VERDICT: [signal day / noise day / investigate]
```

Read it top to bottom. The three layers build the picture; CONTEXT summarizes it;
WATCH points at the risk; VERDICT tells you what kind of day it is.

**The golden habit:** read the three layers first and try to guess the VERDICT
yourself *before* you read it. When your guess matches, your understanding is
growing. When it doesn't, that mismatch is the most valuable thing to study.

---

## Part 2 — Reading the RATES line (Layer 1)

This line answers: **"What has the market already priced, and is a catalyst
near?"**

### What you'll see

```
rates: ECB next-mtg 90% (+22.4bp), 12m path +55.4 (+3.8 vs prev)
       meeting LOCKED (>90%) — the surprise is the MISS, not the hit
       ⚑ USD CPI m/m 2026-08-12 — relevant event near
```

### Line by line

**`ECB next-mtg 90% (+22.4bp)`**
The market prices a 90% chance the ECB moves at its next meeting. The `+22.4bp` is
the raw number — the primary datum. *Why it matters:* 90% means the move is almost
fully expected, so the decision itself won't move the market much. Remember the
apple parable: what's expected is already in the price.

**`12m path +55.4 (+3.8 vs prev)`**
Over the next 12 months, the market prices +55.4bp of hikes total. And it moved
**+3.8bp since yesterday** — that's the important part. *A single number is dead;
a change tells a story.* +3.8 in a day means the market hardened its expectations
— someone got more hawkish.

**`meeting LOCKED (>90%)`**
When odds pass 90%, the brief flags it. *Why:* you don't trade the decision (it's
priced) — you trade the *tone* and the *surprise*. And the surprise flips: when a
hike is 90% priced, the shocking outcome would be a *non-hike*. The rare event is
the miss, not the hit.

**`⚑ event near`** vs **`quiet on the calendar`**
The ⚑ means a *relevant* high-impact event is within 7 days. "Relevant" is key —
only EUR and USD events matter for EUR/USD. If you see "quiet on the calendar," no
catalyst is near, which points toward a noise day.

### You might also see

- **`path +9.0bp in a day — SLAP (real driver hit)`** — a big repricing with no
  meeting means a real driver (data, oil, a speech) just hit. Something happened.
- **`path +3.0bp — notable shift`** — a smaller move; worth noting, not alarming.
  (Remember: 3bp is a breeze, 8bp is a slap.)

---

## Part 3 — Reading the VOL line (Layer 2)

This line answers: **"How much turbulence does the market expect, and which
direction is it afraid of?"**

### What you'll see

```
vol  : EUVL 5.12 (-0.10)
       skew -0.31 (put-tilted), easing toward zero
```

### Line by line

**`EUVL 5.12 (-0.10)`**
The implied-volatility level and its day-change. *Level* = how much movement is
priced. *Change* = is fear building or draining? `-0.10` means vol fell slightly —
the market is a touch calmer than yesterday.

**`vol crushing — event premium draining, worry fading`**
Appears when vol falls hard *after* an event passed. *Why it matters:* the market
paid up for insurance before the event; now it's over, so the insurance drains.
This is the "calm after the storm" — it confirms a quiet window from the vol side.

**`⚑ vol JUMPING — something is moving; check skew for the side`**
Appears when vol spikes. This is an alarm bell: something is happening. But the
level alone doesn't tell you *which way* — for that, read the skew next.

**`skew -0.31 (put-tilted), easing toward zero`**
This is the direction of fear. **The sign is everything:**
- **Negative = put-tilted** = downside insurance is richer = the market fears a
  *fall* in this pair.
- **Positive = call-tilted** = the market fears (or chases) a *rise*.

And the drift: **`easing toward zero`** = fear is fading. **`deepening`** = fear is
building. So `-0.31 easing toward zero` means: "there's still some fear of a fall,
but it's calming down."

### The WATCH line it can trigger

```
▶ WATCH: EUVL skew -0.76 extreme vs its own 1y band [-0.70,+0.10] —
         put-insurance rich, reversal/vol-crush risk
```

*Why this matters:* when skew hits an extreme versus its **own history** (not zero
— its own normal), it means one side is heavily insured. Heavily-insured downside
often means a fall is already priced — so bad news moves it little, and good news
can snap it back hard (a reversal), amplified by the insurance unwinding.

---

## Part 4 — Reading the POS line (Layer 3) — the richest one

This line answers: **"Who has already bet, and how crowded is the boat?"** It's
the most powerful layer because it predicts *asymmetry*.

### What you'll see

```
pos  : Lev funds net -52,205 (short), 2nd pctile 3y
       fast & slow money SAME side → genuine directional consensus
       → crowded short (extreme). Asymmetry: news AGAINST the boat = squeeze up
       (COT as of 2026-08-04 — 6d old)
```

### Line by line

**`Lev funds net -52,205 (short), 2nd pctile 3y`**
Leveraged funds (fast money — the ones that drive short-term price) are net short
52,205 contracts. But the raw number is meaningless alone — the **`2nd pctile 3y`**
is what matters: this short is at the 2nd percentile of its own 3-year history.
Translation: **they have almost never been this short in 3 years.** The boat is
extremely one-sided.

**`fast & slow money SAME side → genuine directional consensus`**
This is Rule 13 (the composition check). It compares fast money (leveraged) with
slow money (commercial/asset managers):
- **SAME side** (both short) = real agreement. Everyone genuinely bets this way.
  Strongest signal.
- **OPPOSITE (mirror)** = they disagree. In bonds this often means structural
  mechanics (a basis trade), near-zero directional signal. In FX it usually means
  a real fast-vs-slow disagreement — read the fast money for your horizon.

*Why this line exists:* a "record short" means one thing if everyone agrees, and a
completely different thing if it's two sides of a hedge. Always check composition
before trusting the crowding.

**`→ crowded short (extreme). Asymmetry: news AGAINST the boat = squeeze up`**
This is the payoff, and the single most important concept in the whole brief.
**Crowding predicts asymmetry, NOT direction.** It does *not* say "price will go
up." It says: because everyone is short, the two sides have unequal fuel:
- News *with* the crowd (bad for this currency) → muted move (everyone's already
  positioned, no fresh sellers).
- News *against* the crowd (good for this currency) → **squeeze**: everyone runs
  for the same exit at once, and the move is violent, in the direction opposite
  the crowd (here, *up*).

**`(COT as of 2026-08-04 — 6d old)`**
The reminder that COT is a Tuesday snapshot released Friday — always a few days
old. Normal for weekly data. Only warns "STALE" if it's more than 10 days old (a
missed release).

---

## Part 5 — Reading the CALENDAR line

```
cal  : upcoming (7d):
        2026-08-11 04:30 AUD Cash Rate
        2026-08-11 04:30 AUD RBA Rate Statement
      • 2026-08-12 12:30 USD CPI m/m
      • 2026-08-12 12:30 USD CPI y/y
```

Every upcoming high-impact event is shown, so you see the full picture. **The dot
(•) marks events relevant to this pair.** Only dotted events drive the verdict.

*Why show the non-relevant ones at all?* Context. An AUD rate decision won't move
EUR/USD directly, but knowing the whole day's landscape helps you understand
cross-market mood. The dot keeps you from mistaking an AUD event for a EUR/USD
catalyst — the exact error that would manufacture a false signal day.

---

## Part 6 — The three verdict types (this is the decision)

### VERDICT: NOISE DAY

```
▶ CONTEXT: Quiet window — no relevant catalyst, no positioning extreme.
▶ VERDICT: NOISE DAY — default: no trade. Preserve capital.
```
**Meaning:** nothing priced-relevant is near, nobody's crowded. Most days are
this. *This is a win, not a boring non-answer.* It's the system doing its main
job: keeping you out of the 40 mediocre trades a year that bleed accounts.

### VERDICT: NOISE DAY (but crowded)

```
▶ CONTEXT: Quiet on relevant calendar, but positioning is crowded — asymmetric setup.
▶ VERDICT: NOISE DAY on the calendar — but crowd is extreme: don't ADD to the
           crowded side; watch for a squeeze against it.
```
**Meaning:** no event, but the boat is dangerously full. No catalyst today, so no
action — but a specific warning: don't pile into the crowded side (you'd be last
on a full boat), and be alert that any surprise could squeeze it.

### VERDICT: SIGNAL DAY

```
▶ CONTEXT: Relevant event window OPEN — a catalyst is near.
▶ VERDICT: SIGNAL DAY — relevant event near; watch the reaction, don't pre-position blindly.
```
**Meaning:** a relevant catalyst is within 7 days. This is when trades can happen
— but "don't pre-position blindly" is the discipline: you don't bet *before* the
event on what you think it'll say (that's gambling on the priced-in). You wait for
the event, measure the surprise, and trade the *reaction*.

### VERDICT: INVESTIGATE

```
▶ CONTEXT: Vol moving with no relevant scheduled event — off-calendar force.
▶ VERDICT: INVESTIGATE — vol jump without a relevant event. Find the driver first.
```
**Meaning:** the golden signal — the layers disagree. Vol is jumping but nothing's
scheduled. Something is moving that isn't on the calendar (geopolitics, a surprise
headline). Don't trade blind — go find what the market smells before it's obvious.

---

## Part 7 — Three full worked examples

### Example A — a clean noise day

```
▌ EUR/USD
  rates: ECB next-mtg 22% (+5.6bp), 12m path +50.4 (+0.2 vs prev)
         no relevant (EUR/USD) HIGH event in 7d → quiet on the calendar
  vol  : EUVL 5.23 (-0.22)
         skew -0.43 (put-tilted), easing toward zero
  pos  : Lev funds net -30,000 (short), 45th pctile 3y
         fast vs slow OPPOSITE → check structural/basis
  ▶ VERDICT: NOISE DAY — default: no trade. Preserve capital.
```
**How to read it:** ECB not near a decision (22%), no event for 7 days, vol
draining (-0.22), fear fading (skew easing), positioning middling (45th pctile —
not crowded). Every layer says "calm." Chart will probably be ranging. **Verdict:
do nothing, and feel good about it.** This is the system earning its keep.

### Example B — a crowded, pre-event day (your real Aug 10)

```
▌ EUR/USD
  rates: ECB next-mtg 90% (+22.4bp), 12m path +55.4 (+3.8 vs prev)
         meeting LOCKED (>90%)
         ⚑ USD CPI m/m 2026-08-12 — relevant event near
  vol  : EUVL 5.12 (-0.10), skew -0.31 easing toward zero
  pos  : Lev funds net -52,205 (short), 2nd pctile 3y
         fast & slow money SAME side → genuine directional consensus
         → crowded short (extreme). news AGAINST the boat = squeeze up
  ▶ VERDICT: SIGNAL DAY — relevant event near; watch the reaction.
```
**How to read it:** three things stack up. (1) A USD CPI is 2 days out — a real
catalyst. (2) The euro boat is at 2nd-percentile short, with fast AND slow money
agreeing — an extremely crowded, one-sided bet. (3) The ECB meeting is locked, so
the euro's own rates aren't the driver — the USD side (CPI) is. **The story the
brief is telling:** if CPI comes in weak (USD-negative, like the recent NFP), it
hits a boat that's maximally short EUR → everyone covers at once → violent squeeze
*up* in EUR/USD. **Your action:** don't short EUR before the print (you'd be
adding to a crowded, dangerous side). Wait for CPI, measure it against expectations,
and trade the reaction. The danger is clearly mapped: a weak print squeezes up.

### Example C — the divergence (golden signal)

```
▌ USD/CAD
  rates: BOC next-mtg 11% (+2.7bp)
         no relevant (CAD/USD) HIGH event in 7d → quiet on the calendar
  vol  : CAVL 5.80 (+0.55)
         ⚑ vol JUMPING — something is moving; check skew for the side
         skew -0.70 (put-tilted), deepening (fear building)
  pos  : Lev funds net -60,000 (short), 20th pctile 3y
  ▶ VERDICT: INVESTIGATE — vol jump without a relevant event. Find the driver first.
```
**How to read it:** the calendar is quiet — no scheduled catalyst. But vol just
jumped +0.55 and skew is deepening (fear of a CAD fall building fast). **The
layers disagree: rates say calm, vol says panic.** That contradiction is the
signal. Something is moving that isn't on your calendar — maybe an oil shock, a
tariff headline, a geopolitical event. **Your action:** don't trade yet — go find
what the vol market smells. The brief caught the whisper before it became a
headline.

---

## Part 8 — The mental checklist for every brief

Read each pair's block and ask, in order:

1. **Is a relevant event near?** (rates line, ⚑) → if yes, it's likely a signal day.
2. **Is fear building or fading?** (vol line, skew drift) → sets the mood.
3. **Is the boat crowded, and do fast+slow agree?** (pos line, pctile + composition)
   → tells you where the squeeze risk is.
4. **What does the VERDICT say, and did I predict it?** → the learning check.
5. **If I traded here, which way is the danger?** (WATCH line) → always know the
   squeeze direction before you act.

If after these five questions the answer is "nothing lines up" — that's a noise
day, and the correct trade is no trade.

---

## Part 9 — What the brief will NEVER tell you (and why)

- **It won't say buy or sell.** Direction comes from your chart. The brief gives
  context, not signals — because a signal machine would just be a faster way to
  overtrade.
- **It won't promise a trade every day.** Some weeks have zero good setups. A
  system that manufactured daily signals would be lying to you.
- **It won't replace your thinking.** The small effort of reading it *is* the
  point — it keeps you engaged instead of blindly obeying. As you practice, the
  effort shrinks, until one day the story forms in your head the moment you see
  the numbers. That day, you've become the analyst — and that was always the goal.

---

*The brief is the ground you stand on. The chart is where you choose to walk.
This guide is how you learn to read the ground — until you don't need the guide.*
