#!/usr/bin/env python3
"""Fetch market-implied policy-rate paths from rateprobability.com.

Unlike the QuikStrike dashboard, this is a plain public JSON API - one endpoint
per central bank, no auth, no session state:

    https://rateprobability.com/api/<bank>/latest

The important limitation is that it is a SNAPSHOT api, not a time series. Each
response carries today plus exactly four backdated snapshots (1w/3w/6w/10w ago);
there is no way to request an arbitrary date - `?date=`/`?as_of=` are ignored
and other paths fall through to the SPA shell.

So history is ACCUMULATED, not fetched. Every run archives the raw JSON under
`<outdir>/raw/<bank>/<as_of>.json` and rebuilds the CSV from every snapshot
ever collected. Run it daily and the history fills in going forward; the ago_*
buckets seed roughly 10 weeks of sparse back-history on the first run. The raw
archive is the source of truth - it keeps every field the api returns, not just
the ones the CSV projects, so new sheet columns can be backfilled later from
snapshots already on disk without re-fetching.

Each CSV row is one (bank, as_of, meeting) triple:

    bank,as_of,as_of_time,meeting,implied_rate,prob_move_pct,is_cut,num_moves,change_bps,horizon

`as_of_time` is the api's `generated_at_utc` for the primary `today` snapshot -
a precise UTC instant recording WHEN the reading was taken, so staleness is
detectable downstream. It is empty for backdated (ago_*) rows, which the server
reconstructs and does not stamp. (Do not confuse this with the bare `as_of`
DATE, which is all the ago_* blocks carry.)

`prob_move_pct` and `num_moves` are signed here (negative = cut) - the api
reports magnitude plus a separate `prob_is_cut`/`num_moves_is_cut` flag, which
is easy to drop on the floor when pivoting. `change_bps` is already signed.

Usage:
    python3 rates.py                       # all banks -> data/rates.csv
    python3 rates.py --banks fed ecb boc
    python3 rates.py --no-fetch            # rebuild csv from the archive only
                                           # (backfills as_of_time for old rows)
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://rateprobability.com/api/{bank}/latest"

# Free tier. rbnz/snb/srb exist but answer 401 "Pro subscription required",
# so they are not fetched by default - pass them explicitly if you have a
# subscription (the cookie/token would need adding to fetch()).
BANKS = ["fed", "ecb", "boe", "boj", "boc", "rba"]
PRO_BANKS = ["rbnz", "snb", "srb"]

# The four backdated snapshots each response carries, alongside `today`.
AGO_KEYS = ["ago_1w", "ago_3w", "ago_6w", "ago_10w"]

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")

# CHANGED: added as_of_time (second position, right after the as_of date).
FIELDS = ["bank", "as_of", "as_of_time", "meeting", "implied_rate",
          "prob_move_pct", "is_cut", "num_moves", "change_bps", "horizon"]


def fetch(bank, timeout=60):
    req = urllib.request.Request(
        BASE.format(bank=bank),
        headers={"Accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def as_of_date(block):
    """Snapshot date as YYYY-MM-DD.

    `as_of` is formatted inconsistently across banks - the Fed gives a bare
    date, the ECB an ISO timestamp, the BoC "2026-07-28 17:11:37 EDT" - so take
    the first whitespace/T-delimited token. Backdated blocks carry `used_date`
    (what the server actually resolved to) rather than `as_of`.
    """
    v = (block.get("used_date") or block.get("requested_date")
         or block.get("as_of"))
    if not v:
        return None
    return str(v).replace("T", " ").split()[0]


def as_of_time(doc):  # NEW
    """The precise instant the api generated this response.

    `generated_at_utc` (e.g. "2026-07-29T04:01:10.012Z") is one consistent UTC
    field present at the top level of every bank's payload - cleaner than the
    per-bank `as_of` formats, and the value staleness checks actually want.
    Only meaningful for the primary `today` snapshot; returned as-is (ISO UTC).
    """
    return doc.get("generated_at_utc") or ""


def snapshots(doc):
    """Yield (as_of, horizon, rows) for today plus each backdated block."""
    for key in ["today"] + AGO_KEYS:
        block = doc.get(key)
        if not isinstance(block, dict) or not block.get("rows"):
            continue
        as_of = as_of_date(block)
        if as_of:
            yield as_of, ("today" if key == "today" else key), block["rows"]


def to_rows(bank, doc):
    gen_time = as_of_time(doc)  # NEW: one timestamp per response (the `today` read)
    for as_of, horizon, rows in snapshots(doc):
        for r in rows:
            meeting = r.get("meeting_iso")
            if not meeting:
                continue
            # Restore sign: the api reports magnitude + a direction flag.
            prob, moves = r.get("prob_move_pct"), r.get("num_moves")
            cut = bool(r.get("prob_is_cut"))
            yield {
                "bank": bank,
                "as_of": as_of,
                # NEW: stamp only the primary observation; ago_* are
                # server reconstructions and carry no generation instant.
                "as_of_time": gen_time if horizon == "today" else "",
                "meeting": meeting,
                "implied_rate": r.get("implied_rate_post_meeting"),
                "prob_move_pct": None if prob is None else (-prob if cut else prob),
                "is_cut": int(cut),
                "num_moves": None if moves is None else (
                    -moves if r.get("num_moves_is_cut") else moves),
                "change_bps": r.get("change_bps"),
                "horizon": horizon,
            }


def archive(doc, bank, rawdir):
    """Save the snapshot verbatim so history accumulates across runs."""
    d = os.path.join(rawdir, bank)
    os.makedirs(d, exist_ok=True)
    as_of = as_of_date(doc.get("today", {})) or dt.date.today().isoformat()
    path = os.path.join(d, f"{as_of}.json")
    with open(path, "w") as f:
        json.dump(doc, f)
    return path


def load_archive(bank, rawdir):
    d = os.path.join(rawdir, bank)
    if not os.path.isdir(d):
        return
    for name in sorted(os.listdir(d)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, name)) as f:
                yield json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  skipping {bank}/{name}: {e}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--banks", nargs="+", default=BANKS,
                    choices=BANKS + PRO_BANKS, metavar="BANK",
                    help=f"default: {' '.join(BANKS)}. "
                         f"{'/'.join(PRO_BANKS)} require a pro subscription")
    ap.add_argument("--outdir", default="data")
    ap.add_argument("-o", "--out", help="default: <outdir>/rates.csv")
    ap.add_argument("--no-fetch", action="store_true",
                    help="rebuild the csv from archived snapshots only")
    a = ap.parse_args()

    rawdir = os.path.join(a.outdir, "raw")
    os.makedirs(a.outdir, exist_ok=True)
    out = a.out or os.path.join(a.outdir, "rates.csv")

    # (bank, as_of, meeting) -> row. A `today` reading always wins over a
    # backdated estimate for the same date: the ago_* buckets are the server's
    # reconstruction, while `today` is the primary observation.
    merged, failed, paywalled = {}, [], []
    for bank in a.banks:
        if not a.no_fetch:
            try:
                archive(fetch(bank), bank, rawdir)
            except urllib.error.HTTPError as e:
                # 401 is the pro paywall, not a breakage - report and move on
                # so one locked bank cannot fail the whole run.
                (paywalled if e.code == 401 else failed).append(bank)
                print(f"{bank:<5} {'PRO ONLY' if e.code == 401 else f'FAILED: {e}'}",
                      file=sys.stderr)
            except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
                failed.append(bank)
                print(f"{bank:<5} FETCH FAILED: {e}", file=sys.stderr)

        for doc in load_archive(bank, rawdir):
            for r in to_rows(bank, doc):
                key = (r["bank"], r["as_of"], r["meeting"])
                if key not in merged or r["horizon"] == "today":
                    merged[key] = r

        dates = sorted({k[1] for k in merged if k[0] == bank})
        n = sum(1 for k in merged if k[0] == bank)
        print(f"{bank:<5} {len(dates):>3} dates {n:>5} rows  "
              f"{dates[0] if dates else '-'} .. {dates[-1] if dates else '-'}",
              file=sys.stderr)

    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for key in sorted(merged):
            w.writerow(merged[key])

    print(f"\n{len(merged)} rows -> {out}", file=sys.stderr)
    if paywalled:
        print(f"skipped (pro only): {', '.join(paywalled)}", file=sys.stderr)
    if failed:
        sys.exit(f"failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()