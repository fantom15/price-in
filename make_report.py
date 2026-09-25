#!/usr/bin/env python3
"""Run the whole chain - collect, assemble, report - with one command.

Steps, in order (each writes the file the next reads; see README "Daily report"):

    collect   rates.py                       -> data/rates.csv
              quikstrike.py --all-measures   -> data/cvol.csv, skew.csv, ...
              cot.py                         -> data/cot.csv
              prices.py                      -> data/prices.csv
              ff_calendar.py                 -> data/calendar.csv
    sheet     build_sheet.py --days 30       -> market_data.csv
    report    brief.py                       (rules only, printed - a quick check)
              story.py --lang en             -> reports/<date>/brief_en.txt
              story.py --lang fa             -> reports/<date>/brief_fa.txt

The saved report is story.py's output (it turns brief.py's facts into a
readable story; Claude API, needs ANTHROPIC_API_KEY), one file per language.
--lang picks which; --no-story stops after the printed brief.py (no API call,
nothing saved). A --pair run is printed only, never saved, so it cannot
replace the full all-pairs report. The report date is
the one the report is for: --date, else the newest date in market_data.csv
(same rule as brief.py/story.py), not necessarily today. reports/index.html is
rebuilt at the end - open it in a browser to read every saved report.

A failing step does not stop the chain: rates.py exits non-zero whenever a
manual input is missing or stale, and the report should still be produced from
everything else. Every failure is listed at the end, and the exit code is
non-zero if anything failed.

Put today's FedWatch download in data/manual/fed/ first (the ECB is automatic).

Usage:
    python3 make_report.py                   # collect -> sheet -> brief_en.txt + brief_fa.txt
    python3 make_report.py --lang fa         # Persian report only
    python3 make_report.py --offline         # no fetching: rebuild from disk, then report
    python3 make_report.py --no-story        # no API call: printed brief.py only
    python3 make_report.py --date 2026-09-25
    python3 make_report.py --pair eurusd     # one pair, printed only (not saved)
    python3 make_report.py --reports-dir ~/price-in-reports
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def report_date(a):
    """The date brief.py/story.py will report on: --date, else the latest
    sheet date. Read after build_sheet.py has run."""
    if a.date:
        return a.date
    import brief as B   # same loader the report uses
    sheet = B.load_sheet(os.path.join(HERE, "market_data.csv"))
    return max(sheet) if sheet else "undated"


def run(cmd, save_to=None):
    """Run one step, output live. With save_to, stdout is also written there
    (stderr stays on the terminal only)."""
    if not save_to:
        return subprocess.run([PY] + cmd, cwd=HERE).returncode
    proc = subprocess.Popen([PY] + cmd, cwd=HERE, stdout=subprocess.PIPE,
                            text=True, bufsize=1)
    lines = []
    for line in proc.stdout:
        sys.stdout.write(line)
        lines.append(line)
    code = proc.wait()
    if lines:   # never overwrite a good report with an empty failed run
        os.makedirs(os.path.dirname(save_to), exist_ok=True)
        # A report may have been edited by hand: keep the old copy whenever the
        # new one differs. *.bak is not shown by the viewer.
        if os.path.exists(save_to):
            old = open(save_to).read()
            if old != "".join(lines):
                stamp = time.strftime("%Y%m%d-%H%M%S",
                                      time.localtime(os.path.getmtime(save_to)))
                bak = f"{save_to}.{stamp}.bak"
                with open(bak, "w") as f:
                    f.write(old)
                print(f"  -> previous version kept as {os.path.relpath(bak, HERE)}",
                      flush=True)
        with open(save_to, "w") as f:
            f.writelines(lines)
        print(f"  -> saved {os.path.relpath(save_to, HERE)}", flush=True)
    return code


def steps(a):
    report_args = (["--pair", a.pair] if a.pair else []) + (["--date", a.date] if a.date else [])
    if a.offline:
        collect = [
            ("rates (archive)", ["rates.py", "--no-fetch"]),
            ("calendar (cached html)", ["ff_calendar.py", "--parse-only"]),
        ]
    else:
        collect = [
            ("rates", ["rates.py"]),
            ("quikstrike", ["quikstrike.py", "--all-measures", "--outdir", "data"]),
            ("cot", ["cot.py"]),
            ("prices", ["prices.py"]),
            ("calendar", ["ff_calendar.py"]),
        ]
    out = collect + [
        ("sheet", ["build_sheet.py", "--days", str(a.days), "--out", "market_data.csv"]),
        ("brief (rules)", ["brief.py"] + report_args),
    ]
    if not a.no_story:
        # The saved report: story.py per language. A --pair run is print-only.
        out += [(f"report ({lang})", ["story.py", "--lang", lang] + report_args,
                 *([] if a.pair else [f"brief_{lang}.txt"])) for lang in a.lang]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", nargs="+", default=["en", "fa"], choices=["en", "fa"],
                    help="report language(s) (default: en fa)")
    ap.add_argument("--no-story", action="store_true",
                    help="skip story.py: no API call, nothing saved")
    ap.add_argument("--offline", action="store_true",
                    help="skip all fetching; rebuild rates from the archive and "
                         "re-parse the cached calendar")
    ap.add_argument("--days", type=int, default=30, help="sheet rows (default 30)")
    ap.add_argument("--pair", help="report one pair only, e.g. eurusd")
    ap.add_argument("--date", help="report date YYYY-MM-DD (default: latest)")
    ap.add_argument("--reports-dir", default=os.path.join(HERE, "reports"),
                    help="where reports are saved (default: ./reports)")
    a = ap.parse_args()

    results, outdir = [], None
    for label, cmd, *save in steps(a):
        print(f"\n{'=' * 64}\n>>> {label}: python3 {' '.join(cmd)}\n{'=' * 64}", flush=True)
        t0 = time.time()
        save_to = None
        if save:
            if outdir is None:   # the sheet is built by now
                outdir = os.path.join(os.path.expanduser(a.reports_dir), report_date(a))
            save_to = os.path.join(outdir, save[0])
        code = run(cmd, save_to)
        results.append((label, code, time.time() - t0))

    print(f"\n{'=' * 64}\nSUMMARY")
    for label, code, secs in results:
        print(f"  {'ok  ' if code == 0 else 'FAIL'}  {label:<24} {secs:6.1f}s"
              + ("" if code == 0 else f"   (exit {code} - see its output above)"))
    failed = [label for label, code, _ in results if code != 0]
    if outdir:
        import reports_html
        page, _ = reports_html.build(os.path.dirname(outdir))
        print(f"\nreports: {os.path.relpath(outdir, HERE)}/")
        print(f"viewer:  {page}   (open in a browser)")
    if failed:
        sys.exit(f"\n{len(failed)} step(s) failed: {', '.join(failed)}")
    print("all steps ok")


if __name__ == "__main__":
    main()
