#!/usr/bin/env python3
"""Fetch CME CVOL index families from the QuikStrike dashboard.

The chart data is not served by a JSON endpoint. It is embedded in the ASP.NET
partial-postback response as the `JSONSettings` property of the
`UserControls.VolIndex.HistoryChart.Chart` client component, so we replay the
postback and pull that blob out.

Two things to know about this endpoint:

  * It is STATEFUL. The selected measure and product set persist server-side for
    the session, so every request sets them explicitly rather than relying on
    whatever was selected last. Do not run these concurrently on one session.
  * Credentials expire with the browser session. Re-copy them from the
    dashboard URL when the script reports the component was not found.

Environment:
    QS_QSID    session id from the dashboard URL (?qsid=...)
    QS_INSID   instrument id from the dashboard URL (?insid=...)

Usage:
    python3 quikstrike.py --measure cvol --out data/cvol.csv
    python3 quikstrike.py --all-measures --outdir data
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request

BASE = "https://cmegroup-tools.quikstrike.net/User/QuikStrikeView.aspx"
COMPONENT = "UserControls.VolIndex.HistoryChart.Chart"

_PREFIX = ("ctl00$MainContent$ucViewControl_IntegratedVolIndexDashboard"
           "$ucViewControl")
_ITEM_PICKER = _PREFIX + "$ucVolIndexItemPicker$lvFamilyItems"

# Switches the dashboard to the chart view. The value picker only exists on
# that view - land on the tile/dashboard view and `ucValuePicker` is absent
# from the page entirely, so the measure postback below silently does nothing
# and the response comes back with sparklines instead of the history chart.
CHART_VIEW = _PREFIX + "$ucViewPicker$lbChart"

# Each measure is its own link button in the value picker.
MEASURES = {
    "cvol":      _PREFIX + "$ucValuePicker$lbCVolIndex",
    "skew":      _PREFIX + "$ucValuePicker$lbSkew",
    "atm":       _PREFIX + "$ucValuePicker$lbATM",
    "convexity": _PREFIX + "$ucValuePicker$lbConvexity",
    "skewratio": _PREFIX + "$ucValuePicker$lbSkewRatio",
    "upvar":     _PREFIX + "$ucValuePicker$lbUpVar",
    "downvar":   _PREFIX + "$ucValuePicker$lbDownVar",
}

# Product families in the item picker, and how many items each contains.
# Ticking every box widens the pull from the 8 default FX products to all 36
# (rates, FX, metals, energy, ags), which is where S1VL/SRVL live.
FAMILY_SIZES = {0: 5, 1: 5, 2: 3, 3: 8, 4: 5, 5: 4, 6: 10}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")


def _post(url, fields, timeout):
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://cmegroup-tools.quikstrike.net",
        "Referer": url,
        "X-MicrosoftAjax": "Delta=true",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _fields(target, all_products):
    """Postback body for clicking one link button."""
    fields = [("ctl00$smPublic", f"ctl00$upMain|{target}")]
    if all_products:
        for fam, count in FAMILY_SIZES.items():
            for i in range(count):
                fields.append(
                    (f"{_ITEM_PICKER}$ctrl{fam}$lvItems$ctrl{i}$chkItem", "on"))
    return fields + [
        ("__EVENTTARGET", target),
        ("__EVENTARGUMENT", ""),
        ("__VIEWSTATEGENERATOR", "7E260167"),
        ("__ASYNCPOST", "true"),
    ]


def fetch(qsid, insid, measure="cvol", all_products=True, timeout=180):
    """Select the chart view, then the measure; return the delta response.

    Two postbacks, because the dashboard keeps the current view in server-side
    session state and the value picker is only rendered on the chart view. If
    the session happens to be sitting on the tile view, posting the measure
    alone targets a control that is not on the page - the request succeeds but
    returns the tile sparklines, with no history chart in it.
    """
    qs = urllib.parse.urlencode({
        "viewitemid": "IntegratedVolIndexDashboard",
        "insid": insid,
        "qsid": qsid,
    })
    url = f"{BASE}?{qs}"

    _post(url, _fields(CHART_VIEW, all_products), timeout)
    return _post(url, _fields(MEASURES[measure], all_products), timeout)


def extract_settings(doc):
    """Pull the JSONSettings blob out of the $create(...) call."""
    i = doc.find(COMPONENT)
    if i < 0:
        # Distinguish the two ways this fails: an expired session returns a
        # short login/redirect delta, while a live session on the wrong view
        # returns a full page of tile sparklines. Saying "qsid expired" for
        # both sends you chasing a credential that is perfectly fine.
        hint = ("the qsid has most likely expired; reopen the dashboard and "
                "copy a fresh one from the URL")
        if "SparkChart" in doc:
            hint = ("the session is alive but returned the tile view - the "
                    "chart-view postback did not take effect")
        raise SystemExit(f"chart component not found - {hint}")
    m = re.search(r'"JSONSettings":"', doc[i:])
    if not m:
        raise SystemExit("JSONSettings property not found in response")

    seg, j, out = doc[i:], m.end(), []
    while j < len(seg):                      # walk the JS string literal
        c = seg[j]
        if c == "\\":
            out.append(seg[j:j + 2])
            j += 2
            continue
        if c == '"':
            break
        out.append(c)
        j += 1
    return json.loads(json.loads('"' + "".join(out) + '"'))


def to_rows(cfg):
    """Yield (ticker, series_name, date, value) for every point."""
    for s in cfg.get("Series", []):
        name = s.get("name") or ""
        m = re.search(r"\(([A-Z0-9]+)\)", name)
        ticker = m.group(1) if m else name
        for p in s.get("data") or []:
            x, y = p.get("x"), p.get("y")
            if x is None or y is None:
                continue
            date = dt.datetime.fromtimestamp(
                x / 1000.0, dt.timezone.utc).strftime("%Y-%m-%d")
            yield ticker, name, date, y


def write_csv(cfg, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "series", "date", "value"])
        n = 0
        for row in to_rows(cfg):
            w.writerow(row)
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("-m", "--measure", choices=sorted(MEASURES), default="cvol")
    g.add_argument("--all-measures", action="store_true",
                   help="pull every measure in sequence")
    ap.add_argument("-o", "--out", help="output csv (single measure only)")
    ap.add_argument("--outdir", default="data")
    ap.add_argument("--fx-only", action="store_true",
                    help="only the 8 default FX products instead of all 36")
    a = ap.parse_args()

    qsid, insid = os.environ.get("QS_QSID"), os.environ.get("QS_INSID")
    if not qsid or not insid:
        sys.exit("set QS_QSID and QS_INSID (copy them from the dashboard URL)")

    measures = sorted(MEASURES) if a.all_measures else [a.measure]
    os.makedirs(a.outdir, exist_ok=True)

    for measure in measures:
        cfg = extract_settings(
            fetch(qsid, insid, measure, all_products=not a.fx_only))
        out = a.out if (a.out and not a.all_measures) \
            else os.path.join(a.outdir, f"{measure}.csv")
        n = write_csv(cfg, out)
        print(f"{cfg.get('Title'):<34} {len(cfg.get('Series', [])):>3} series  "
              f"{n:>7} points -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
