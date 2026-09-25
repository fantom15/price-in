"""Fed - expectations MANUAL, current band automated.

Expectations: CME FedWatch bucket probabilities, downloaded by hand - CME's
Data Terms of Use prohibit scripted access. Do not automate this.

Current target band: NY Fed EFFR api (fetched, archived). Each record carries
targetRateFrom/To, so the band tracks every hike/cut without a constant to
maintain (the doc's "(350-375)" was already stale after the 2026-09-16 hike).

Manual input: drop the FedWatch download into data/manual/fed/ as-is
(FedWatch -> Historical -> Downloads -> "All upcoming meetings", e.g.
FedMeetingHistory_20260925.csv). Any *.csv there is read. Layout, as exported:

    ,History for 28 Oct 2026 Fed meeting,,...,History for 9 Dec 2026 Fed meeting,...
    Date,(0-25),(25-50),...,(1525-1550),(0-25),(25-50),...
    9/23/2026,,,...,0.291429,0.708571,...

One Date column, then one block of bucket columns per upcoming meeting (the
bucket list restarts at (0-25) for each block; blocks differ in length). Each
row is a trading day, so one download carries ~a year of history for every
meeting. Empty cells = bucket or meeting not listed that day.

Derivation (verified against the site in rates-sources.md):
    hike = P(bucket mid > current mid)          prob_move_pct (signed: -cut if bps<0)
    bps  = sum p * (bucket mid - current mid)   change_bps
"""
import csv
import datetime as dt
import io
import json
import os
import re

from . import common as C

BANK = "fed"
MANUAL = True   # expectations come from data/manual/fed/
REAL_MEETING_DATES = True   # `meeting` = FOMC date, same as legacy rows
EFFR = ("https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"
        "?startDate={frm}&endDate={to}")
BUCKET = re.compile(r"\(?\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*\)?")


def fetch(ctx):
    # ~13 months, so a year-long single-meeting history file finds its bands.
    frm = (ctx.today - dt.timedelta(days=400)).isoformat()
    body = C.http_get(EFFR.format(frm=frm, to=ctx.today.isoformat()))
    if not json.loads(body).get("refRates"):
        raise ValueError("NY Fed EFFR: empty refRates")
    C.save(C.archive_path(ctx, BANK, "effr", "json"), body)


def bands(ctx):
    """date -> target band midpoint in bps (e.g. 3.75-4.00 -> 387.5)"""
    out = {}
    for path in C.archived(ctx, BANK, "effr", "json"):
        try:
            recs = json.load(open(path)).get("refRates", [])
        except (json.JSONDecodeError, OSError) as e:
            ctx.note(BANK, f"{path}: unreadable ({e})")
            continue
        for r in recs:
            try:
                out[dt.date.fromisoformat(r["effectiveDate"])] = (
                    (float(r["targetRateFrom"]) + float(r["targetRateTo"])) * 50)
            except (KeyError, TypeError, ValueError):
                continue
    return out


def band_on(series, day):
    """Band in force on `day`: the newest EFFR record on or before it. A
    decision is public the day it is made, so unlike a rate fixing the same
    day counts. (The live run the morning after a hike may not have that
    day's EFFR yet; the next rebuild corrects it from the newer archive.)"""
    return C.rate_before(series, day + dt.timedelta(days=1))[1]


TITLE = re.compile(r"History for (.+?) Fed meeting", re.I)


def read_history(path):
    """-> ([(as_of, meeting, {bucket_mid_bps: prob})], [meetings with no columns])"""
    rows = list(csv.reader(io.StringIO(open(path, encoding="utf-8-sig").read())))
    hdr_i = next((i for i, r in enumerate(rows)
                  if r and r[0].strip().lower() == "date"), None)
    if hdr_i is None:
        raise ValueError("no header row starting with 'Date'")
    header = rows[hdr_i]
    titles = []   # (column, meeting date)
    for r in rows[:hdr_i]:
        for i, c in enumerate(r):
            if (m := TITLE.search(c)):
                titles.append((i, C.parse_date(m.group(1))))
    # The export names one meeting more than it has columns for: the last
    # title sits past the end of the header with no buckets and no data
    # (seen in FedMeetingHistory_20260925.csv - 8 Dec 2027). Nothing to parse,
    # so drop it and say so; any other mismatch is still an error below.
    dropped = [d for i, d in titles if i >= len(header)]
    titles = [d for i, d in titles if i < len(header)]

    # Split the bucket columns into per-meeting blocks where the bucket list
    # restarts (lower bound drops). This does not rely on the title cells
    # being aligned with the block starts.
    blocks, prev = [], None
    for i, h in enumerate(header):
        if i == 0 or not h.strip():
            continue
        m = BUCKET.fullmatch(h.strip())
        if not m:
            raise ValueError(f"column {i} {h!r} is not a rate bucket like (350-375)")
        lo, hi = float(m.group(1)), float(m.group(2))
        if prev is None or lo <= prev:
            blocks.append({})
        blocks[-1][i] = (lo + hi) / 2
        prev = lo
    if len(titles) != len(blocks):
        raise ValueError(f"{len(titles)} meeting titles but {len(blocks)} bucket blocks")

    out = []
    for r in rows[hdr_i + 1:]:
        if not r or not r[0].strip():
            continue
        as_of = C.parse_date(r[0])
        for meeting, cols in zip(titles, blocks):
            probs = {}
            for i, mid in cols.items():
                v = r[i].strip() if i < len(r) else ""
                if v:
                    probs[mid] = float(v.rstrip("%")) / 100 if v.endswith("%") else float(v)
            if not probs:
                continue   # meeting not yet listed on this day
            if sum(probs.values()) > 1.5:   # percent without a % sign
                probs = {k: p / 100 for k, p in probs.items()}
            out.append((as_of, meeting, probs))
    return out, dropped


def derive(probs, cur):
    bps = sum(p * (mid - cur) for mid, p in probs.items())
    hike = sum(p for mid, p in probs.items() if mid > cur) * 100
    cut = sum(p for mid, p in probs.items() if mid < cur) * 100
    return bps, (hike if bps >= 0 else -cut)


def build(ctx):
    band = bands(ctx)
    d = os.path.join(ctx.manualdir, BANK)
    names = sorted(n for n in os.listdir(d) if not n.startswith(".")) if os.path.isdir(d) else []
    merged, seen_dates, missing_band = {}, [], set()
    for name in names:
        path = os.path.join(d, name)
        if not name.lower().endswith(".csv"):
            ctx.problem(BANK, f"manual/{BANK}/{name}: ignored - not a .csv")
            continue
        try:
            obs, dropped = read_history(path)
        except (ValueError, OSError) as e:
            ctx.problem(BANK, f"manual/{BANK}/{name}: unreadable ({e})")
            continue
        for m in dropped:
            ctx.note(BANK, f"manual/{BANK}/{name}: {m} meeting is titled but has no "
                           f"columns in the export - left out")
        stamp, newest = C.mtime_utc(path), max((o[0] for o in obs), default=None)
        seen_dates += [o[0] for o in obs]
        for as_of, meeting, probs in obs:
            if meeting < as_of:
                continue
            if abs(sum(probs.values()) - 1) > 0.02:
                ctx.note(BANK, f"{as_of} {meeting}: probabilities sum to "
                               f"{sum(probs.values()):.3f}, not 1")
            st = stamp if as_of == newest else ""
            cur = band_on(band, as_of)
            if cur is None:
                missing_band.add(as_of)
                new = C.row(BANK, as_of, meeting, None, None, as_of_time=st)
            else:
                bps, prob = derive(probs, cur)
                new = C.row(BANK, as_of, meeting, (cur + bps) / 100, bps,
                            as_of_time=st, prob_move_pct=prob)
            key = (new["as_of"], new["meeting"])
            old = merged.get(key)
            # Later files win, except an unstamped copy never replaces the
            # stamped reading of the same day.
            if old is None or new["as_of_time"] or not old["as_of_time"]:
                merged[key] = new
    C.report_missing_rate(ctx, BANK, missing_band, "EFFR target-band")
    # The export lags: a download on the 25th ends on the 23rd.
    C.check_fresh(ctx, BANK, seen_dates,
                  "download FedWatch -> Historical -> Downloads -> 'All upcoming "
                  f"meetings' into {os.path.join(ctx.manualdir, BANK)}/",
                  max_lag_bdays=2)
    return list(merged.values())
