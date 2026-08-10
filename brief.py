#!/usr/bin/env python3
"""Daily brief — the narrative layer of the price-in platform.

Reads collected data (rates+vol via market_data.csv, plus cot/prices/calendar),
evaluates the dashboard rules per traded pair, and prints a plain-language brief:
per pair, three layers + CONTEXT / WATCH / VERDICT.

Does NOT decide direction. Reports context: signal day or noise, where the
positioning asymmetry is, what to watch. Direction stays with the chart.

Every sentence traces to a rule in dashboard-rules.md — transparency over magic.
No free-form analysis; only coded if/then rules rendered in words.

Design notes from a month of practice:
- Calendar: SHOW all upcoming events (full picture), but only currency-RELEVANT
  events drive the VERDICT (an AUD event must not make EUR/USD a signal day).
- COT: composition first (Rule 13) — leveraged vs commercial — then percentile
  vs the symbol's own 3y/1y history (Rule 9: crowding = asymmetry, not direction).
  Always flag the Tuesday-snapshot lag; warn if the report is stale (>7d).
- Missing data is named, never fabricated (Rule 7).
- Thresholds are named constants below, tunable as practice sharpens them.

Usage:
    python3 brief.py                     # latest date, all pairs
    python3 brief.py --date 2026-08-10
    python3 brief.py --pair eurusd
"""
import argparse
import csv
import datetime as dt
import os
from collections import defaultdict

# ── tunable thresholds ─────────────────────────────────────────────────────
EVENT_WINDOW_DAYS = 7
PATH_SHIFT_BP = 5.0
PATH_SLAP_BP = 8.0
MEETING_MOVE_BP = 3.0
LOCKED_ODDS = 90.0
VOL_CRUSH = -0.15
VOL_JUMP = 0.40
PCTILE_LOW = 15
PCTILE_HIGH = 85
COT_3Y_WEEKS = 156
COT_1Y_WEEKS = 52
SKEW_HIST_MIN = 20
SKEW_EXTREME_PCT = 10

DATA = "data"

PAIRS = {
    "eurusd": {
        "label": "EUR/USD",
        "banks": ["ecb", "fed"],
        "cvol": "EUVL", "skew": "euvl_skew",
        "cot": "EUR",
        "price": "eurusd", "filters": ["dxy"],
        "currencies": {"EUR", "USD"},
    },
    "usdcad": {
        "label": "USD/CAD",
        "banks": ["boc", "fed"],
        "cvol": "CAVL", "skew": "cavl_skew",
        "cot": "CAD",
        "price": "usdcad", "filters": ["dxy", "wti"],
        "currencies": {"CAD", "USD"},
    },
}


def load_sheet(path):
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path) as fh:
        for r in csv.DictReader(fh):
            rows[r["date"]] = r
    return rows


def load_calendar(path):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return list(csv.DictReader(fh))


def load_cot(path):
    by_symbol = defaultdict(list)
    if not os.path.exists(path):
        return by_symbol
    with open(path) as fh:
        for r in csv.DictReader(fh):
            by_symbol[r["symbol"]].append(r)
    for sym in by_symbol:
        by_symbol[sym].sort(key=lambda x: x["report_date"])
    return by_symbol


def load_prices(path):
    px = {}
    if not os.path.exists(path):
        return px
    with open(path) as fh:
        for r in csv.DictReader(fh):
            px[(r["date"], r["series"])] = r
    return px


def f(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace("+", ""))
    except ValueError:
        return None


def ordinal(n):
    n = int(round(n))
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def prev_date(sheet, date):
    earlier = sorted(d for d in sheet if d < date)
    return earlier[-1] if earlier else None


def pct_rank(values, current, window=None):
    v = [x for x in values if x is not None]
    if window:
        v = v[-window:]
    if not v:
        return None
    return round(100.0 * sum(1 for x in v if x < current) / len(v), 1)


def cot_reading(cot_rows):
    if not cot_rows:
        return None
    latest = cot_rows[-1]
    net_spec = f(latest["net_spec"])
    net_comm = f(latest.get("net_comm"))
    if net_spec is None:
        return None
    nets = [f(r["net_spec"]) for r in cot_rows]
    composition = None
    if net_comm is not None:
        composition = "aligned" if (net_spec > 0) == (net_comm > 0) else "mirror"
    return {
        "net_spec": net_spec, "net_comm": net_comm, "composition": composition,
        "date": latest["report_date"],
        "pctile_3y": pct_rank(nets, net_spec, COT_3Y_WEEKS),
        "pctile_1y": pct_rank(nets, net_spec, COT_1Y_WEEKS),
    }


def skew_extreme(sheet, col, current, asof_date):
    hist = []
    for d in sorted(sheet):
        if d > asof_date:
            break
        v = f(sheet[d].get(col))
        if v is not None:
            hist.append(v)
    hist = hist[-252:]
    if len(hist) < SKEW_HIST_MIN or current is None:
        return (False, None, None)
    s = sorted(hist)
    lo = s[max(0, int(len(s) * SKEW_EXTREME_PCT / 100) - 1)]
    hi = s[min(len(s) - 1, int(len(s) * (100 - SKEW_EXTREME_PCT) / 100))]
    return (current <= lo or current >= hi, lo, hi)


def upcoming_events(calendar, date, days=EVENT_WINDOW_DAYS, currencies=None,
                    min_impact="HIGH"):
    d0 = dt.date.fromisoformat(date)
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    thr = order.get(min_impact, 2)
    out = []
    for e in calendar:
        try:
            ed = dt.date.fromisoformat(e["date"])
        except (ValueError, KeyError):
            continue
        if not (0 <= (ed - d0).days <= days):
            continue
        if order.get(e.get("impact", "LOW"), 0) < thr:
            continue
        if currencies is not None and e.get("currency") not in currencies:
            continue
        out.append(e)
    return sorted(out, key=lambda x: (x["date"], x.get("time", "")))


def brief_for_pair(pair, cfg, date, sheet, calendar, cot, prices):
    today = sheet.get(date, {})
    pd = prev_date(sheet, date)
    yest = sheet.get(pd, {}) if pd else {}
    lines = {"rates": [], "vol": [], "pos": []}
    watch, flags = [], []

    # Layer 1
    primary = cfg["banks"][0]
    odds = f(today.get(f"{primary}_odds") or today.get(f"{primary}_odds_pct"))
    bps = f(today.get(f"{primary}_bps"))
    path = f(today.get(f"{primary}_path_12m"))
    ppath = f(yest.get(f"{primary}_path_12m"))
    pbps = f(yest.get(f"{primary}_bps"))
    if odds is None:
        lines["rates"].append(f"no {primary.upper()} rate data")
    else:
        seg = f"{primary.upper()} next-mtg {odds:.0f}%"
        if bps is not None:
            seg += f" ({bps:+.1f}bp)"
        if path is not None:
            seg += f", 12m path {path:+.1f}"
            if ppath is not None:
                seg += f" ({path - ppath:+.1f} vs prev)"
        lines["rates"].append(seg)
        if odds >= LOCKED_ODDS:
            lines["rates"].append("meeting LOCKED (>90%) — the surprise is the MISS, not the hit")
        if path is not None and ppath is not None:
            dp = path - ppath
            if abs(dp) >= PATH_SLAP_BP:
                lines["rates"].append(f"path {dp:+.1f}bp in a day — SLAP (real driver hit)")
                flags.append("repricing")
            elif abs(dp) >= PATH_SHIFT_BP:
                lines["rates"].append(f"path {dp:+.1f}bp — notable shift")
        if bps is not None and pbps is not None and abs(bps - pbps) >= MEETING_MOVE_BP:
            lines["rates"].append(f"next-mtg {bps - pbps:+.1f}bp — meeting repricing")

    events_all = upcoming_events(calendar, date, currencies=None)
    events_rel = upcoming_events(calendar, date, currencies=cfg["currencies"])
    if events_rel:
        nxt = events_rel[0]
        lines["rates"].append(
            f"⚑ {nxt['currency']} {nxt['event']} {nxt['date']} — relevant event near")
        flags.append("event_near")
    else:
        lines["rates"].append(
            f"no relevant ({'/'.join(sorted(cfg['currencies']))}) HIGH event in "
            f"{EVENT_WINDOW_DAYS}d → quiet on the calendar")

    # Layer 2
    cvol = f(today.get(cfg["cvol"]))
    cvol_p = f(yest.get(cfg["cvol"]))
    skew = f(today.get(cfg["skew"]))
    skew_p = f(yest.get(cfg["skew"]))
    if cvol is None:
        lines["vol"].append(f"no {cfg['cvol']} data")
    else:
        seg = f"{cfg['cvol']} {cvol:.2f}"
        if cvol_p is not None:
            d = cvol - cvol_p
            seg += f" ({d:+.2f})"
            if d <= VOL_CRUSH and not events_rel:
                lines["vol"].append("vol crushing — event premium draining, worry fading")
            if d >= VOL_JUMP:
                lines["vol"].append("⚑ vol JUMPING — something is moving; check skew for the side")
                flags.append("vol_jump")
        lines["vol"].insert(0, seg)
    if skew is not None:
        side = "put" if skew < 0 else "call"
        seg = f"skew {skew:+.2f} ({side}-tilted)"
        if skew_p is not None:
            seg += (", easing toward zero" if abs(skew) < abs(skew_p)
                    else ", deepening (fear building)")
        lines["vol"].append(seg)
        ext, lo, hi = skew_extreme(sheet, cfg["skew"], skew, date)
        if ext:
            watch.append(f"{cfg['cvol']} skew {skew:+.2f} extreme vs its own 1y band "
                         f"[{lo:+.2f},{hi:+.2f}] — {side}-insurance rich, reversal/vol-crush risk")

    # Layer 3
    cot_read = cot_reading(cot.get(cfg["cot"], []))
    if not cot_read:
        lines["pos"].append(f"no COT data for {cfg['cot']}")
    else:
        ns = cot_read["net_spec"]
        direction = "short" if ns < 0 else "long"
        seg = f"Lev funds net {ns:+,.0f} ({direction})"
        p3 = cot_read["pctile_3y"]
        if p3 is not None:
            seg += f", {ordinal(p3)} pctile 3y"
        lines["pos"].append(seg)
        comp = cot_read["composition"]
        if comp == "aligned":
            lines["pos"].append("fast & slow money SAME side → genuine directional consensus")
        elif comp == "mirror":
            lines["pos"].append("fast vs slow OPPOSITE → check structural/basis "
                                "(in FX usually a real fast-vs-slow disagreement)")
        if p3 is not None and (p3 <= PCTILE_LOW or p3 >= PCTILE_HIGH):
            opp = "up" if direction == "short" else "down"
            lines["pos"].append(f"→ crowded {direction} (extreme). "
                                f"Asymmetry: news AGAINST the boat = squeeze {opp}")
            watch.append(f"{cfg['label']} positioning extreme ({ordinal(p3)} pctile) — "
                         f"a move against the crowd squeezes hard {opp}")
            flags.append("crowded")
        try:
            lag = (dt.date.fromisoformat(date) - dt.date.fromisoformat(cot_read["date"])).days
        except ValueError:
            lag = None
        note = f"(COT as of {cot_read['date']}"
        if lag is not None:
            # COT is weekly, so a few days' age is normal; only warn if a
            # weekly release looks actually missed (>10 days).
            note += f" — {lag}d old" + ("; STALE, re-run collector" if lag > 10 else "")
        note += ")"
        lines["pos"].append(note)

    divergence = ("vol_jump" in flags and "event_near" not in flags
                  and "repricing" not in flags)
    if divergence:
        context = "Vol moving with no relevant scheduled event — off-calendar force. Investigate."
        verdict = "INVESTIGATE — vol jump without a relevant event. Find the driver first."
    elif "event_near" in flags:
        context = "Relevant event window OPEN — a catalyst is near."
        verdict = "SIGNAL DAY — relevant event near; watch the reaction, don't pre-position blindly."
    elif "repricing" in flags:
        context = "Rates repricing hard with no meeting — a driver is live."
        verdict = "SIGNAL DAY — path moving; identify the driver, watch for follow-through."
    elif "crowded" in flags:
        context = "Quiet on relevant calendar, but positioning is crowded — asymmetric setup."
        verdict = ("NOISE DAY on the calendar — but crowd is extreme: "
                   "don't ADD to the crowded side; watch for a squeeze against it.")
    else:
        context = "Quiet window — no relevant catalyst, no positioning extreme."
        verdict = "NOISE DAY — default: no trade. Preserve capital."

    return {"cfg": cfg, "lines": lines, "events_all": events_all,
            "watch": watch, "context": context, "verdict": verdict}


def render(date, briefs):
    print("=" * 64)
    print(f"  DAILY BRIEF — {date}")
    print("=" * 64)
    for b in briefs:
        cfg = b["cfg"]
        print(f"\n▌ {cfg['label']}")
        for layer, tag in [("rates", "rates"), ("vol", "vol  "), ("pos", "pos  ")]:
            for i, ln in enumerate(b["lines"][layer]):
                head = f"  {tag}:" if i == 0 else "        "
                print(f"{head} {ln}")
        if b["events_all"]:
            rel = cfg["currencies"]
            print("  cal  : upcoming (7d):")
            for e in b["events_all"][:6]:
                mark = "•" if e.get("currency") in rel else " "
                print(f"        {mark} {e['date']} {e.get('time','')} "
                      f"{e.get('currency','')} {e.get('event','')}")
        print(f"  ▶ CONTEXT: {b['context']}")
        for w in b["watch"]:
            print(f"  ▶ WATCH:   {w}")
        print(f"  ▶ VERDICT: {b['verdict']}")
    print("\n" + "=" * 64)
    print("  Direction is yours (the chart). This is the ground you stand on.")
    print("  • = event relevant to that pair (drives the verdict).")
    print("=" * 64)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=None)
    ap.add_argument("--pair", default=None)
    ap.add_argument("--datadir", default=DATA)
    ap.add_argument("--sheet", default="market_data.csv")
    a = ap.parse_args()

    sheet = load_sheet(a.sheet)
    calendar = load_calendar(os.path.join(a.datadir, "calendar.csv"))
    cot = load_cot(os.path.join(a.datadir, "cot.csv"))
    prices = load_prices(os.path.join(a.datadir, "prices.csv"))
    if not sheet:
        raise SystemExit(f"no sheet at {a.sheet} — run build_sheet.py first")

    date = a.date or max(sheet)
    pairs = {a.pair: PAIRS[a.pair]} if a.pair else PAIRS
    briefs = [brief_for_pair(p, cfg, date, sheet, calendar, cot, prices)
              for p, cfg in pairs.items()]
    render(date, briefs)


if __name__ == "__main__":
    main()