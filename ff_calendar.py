#!/usr/bin/env python3
"""Fetch the ForexFactory economic calendar.

Ported from tradewind-system/scraper-army (ff_calendar_cache.py + the parser in
surprises.py), with storage changed to CSV. Unlike the other fetchers here this
one is NOT stdlib-only: forexfactory.com answers plain HTTP with 403, so it
needs Camoufox (a stealth Firefox) to get the page at all.

    pip install camoufox[geoip] && python3 -m camoufox fetch

The lightweight alternative, nfs.faireconomy.media, was rejected on purpose: it
serves only the current week and carries no `actual` values, so it cannot
support actual-vs-forecast surprise.

Two phases, so a slow fetch is done once and parsing stays cheap:

  1. fetch  - download each week's HTML to data/ff_html/<week>.html.
              Already-cached weeks are skipped, so a run is resumable, and the
              browser is restarted every BATCH weeks so one hang cannot stall
              the whole backfill. Each file is written as it arrives.
  2. parse  - read the cached HTML and write data/calendar.csv.

The cached HTML is the source of truth: re-parsing is free, so new fields can
be extracted later without re-fetching anything. `--parse-only` does exactly
that.

The calendar is embedded in the page as JSON in `window.calendarComponentStates`
rather than in the table markup, so the parser pulls that blob out.

Output: data/calendar.csv
    date,time,currency,impact,event,actual,forecast,previous,
    actual_val,forecast_val,previous_val,surprise,surprise_dir

Usage:
    python3 calendar.py                       # current week + reparse
    python3 calendar.py --backfill 2020       # every week from 2020
    python3 calendar.py --parse-only          # rebuild csv from cache
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

CACHE = Path(__file__).resolve().parent / "data" / "ff_html"
SELECTOR = "table.calendar__table"
BATCH = 15        # restart the browser every N weeks (hang isolation)
DELAY = 1.5       # polite delay between pages

# The calendar ships as a JS assignment, not as markup we can walk.
CAL_JSON = re.compile(
    r'window\.calendarComponentStates\[\d+\]\s*=\s*\{[^;]*?days:\s*(\[.*?\])\s*,',
    re.S)

_MAG = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}
_IMPACT = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW",
           "holiday": "HOLIDAY"}

FIELDS = ["date", "time", "currency", "impact", "event",
          "actual", "forecast", "previous",
          "actual_val", "forecast_val", "previous_val",
          "surprise", "surprise_dir"]


def week_param(d):
    """FF addresses weeks by the Sunday that starts them, e.g. 'aug9.2026'."""
    sunday = d - dt.timedelta(days=(d.weekday() + 1) % 7)
    return f"{sunday.strftime('%b').lower()}{sunday.day}.{sunday.year}"


def weeks_between(start, end):
    out, seen, cur = [], set(), start
    while cur <= end:
        w = week_param(cur)
        if w not in seen:
            seen.add(w)
            out.append(w)
        cur += dt.timedelta(weeks=1)
    return out


def parse_val(s):
    """FF writes values as '1.9%', '2K', '250B', '-0.1%'. Take number+magnitude."""
    if not s:
        return None
    s = s.strip().replace("%", "").replace(",", "")
    m = re.match(r"^(-?\d+\.?\d*)\s*([kmbtKMBT]?)", s)
    if not m:
        return None
    return float(m.group(1)) * _MAG.get(m.group(2).lower(), 1.0)


def fetch_weeks(want, headless=True):
    """Download any weeks not already cached. Returns (fetched, failed)."""
    try:
        from camoufox.sync_api import Camoufox
    except ImportError:
        sys.exit("camoufox is required to fetch (pip install 'camoufox[geoip]' "
                 "&& python3 -m camoufox fetch).\n"
                 "Already-cached weeks can be reparsed with --parse-only.")

    CACHE.mkdir(parents=True, exist_ok=True)
    todo = [w for w in want if not (CACHE / f"{w}.html").exists()]
    print(f"weeks: {len(want)} wanted, {len(want) - len(todo)} cached, "
          f"{len(todo)} to fetch", file=sys.stderr)

    fetched = failed = 0
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        try:
            with Camoufox(headless=headless) as b:
                page = b.new_page()
                for w in batch:
                    url = f"https://www.forexfactory.com/calendar?week={w}"
                    try:
                        page.goto(url, wait_until="domcontentloaded",
                                  timeout=45000)
                        page.wait_for_selector(SELECTOR, timeout=25000)
                        (CACHE / f"{w}.html").write_text(page.content(),
                                                         encoding="utf-8")
                        fetched += 1
                        if fetched % 10 == 0:
                            print(f"  fetched {fetched}/{len(todo)} (last {w})",
                                  file=sys.stderr)
                        time.sleep(DELAY)
                    except Exception as e:            # noqa: BLE001
                        failed += 1
                        print(f"  [skip] {w}: {type(e).__name__}",
                              file=sys.stderr)
        except Exception as e:                        # noqa: BLE001
            # One bad browser session must not lose the weeks already written.
            print(f"  [browser restart: {type(e).__name__}]", file=sys.stderr)
            time.sleep(3)

    print(f"fetch: {fetched} ok, {failed} failed, "
          f"{len(list(CACHE.glob('*.html')))} cached total", file=sys.stderr)
    return fetched, failed


def parse_week(html):
    """Every event in one week's page - no currency or impact filtering."""
    m = CAL_JSON.search(html)
    if not m:
        return []
    try:
        days = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []

    out = []
    for day in days:
        for e in day.get("events") or []:
            dl = e.get("dateline")
            if not dl:
                continue
            when = dt.datetime.fromtimestamp(dl, dt.timezone.utc)
            actual = e.get("actual") or None
            forecast = e.get("forecast") or None
            previous = e.get("previous") or None
            av, fv = parse_val(actual), parse_val(forecast)
            surprise = (av - fv) if (av is not None and fv is not None) else None
            out.append({
                "date": when.strftime("%Y-%m-%d"),
                "time": when.strftime("%H:%M"),
                "currency": e.get("currency") or "",
                "impact": _IMPACT.get(e.get("impactName", ""), "LOW"),
                "event": (e.get("name") or "").strip(),
                "actual": actual, "forecast": forecast, "previous": previous,
                "actual_val": av, "forecast_val": fv,
                "previous_val": parse_val(previous),
                "surprise": None if surprise is None else round(surprise, 6),
                "surprise_dir": None if surprise is None else (
                    "beat" if surprise > 0 else
                    "miss" if surprise < 0 else "inline"),
            })
    return out


def parse_cache(out_path):
    """Rebuild the csv from every cached week."""
    rows = {}
    files = sorted(CACHE.glob("*.html"))
    for path in files:
        try:
            html = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"  [skip] {path.name}: {e}", file=sys.stderr)
            continue
        for row in parse_week(html):
            # An event is identified by when + who + what: re-parsing or
            # re-fetching a week updates in place instead of duplicating.
            rows[(row["date"], row["time"], row["currency"], row["event"])] = row

    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for key in sorted(rows):
            w.writerow(rows[key])

    with_actual = sum(1 for r in rows.values() if r["actual"])
    print(f"\n{len(rows)} events from {len(files)} cached weeks "
          f"({with_actual} with actuals) -> {out_path}", file=sys.stderr)
    return rows


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backfill", type=int, metavar="YEAR",
                    help="fetch every week from this year (e.g. 2020)")
    ap.add_argument("--weeks", type=int, default=1,
                    help="how many recent weeks to refresh (default: 1)")
    ap.add_argument("--parse-only", action="store_true",
                    help="rebuild the csv from cached html, no fetching")
    ap.add_argument("--no-headless", action="store_true",
                    help="show the browser (debugging)")
    ap.add_argument("--outdir", default="data")
    ap.add_argument("-o", "--out", help="default: <outdir>/calendar.csv")
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    out = a.out or os.path.join(a.outdir, "calendar.csv")

    if not a.parse_only:
        today = dt.datetime.now(dt.timezone.utc)
        if a.backfill:
            start = dt.datetime(a.backfill, 1, 5, tzinfo=dt.timezone.utc)
        else:
            start = today - dt.timedelta(weeks=max(a.weeks - 1, 0))
        want = weeks_between(start, today)

        # The current week is still filling in - actuals appear as releases
        # land - so always re-fetch it even though it is already cached.
        current = week_param(today)
        (CACHE / f"{current}.html").unlink(missing_ok=True)

        fetch_weeks(want, headless=not a.no_headless)

    if not CACHE.exists() or not any(CACHE.glob("*.html")):
        sys.exit(f"no cached weeks in {CACHE} - run without --parse-only first")

    parse_cache(out)


if __name__ == "__main__":
    main()
