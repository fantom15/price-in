#!/usr/bin/env python3
"""Daily brief — the narrative layer of the price-in platform.

Reads the collected data (rates, cvol, cot, prices, calendar), evaluates the
dashboard rules per traded pair, and prints a plain-language brief:
per pair, three layers + CONTEXT / WATCH / VERDICT.

This does NOT decide direction. It reports context: is today a signal day or
noise, where is the asymmetry, what to watch. Direction stays with the chart.

Every sentence traces to a rule in dashboard-rules.md — transparency over magic.
No free-form analysis; only the rules you wrote, rendered in words.

Usage:
    python3 brief.py                    # today, all pairs
    python3 brief.py --date 2026-08-05  # a specific day
    python3 brief.py --pair eurusd
"""
import argparse
import csv
import datetime as dt
import os
from collections import defaultdict

DATA = "data"

# ── pair configuration ────────────────────────────────────────────────────
# Each pair maps to the columns/symbols that describe it across the layers.
PAIRS = {
    "eurusd": {
        "label": "EUR/USD",
        "banks": ["ecb", "fed"],          # rates legs (primary first)
        "cvol": "EUVL", "skew": "euvl_skew",
        "cot": "EUR",                      # COT symbol
        "price": "eurusd", "filters": ["dxy"],
    },
    "usdcad": {
        "label": "USD/CAD",
        "banks": ["boc", "fed"],
        "cvol": "CAVL", "skew": "cavl_skew",
        "cot": "CAD",
        "price": "usdcad", "filters": ["dxy", "wti"],
    },
}

# ── data loading ──────────────────────────────────────────────────────────

def load_sheet(path):
    """market_data.csv → {date: {col: value}}. Values kept as strings; caller floats."""
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        for r in csv.DictReader(f):
            rows[r["date"]] = r
    return rows


def load_calendar(path):
    """calendar.csv → list of event dicts."""
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def load_cot(path):
    """cot.csv → {symbol: [rows sorted by date]} for percentile math."""
    by_symbol = defaultdict(list)
    if not os.path.exists(path):
        return by_symbol
    with open(path) as f:
        for r in csv.DictReader(f):
            by_symbol[r["symbol"]].append(r)
    for sym in by_symbol:
        by_symbol[sym].sort(key=lambda x: x["report_date"])
    return by_symbol


def load_prices(path):
    """prices.csv → {(date, series): row}."""
    px = {}
    if not os.path.exists(path):
        return px
    with open(path) as f:
        for r in csv.DictReader(f):
            px[(r["date"], r["series"])] = r
    return px


# ── helpers ───────────────────────────────────────────────────────────────

def f(v):
    """Parse a possibly-empty/None/signed string to float or None."""
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace("+", ""))
    except ValueError:
        return None


def prev_date(sheet, date):
    """The most recent sheet date strictly before `date`."""
    earlier = sorted(d for d in sheet if d < date)
    return earlier[-1] if earlier else None


def pct_rank(values, current, window=None):
    """Percentile of `current` within `values` (% strictly below). Low = more short."""
    v = [x for x in values if x is not None]
    if window:
        v = v[-window:]
    if not v:
        return None
    return round(100.0 * sum(1 for x in v if x < current) / len(v), 1)


def cot_reading(cot_rows):
    """Latest net_spec + its 3y/1y percentile (weekly ≈ 156/52 reports)."""
    if not cot_rows:
        return None
    nets = [f(r["net_spec"]) for r in cot_rows]
    cur = nets[-1]
    if cur is None:
        return None
    return {
        "net": cur,
        "date": cot_rows[-1]["report_date"],
        "pctile_3y": pct_rank(nets, cur, 156),
        "pctile_1y": pct_rank(nets, cur, 52),
    }


def upcoming_events(calendar, date, days=7, min_impact="HIGH"):
    """High-impact events within `days` after `date` (for the quiet-window rule)."""
    d0 = dt.date.fromisoformat(date)
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    thr = order.get(min_impact, 2)
    out = []
    for e in calendar:
        try:
            ed = dt.date.fromisoformat(e["date"])
        except (ValueError, KeyError):
            continue
        if 0 <= (ed - d0).days <= days and order.get(e.get("impact", "LOW"), 0) >= thr:
            out.append(e)
    return sorted(out, key=lambda x: x["date"])


# ── the rules → sentences (each maps to dashboard-rules.md) ────────────────

def brief_for_pair(pair, cfg, date, sheet, calendar, cot, prices):
    today = sheet.get(date, {})
    pd = prev_date(sheet, date)
    yest = sheet.get(pd, {}) if pd else {}

    lines = {"rates": [], "vol": [], "pos": []}
    watch, verdict_bits = [], []

    # ---- Layer 1: rates ----
    primary = cfg["banks"][0]
    odds = f(today.get(f"{primary}_odds") or today.get(f"{primary}_odds_pct"))
    bps = f(today.get(f"{primary}_bps"))
    path = f(today.get(f"{primary}_path_12m"))
    ppath = f(yest.get(f"{primary}_path_12m"))
    evs = upcoming_events(calendar, date, 7, "HIGH")

    if odds is not None:
        seg = f"{primary.upper()} next-mtg {odds:.0f}%"
        if bps is not None:
            seg += f" ({bps:+.1f}bp)"
        if path is not None:
            seg += f", 12m path {path:+.1f}"
            if ppath is not None:
                seg += f" ({path - ppath:+.1f} vs prev)"
        lines["rates"].append(seg)
    # R3 locked-meeting (reverse)
    if odds is not None and odds >= 90:
        lines["rates"].append("meeting LOCKED (>90%) — surprise is the MISS, not the hit")
    # R1 / R4 quiet vs tripwire
    if evs:
        nxt = evs[0]
        lines["rates"].append(f"⚑ {nxt['currency']} {nxt['event']} on {nxt['date']} — window closing")
        verdict_bits.append("event near")
    else:
        lines["rates"].append("no high-impact event in 7d → quiet window")
        verdict_bits.append("quiet")

    # ---- Layer 2: vol ----
    cvol = f(today.get(cfg["cvol"]))
    cvol_p = f(yest.get(cfg["cvol"]))
    skew = f(today.get(cfg["skew"]))
    skew_p = f(yest.get(cfg["skew"]))
    if cvol is not None:
        seg = f"{cfg['cvol']} {cvol:.2f}"
        if cvol_p is not None:
            d = cvol - cvol_p
            seg += f" ({d:+.2f})"
            # R5 vol crush
            if d <= -0.15 and not evs:
                lines["vol"].append("vol crushing — event premium draining, worry fading")
            # R7 vol jump = alarm
            if d >= 0.40:
                lines["vol"].append("⚑ vol JUMPING — something is moving; check skew for direction")
                verdict_bits.append("vol spike")
        lines["vol"].insert(0, seg)
    if skew is not None:
        side = "put" if skew < 0 else "call"
        seg = f"skew {skew:+.2f} ({side}-tilted)"
        if skew_p is not None:
            drift = "toward zero (fear easing)" if abs(skew) < abs(skew_p) else "deeper (fear building)"
            seg += f", {drift}"
        lines["vol"].append(seg)
        # R6 extreme skew (rough; real version uses 1y band)
        if abs(skew) >= 0.65:
            watch.append(f"{cfg['cvol']} skew extreme ({skew:+.2f}) — {side}-insurance rich; "
                         f"reversal + vol-crush risk on that side")

    # ---- Layer 3: positioning ----
    cot_read = cot_reading(cot.get(cfg["cot"], []))
    if cot_read:
        p3, p1 = cot_read["pctile_3y"], cot_read["pctile_1y"]
        net = cot_read["net"]
        direction = "short" if net < 0 else "long"
        seg = f"Lev funds net {net:+,.0f} ({direction})"
        if p3 is not None:
            seg += f", {p3:.0f}th pctile 3y"
        lines["pos"].append(seg)
        # R8 / R9 crowding = asymmetry
        if p3 is not None and (p3 <= 15 or p3 >= 85):
            zone = "crowded " + direction
            opp = "up" if direction == "short" else "down"
            lines["pos"].append(f"→ {zone} (extreme). Asymmetry: news AGAINST the boat = squeeze {opp}")
            watch.append(f"{cfg['label']} positioning extreme — a move against the crowd squeezes hard {opp}")
            verdict_bits.append("crowded")
        # note on staleness (COT is a Tuesday snapshot)
        lines["pos"].append(f"(COT as of {cot_read['date']} — 3d lag)")

    # ---- context sentence + verdict ----
    if "event near" in verdict_bits:
        context = "Event window OPEN — a catalyst is near. Signal day: stay alert."
        verdict = "SIGNAL DAY — event near; watch the reaction, don't pre-position blindly."
    elif "vol spike" in verdict_bits:
        context = "Vol is moving without a scheduled event — something off-calendar. Investigate."
        verdict = "INVESTIGATE — vol jump, no event. Find the driver before acting."
    else:
        context = "Quiet window, no near catalyst."
        if "crowded" in verdict_bits:
            context += " Positioning is crowded — the setup is asymmetric."
            verdict = "NOISE DAY — no catalyst. But crowd is extreme: don't ADD to the crowded side."
        else:
            verdict = "NOISE DAY — no catalyst, no extreme. Default: no trade."

    return {"cfg": cfg, "lines": lines, "watch": watch,
            "context": context, "verdict": verdict}


# ── render ────────────────────────────────────────────────────────────────

def render(date, briefs):
    print("=" * 60)
    print(f"  DAILY BRIEF — {date}")
    print("=" * 60)
    for b in briefs:
        cfg = b["cfg"]
        print(f"\n▌ {cfg['label']}")
        for layer, tag in [("rates", "rates"), ("vol", "vol "), ("pos", "pos ")]:
            for i, ln in enumerate(b["lines"][layer]):
                head = f"  {tag}:" if i == 0 else "        "
                print(f"{head} {ln}")
        print(f"  ▶ CONTEXT: {b['context']}")
        if b["watch"]:
            for w in b["watch"]:
                print(f"  ▶ WATCH:   {w}")
        print(f"  ▶ VERDICT: {b['verdict']}")
    print("\n" + "=" * 60)
    print("  Direction is yours (the chart). This is the ground you stand on.")
    print("=" * 60)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: latest in sheet)")
    ap.add_argument("--pair", default=None, help="single pair (e.g. eurusd)")
    ap.add_argument("--datadir", default=DATA, help="dir with cot/prices/calendar csvs")
    ap.add_argument("--sheet", default="market_data.csv",
                    help="path to market_data.csv (default: project root)")
    a = ap.parse_args()

    sheet = load_sheet(a.sheet)
    calendar = load_calendar(os.path.join(a.datadir, "calendar.csv"))
    cot = load_cot(os.path.join(a.datadir, "cot.csv"))
    prices = load_prices(os.path.join(a.datadir, "prices.csv"))

    if not sheet:
        raise SystemExit("no market_data.csv — run build_sheet.py first")

    date = a.date or max(sheet)
    pairs = {a.pair: PAIRS[a.pair]} if a.pair else PAIRS

    briefs = [brief_for_pair(p, cfg, date, sheet, calendar, cot, prices)
              for p, cfg in pairs.items()]
    render(date, briefs)


if __name__ == "__main__":
    main()
