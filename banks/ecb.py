"""ECB - fully automatable: ICE Three-Month Euribor futures vs the ECB deposit rate.

Replaces the CME €STR (ESR) manual input: those contracts had zero volume and
a priorSettle that predated the 2026-09-16 hike, which produced a -45.7bp
"cut" days after the ECB hiked.

Sources (all public, no auth):
  prices   ICE contract-data  - every Euribor contract, lastPrice/volume/lastTime
  history  ICE historical     - ~4 months of daily settlements per marketId
  policy   ECB data api FM.D.U2.EUR.4F.KR.DFR.LEV - the deposit facility rate
  meetings ECB Governing Council calendar (press/calendars/mgcgc)

Rows: one per contract, `meeting` = 3rd Wednesday of the contract month (start
of its 3-month reference period, like the other futures here), period end =
start + 3 months.

    implied_rate = 100 - price
    change_bps   = (implied_rate - DFR in force on as_of) * 100

Two gotchas (see rates-sources.md):
  1. Euribor is an interbank rate with a spread over the DFR. The spread
     `front implied - DFR` is printed every run and written to
     data/ecb_spread.csv, so drift is visible. It is NOT subtracted.
  2. Decisions take effect at the start of the next reserve maintenance
     period, not on the decision date. The ECB's maintenance calendar is not
     machine-readable (the page fills it in by script), so the effective date
     is APPROXIMATED as decision + EFFECTIVE_LAG_DAYS - a constant fitted to the
     DFR changes on file (2026-06-17, 2026-09-16), re-checked against every DFR
     change on each run; a mismatch is reported loudly.

prob_move_pct is only kept when exactly one decision takes effect between
as_of and the end of the front contract's window; a 3-month window usually
spans two, so the ECB is normally bps-only (a probability applies to ONE
meeting).

Liquidity guard: a contract whose live volume is below MIN_VOLUME is skipped,
and its history is skipped too. History bars carry no volume, so backfilled
rows cannot be liquidity-checked on their own.
"""
import csv
import datetime as dt
import html
import json
import os
import re

from . import common as C

BANK = "ecb"
ICE_CONTRACTS = ("https://www.ice.com/marketdata/api/productguide/charting/"
                 "contract-data?productId=15275&hubId=17455")
ICE_HISTORY = ("https://www.ice.com/marketdata/api/productguide/charting/data/"
               "historical?marketId={mid}&historicalSpan=2")   # 2 = ~4 months (max)
DFR = ("https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV"
       "?startPeriod={frm}&format=csvdata")
GC_CALENDAR = "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"

MIN_VOLUME = 300
decision_calendar = []   # filled by build(); read by rates.py for cb_meetings.csv
# APPROXIMATION, fitted to two observations (decision 2026-06-11 -> DFR change
# 2026-06-17; 2026-09-10 -> 2026-09-16). The real rule is the ECB's published
# maintenance-period calendar, which is not available in machine-readable form.
# check_effective_lag() re-tests this against every DFR change each run.
EFFECTIVE_LAG_DAYS = 6
MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def fetch(ctx):
    frm = (ctx.today - dt.timedelta(days=400)).isoformat()
    C.save(C.archive_path(ctx, BANK, "dfr", "csv"), C.http_get(DFR.format(frm=frm)))
    body = C.http_get(ICE_CONTRACTS)
    contracts = json.loads(body)
    if not contracts or "lastPrice" not in contracts[0]:
        raise ValueError("ICE contract-data: unexpected payload")
    C.save(C.archive_path(ctx, BANK, "euribor", "json"), body)
    hist = {}
    for c in contracts:
        try:
            hist[str(c["marketId"])] = {
                "strip": c["marketStrip"],
                **json.loads(C.http_get(ICE_HISTORY.format(mid=c["marketId"])))}
        except Exception as e:  # noqa: BLE001 - one contract's history is optional
            ctx.note(BANK, f"history for {c.get('marketStrip')} not fetched ({e})")
    C.save(C.archive_path(ctx, BANK, "euribor_hist", "json"),
           json.dumps(hist).encode())
    C.save(C.archive_path(ctx, BANK, "gc_calendar", "html"),
           C.http_get(GC_CALENDAR, expect_html=True))


# --- parsing -----------------------------------------------------------------

def strip_month(strip):
    """'Oct26' -> (2026, 10)"""
    m = re.fullmatch(r"([A-Z][a-z]{2})(\d{2})", strip.strip())
    if not m or m.group(1) not in MONTHS:
        raise ValueError(f"not a contract month: {strip!r}")
    return 2000 + int(m.group(2)), MONTHS[m.group(1)]


def period(strip):
    """(start, end) of a 3-month Euribor contract's reference period."""
    y, m = strip_month(strip)
    end_y, end_m = y + (m + 2) // 12, (m + 2) % 12 + 1
    return C.third_wednesday(y, m), C.third_wednesday(end_y, end_m)


def dfr_series(ctx):
    """date -> deposit facility rate in force (%), from every archived file."""
    out = {}
    for path in C.archived(ctx, BANK, "dfr", "csv"):
        for r in csv.DictReader(open(path, encoding="utf-8-sig")):
            try:
                out[C.parse_date(r["TIME_PERIOD"])] = float(r["OBS_VALUE"])
            except (KeyError, ValueError):
                continue
    return out


def dfr_on(series, day):
    """The rate in force on `day` (a policy rate, not a fixing - same day counts)."""
    return C.rate_before(series, day + dt.timedelta(days=1))[1]


def decisions(ctx, legacy_meetings=()):
    """ECB monetary-policy decision dates: every archived Governing Council
    calendar (Day 2 of a two-day meeting, or a single-day one) plus the meeting
    dates in the old rateprobability snapshots (they cover past decisions)."""
    out = {dt.date.fromisoformat(m) for m in legacy_meetings}
    for path in C.archived(ctx, BANK, "gc_calendar", "html"):
        text = open(path, encoding="utf-8", errors="replace").read()
        text = re.sub(r"(?s)<script.*?</script>", "", text)
        flat = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " | ", text)))
        days = {}
        for m in re.finditer(r"(\d{2}/\d{2}/\d{4})[ |]+([^|]{0,120})", flat):
            label = m.group(2).lower()
            if "monetary policy meeting" in label and "non-monetary" not in label:
                days[dt.datetime.strptime(m.group(1), "%d/%m/%Y").date()] = "day 1" in label
        for d, is_day1 in days.items():
            if not (is_day1 and d + dt.timedelta(days=1) in days):
                out.add(d)
    return sorted(out)


def check_effective_lag(ctx, dfr, decided):
    """Every DFR change should start EFFECTIVE_LAG_DAYS after a decision."""
    days = sorted(dfr)
    for a, b in zip(days, days[1:]):
        if dfr[a] == dfr[b]:
            continue
        prior = [d for d in decided if d < b and (b - d).days <= 14]
        if not prior:
            ctx.note(BANK, f"DFR changed on {b} with no known decision before it - "
                           f"effective-date lag not checked for it")
        elif (b - prior[-1]).days != EFFECTIVE_LAG_DAYS:
            ctx.problem(BANK, f"EFFECTIVE-DATE APPROXIMATION BROKE: decision {prior[-1]} "
                              f"took effect {b} ({(b - prior[-1]).days}d, not "
                              f"{EFFECTIVE_LAG_DAYS}d) - meeting mapping may be wrong")


def live_quotes(ctx):
    """[(as_of, as_of_time, strip, price, volume)] from archived contract-data."""
    out = []
    for path in C.archived(ctx, BANK, "euribor", "json"):
        try:
            data = json.load(open(path))
        except (json.JSONDecodeError, OSError) as e:
            ctx.problem(BANK, f"{path}: unreadable ({e})")
            continue
        for c in data:
            try:
                t = dt.datetime.strptime(c["lastTime"], "%m/%d/%Y %I:%M %p GMT")
            except (KeyError, TypeError, ValueError):
                continue
            out.append((t.date(), t.strftime("%Y-%m-%dT%H:%M:00Z"), c["marketStrip"],
                        c.get("lastPrice"), c.get("volume") or 0))
    return out


def history_bars(ctx):
    """strip -> {date: settlement}, merged over every archived history file."""
    out = {}
    for path in C.archived(ctx, BANK, "euribor_hist", "json"):
        try:
            data = json.load(open(path))
        except (json.JSONDecodeError, OSError) as e:
            ctx.problem(BANK, f"{path}: unreadable ({e})")
            continue
        for rec in data.values():
            for day, price in rec.get("bars", []):
                try:
                    d = dt.datetime.strptime(day, "%a %b %d %H:%M:%S %Y").date()
                except ValueError:
                    continue
                out.setdefault(rec["strip"], {})[d] = float(price)
    return out


# --- rows --------------------------------------------------------------------

def build(ctx, legacy_meetings=()):
    dfr = dfr_series(ctx)
    decided = decisions(ctx, legacy_meetings)
    global decision_calendar
    decision_calendar = [d.isoformat() for d in decided]
    effective = [(d + dt.timedelta(days=EFFECTIVE_LAG_DAYS)).isoformat() for d in decided]
    check_effective_lag(ctx, dfr, decided)

    quotes = live_quotes(ctx)
    # Liquidity is judged on the newest live quote per contract. A contract
    # that fails it is skipped everywhere, history included (bars carry no
    # volume, so they cannot be checked on their own).
    newest = {}
    for q in quotes:
        if q[2] not in newest or q[0] >= newest[q[2]][0]:
            newest[q[2]] = q
    thin = {s for s, q in newest.items() if q[4] < MIN_VOLUME}
    for s in sorted(thin, key=strip_month):
        ctx.note(BANK, f"{s}: volume {newest[s][4]} < {MIN_VOLUME} - skipped as "
                       f"illiquid (its history too)")

    obs = {}   # (as_of, strip) -> (price, as_of_time)
    for strip, bars in history_bars(ctx).items():
        if strip not in thin:
            for d, price in bars.items():
                obs[(d, strip)] = (price, "")
    for as_of, stamp, strip, price, vol in quotes:
        if strip not in thin and vol >= MIN_VOLUME and price:
            obs[(as_of, strip)] = (float(price), stamp)   # live beats the bar

    rows, missing_rate, spread_log = [], set(), {}
    for (as_of, strip), (price, stamp) in obs.items():
        try:
            start, end = period(strip)
        except ValueError as e:
            ctx.note(BANK, str(e))
            continue
        implied = 100 - price
        cur = dfr_on(dfr, as_of)
        if cur is None:
            missing_rate.add(as_of)
        bps = None if cur is None else (implied - cur) * 100
        r = C.row(BANK, as_of, start, implied, bps, as_of_time=stamp)
        r["_period_end"] = end.isoformat()
        rows.append(r)
        if cur is not None and start >= as_of:
            prev = spread_log.get(as_of)
            if prev is None or start < prev[0]:
                spread_log[as_of] = (start, strip, implied, cur)

    # One decision per probability: keep prob_move_pct on the front row only
    # when exactly one decision takes effect between as_of and its window end.
    by_day = {}
    for r in rows:
        by_day.setdefault(r["as_of"], []).append(r)
    for as_of, snap in by_day.items():
        front = min((r for r in snap if r["meeting"] >= as_of),
                    key=lambda r: r["meeting"], default=None)
        for r in snap:
            n = sum(1 for e in effective if as_of < e <= r["_period_end"])
            if r is not front or n != 1:
                r["prob_move_pct"] = ""

    C.report_missing_rate(ctx, BANK, missing_rate, "ECB deposit-rate")
    write_spread(ctx, spread_log)
    return rows


def write_spread(ctx, log):
    """data/ecb_spread.csv - front Euribor implied minus DFR per as_of - and
    print the newest, so drift in the Euribor-DFR basis stays visible."""
    if not log:
        return
    path = os.path.join(os.path.dirname(os.path.abspath(ctx.rawdir)), "ecb_spread.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["as_of", "front_contract", "front_implied", "dfr", "spread_bps"])
        for d in sorted(log):
            _, strip, implied, cur = log[d]
            w.writerow([d, strip, round(implied, 4), cur, round((implied - cur) * 100, 1)])
    d = max(log)
    _, strip, implied, cur = log[d]
    ctx.note(BANK, f"spread {d}: front {strip} implied {implied:.3f}% - DFR {cur:.2f}% "
                   f"= {(implied - cur) * 100:+.1f}bp (Euribor-DFR basis + expectations; "
                   f"history in {path})")
