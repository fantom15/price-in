"""BoC - fully automatable.

Current rate: CORRA from the Bank of Canada Valet api.
Expectations: Montréal Exchange CORRA futures settlements.
    COA  one-month CORRA futures  - reference period = the contract month
    CRA  three-month CORRA futures - reference quarter starts on the 3rd
         Wednesday (IMM date) of the contract month

The `meeting` column holds the START of each contract's reference period, not a
BoC decision date: build_sheet.py then takes the first period starting on/after
as_of as "next" and the one nearest +365d as the 12m path.
"""
import csv
import datetime as dt
import io

from . import common as C

BANK = "boc"
VALET = "https://www.bankofcanada.ca/valet/observations/group/CORRA/csv?recent=60"
# The doc's URL (symbol/from/to only) returns the HTML page; the CSV needs the
# form's own `f` and `dnld` fields too.
MX = ("https://www.m-x.ca/en/trading/data/historical"
      "?symbol={sym}&f={sym}&from={frm}&to={to}&dnld=1")
SYMBOLS = ["COA", "CRA"]
# Refetch a trailing window every run so a missed day heals itself.
WINDOW_DAYS = 10


def fetch(ctx):
    C.save(C.archive_path(ctx, BANK, "corra", "csv"), C.http_get(VALET))
    frm = (ctx.today - dt.timedelta(days=WINDOW_DAYS)).isoformat()
    for sym in SYMBOLS:
        body = C.http_get(MX.format(sym=sym, frm=frm, to=ctx.today.isoformat()))
        if b"Settlement Price" not in body[:2000]:
            raise ValueError(f"M-X {sym}: no 'Settlement Price' column")
        C.save(C.archive_path(ctx, BANK, sym.lower(), "csv"), body)


def corra_series(ctx):
    """date -> CORRA %. Valet prepends ~20 metadata lines; data starts after
    the line reading "OBSERVATIONS"."""
    out = {}
    for path in C.archived(ctx, BANK, "corra", "csv"):
        text = open(path, encoding="utf-8-sig").read()
        _, sep, body = text.partition('"OBSERVATIONS"')
        if not sep:
            ctx.note(BANK, f"{path}: no OBSERVATIONS marker, skipped")
            continue
        for r in csv.DictReader(io.StringIO(body.strip())):
            try:
                out[C.parse_date(r["date"])] = float(r["AVG.INTWO"])
            except (KeyError, ValueError):
                continue
    return out


def period_start(sym, code, ref):
    year, month = C.contract_month(code, sym, ref)
    return dt.date(year, month, 1) if sym == "COA" else C.third_wednesday(year, month)


def period_end(sym, start):
    """COA: last day of its month. CRA: the next IMM date, 3 months on."""
    if sym == "COA":
        return C.add_months(start, 1) - dt.timedelta(days=1)
    y, m = start.year + (start.month + 2) // 12, (start.month + 2) % 12 + 1
    return C.third_wednesday(y, m)


def build(ctx):
    corra = corra_series(ctx)
    merged, missing_rate = {}, set()
    for sym in SYMBOLS:
        for path in C.archived(ctx, BANK, sym.lower(), "csv"):
            stamp = C.mtime_utc(path)
            recs = list(csv.DictReader(open(path, encoding="utf-8-sig")))
            newest = max((r["Date"] for r in recs), default=None)
            for r in recs:
                try:
                    as_of = C.parse_date(r["Date"])
                    code = r["Symbol"]
                    # Settlement, never Last: Last is 0 on no-trade days.
                    price = float(r["Settlement Price"])
                    meeting = period_start(sym, code, as_of)
                except (KeyError, ValueError) as e:
                    ctx.note(BANK, f"{path}: bad row skipped ({e})")
                    continue
                if price <= 0:
                    ctx.note(BANK, f"{as_of} {code}: no settlement price, left empty")
                    continue
                implied = 100 - price
                _, cur = C.rate_before(corra, as_of)
                if cur is None:
                    missing_rate.add(as_of)
                bps = None if cur is None else (implied - cur) * 100
                new = C.row(BANK, as_of, meeting, implied, bps,
                            as_of_time=stamp if r["Date"] == newest else "")
                new["_sym"] = sym
                new["_period_end"] = period_end(sym, meeting).isoformat()
                key = (new["as_of"], new["meeting"])
                old = merged.get(key)
                # Later files win, except an unstamped copy never replaces the
                # stamped reading of the same settlement.
                if old is None or new["as_of_time"] or not old["as_of_time"]:
                    merged[key] = new
    C.report_missing_rate(ctx, BANK, missing_rate, "CORRA")
    # COA (monthly) is the near curve, CRA (quarterly) only the path beyond it.
    # A CRA quarter starting inside the COA months - e.g. CRAU26 from 16 Sep -
    # would otherwise be picked as the "next meeting" ahead of the October COA
    # and make the next-meeting odds jump when the row switches back.
    last_coa = {}
    for r in merged.values():
        if r["_sym"] == "COA":
            last_coa[r["as_of"]] = max(last_coa.get(r["as_of"], ""), r["meeting"])
    out = []
    for r in merged.values():
        sym = r.pop("_sym")
        if sym == "CRA" and r["meeting"] <= last_coa.get(r["as_of"], ""):
            continue
        out.append(r)
    return out
