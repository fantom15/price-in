#!/usr/bin/env python3
"""Assemble the market_data_template sheet from the fetched CSVs.

Reads the long-format files written by quikstrike.py and rates.py and pivots
them into one wide row per date:

    date, CAVL, CAVL_chg, cavl_skew, ..., fed_odds_pct, fed_bps, fed_path_12m, ...

`_chg` columns are day-over-day differences computed per ticker; `_skew` columns
come from the skew measure for the same ticker.

Central bank columns come from data/rates.csv (rateprobability.com):

    <bank>_odds_pct   signed probability of a move at the next meeting
    <bank>_bps        implied change at the next meeting
    <bank>_path_12m   implied change at the meeting nearest 12 months out

Those are only populated on dates rateprobability has a snapshot for. The api
exposes today plus 1w/3w/6w/10w ago, so early rows are sparse - run rates.py
daily and the coverage fills in going forward. Remaining columns (dxy, usdcad,
eurusd, wti) are still emitted empty so the sheet keeps its shape.

Usage:
    python3 build_sheet.py --days 30
    python3 build_sheet.py --start 2026-07-16 --end 2026-07-22
"""
import argparse
import csv
import datetime as dt
import os
import sys
from collections import defaultdict

# Tickers that get level + change + skew columns, in template order.
VOL_TICKERS = ["CAVL", "EUVL", "S1VL"]

# Central banks -> which of the three columns the template wants. The sheet has
# a 12m path for fed/ecb but not boc, so the set is per-bank.
CB_COLS = [
    ("fed", ["odds_pct", "bps", "path_12m"]),
    ("ecb", ["odds", "bps", "path_12m"]),
    ("boc", ["odds", "bps"]),
]

# Columns this script cannot fill yet, kept so the sheet matches the template.
EXTERNAL_COLS = ["dxy", "usdcad", "eurusd", "wti"]

# How far out "12 month path" looks, and how far a meeting may sit from that
# mark before it is rejected. Meetings are ~6-8 weeks apart, so a 60-day window
# keeps the nearest real meeting without silently reaching much further.
PATH_HORIZON_DAYS = 365
PATH_TOLERANCE_DAYS = 60


def root(ticker):
    """Strip the measure suffix so the same product matches across measures.

    Each measure renames the ticker: CVOL is CAVL/S1VL/TYVY, skew is
    CASK/S1SK/TYSY. The last two characters carry the measure (VL/SK for most
    products, VY/SY for the Treasury family), so the leading stem identifies
    the product.
    """
    return ticker[:-2] if len(ticker) > 2 else ticker


def load(path):
    """product root -> {date: value}"""
    out = defaultdict(dict)
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                out[root(r["ticker"])][r["date"]] = float(r["value"])
            except (ValueError, KeyError):
                continue
    return out


def load_rates(path):
    """bank -> {as_of: {odds_pct, odds, bps, path_12m}}

    rates.csv holds one row per (bank, as_of, meeting); the sheet wants one
    value per date. For each snapshot: the *next* meeting is the earliest one
    on or after as_of, and the 12m path is the meeting closest to a year out.
    """
    by_date = defaultdict(lambda: defaultdict(list))
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                by_date[r["bank"]][r["as_of"]].append((
                    dt.date.fromisoformat(r["meeting"]),
                    float(r["prob_move_pct"]),
                    float(r["change_bps"]),
                ))
            except (ValueError, KeyError):
                continue

    out = defaultdict(dict)
    for bank, dates in by_date.items():
        for as_of, meetings in dates.items():
            try:
                ref = dt.date.fromisoformat(as_of)
            except ValueError:
                continue
            meetings.sort()
            upcoming = [m for m in meetings if m[0] >= ref]
            if not upcoming:
                continue
            _, prob, bps = upcoming[0]

            target = ref + dt.timedelta(days=PATH_HORIZON_DAYS)
            when, _, path_bps = min(upcoming, key=lambda m: abs(m[0] - target))
            if abs((when - target).days) > PATH_TOLERANCE_DAYS:
                path_bps = None

            out[bank][as_of] = {
                "odds_pct": prob, "odds": prob,
                "bps": bps, "path_12m": path_bps,
            }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datadir", default="data")
    ap.add_argument("--out", default="market_data.csv")
    ap.add_argument("--days", type=int, help="most recent N rows")
    ap.add_argument("--start")
    ap.add_argument("--end")
    a = ap.parse_args()

    levels = load(os.path.join(a.datadir, "cvol.csv"))
    skews = load(os.path.join(a.datadir, "skew.csv"))
    rates = load_rates(os.path.join(a.datadir, "rates.csv"))
    if not levels:
        sys.exit(f"no data in {a.datadir}/cvol.csv - run quikstrike.py first")

    dates = sorted({d for t in VOL_TICKERS for d in levels.get(root(t), {})})
    if a.start:
        dates = [d for d in dates if d >= a.start]
    if a.end:
        dates = [d for d in dates if d <= a.end]
    if a.days:
        dates = dates[-a.days:]

    header = ["date"]
    for t in VOL_TICKERS:
        header += [t, f"{t}_chg", f"{t.lower()}_skew"]
    for bank, cols in CB_COLS:
        header += [f"{bank}_{c}" for c in cols]
    header += EXTERNAL_COLS

    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for d in dates:
            row = [d]
            for t in VOL_TICKERS:
                series = levels.get(root(t), {})
                val = series.get(d)
                # previous available observation for this ticker
                prior = [x for x in sorted(series) if x < d]
                chg = (val - series[prior[-1]]) if (val is not None and prior) else None
                sk = skews.get(root(t), {}).get(d)
                row += [
                    "" if val is None else f"{val:.2f}",
                    "" if chg is None else f"{chg:+.2f}",
                    "" if sk is None else f"{sk:.2f}",
                ]
            for bank, cols in CB_COLS:
                snap = rates.get(bank, {}).get(d) or {}
                for c in cols:
                    v = snap.get(c)
                    # odds are a percentage, bps are basis points and signed
                    row.append("" if v is None else
                               (f"{v:.2f}" if c.startswith("odds") else f"{v:+.1f}"))
            row += [""] * len(EXTERNAL_COLS)
            w.writerow(row)

    print(f"{len(dates)} rows -> {a.out}", file=sys.stderr)
    if dates:
        print(f"range: {dates[0]} .. {dates[-1]}", file=sys.stderr)


if __name__ == "__main__":
    main()
