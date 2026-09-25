"""Shared plumbing for the per-bank Layer 1 sources.

Every bank module exposes the same two functions:

    fetch(ctx)  -> None         download raw files into ctx.rawdir/<bank>/ (archive-first)
    build(ctx)  -> list[dict]   rows in FIELDS shape, parsed from the archive only

The split is what makes `--no-fetch` work: build() never touches the network,
so the CSV can always be rebuilt (and new columns backfilled) from disk.

Core formula (rates-sources.md):
    implied_rate = 100 - futures_price
    change_bps   = (implied_rate - current_policy_rate) * 100
    odds_pct     = change_bps / 25 * 100
"""
import datetime as dt
import io
import os
import posixpath
import re
import sys
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

FIELDS = ["bank", "as_of", "as_of_time", "meeting", "implied_rate",
          "prob_move_pct", "is_cut", "num_moves", "change_bps", "horizon"]

STEP_BPS = 25

# A policy-rate fixing older than this (relative to as_of) is not "current".
# Covers weekends plus a holiday; anything longer means the rate feed broke.
MAX_RATE_GAP_DAYS = 7

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")

MONTH_CODES = "FGHJKMNQUVXZ"   # Jan..Dec futures month letters


class Ctx:
    """What a bank module needs: where the archive lives, and how to complain."""

    def __init__(self, rawdir, manualdir, today):
        self.rawdir = rawdir
        self.manualdir = manualdir
        self.today = today
        self.problems = []   # (bank, message) - anything that should fail the run

    def note(self, bank, msg):
        """Informational - printed, does not fail the run."""
        print(f"  {bank}: {msg}", file=sys.stderr)

    def problem(self, bank, msg):
        """Loud - printed and fails the run, so run_daily.py alerts."""
        print(f"  {bank}: !! {msg}", file=sys.stderr)
        self.problems.append((bank, msg))


# --- network + archive -------------------------------------------------------

def http_get(url, timeout=60, expect_html=False):
    """GET -> bytes. Refuses an HTML page where data was expected: several of
    these sites answer a bad query with a 200 HTML page instead of an error."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    head = body[:512].lstrip().lower()
    if not expect_html and (head.startswith(b"<!doctype") or head.startswith(b"<html")):
        raise ValueError(f"got an HTML page, not data: {url}")
    return body


def archive_path(ctx, bank, kind, ext, day=None):
    d = os.path.join(ctx.rawdir, bank)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{(day or ctx.today).isoformat()}.{kind}.{ext}")


def save(path, data):
    with open(path, "wb") as f:
        f.write(data)
    return path


def archived(ctx, bank, kind, ext):
    """Archive files of one kind, oldest first (names start with the date)."""
    d = os.path.join(ctx.rawdir, bank)
    if not os.path.isdir(d):
        return []
    suffix = f".{kind}.{ext}"
    return [os.path.join(d, n) for n in sorted(os.listdir(d)) if n.endswith(suffix)]


def mtime_utc(path):
    """When a raw file was written (fetched / downloaded), ISO UTC. This is the
    as_of_time for the newest observation in that file."""
    t = dt.datetime.fromtimestamp(os.stat(path).st_mtime, dt.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# --- dates -------------------------------------------------------------------

def parse_date(s):
    s = s.strip().strip('"')
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %b %y", "%m/%d/%Y", "%m/%d/%y",
                "%d-%b-%Y", "%d-%b-%y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date {s!r}")


def excel_date(serial):
    return dt.date(1899, 12, 30) + dt.timedelta(days=int(float(serial)))


def add_months(day, n):
    m = day.month - 1 + n
    y, m = day.year + m // 12, m % 12 + 1
    for d in (day.day, 30, 29, 28):
        try:
            return dt.date(y, m, d)
        except ValueError:
            continue


def third_wednesday(year, month):
    first = dt.date(year, month, 1)
    return first + dt.timedelta(days=(2 - first.weekday()) % 7 + 14)


def contract_month(code, root, ref):
    """'ESRV6' / 'COAU26' -> (year, month). A 1-digit year resolves to the
    decade that puts the contract nearest `ref`."""
    m = re.fullmatch(rf"{root}([{MONTH_CODES}])(\d{{1,2}})", code.strip().upper())
    if not m:
        raise ValueError(f"not a {root} contract code: {code!r}")
    month = MONTH_CODES.index(m.group(1)) + 1
    y = m.group(2)
    if len(y) == 2:
        return 2000 + int(y), month
    base = ref.year - ref.year % 10 + int(y)
    year = min((base - 10, base, base + 10), key=lambda c: abs(c - ref.year))
    return year, month


def prev_business_day(day):
    day -= dt.timedelta(days=1)
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


# --- the formula -------------------------------------------------------------

def rate_before(series, day):
    """Latest fixing dated strictly before `day` - the rate actually known on
    that date (SONIA/CORRA/EFFR/€STR are all published the next morning).
    None if the newest one is too old to count as current."""
    best = None
    for d in series:
        if d < day and (best is None or d > best):
            best = d
    if best is None or (day - best).days > MAX_RATE_GAP_DAYS:
        return None, None
    return best, series[best]


def report_missing_rate(ctx, bank, dates, what, recent_days=10):
    """No current fixing -> bps/odds were left empty. Recent dates fail the
    run (the rate feed is broken); old ones (e.g. a backfilled workbook that
    predates the rate archive) are summarised once."""
    cutoff = ctx.today - dt.timedelta(days=recent_days)
    recent = sorted(d for d in dates if d >= cutoff)
    old = sorted(d for d in dates if d < cutoff)
    for d in recent:
        ctx.problem(bank, f"{d}: no {what} fixing before this date - bps/odds left empty")
    if old:
        ctx.note(bank, f"{len(old)} older dates ({old[0]}..{old[-1]}) have no {what} "
                       f"fixing on file - bps/odds left empty")


def check_fresh(ctx, bank, dates, how, max_lag_bdays=1):
    """Manual input is fresh if it covers the previous business day or later
    (today's may legitimately not exist yet when cron runs)."""
    want = ctx.today
    for _ in range(max_lag_bdays):
        want = prev_business_day(want)
    latest = max(dates, default=None)
    if latest is None:
        ctx.problem(bank, f"NO MANUAL INPUT on file - expectations empty. To fix: {how}")
    elif latest < want:
        ctx.problem(bank, f"MANUAL INPUT STALE - newest is {latest}, nothing since; "
                          f"those days stay empty (never carried forward). To fix: {how}")


def row(bank, as_of, meeting, implied_rate, change_bps, as_of_time="",
        prob_move_pct=None):
    """One output row. change_bps is the primary datum; prob_move_pct defaults
    to change_bps/25*100 (so |x|>100 = more than one step priced). Both signed:
    negative = cut."""
    if change_bps is not None and prob_move_pct is None:
        prob_move_pct = change_bps / STEP_BPS * 100
    return {
        "bank": bank,
        "as_of": as_of.isoformat(),
        "as_of_time": as_of_time,
        "meeting": meeting.isoformat(),
        "implied_rate": _fmt(implied_rate, 4),
        "prob_move_pct": _fmt(prob_move_pct, 1),
        "is_cut": "" if change_bps is None else int(change_bps < 0),
        "num_moves": "" if change_bps is None else _fmt(change_bps / STEP_BPS, 2),
        "change_bps": _fmt(change_bps, 1),
        "horizon": "today",
    }


def _fmt(v, nd):
    return "" if v is None else round(v, nd)


# --- xlsx (stdlib; the VPS has no venv, so no openpyxl) ------------------------

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def xlsx_sheet(data, name):
    """Rows of one worksheet as lists of raw cell strings (None = empty)."""
    x = zipfile.ZipFile(io.BytesIO(data))
    wb = ET.fromstring(x.read("xl/workbook.xml"))
    rid = next((s.get(f"{{{_NS['r']}}}id") for s in wb.iter(f"{{{_NS['m']}}}sheet")
                if s.get("name") == name), None)
    if rid is None:
        raise KeyError(f"no sheet {name!r}")
    rels = ET.fromstring(x.read("xl/_rels/workbook.xml.rels"))
    target = next(r.get("Target") for r in rels if r.get("Id") == rid)
    path = target[1:] if target.startswith("/") else posixpath.normpath(
        posixpath.join("xl", target))

    shared = []
    if "xl/sharedStrings.xml" in x.namelist():
        for si in ET.fromstring(x.read("xl/sharedStrings.xml")).iter(f"{{{_NS['m']}}}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))

    rows = []
    for r in ET.fromstring(x.read(path)).iter(f"{{{_NS['m']}}}row"):
        cells = {}
        for c in r.iter(f"{{{_NS['m']}}}c"):
            col = 0
            for ch in re.match(r"[A-Z]+", c.get("r")).group():
                col = col * 26 + ord(ch) - 64
            v, t = c.find("m:v", _NS), c.get("t")
            if t == "inlineStr":
                val = "".join(e.text or "" for e in c.iter(f"{{{_NS['m']}}}t"))
            elif v is None:
                continue
            else:
                val = shared[int(v.text)] if t == "s" else v.text
            cells[col - 1] = val
        rows.append([cells.get(i) for i in range(max(cells) + 1)] if cells else [])
    return rows
