# The Pricing-In Mechanism: A Complete Field Guide
### From overnight money to positioning squeezes — everything in one place
*Compiled from a three-week mentorship, July 2026. Written to be re-read weekly.*

---

# Part I — The Central Idea

Markets do not react to news. They react to the **gap between news and what was already expected**.

> **Price move = Reality − Priced-in expectation**

Everything else in this guide is machinery for measuring the right-hand side of that equation *before* reality arrives.

## The apple-seller parable

Apples cost 100 today. The weather service announces: "Hail in three days; half the orchards will be destroyed." When does the price rise? **Today** — not in three days. Sellers won't part with soon-to-be-scarce apples below 150, and buyers know it too. When the hail actually strikes, the price doesn't move at all: the event everyone saw coming was already absorbed. That is **pricing-in**.

The price only moves again if reality *differs* from the forecast: hail worse than feared → 150 jumps to 200; no hail at all → 150 collapses to 100, even though "good news" arrived. Whoever bought at 150 learns the hard lesson: you don't profit from being right about events — you profit from being right about the *gap*.

Pricing-in is a two-way street. Money arrives early on expectation; if the expectation dies, that same money leaves. A currency can fall on "no news" simply because the hope that had been priced into it drained away.

## Why prices equal expectations: arbitrage

A derivative price is not an opinion poll. It is a settled bet. If a contract that collectively "should" be worth 10 trades at 40, sellers swarm it for free money until it falls back to 10. **Any gap between price and collective belief is a free-profit opportunity, and the hunting of that opportunity closes the gap.** Prices cling to collective expectations not out of consensus but out of greed. This single mechanism is why we can read expectations *out of* prices — the entire foundation of this guide.

*A sentence worth memorizing: prices in derivatives markets are not opinions — they are money-settled bets, and money doesn't lie unless someone is willing to pay for the lie.*

## The asset hierarchy: where waves come from

Not all assets are equal. Shocks flow downhill through a pyramid:

1. **US interest rates (Treasury yields)** — the price of money itself. Every asset on Earth is ultimately priced against the question: "How does this compare to holding riskless US paper?" When the risk-free rate moves, every valuation's denominator moves.
2. **The dollar (DXY)** — itself a consequence of rates, but also an independent driver: the world's reserve and invoicing currency. A strong dollar tightens the entire planet.
3. **Oil** — the driver of inflation and terms of trade. It feeds back into layer 1 via central bank policy, and it redistributes income between exporters (CAD, NOK) and importers (JPY, INR).
4. **Risk gauges (S&P, VIX)** — the risk-on/risk-off switch that moves funding currencies (JPY, CHF) against high-beta ones (AUD, NZD, EM) almost regardless of local stories.

Gold is *not* a driver — it is a **thermometer**, reflecting real yields, the dollar, and fear. No currency pair moves *because* gold moved; both respond to shared causes. Correlation is not causation, and the distinction saves you from entire families of bad analysis.

**Corollary — attribution:** spot price action is an inseparable mixture of these drivers. USD/CAD falling could be a dollar story (check DXY), an oil story (check WTI), a rates story (check the 2-year spread), or pre-event position squaring. To isolate the currency-specific component, use **crosses**: if USD/CAD falls *and* EUR/CAD falls, CAD is strengthening against everyone — a genuinely Canadian story. If only USD/CAD falls, it's a dollar story wearing a CAD costume.

## Where expectations live

Human fear and greed do drive markets — but you cannot measure feelings directly, and any attempt to explain price by mood inferred *from* price is circular (the socionomics trap). Instead, measure the **monetized footprints** of emotion:

| Instrument | What it stores |
|---|---|
| OIS / STIR futures | Expected path of policy rates, with probabilities |
| FX options (IV, RR, term structure) | Expected turbulence — its size, direction, and *date* |
| COT positioning | Expectations already converted into held positions |

These are the three layers. The rest of this guide teaches each language, then how to combine them.

---

# Part II — Layer 1: The Language of Rates
*Question answered: "Which scenario, with what probability, has the market priced?"*

## 1. Overnight money: the atom of finance

Banks end every day long or short of cash. The shorts must borrow *tonight*; the longs want their cash working. The market where they meet is the **overnight market**, and its rate — CORRA in Canada, SOFR in the US, €STR in the euro area — is the shortest, purest price of money.

The central bank does not *dictate* this rate; it **herds** it inside a corridor:
- **Floor (deposit rate):** banks can always park cash at the central bank risk-free at this rate — so no one lends to another bank for less.
- **Ceiling (lending rate):** banks can always borrow from the central bank at this rate — so no one pays another bank more.

The actual market rate lives inside this cage, hovering near the announced **policy target**. (Proof it isn't dictated: CORRA prints at 2.29% while the target is 2.25% — a market price inside a cage, not a decree.)

## 2. Why one tiny rate moves everything

Lending for 3 months must yield roughly the same as lending overnight 90 nights in a row — otherwise arbitrage closes the gap. So:

- 3-month rate ≈ expected average overnight rate over 3 months
- 2-year rate ≈ expected average overnight rate over 2 years + term premium

**The entire yield curve is built from one raw material: expectations of the future overnight rate** — which the central bank sets at eight scheduled meetings a year. The chain: policy rate → overnight → short rates → yield curve → mortgages, equity valuations, and — critically for FX — **relative currency attractiveness**.

*Note on convention: all rates are quoted annualized, even for a one-night loan. 2.25% overnight means ≈0.006% per night (2.25 ÷ 365), not 2.25% per night. Whenever a calculation implies absurd riskless profit, you've misread a convention — annualization or day-count (365 vs 360).*

## 3. OIS: the thermometer of expectations

An **Overnight Index Swap** is a two-sided bet on one question: "What will the *average* overnight rate be over some future window?" One side pays a fixed rate (the quoted OIS rate); the other pays whatever the realized average turns out to be; they settle the difference.

The fixed rate that clears the market must sit exactly at the collective expectation — anywhere else, one side is free money and arbitrage drags it back. Therefore: **OIS rate = the market's money-weighted forecast of the average overnight rate.** No survey needed; the votes are cast in dollars.

## 4. Extracting probabilities: the lottery-ticket trick

Imagine a ticket paying 100 if the central bank hikes, 0 if not. Its market price *is* the probability: trading at 10 means 10% odds. OIS embeds the same ticket. The mental formula:

**P(move) = (OIS rate − hold rate) ÷ step size (usually 25bp)**

Example: hold rate 2.28%, post-meeting OIS at 2.305% → gap 2.5bp → 2.5 ÷ 25 = **10% hike odds**.

Three critical refinements:

- **The raw bps number is the datum; the percentage is an interpretation.** The same +5.7bp reads as "23% hike" with a 25bp step or "57% hike" with a 10bp step. Since major central banks move in 25s, use step 25 — but always record the raw bps.
- **OIS prices the *weighted average* of scenarios, not a prediction.** +5.7bp doesn't mean anyone expects a 5.7bp move (no such move exists); it means 77% × 0 + 23% × 25. Like a die averaging 3.5: no face shows 3.5. Whenever you see a number that matches no real scenario, you are looking at a probability-weighted mixture — and the extraction formula simply runs the averaging backwards.
- **The two-scenario model is a simplification.** In crisis meetings where 50bp moves or cuts are live, the distribution has more branches. For ~95% of meetings, hold-vs-25 is enough.

## 5. Baseline, surprise, and the locked event

**Baseline** = the snapshot of priced expectations at a moment in time. Surprise is only measurable against it — and against the *final* pre-event snapshot, not last week's.

- Event >90% priced ("locked"): the decision itself is untradeable. The game moves to **the path** (odds of subsequent meetings, the 12-month cumulative bps) and **the tone**.
- Surprise is a **continuum, not a switch** — from a breeze (3bp path shift) to a slap (15bp+). Scenario matrices are compasses; reality usually lands *between* rows.
- Hawkish/dovish are **relative to baseline**, never absolute. A statement is hawkish if it's harder than what was priced — even if it sounds gentle in isolation.
- Tone hides in **textual diffs**: a deleted sentence, a changed verb, new forward guidance. Central banks sometimes engineer deliberate balance — one hawkish signal offsetting one dovish — precisely so that *nothing new gets priced*. A ±3bp path shift after such a statement means the message "we're still waiting" was successfully delivered.

## 6. Event anatomy: the three waves

A central bank "event" is a ~75-minute window, not a moment:
1. **Wave 1 (milliseconds–seconds):** algorithms react to statement keywords. Never judge from this spike.
2. **Wave 2 (~15 min):** humans digest the full statement and attached projections. Usually the more valid move.
3. **Wave 3 (press conference/Q&A):** unscripted answers carry the highest odds of a "slip." Congressional **testimony** is this wave stretched over hours — often more market-moving than a prepared speech.

## 7. Rate differentials: why FX exists

If every central bank always held the same rate, no currency would carry an interest advantage and macro FX would largely vanish. Rates differ because economies differ — different cycles, structures (oil exporter vs importer), and neutral rates (r*: the rate that neither stimulates nor brakes; each economy has its own, set by demographics and productivity).

The total return of holding a currency = interest **plus currency movement** — and the movement usually dwarfs the carry over trading horizons (1.4% annual differential vs 0.5% spot moves in three days). The marginal buyer isn't chasing the higher level; they're betting on the **change in the expected differential**. The current level is already in the price (apple logic); only shifts in the gap move it.

**All of macro FX in one sentence: betting on changes in the distance between two central banks' expected paths.** The 2-year yield spread is that distance's cleanest summary — pure enough that central banks themselves cite it when explaining their currency's moves.

Deeper still: nothing moves any price except supply and demand — but flows follow *expectations of the future*, not present conditions. Nobody buys CAD because it's good now; they buy because they believe it will turn out better than the current price assumes. **Demand is always the proximate cause; changing expectations are the cause of the cause.** In your trading horizon (minutes to weeks), fast speculative money dominates flow — which is why short-term FX is glued to rate expectations rather than trade balances.

---

# Part III — Layer 2: The Language of Options
*Question answered: "How much turbulence does the market expect — in which direction, and dated when?"*

Layer 1 has a blind spot: 90% hold odds can describe a genuinely calm market *or* a terrified one whose base case merely happens to be "hold." The difference lives in the **insurance market**.

## 1. Options as insurance

- **Put = crash insurance:** pays if price falls below your chosen level (strike) before expiry.
- **Call = melt-up insurance:** same, for upside (a risk if you're short).
- The **premium** is the price of the policy; like car insurance, it's "wasted" if nothing happens — you were buying certainty, not a lottery.
- Every policy has two sides: someone collects the premium and carries the risk. When "everyone is buying insurance," someone is selling it to everyone — and that seller's behavior matters too (Layer 3 territory).

## 2. Implied Volatility: the price of fear, read backwards

Insurers charge young drivers in busy neighborhoods more — premium = price of expected trouble. Options work identically: the more turbulence the market expects, the richer the insurance. Now run it backwards: from the *traded* price of insurance, extract the turbulence assumption baked into it. That is **Implied Volatility**:

> **IV = the market's expectation of future turbulence, extracted from real insurance prices.**

Quoted as an annualized percentage. Rule of 16: **daily expected move ≈ IV ÷ 16** (≈√252 trading days; volatility scales with the square root of time because daily wiggles partially cancel). EUR/USD IV of 5.2% → ≈0.33%/day → ≈37 pips of "normal day" priced.

IV says nothing about direction — only magnitude. Its absolute level matters less than its **change and comparison**: vs last week, vs the same event last cycle, vs realized volatility.

## 3. Risk Reversal: which side is scared?

At equal distance from spot, compare the put's IV to the call's:
- **RR = IV(call) − IV(put)**. Negative → downside insurance richer → fear points down. Positive → upside richer.
- **Never quote or think an RR without its sign.**
- Judge RR against **its own normal**, not zero: gold's RR is chronically call-skewed (gold *is* catastrophe insurance, so insurance-on-the-insurance always has buyers). The signal is the *deviation from its own baseline*.

RR is precious for two reasons. It's expensive to fake — millions in premium is monetized worry, not commentary. And it often **speaks before spot**: big money buys insurance first (cheap, quiet) and adjusts core positions later. A drifting RR under a calm spot is the market whispering.

## 4. Term structure and Event Premium: fear has an address

Normally, longer-dated insurance costs (annualized) the same or slightly more than short-dated. When a major event sits inside the short window, the short-dated policy must carry the entire event risk in a few days → its IV jumps *above* the long-dated. This **inversion is the signature of event premium**, and its size measures how much move is priced for the event.

Logic of extraction: 1-week IV containing the event ≈ average of "4 normal days + 1 event day"; 1-month IV ≈ the normal-day proxy; the excess belongs almost entirely to the event day, convertible to pips. (Formal method: variance subtraction.)

**The address rule:** *where* premium clusters on the expiry axis names the fear. Premium piled on the meeting-week expiry → fear of the meeting itself. All expiries rising together → fear with no calendar date (geopolitics, systemic risk). Also note the timing prior: event premium normally dominates in the final week; a violent IV jump three weeks early smells of off-calendar risk.

**Uses:**
- **The ruler:** knowing the event is priced for, say, 80 pips converts post-event judgment from feeling to measurement — actual move ÷ premium = surprise ratio (<0.5 event undersold; >1.5 genuine surprise).
- **Vol crush:** after the event passes, its premium drains from insurance prices. IV falling right after CPI + a central bank meeting is not complacency; it's a consumed event.

## 5. Combination patterns (Layer 1 × Layer 2)

- **False calm:** odds locked (95% hold) + IV jumping. *The tongue says relaxed; the money buys insurance. Believe the money.* Either the event's tone/projections are feared despite a locked decision, or an off-calendar risk is being smelled. The disagreement between layers *is* the signal.
- **Priced storm:** odds split 50-50 (maximum directional uncertainty) + only modest IV. The market says: "I don't know which way, but either way the move will be small" — both scenarios well-telegraphed.

---

# Part IV — Layer 3: The Language of Positioning
*Question answered: "Who has already bet, and how crowded is the boat?"*

Two worlds can share identical odds and IV: in world A everyone *thinks* EUR goes up but hasn't bought; in world B everyone thinks it *and has already bought*. The same news lands utterly differently in each. Only positioning data tells them apart.

## 1. The COT report: a map, not a weather report

The CFTC's weekly **Commitments of Traders** discloses futures positioning by trader type. Two structural facts to burn in:
- **It's a Tuesday snapshot released Friday** — always three days stale. After a big Wednesday–Friday move, the map is outdated.
- **Futures only** — the larger OTC market is invisible, but big players run both books in parallel, so futures are a valid *sample*, not a census.

In the TFF dataset, two categories matter most:
- **Leveraged Funds** — hedge funds, CTAs: fast money. Drives short-term price, prone to crowding. The star of this analysis.
- **Asset Managers** — pensions, insurers: slow money whose months-long repositioning builds the "clean" multi-month trends visible on monthly charts.

## 2. Net, and the only number that gives net meaning

**Net = Long − Short** per category. But a net figure alone is nearly meaningless — is −50k a lot? The answer only exists relative to **its own history**, via the **percentile**: where does today's net sit in its own 3-year distribution?

- ~50th percentile: unremarkable
- **>85–90: crowded long** / **<10–15: crowded short** — the red zones
- Convention (fix yours and never change it): percentile = % of weekly observations strictly *below* current net, so **low percentile = more short than usual**. Run 1-year alongside 3-year; agreement strengthens the signal.

## 3. Crowding creates asymmetry — the heart of Layer 3

Picture leveraged funds at the 92nd percentile long EUR:
- **Aligned news** (hawkish ECB): who is left to buy? Nearly everyone already has. Confirming news → muted move. *The fuel is spent.*
- **Opposing news** (dovish ECB): 92% of the boat must exit through one door. Each forced sale deepens the next holder's loss and forces *their* exit — a self-reinforcing cascade. **Squeeze:** an explosive move several times the "size of the news."

This solves the ancient mystery of "good news, price falls": aligned news meeting a full boat = spent fuel + profit-taking excuse. Most "inexplicable reversals" are this mechanism wearing a mask.

**The crowding rule — sharpest nuance of the layer:** saturation predicts **asymmetry, not direction**. A 0th-percentile short can stay saturated for weeks while price keeps falling. What it *guarantees* is that the two sides' fuel is unequal: news against the boat moves price far more violently than news with it. You are not being handed a forecast; you are being handed a map of which surprise hurts more.

(Also why the fade rule exists: countertrend trades are only legitimate with a measured crowding witness — a red percentile or demonstrated full pricing-in. "It's gone too far" is a feeling, not a witness. And the rule works in reverse: jumping *into* a live squeeze without a plan is gambling.)

---

# Part V — Integration: The Pricing Sheet

**Reaction = Gap (L1) × Priced sensitivity (L2) × Positioning asymmetry (L3)**

Before a major event, build the three-layer table:

| Layer | Data | Reading |
|---|---|---|
| 1 — Path | meeting odds + 12m path bps | locked or live? game on decision or tone? |
| 2 — Insurance | CVOL level/trend, term structure, RR | premium forming? fear's direction and address? |
| 3 — Position | lev funds net + percentile | which side's fuel is spent? squeeze risk where? |

Then write the **synthesis sentence** — one line naming the asymmetric risk. Worked example (ECB, July 2026): *"The market has priced, insured, and positioned for a dovish confirmation — meaning the dovish scenario is largely consumed; the real asymmetric risk is any hawkish shade in the tone landing on a boat that is 0th-percentile short EUR."*

Three agreeing layers = a coherent picture, **not a guaranteed trade**. Crowds can crowd further; squeezes can fail to fire; a central banker can land deliberately in the middle. The sheet maps asymmetry; it does not prophesy.

**Events contaminate each other.** Back-to-back events (ECB then Fed six days later) are not priced independently — the first one's tone shifts the second one's odds through the shared global narrative. Record both thermometers and watch the spillover.

---

# Part VI — The Discipline

Knowledge of mechanism does not fix a trading account; behavior does. Standing rules, each born from a real mistake:

1. **One-sentence entry test:** "The priced expectation is X; I believe reality diverges because Y." Can't write it → can't enter. (Anti-overtrading: the framework's natural state is "no trade here.")
2. **Fade rule:** never against strong momentum without measured saturation. Feelings of "too far" are how five years of losses happened.
3. **"I think" rule:** every "I think" becomes a measurement or gets deleted. Its only legal home is a labeled hypothesis (HYP).
4. **Missing-data rule:** if the answer isn't in the data at hand, the correct answer is the *name of the missing data*, not a confident guess. "I don't know; I need to see X" is a position that saves accounts.
5. **Banned words:** better/worse/good/bad/"it moved." Required: softer/harder *than expected*, above/below *baseline*, toward X, with sign and number.
6. **Observation hygiene:** daily OBS comes from today-minus-yesterday arithmetic, never from continuing yesterday's narrative. The day you copy the old story is the day the data turned.
7. **Feynman test:** a concept isn't yours until you can explain it in two plain sentences to a non-trader. Fluency in recognition ≠ ability to reconstruct.
8. **Institutions don't "know."** Clean multi-month trends are hundreds of small same-direction corrections (slow data digestion + slow institutional flow), not executed foreknowledge. If they knew, odds wouldn't update daily and CPI wouldn't move markets. The professional edge is better probability distributions, cheaper bets, and faster ego-free correction — so your job is scenarios, weights, and updates, not destination prophecy. Beware hindsight bias: monthly charts are its factory.
9. **Regime rule:** driver signs are not fixed (geopolitics flipped from haven-bid to inflationary-bearish for gold within one year). Several "backwards" reactions in a row → suspect regime change before doubting the mechanism.
10. **Manual before automated.** Run at least ten full event cycles by hand before building the software version. Automating a half-formed judgment freezes it; the sheet's columns after ten events *are* the system's spec.

---

# Part VII — Case Studies (July 2026, live)

**BoC, July 15 — the confirmed non-event.** Baseline ~93% hold, path +55bp. Outcome: hold, deliberately balanced tone (hawkish energy-inflation sentence deleted; oil-spillover warning kept in the presser). Path shifted ~3bp softer — a breeze. USD/CAD moved 9 pips. Lesson: a fully priced event with a balanced message produces nothing — *the mechanism's null result, observed live.* Bonus: the BoC's own statement attributed CAD weakness to the yield differential — the framework used by its subjects.

**US CPI, July 14 — the clean surprise.** All four prints below forecast. Predicted before looking: rates down → DXY down, gold up, USD/CAD down. All three confirmed within the hour. Lesson: a large, one-directional surprise executes the pyramid cleanly; mixed data doesn't.

**Warsh testimony + repricing, July 14–16 — the invisible event.** A months-telegraphed meeting moved 9 pips; an under-the-radar testimony plus one CPI moved the Fed path ~15bp in 48 hours and halved meeting odds. Lesson: **reaction size tracks surprise size, not event size.** Also: the US leg of the spread moved while the Canadian leg stood still — full attribution of USD/CAD's fall, done with two screenshots and a subtraction.

**ECB setup, July 23 — the first full three-layer sheet.** L1: 4.8% hike, path +53bp (locked meeting, tone game). L2: EUVL waking from post-event purge with the meeting inside the weekly window; hypothesis of put-EUR skew richening. L3: leveraged funds at the **0th percentile** — deepest EUR short in three years, built with momentum. Synthesis above. Outcome: pending — graded against the event premium ruler.

---

# Appendix — Glossary (one-liners)

- **Pricing-in:** absorption of expectations into price before the event.
- **Baseline:** the recorded snapshot of priced expectations that surprise is measured against.
- **OIS:** swap whose fixed rate = market's expected average overnight rate; the odds thermometer.
- **bp:** 0.01%. The native unit; percentages are step-dependent interpretations.
- **Hawkish/Dovish:** harder/softer than *baseline* — always relative.
- **Forward guidance:** future-facing statement language; moves the path directly.
- **IV:** expected turbulence extracted from option prices; annualized; ÷16 for daily.
- **Risk reversal:** call IV − put IV at equal distance; the direction of worry; never without sign.
- **Term structure inversion:** short-dated IV above long-dated; the signature and address of event premium.
- **Event premium:** the move priced for a specific event, in pips; the post-event ruler.
- **Vol crush:** premium draining after the event passes.
- **False calm:** locked odds + rising insurance; believe the money.
- **COT / TFF:** weekly CFTC positioning report; Tuesday snapshot, Friday release; futures only.
- **Net / Percentile:** long−short; its rank in its own 3-year history — the only context that gives it meaning.
- **Crowding / Squeeze:** saturated positioning; the forced-exit cascade when news opposes it.
- **Surprise ratio:** actual move ÷ event premium.
- **Attribution:** decomposing spot moves across drivers via DXY, commodities, and isolating crosses.
- **Regime shift:** a change in a driver's sign or weight; suspect it after repeated "backwards" reactions.
