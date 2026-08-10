#!/usr/bin/env python3
"""Fetch CFTC Commitments of Traders positioning.

Ported from the tradewind-system scraper, with two changes for this project:
storage is CSV rather than Postgres, and it uses urllib instead of httpx so the
fetchers stay stdlib-only.

COT comes from two CFTC datasets with DIFFERENT schemas, normalized here into
one shape so FX and commodities can be analysed the same way:

  TFF (financial futures)   gpe5-46if : currencies + USD index
      speculators = leveraged funds ; commercials = dealers
  Disaggregated (commodities) 6dca-aqww : gold, silver, oil, copper
      speculators = non-commercials ; commercials = commercials

Unlike rateprobability, this api serves real history - `--backfill` pulls
everything from a date, so there is no accumulate-daily requirement. Reports
are published weekly (Friday, for the preceding Tuesday), so a daily run mostly
re-fetches the same rows; writes are idempotent on (report_date, symbol).

Output: data/cot.csv
    report_date,symbol,instrument,dataset,spec_long,spec_short,comm_long,
    comm_short,net_spec,net_comm,open_interest

Usage:
    python3 cot.py                        # recent weeks, merged into the csv
    python3 cot.py --backfill 2010-01-01  # full history
"""
import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TFF_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"  # currencies
DIS_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"  # commodities

# (symbol, instrument_name, cftc_code, dataset)
CONTRACTS = [
    # currencies (TFF: spec=lev_money, comm=dealer)
    ("EUR", "EURO FX",            "099741", "tff"),
    ("GBP", "BRITISH POUND",      "096742", "tff"),
    ("JPY", "JAPANESE YEN",       "097741", "tff"),
    ("AUD", "AUSTRALIAN DOLLAR",  "232741", "tff"),
    ("CAD", "CANADIAN DOLLAR",    "090741", "tff"),
    ("CHF", "SWISS FRANC",        "092741", "tff"),
    ("NZD", "NEW ZEALAND DOLLAR", "112741", "tff"),
    ("USD", "US DOLLAR INDEX",    "098662", "tff"),
    # commodities (disaggregated: spec=noncomm, comm=comm)
    ("GOLD",   "GOLD",          "088691", "dis"),
    ("SILVER", "SILVER",        "084691", "dis"),
    ("OIL",    "WTI CRUDE OIL", "06765A", "dis"),
    ("COPPER", "COPPER",        "085692", "dis"),
]

FIELDS = ["report_date", "symbol", "instrument", "dataset",
          "spec_long", "spec_short", "comm_long", "comm_short",
          "net_spec", "net_comm", "open_interest"]

UA = "price-in/1.0 (cot fetcher)"


def _i(v):
    """CFTC sends numbers as strings, and blanks for missing values."""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def normalize(rec, sym, instrument, dataset):
    """Map either CFTC schema onto the unified row."""
    if dataset == "tff":
        spec_l = _i(rec.get("lev_money_positions_long"))
        spec_s = _i(rec.get("lev_money_positions_short"))
        comm_l = _i(rec.get("dealer_positions_long_all"))
        comm_s = _i(rec.get("dealer_positions_short_all"))
    else:
        spec_l = _i(rec.get("noncomm_positions_long_all"))
        spec_s = _i(rec.get("noncomm_positions_short_all"))
        comm_l = _i(rec.get("comm_positions_long_all"))
        comm_s = _i(rec.get("comm_positions_short_all"))
    return {
        "report_date": str(rec["report_date_as_yyyy_mm_dd"]).split("T")[0],
        "symbol": sym,
        "instrument": instrument,
        "dataset": dataset,
        "spec_long": spec_l, "spec_short": spec_s,
        "comm_long": comm_l, "comm_short": comm_s,
        # Net positioning is what actually gets read; precomputing it keeps the
        # sign convention in one place rather than in every consumer.
        "net_spec": spec_l - spec_s,
        "net_comm": comm_l - comm_s,
        "open_interest": _i(rec.get("open_interest_all")),
    }


def fetch(url, code, start=None, timeout=60):
    if start:
        params = {
            "$where": (f"cftc_contract_market_code='{code}' "
                       f"AND report_date_as_yyyy_mm_dd >= '{start}T00:00:00'"),
            "$order": "report_date_as_yyyy_mm_dd ASC",
            "$limit": 5000,
        }
    else:
        params = {
            "cftc_contract_market_code": code,
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": 12,
        }
    req = urllib.request.Request(
        f"{url}?{urllib.parse.urlencode(params)}",
        headers={"Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def load_existing(path):
    """(report_date, symbol) -> row, so a re-run updates rather than duplicates."""
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        for r in csv.DictReader(f):
            rows[(r.get("report_date"), r.get("symbol"))] = r
    return rows


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backfill", metavar="YYYY-MM-DD",
                    help="fetch full history from this date")
    ap.add_argument("--outdir", default="data")
    ap.add_argument("-o", "--out", help="default: <outdir>/cot.csv")
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    out = a.out or os.path.join(a.outdir, "cot.csv")

    merged, failed = load_existing(out), []
    added = 0
    for sym, instrument, code, dataset in CONTRACTS:
        url = TFF_URL if dataset == "tff" else DIS_URL
        try:
            recs = fetch(url, code, a.backfill)
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            failed.append(sym)
            print(f"  {sym:<7} FAILED: {e}", file=sys.stderr)
            continue
        new = 0
        for rec in recs:
            try:
                row = normalize(rec, sym, instrument, dataset)
            except (KeyError, TypeError) as e:
                print(f"  {sym:<7} skipping malformed record: {e}",
                      file=sys.stderr)
                continue
            key = (row["report_date"], row["symbol"])
            if key not in merged:
                new += 1
            merged[key] = row
        added += new
        dates = sorted(k[0] for k in merged if k[1] == sym)
        print(f"  {sym:<7} {instrument:<20} {len(recs):>4} fetched  "
              f"{new:>4} new  latest={dates[-1] if dates else '-'}",
              file=sys.stderr)

    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for key in sorted(merged):
            w.writerow(merged[key])

    print(f"\n{len(merged)} rows ({added} new) -> {out}", file=sys.stderr)
    if failed:
        sys.exit(f"failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
