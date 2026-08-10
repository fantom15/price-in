#!/usr/bin/env python3
"""Fetch FX and commodity prices.

Both sources are carried over from tradewind-system/scraper-army, with storage
changed to CSV and httpx/yfinance swapped for urllib to keep this project
stdlib-only:

  polygon (volume.py)      FX pairs and metals - C: prefixed tickers, OHLCV.
                           Needs POLYGON_API_KEY (environment or .env).
  yahoo   (market_data.py) DXY and WTI futures, which are NOT on the polygon
                           plan - polygon returns an empty result for I:DXY
                           and C:WTIUSD. No key required.

Both serve bars through today.

To add an instrument, add one line to SERIES with the source that carries it.
Polygon prefixes FX and metals with `C:` (C:EURUSD, C:XAUUSD); yahoo uses its
own symbols (DX-Y.NYB, CL=F, GC=F).

Volume caveat, inherited from the tradewind scraper: for spot FX, Polygon's
volume is an aggregated ACTIVITY PROXY (tick/quote counts across its venues),
not true traded volume - spot FX is decentralised, so no single true volume
exists. Read it as "busy vs quiet day". For metals it is closer to real.

Output: data/prices.csv
    date,series,open,high,low,close,volume

Usage:
    python3 prices.py                       # last 60 days
    python3 prices.py --backfill 2020-01-01
    python3 prices.py --series eurusd wti
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AGGS = ("https://api.polygon.io/v2/aggs/ticker/{ticker}"
        "/range/1/day/{start}/{end}")
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

# name -> (source, ticker, label)
SERIES = {
    "eurusd": ("polygon", "C:EURUSD",  "EUR/USD"),
    "usdcad": ("polygon", "C:USDCAD",  "USD/CAD"),
    "dxy":    ("yahoo",   "DX-Y.NYB",  "US Dollar Index"),
    "wti":    ("yahoo",   "CL=F",      "WTI crude"),
}

FIELDS = ["date", "series", "open", "high", "low", "close", "volume", "source"]

UA = "price-in/1.0 (prices fetcher)"
ENV_PATH = Path(__file__).resolve().parent / ".env"


def api_key():
    """POLYGON_API_KEY from the environment, falling back to .env."""
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if key:
        return key
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if line.strip().startswith("POLYGON_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'").strip('"')
    return ""


def _get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_polygon(name, ticker, start, end, key, timeout=60):
    url = AGGS.format(ticker=ticker, start=start, end=end) + "?" + \
        urllib.parse.urlencode({"apiKey": key, "limit": 50000, "sort": "asc"})
    payload = _get(url, timeout)
    rows = []
    for b in payload.get("results") or []:
        # Polygon stamps each bar with epoch ms at UTC midnight.
        rows.append({
            "date": dt.datetime.fromtimestamp(
                b["t"] / 1000, dt.timezone.utc).strftime("%Y-%m-%d"),
            "series": name,
            "open": b.get("o"), "high": b.get("h"),
            "low": b.get("l"), "close": b.get("c"),
            "volume": int(b.get("v") or 0),
            "source": "polygon",
        })
    return rows


def fetch_yahoo(name, ticker, start, end, timeout=60):
    """Daily bars from Yahoo's chart endpoint (no key, unofficial)."""
    url = YAHOO.format(ticker=urllib.parse.quote(ticker)) + "?" + \
        urllib.parse.urlencode({
            "period1": int(dt.datetime.fromisoformat(start)
                           .replace(tzinfo=dt.timezone.utc).timestamp()),
            "period2": int(dt.datetime.fromisoformat(end)
                           .replace(tzinfo=dt.timezone.utc).timestamp()
                           + 86400),
            "interval": "1d",
        })
    payload = _get(url, timeout)
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        return []
    r0 = result[0]
    q = (r0.get("indicators") or {}).get("quote") or [{}]
    q = q[0]
    rows = []
    for i, ts in enumerate(r0.get("timestamp") or []):
        close = (q.get("close") or [None] * (i + 1))[i]
        if close is None:          # holidays come back as nulls
            continue
        rows.append({
            "date": dt.datetime.fromtimestamp(
                ts, dt.timezone.utc).strftime("%Y-%m-%d"),
            "series": name,
            "open": (q.get("open") or [None])[i],
            "high": (q.get("high") or [None])[i],
            "low": (q.get("low") or [None])[i],
            "close": close,
            "volume": int((q.get("volume") or [0])[i] or 0),
            "source": "yahoo",
        })
    return rows


def load_existing(path):
    """(date, series) -> row, so re-runs update in place instead of duplicating."""
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        for r in csv.DictReader(f):
            rows[(r.get("date"), r.get("series"))] = r
    return rows


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--series", nargs="+", default=sorted(SERIES),
                    choices=sorted(SERIES), metavar="NAME",
                    help=f"default: {' '.join(sorted(SERIES))}")
    ap.add_argument("--backfill", metavar="YYYY-MM-DD",
                    help="fetch history from this date (default: last 60 days)")
    ap.add_argument("--outdir", default="data")
    ap.add_argument("-o", "--out", help="default: <outdir>/prices.csv")
    a = ap.parse_args()

    # Only polygon series need the key; a yahoo-only run must not be blocked.
    key = api_key()
    if not key and any(SERIES[n][0] == "polygon" for n in a.series):
        sys.exit("set POLYGON_API_KEY (environment or .env)")

    start = a.backfill or (dt.date.today() - dt.timedelta(days=60)).isoformat()
    end = dt.date.today().isoformat()

    os.makedirs(a.outdir, exist_ok=True)
    out = a.out or os.path.join(a.outdir, "prices.csv")

    merged, failed = load_existing(out), []
    added = 0
    for name in a.series:
        source, ticker, label = SERIES[name]
        try:
            if source == "polygon":
                rows = fetch_polygon(name, ticker, start, end, key)
            else:
                rows = fetch_yahoo(name, ticker, start, end)
        except urllib.error.HTTPError as e:
            failed.append(name)
            print(f"  {name:<8} {ticker:<10} FAILED: HTTP {e.code} "
                  f"({'bad api key' if e.code in (401, 403) else e.reason})",
                  file=sys.stderr)
            continue
        except (urllib.error.URLError, json.JSONDecodeError, OSError,
                KeyError, IndexError) as e:
            failed.append(name)
            print(f"  {name:<8} {ticker:<10} FAILED: {e}", file=sys.stderr)
            continue

        if not rows:
            # Polygon answers status=OK with no results when a ticker is not
            # on your plan - silent unless called out explicitly.
            failed.append(name)
            print(f"  {name:<8} {ticker:<10} NO DATA - wrong ticker, or not "
                  f"included in your {source} plan", file=sys.stderr)
            continue

        new = 0
        for row in rows:
            k = (row["date"], row["series"])
            if k not in merged:
                new += 1
            merged[k] = row
        added += new
        dates = sorted(k[0] for k in merged if k[1] == name)
        print(f"  {name:<8} {ticker:<10} {source:<8} {len(rows):>5} bars  "
              f"{new:>4} new  latest={dates[-1]} close={rows[-1]['close']}",
              file=sys.stderr)

    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for k in sorted(merged):
            w.writerow(merged[k])

    print(f"\n{len(merged)} rows ({added} new) -> {out}", file=sys.stderr)
    if failed:
        sys.exit(f"failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
