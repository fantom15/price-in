#!/usr/bin/env python3
"""Provision a QuikStrike session automatically - no browser, no manual paste.

QuikStrike is reached through an iframe on cmegroup.com. Hitting the iframe's
entry url mints a fresh insid/qsid pair and auto-logs-in, but only if the
request looks like it came from that page:

    Access to QuikStrike has been denied - unexpected null referrer
        at QuikStrike.BusinessLogic.LoginManager.PerformReferrerCheck

So a `Referer: cmegroup.com` header is mandatory. That is the whole gate - no
credentials and no captcha are involved.

Fresh ids are NOT enough on their own. insid/qsid are a pointer to server-side
session state, and a new session sits on the FedWatch tool, where the CVOL
controls do not exist: a measure postback against it returns an 80KB FedWatch
page instead of the 11MB chart response. The session has to be walked to the
chart first, exactly as a person clicking the site would:

    lbCVOLDashboard -> lbDashboard -> lbChart

The middle step is the one that is easy to miss. After the CVOL tab you land on
a product-family landing page that has no ucViewPicker/ucValuePicker at all;
lbDashboard is what renders them.

Each postback must carry the viewstate returned by the previous one, and all of
them must share one cookie jar.

Once warmed, the ids work from anywhere - quikstrike.py can use them with plain
urllib and no cookies, which is why this returns ids rather than a session.

Usage:
    python3 qs_session.py              # print QS_INSID / QS_QSID
    python3 qs_session.py --export     # shell-eval-able output

    from qs_session import provision
    insid, qsid = provision()
"""
import argparse
import http.cookiejar
import re
import sys
import urllib.parse
import urllib.request

REFERER = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"
ENTRY = ("https://cmegroup-tools.quikstrike.net/User/QuikStrikeTools.aspx"
         "?viewitemid=IntegratedFedWatchTool&userId=lwolf")
VIEW = "https://cmegroup-tools.quikstrike.net/User/QuikStrikeView.aspx"

# Control ids are relative to the tool that hosts the dashboard.
_FW = "ctl00$MainContent$ucViewControl_IntegratedFedWatchTool"
_VC = _FW + "$ucCVOLDashboardVC"
_ITEM_PICKER = _VC + "$ucVolIndexItemPicker$lvFamilyItems"

# Product families and their sizes, so the warm-up selects all 36 products
# rather than the 8 FX defaults. Mirrors quikstrike.FAMILY_SIZES.
FAMILY_SIZES = {0: 5, 1: 5, 2: 3, 3: 8, 4: 5, 5: 4, 6: 10}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")


def _viewstate(doc):
    """__VIEWSTATE from either a delta response or a full page."""
    m = (re.search(r'\|hiddenField\|__VIEWSTATE\|([^|]*)\|', doc)
         or re.search(r'id="__VIEWSTATE"[^>]*value="([^"]*)"', doc))
    return m.group(1) if m else ""


def provision(timeout=300, verbose=False):
    """Return (insid, qsid) for a session already walked to the CVOL chart."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj))

    def get(url, referer):
        req = urllib.request.Request(
            url, headers={"User-Agent": UA, "Referer": referer})
        r = opener.open(req, timeout=timeout)
        return r.geturl(), r.read().decode("utf-8", "replace")

    def post(url, fields):
        req = urllib.request.Request(
            url, data=urllib.parse.urlencode(fields).encode(), headers={
                "User-Agent": UA, "Referer": url, "Accept": "*/*",
                "X-MicrosoftAjax": "Delta=true",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type":
                    "application/x-www-form-urlencoded; charset=UTF-8"})
        return opener.open(req, timeout=timeout).read().decode("utf-8",
                                                               "replace")

    # 1. mint ids. The referer header is what makes the auto-login succeed.
    final, _ = get(ENTRY, REFERER)
    m_i, m_q = re.search(r'insid=(\d+)', final), \
        re.search(r'qsid=([0-9a-f-]{36})', final)
    if not (m_i and m_q):
        raise SystemExit(
            "could not provision a session - no insid/qsid in the redirect.\n"
            f"landed on: {final[:200]}")
    insid, qsid = m_i.group(1), m_q.group(1)

    view = f"{VIEW}?" + urllib.parse.urlencode({
        "viewitemid": "IntegratedFedWatchTool", "insid": insid, "qsid": qsid})
    _, html = get(view, REFERER)
    state = {"vs": _viewstate(html)}

    def click(target, all_products=False):
        fields = [("ctl00$smPublic", f"ctl00$upMain|{target}"),
                  ("__EVENTTARGET", target), ("__EVENTARGUMENT", "")]
        if all_products:
            for fam, count in FAMILY_SIZES.items():
                for i in range(count):
                    fields.append(
                        (f"{_ITEM_PICKER}$ctrl{fam}$lvItems$ctrl{i}$chkItem",
                         "on"))
        fields += [("__VIEWSTATE", state["vs"]),
                   ("__VIEWSTATEGENERATOR", "7E260167"),
                   ("__ASYNCPOST", "true")]
        doc = post(view, fields)
        vs = _viewstate(doc)
        if vs:                       # each postback returns the next viewstate
            state["vs"] = vs
        return doc

    # 2. walk to the chart, the way a person clicking the site would.
    steps = [
        ("CVOL tab", _FW + "$lbCVOLDashboard", False),
        # Without this the pickers below simply are not on the page.
        ("dashboard", _VC + "$lbDashboard", False),
        ("chart view", _VC + "$ucViewPicker$lbChart", True),
    ]
    doc = ""
    for label, target, all_products in steps:
        doc = click(target, all_products)
        if verbose:
            print(f"  {label:<11} {len(doc):>9} bytes", file=sys.stderr)

    if "UserControls.VolIndex.HistoryChart.Chart" not in doc:
        raise SystemExit(
            "session provisioned but never reached the chart - the control ids "
            "have probably changed again.\n"
            f"last response was {len(doc)} bytes; expected ~11MB.")

    return insid, qsid


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", action="store_true",
                    help="print as `export VAR=...` for shell eval")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="only print the ids")
    a = ap.parse_args()

    insid, qsid = provision(verbose=not a.quiet)
    if a.export:
        print(f"export QS_INSID={insid}")
        print(f"export QS_QSID={qsid}")
    else:
        print(f"QS_INSID={insid}")
        print(f"QS_QSID={qsid}")


if __name__ == "__main__":
    main()
