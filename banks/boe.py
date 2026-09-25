"""BoE - fully automatable.

Current rate: SONIA (IUDSOIA) from the BoE statistical database.
Expectations: the BoE's own OIS instantaneous forward curve.
    latest-yield-curve-data.zip -> "OIS daily data current month.xlsx"
    -> sheet "1. fwds, short end": row = date, column = months ahead (1..60)

The zip also holds GLC Nominal/Real/Inflation files - government bond curves,
NOT policy expectations. Only the OIS file is used.

The current-month file restarts every month, so history exists only because
each day's copy is archived. For a backfill, drop the BoE archive workbook
("OIS daily data_2025 to present.xlsx") into data/raw/boe/ renamed to
<any-date>.ois.xlsx - it has the same sheet.

`meeting` = as_of + N months, the date each forward refers to - not an MPC date.
"""
import csv
import datetime as dt
import io
import zipfile

from . import common as C

BANK = "boe"
# The doc's fromshowcolumns.asp URL now answers with an HTML "search again"
# page; the database's CSV export endpoint is _iadb-fromshowcolumns.asp.
SONIA = ("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
         "?csv.x=yes&Datefrom={frm}&Dateto=now&SeriesCodes=IUDSOIA"
         "&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")
ZIP = ("https://www.bankofengland.co.uk/-/media/boe/files/statistics/"
       "yield-curves/latest-yield-curve-data.zip")
OIS_MEMBER = "OIS daily data current month.xlsx"
SHEET = "1. fwds, short end"


def fetch(ctx):
    frm = (ctx.today - dt.timedelta(days=90)).strftime("%d/%b/%Y")
    C.save(C.archive_path(ctx, BANK, "sonia", "csv"), C.http_get(SONIA.format(frm=frm)))
    z = zipfile.ZipFile(io.BytesIO(C.http_get(ZIP)))
    if OIS_MEMBER not in z.namelist():
        raise ValueError(f"zip has no {OIS_MEMBER!r}: {z.namelist()}")
    # Keep only the OIS workbook (~95KB), not the 1MB of gilt curves.
    C.save(C.archive_path(ctx, BANK, "ois", "xlsx"), z.read(OIS_MEMBER))


def sonia_series(ctx):
    out = {}
    for path in C.archived(ctx, BANK, "sonia", "csv"):
        for r in csv.DictReader(open(path, encoding="utf-8-sig")):
            try:
                # "22 Sep 2026" (the doc's sample had "14 Sep 26"; both parse)
                out[C.parse_date(r["DATE"])] = float(r["IUDSOIA"])
            except (KeyError, ValueError):
                continue
    return out


def forwards(ctx, path):
    """date -> {months_ahead: fwd %}"""
    rows = C.xlsx_sheet(open(path, "rb").read(), SHEET)
    header = next((r for r in rows if r and r[0] == "months:"), None)
    if header is None:
        raise ValueError("no 'months:' header row")
    months = {i: round(float(v)) for i, v in enumerate(header) if i and v}
    out = {}
    for r in rows:
        if not r or not r[0]:
            continue
        try:
            day = C.excel_date(r[0])
        except ValueError:
            continue  # header / label rows
        out[day] = {n: float(r[i]) for i, n in months.items()
                    if i < len(r) and r[i] not in (None, "", "#N/A")}
    return out


def build(ctx):
    sonia = sonia_series(ctx)
    merged, missing_rate = {}, set()
    for path in C.archived(ctx, BANK, "ois", "xlsx"):
        try:
            curve = forwards(ctx, path)
        except (KeyError, ValueError, OSError) as e:
            ctx.problem(BANK, f"{path}: unreadable ({e})")
            continue
        stamp, newest = C.mtime_utc(path), max(curve, default=None)
        for as_of, fwd in curve.items():
            _, cur = C.rate_before(sonia, as_of)
            if cur is None:
                missing_rate.add(as_of)
            for n, rate in fwd.items():
                bps = None if cur is None else (rate - cur) * 100
                new = C.row(BANK, as_of, C.add_months(as_of, n), rate, bps,
                            as_of_time=stamp if as_of == newest else "")
                key = (new["as_of"], new["meeting"])
                old = merged.get(key)
                if old is None or new["as_of_time"] or not old["as_of_time"]:
                    merged[key] = new
    C.report_missing_rate(ctx, BANK, missing_rate, "SONIA")
    return list(merged.values())
