#!/usr/bin/env python3
"""Daily brief — FULLY EXPLANATORY version.

Same data and rules as brief.py, but every line is written as a complete,
plain-language explanation: each term is defined where it appears, and each layer
ends with a "what this means for you" paragraph tying it to a decision.

Goal: you (or a non-trader friend) can read this top to bottom and understand the
whole market situation without any outside glossary. Understanding over brevity.

Reads: market_data.csv (root), data/cot.csv, data/prices.csv, data/calendar.csv.

Usage:
    python3 brief_explain.py                    # latest date, all pairs
    python3 brief_explain.py --date 2026-08-10
    python3 brief_explain.py --pair eurusd
"""
import argparse
import csv
import datetime as dt
import os
import textwrap
from collections import defaultdict

# thresholds (same as brief.py)
EVENT_WINDOW_DAYS = 7
PATH_SLAP_BP = 8.0
LOCKED_ODDS = 90.0
VOL_CRUSH = -0.15
VOL_JUMP = 0.40
PCTILE_LOW = 15
PCTILE_HIGH = 85
COT_3Y_WEEKS = 156
COT_1Y_WEEKS = 52

DATA = "data"
W = 78  # wrap width

PAIRS = {
    "eurusd": {"label": "EUR/USD", "ccy": "euro", "banks": ["ecb", "fed"],
               "cvol": "EUVL", "skew": "euvl_skew", "cot": "EUR",
               "price": "eurusd", "currencies": {"EUR", "USD"}},
    "usdcad": {"label": "USD/CAD", "ccy": "Canadian dollar", "banks": ["boc", "fed"],
               "cvol": "CAVL", "skew": "cavl_skew", "cot": "CAD",
               "price": "usdcad", "currencies": {"CAD", "USD"}},
}


# ── loading ───────────────────────────────────────────────────────────────
def load_sheet(p):
    r = {}
    if os.path.exists(p):
        for row in csv.DictReader(open(p)):
            r[row["date"]] = row
    return r


def load_calendar(p):
    return list(csv.DictReader(open(p))) if os.path.exists(p) else []


def load_cot(p):
    d = defaultdict(list)
    if os.path.exists(p):
        for row in csv.DictReader(open(p)):
            d[row["symbol"]].append(row)
        for s in d:
            d[s].sort(key=lambda x: x["report_date"])
    return d


def f(v):
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace("+", ""))
    except ValueError:
        return None


def ordinal(n):
    n = int(round(n))
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def prev_date(sheet, date):
    e = sorted(d for d in sheet if d < date)
    return e[-1] if e else None


def pct_rank(vals, cur, window=None):
    v = [x for x in vals if x is not None]
    if window:
        v = v[-window:]
    return round(100.0 * sum(1 for x in v if x < cur) / len(v), 1) if v else None


def wrap(s, indent="    "):
    return "\n".join(textwrap.fill(line, W, initial_indent=indent,
                                   subsequent_indent=indent) if line else ""
                     for line in s.split("\n"))


def upcoming(cal, date, currencies=None, days=EVENT_WINDOW_DAYS, min_impact="HIGH"):
    d0 = dt.date.fromisoformat(date)
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    out = []
    for e in cal:
        try:
            ed = dt.date.fromisoformat(e["date"])
        except (ValueError, KeyError):
            continue
        if not (0 <= (ed - d0).days <= days):
            continue
        if order.get(e.get("impact", "LOW"), 0) < order.get(min_impact, 2):
            continue
        if currencies is not None and e.get("currency") not in currencies:
            continue
        out.append(e)
    return sorted(out, key=lambda x: (x["date"], x.get("time", "")))


# ── the explanatory brief for one pair ─────────────────────────────────────
def explain_pair(pair, cfg, date, sheet, cal, cot):
    today = sheet.get(date, {})
    yest = sheet.get(prev_date(sheet, date), {})
    ccy = cfg["ccy"]
    out = []
    out.append("\n" + "─" * W)
    out.append(f"  {cfg['label']}  —  what the market is telling us about the {ccy}")
    out.append("─" * W)

    flags = []

    # ============ LAYER 1: RATES ============
    out.append("\n① INTEREST-RATE EXPECTATIONS  (what the market has already priced)")
    primary = cfg["banks"][0]
    bank = primary.upper()
    odds = f(today.get(f"{primary}_odds") or today.get(f"{primary}_odds_pct"))
    bps = f(today.get(f"{primary}_bps"))
    path = f(today.get(f"{primary}_path_12m"))
    ppath = f(yest.get(f"{primary}_path_12m"))

    if odds is None:
        out.append(wrap(f"No {bank} rate data available today, so we can't read what "
                        f"the market expects from the central bank. (Rule: when data "
                        f"is missing, we say so — we never guess.)"))
    else:
        out.append(wrap(
            f"The market currently prices a {odds:.0f}% chance that the {bank} (the "
            f"central bank behind the {ccy}) changes interest rates at its next "
            f"meeting. In plain terms: out of 100 possible futures, the market bets "
            f"{odds:.0f} of them include a rate move."))
        if path is not None:
            change = ""
            if ppath is not None:
                dp = path - ppath
                if abs(dp) >= 0.1:
                    dirw = "harder (more hikes expected)" if dp > 0 else "softer (fewer hikes expected)"
                    change = (f" Since yesterday this expectation moved {dp:+.1f} — the "
                              f"outlook got {dirw}.")
            out.append("")
            out.append(wrap(
                f"Looking further out, the market prices about {path:+.0f} basis points "
                f"of rate change over the next 12 months. (A 'basis point' is one "
                f"hundredth of a percent; {path:+.0f} basis points ≈ {path/100:+.2f}% of "
                f"total rate change priced for the year.){change}"))
        if odds >= LOCKED_ODDS:
            out.append("")
            out.append(wrap(
                f"⚑ This meeting is now 'LOCKED' — over 90% priced. That flips the "
                f"logic: since the move is almost fully expected, the decision itself "
                f"won't move the market much. The surprise would be if they do NOT "
                f"move. When something is this expected, the shock is the miss, not "
                f"the hit."))
        if path is not None and ppath is not None and abs(path - ppath) >= PATH_SLAP_BP:
            flags.append("repricing")
            out.append("")
            out.append(wrap(
                f"⚑ A big shift: the 12-month outlook jumped {path - ppath:+.1f} basis "
                f"points in a single day. A move this size means a real driver hit — "
                f"a data release, an oil move, or an official's speech. Something "
                f"happened; find out what."))

    # events
    ev_rel = upcoming(cal, date, cfg["currencies"])
    ev_all = upcoming(cal, date, None)
    out.append("")
    if ev_rel:
        nxt = ev_rel[0]
        flags.append("event_near")
        out.append(wrap(
            f"⚑ A relevant economic event is coming: {nxt['currency']} "
            f"{nxt['event']} on {nxt['date']}. 'Relevant' means it directly affects "
            f"the {cfg['label']} pair (only {' and '.join(sorted(cfg['currencies']))} "
            f"events count here). This is a potential catalyst — a day when the "
            f"market could actually move on news."))
    else:
        cset = " or ".join(sorted(cfg["currencies"]))
        out.append(wrap(
            f"No important {cset} event is scheduled in the next {EVENT_WINDOW_DAYS} "
            f"days. The calendar is quiet for this pair — no scheduled catalyst on "
            f"the horizon."))

    # ============ LAYER 2: VOL ============
    out.append("\n② FEAR IN THE OPTIONS MARKET  (how nervous, and about which direction)")
    cvol = f(today.get(cfg["cvol"]))
    cvol_p = f(yest.get(cfg["cvol"]))
    skew = f(today.get(cfg["skew"]))
    skew_p = f(yest.get(cfg["skew"]))
    if cvol is None:
        out.append(wrap(f"No volatility data for {cfg['cvol']} today — can't read the "
                        f"fear level. (We note the gap rather than guess.)"))
    else:
        seg = (f"The 'implied volatility' — how much movement the market expects, "
               f"read from the price of options (insurance contracts) — is {cvol:.2f}.")
        if cvol_p is not None:
            d = cvol - cvol_p
            if d <= VOL_CRUSH:
                seg += (f" It fell {d:+.2f} from yesterday. Falling fear usually means "
                        f"a worry has passed — the market paid for insurance, the "
                        f"event came and went, and now that insurance is draining out. "
                        f"Calm after a storm.")
            elif d >= VOL_JUMP:
                flags.append("vol_jump")
                seg += (f" ⚑ It JUMPED {d:+.2f} from yesterday — a sharp rise in fear. "
                        f"Something is moving. The level alone doesn't say which "
                        f"direction, so we read the skew next to locate it.")
            else:
                seg += f" It changed {d:+.2f} from yesterday — a small, calm move."
        out.append(wrap(seg))
    if skew is not None:
        side = "downside (a FALL)" if skew < 0 else "upside (a RISE)"
        seg = (f"The 'skew' is {skew:+.2f}. Skew tells us which direction the market "
               f"fears more, by comparing the cost of insurance against a fall versus "
               f"a rise. A NEGATIVE number means insurance against a {('fall' if skew<0 else 'rise')} "
               f"is more expensive — so the market's bigger fear is a {side} in the {ccy}.")
        if skew_p is not None:
            if abs(skew) < abs(skew_p):
                seg += (f" Compared to yesterday ({skew_p:+.2f}), it's moving toward "
                        f"zero — meaning that fear is EASING.")
            else:
                seg += (f" Compared to yesterday ({skew_p:+.2f}), it's getting more "
                        f"extreme — meaning that fear is BUILDING.")
        out.append("")
        out.append(wrap(seg))

    # ============ LAYER 3: POSITIONING ============
    out.append("\n③ WHO HAS ALREADY BET  (positioning — the most powerful layer)")
    rows = cot.get(cfg["cot"], [])
    if not rows:
        out.append(wrap(f"No positioning (COT) data for {cfg['cot']} — can't see who's "
                        f"crowded. (Noted, not guessed.)"))
    else:
        latest = rows[-1]
        ns = f(latest["net_spec"])
        nc = f(latest.get("net_comm"))
        nets = [f(r["net_spec"]) for r in rows]
        p3 = pct_rank(nets, ns, COT_3Y_WEEKS)
        direction = "SHORT (betting it falls)" if ns < 0 else "LONG (betting it rises)"
        out.append(wrap(
            f"This data (called COT) shows what big traders have actually bet, "
            f"reported weekly. The fast-money funds — hedge funds, the ones that "
            f"drive short-term price — are net {direction} the {ccy} by "
            f"{abs(ns):,.0f} contracts."))
        if p3 is not None:
            crowded = p3 <= PCTILE_LOW or p3 >= PCTILE_HIGH
            out.append("")
            seg = (f"But the raw number means little on its own. What matters is how "
                   f"this compares to their own history: it's at the {ordinal(p3)} "
                   f"percentile of the last 3 years. ")
            if crowded:
                flags.append("crowded")
                seg += (f"That is an EXTREME — they have almost never been positioned "
                        f"this way. The boat is dangerously one-sided.")
            else:
                seg += (f"That's fairly normal — not a crowded, one-sided bet. "
                        f"({ordinal(p3)} percentile sits in the middle range.)")
            out.append(wrap(seg))
        # composition (Rule 13)
        if nc is not None:
            same = (ns > 0) == (nc > 0)
            out.append("")
            if same:
                out.append(wrap(
                    f"Composition check: the slow money (pension funds, insurers) is "
                    f"betting the SAME direction as the fast money. When both agree, "
                    f"it's a genuine, real conviction — not just mechanical hedging. "
                    f"This is a true one-directional consensus."))
            else:
                out.append(wrap(
                    f"Composition check: the slow money (pensions, insurers) is "
                    f"betting the OPPOSITE direction from the fast money. In currencies "
                    f"this usually means a genuine disagreement between patient and "
                    f"fast capital — and for short-term trading, the fast money is the "
                    f"one that drives your timeframe."))
        # asymmetry payoff
        if p3 is not None and (p3 <= PCTILE_LOW or p3 >= PCTILE_HIGH):
            crowd_dir = "short" if ns < 0 else "long"
            squeeze = "UP" if ns < 0 else "DOWN"
            good_bad = "GOOD news for" if ns < 0 else "BAD news for"
            out.append("")
            out.append(wrap(
                f"WHAT THIS MEANS FOR YOU: because almost everyone is already "
                f"{crowd_dir}, there's hardly anyone left to bet that way. So news that "
                f"agrees with the crowd moves price very little — it's already priced "
                f"in. But {good_bad} the {ccy} forces the whole crowd to run for the "
                f"exit at once, and the price snaps {squeeze} violently — this is "
                f"called a 'squeeze'. So the real danger here is a sharp move "
                f"{squeeze}, NOT in the direction the crowd is betting."))
        # staleness
        try:
            lag = (dt.date.fromisoformat(date) - dt.date.fromisoformat(latest["report_date"])).days
        except ValueError:
            lag = None
        out.append("")
        note = (f"(This positioning data is from {latest['report_date']}"
                + (f", {lag} days ago" if lag is not None else "")
                + ". It's a weekly snapshot, so being a few days old is normal"
                + ("; but over 10 days means a release was missed — re-run the "
                   "collector." if (lag or 0) > 10 else ".") + ")")
        out.append(wrap(note))

    # ============ THE VERDICT ============
    out.append("\n" + "═" * W)
    if "vol_jump" in flags and "event_near" not in flags and "repricing" not in flags:
        out.append(wrap(
            "TODAY'S READ — INVESTIGATE: Fear is rising in the options market, but "
            "nothing is scheduled on the calendar to explain it. That contradiction "
            "is a warning sign — something is moving that isn't public news yet "
            "(geopolitics, a surprise headline). Don't trade blind: go find out what "
            "the market smells before it becomes obvious.", indent="  "))
    elif "event_near" in flags:
        out.append(wrap(
            "TODAY'S READ — SIGNAL DAY: A relevant catalyst is near. This is a day "
            "when the market could genuinely move. But do NOT place a bet before the "
            "event guessing what it will say — that's gambling on what's already "
            "priced in. Wait for the news, measure how it compares to expectations, "
            "and trade the reaction. Direction comes from your chart; this just tells "
            "you today is worth watching closely.", indent="  "))
    elif "repricing" in flags:
        out.append(wrap(
            "TODAY'S READ — SIGNAL DAY: Rate expectations moved hard with no "
            "scheduled meeting, so a live driver is at work. Identify what moved it "
            "and watch whether the move follows through.", indent="  "))
    elif "crowded" in flags:
        out.append(wrap(
            "TODAY'S READ — NOISE DAY, BUT CROWDED: No relevant catalyst is near, so "
            "there's no reason to act today. BUT positioning is at an extreme. The "
            "one rule this creates: do NOT add to the crowded side — you'd be the "
            "last one onto a full boat. And stay alert, because any surprise could "
            "trigger a squeeze against that crowd.", indent="  "))
    else:
        out.append(wrap(
            "TODAY'S READ — NOISE DAY: No relevant catalyst is near, fear is calm, "
            "and positioning is not extreme. Nothing lines up. The correct action is "
            "no action. Most days are like this, and skipping them is exactly how you "
            "avoid the small, pointless trades that bleed an account. Doing nothing "
            "today is a disciplined win, not a wasted day.", indent="  "))
    out.append("═" * W)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=None)
    ap.add_argument("--pair", default=None)
    ap.add_argument("--datadir", default=DATA)
    ap.add_argument("--sheet", default="market_data.csv")
    a = ap.parse_args()

    sheet = load_sheet(a.sheet)
    cal = load_calendar(os.path.join(a.datadir, "calendar.csv"))
    cot = load_cot(os.path.join(a.datadir, "cot.csv"))
    if not sheet:
        raise SystemExit(f"no sheet at {a.sheet} — run build_sheet.py first")

    date = a.date or max(sheet)
    pairs = {a.pair: PAIRS[a.pair]} if a.pair else PAIRS

    print("╔" + "═" * (W - 2) + "╗")
    line = f"  DAILY MARKET BRIEF — {date}  (full explanatory version)"
    print(line + " " * (W - len(line) - 1) + "")
    print("  Read top to bottom. Every term is explained where it appears.")
    print("╚" + "═" * (W - 2) + "╝")
    for p, cfg in pairs.items():
        print(explain_pair(p, cfg, date, sheet, cal, cot))
    print("\n  Remember: this brief gives you CONTEXT, never a buy/sell order.")
    print("  Direction is your decision, from the chart. This is the ground you")
    print("  stand on — whether today is solid or mined.\n")


if __name__ == "__main__":
    main()
