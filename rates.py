#!/usr/bin/env python3
"""Layer 1: market-implied policy-rate paths, from official sources.

Replaces rateprobability.com (which blocked scripted access). Every number is
now computed here from central-bank and exchange data - see rates-sources.md
for each source, format and gotcha:

    bank  current rate                 expectations
    boc   BoC Valet CORRA              Montréal Exchange COA/CRA settlements
    boe   BoE database SONIA           BoE OIS forward curve (xlsx in a zip)
    ecb   ECB api deposit rate (DFR)   ICE Three-Month Euribor futures
    fed   NY Fed EFFR target band      CME FedWatch buckets  - MANUAL input

    implied_rate = 100 - futures_price
    change_bps   = (implied_rate - current_policy_rate) * 100     (primary datum)
    odds_pct     = change_bps / 25 * 100      (|x| > 100 = more than one step)

The "current" rate for a snapshot is the latest fixing dated strictly before
it - what was actually known that day. CME data is never fetched: its terms
prohibit scripted access. Fed expectations come from the FedWatch file you drop
in data/manual/fed/ (format in banks/fed.py). Rows whose period has fully
elapsed (period_end < as_of) are dropped; data/cb_meetings.csv lists every known
decision date, which the report uses to withhold a pre-decision reading.

ARCHIVE-FIRST. Every raw download is saved under data/raw/<bank>/ as
<date>.<kind>.<ext> before anything is parsed, and the CSV is rebuilt from the
whole archive (plus data/manual/) every run - so `--no-fetch` reproduces it
offline and new columns can be backfilled without refetching. The old
rateprobability snapshots (<date>.json) are still read, so the May-Sep 2026
history stays in the CSV; for any (bank, date) a new source covers, they are
dropped.

Output, one row per (bank, as_of, meeting) - schema unchanged:

    bank,as_of,as_of_time,meeting,implied_rate,prob_move_pct,is_cut,num_moves,change_bps,horizon

`meeting` is the date the implied rate refers to: a real FOMC date for the Fed
and for legacy rows; the start of the contract's reference period for BoC/ECB;
as_of + N months for the BoE forward curve. prob_move_pct and change_bps are
signed (negative = cut). A value that cannot be computed is left empty with a
note on stderr - nothing is ever carried forward from a previous day.

`as_of_time` = when the raw file was fetched/downloaded (UTC), on the newest
observation in that file only.

One bank failing never stops the others. Anything that failed - a fetch, a
stale or missing manual file, a missing rate fixing - is listed at the end and
the exit code is non-zero, so run_daily.py alerts.

Usage:
    python3 rates.py                       # fetch all banks -> data/rates.csv
    python3 rates.py --banks boc boe       # fetch only these (csv still rebuilt from all)
    python3 rates.py --no-fetch            # rebuild csv from archive only
"""
import argparse
import csv
import datetime as dt
import inspect
import os
import sys

from banks import SOURCES, legacy
from banks.common import FIELDS, Ctx

BANKS = list(SOURCES)

# BoE's OIS curve lags ~2 business days; past this, the source is stuck.
STALE_DAYS = 5


# FOMC meetings are at most ~8 weeks apart; a first listed meeting further
# out than this means the snapshot is missing its real next meeting.
MAX_MEETING_GAP_DAYS = 63


def blank_multi_meeting_odds(rows, calendar=None):
    """A probability applies to ONE meeting. Every row after the next meeting is
    a cumulative horizon (e.g. +128bp over 12m), where bps/25*100 would read as
    a meaningless 512% - so keep prob_move_pct only on the next-meeting row and
    let num_moves (5.12) carry the step count. change_bps is untouched.

    `calendar` (real meeting dates, for banks keyed on them) is every meeting
    date seen in any snapshot, legacy included. It catches a snapshot whose
    first row is NOT the next meeting - a FedWatch download omits meetings
    already past when it was taken, so its history rows start at a later
    meeting. Such a snapshot keeps no probability at all.

    Applied to the new sources only: legacy rateprobability rows carry a genuine
    per-meeting probability for every meeting."""
    by_snap = {}
    for r in rows:
        by_snap.setdefault(r["as_of"], []).append(r)
    for as_of, snap in by_snap.items():
        upcoming = [r for r in snap if r["meeting"] >= as_of]
        nxt = min(upcoming, key=lambda r: r["meeting"]) if upcoming else None
        if nxt is not None and calendar is not None:
            gap = (dt.date.fromisoformat(nxt["meeting"])
                   - dt.date.fromisoformat(as_of)).days
            skipped = any(as_of <= m < nxt["meeting"] for m in calendar)
            if skipped or gap > MAX_MEETING_GAP_DAYS:
                nxt = None
        for r in snap:
            if r is not nxt:
                r["prob_move_pct"] = ""


def drop_expired(rows):
    """Drop a row only once its period has fully elapsed (period_end < as_of).
    An in-progress contract - e.g. a 3-month period that started last week - is
    live and carries the nearest expectations, so it stays. Sources give the
    end in a private `_period_end` key (default: the meeting date itself)."""
    out = []
    for r in rows:
        end = r.pop("_period_end", r["meeting"])
        if end >= r["as_of"]:
            out.append(r)
    return out


def decision_dates(bank, old, new):
    """Central-bank decision dates for data/cb_meetings.csv, which the report
    uses to refuse a reading taken before a decision it doesn't reflect.
    Legacy rows and Fed rows are keyed on real meetings; the ECB module knows
    its Governing Council calendar; futures/forward rows are not decisions."""
    days = {m for _, m in old}
    if getattr(SOURCES.get(bank), "REAL_MEETING_DATES", False):
        days |= {r["meeting"] for r in new}
    mod = SOURCES.get(bank)
    if hasattr(mod, "decision_calendar"):
        days |= set(mod.decision_calendar)
    return [(bank, d) for d in days]


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--banks", nargs="+", default=BANKS, choices=BANKS, metavar="BANK",
                    help=f"which banks to fetch (default: {' '.join(BANKS)}). The csv "
                         f"is always rebuilt from every bank's archive")
    ap.add_argument("--outdir", default="data")
    ap.add_argument("-o", "--out", help="default: <outdir>/rates.csv")
    ap.add_argument("--manual-dir", help="default: <outdir>/manual")
    ap.add_argument("--no-fetch", action="store_true",
                    help="rebuild the csv from archived files only")
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today(),
                    help=argparse.SUPPRESS)   # testing / replay
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    out = a.out or os.path.join(a.outdir, "rates.csv")
    ctx = Ctx(rawdir=os.path.join(a.outdir, "raw"),
              manualdir=a.manual_dir or os.path.join(a.outdir, "manual"),
              today=a.today)

    failed = []
    if not a.no_fetch:
        for bank in a.banks:
            try:
                SOURCES[bank].fetch(ctx)
            except Exception as e:  # noqa: BLE001 - one bank must not sink the rest
                failed.append(bank)
                print(f"{bank:<5} FETCH FAILED: {e}", file=sys.stderr)

    merged = {}   # (bank, as_of, meeting) -> row
    decisions = []   # (bank, decision date) -> data/cb_meetings.csv
    for bank in sorted(set(BANKS) | set(legacy.BANKS)):
        old = legacy.build(ctx.rawdir, bank, lambda m, b=bank: ctx.note(b, m))
        old = {k: r for k, r in old.items() if r["meeting"] >= r["as_of"]}
        new = []
        if bank in SOURCES:
            print(f"{bank}:", file=sys.stderr)
            mod = SOURCES[bank]
            try:
                if "legacy_meetings" in inspect.signature(mod.build).parameters:
                    new = mod.build(ctx, legacy_meetings={m for _, m in old})
                else:
                    new = mod.build(ctx)
            except Exception as e:  # noqa: BLE001
                ctx.problem(bank, f"BUILD FAILED: {e!r}")
        new = drop_expired(new)
        covered = {r["as_of"] for r in new}
        # Manual banks police their own input (check_fresh); for automated
        # ones, a fetch can "succeed" while the source has stopped updating.
        if bank in SOURCES and not getattr(SOURCES[bank], "MANUAL", False):
            newest = max(covered, default=None)
            if newest is None or newest < (a.today - dt.timedelta(
                    days=STALE_DAYS)).isoformat():
                ctx.problem(bank, f"SOURCE STALE - newest observation is {newest}, "
                                  f"over {STALE_DAYS} days old")
        per_meeting = getattr(SOURCES.get(bank), "REAL_MEETING_DATES", False)
        blank_multi_meeting_odds(new, calendar={r["meeting"] for r in new} | {
            m for _, m in old} if per_meeting else None)
        # Sources keyed on real meeting dates (Fed) merge with legacy per
        # meeting: a FedWatch download omits meetings already past on the day
        # it was taken, so legacy may hold the only row for them. Sources
        # keyed on contract/forward periods never share keys with legacy, so
        # a date they cover drops legacy entirely rather than mixing the two.
        for (as_of, meeting), r in old.items():
            if per_meeting or as_of not in covered:
                merged[(bank, as_of, meeting)] = r
        for r in new:
            merged[(bank, r["as_of"], r["meeting"])] = r
        decisions += decision_dates(bank, old, new)

        dates = sorted({k[1] for k in merged if k[0] == bank})
        n = sum(1 for k in merged if k[0] == bank)
        print(f"{bank:<5} {len(dates):>3} dates {n:>5} rows  "
              f"{dates[0] if dates else '-'} .. {dates[-1] if dates else '-'}"
              f"{'' if new or bank not in SOURCES else '   (no new-source rows)'}",
              file=sys.stderr)

    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for key in sorted(merged):
            w.writerow(merged[key])
    print(f"\n{len(merged)} rows -> {out}", file=sys.stderr)
    cal = os.path.join(a.outdir, "cb_meetings.csv")
    with open(cal, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bank", "decision_date"])
        w.writerows(sorted(set(decisions)))
    print(f"{len(set(decisions))} decision dates -> {cal}", file=sys.stderr)

    problem_banks = sorted({b for b, _ in ctx.problems} - set(failed))
    if failed or problem_banks:
        parts = []
        if failed:
            parts.append(f"fetch failed: {', '.join(failed)}")
        if problem_banks:
            parts.append(f"incomplete: {', '.join(problem_banks)} (see '!!' lines above)")
        sys.exit("; ".join(parts))


if __name__ == "__main__":
    main()
