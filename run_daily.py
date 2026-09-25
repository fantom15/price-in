#!/usr/bin/env python3
"""price-in daily collection wrapper (VPS).

Runs the rate-path collector, captures failures, and pushes ONE Telegram alert
naming what broke. Intended to be called by cron. Exits non-zero on failure so
cron/monitoring can also detect it independently of the alert.

Config comes from a .env file in the project dir (gitignored):
    TG_TOKEN=...
    TG_CHAT=...

<<<<<<< Updated upstream
Scope: this runs rates.py only. build_sheet.py needs the CVOL csvs that live on
the Mac (QuikStrike is manual), so the sheet is assembled there, not here. The
VPS has one job: never miss a rate snapshot.
=======
Scope: this runs rates.py plus cot/prices/calendar/quikstrike/sheet.
build_sheet.py needs the CVOL csvs that live on the Mac (QuikStrike is manual),
so the sheet is assembled there, not here. The VPS has one job: never miss a
rate snapshot.

rates.py: official central-bank/exchange sources (see rates-sources.md), plain
stdlib HTTP - no browser needed. BoC, BoE and ECB (ICE Euribor) are fully
automatic. Fed expectations are manual (CME terms forbid scraping): rates.py
reads them from data/manual/fed/ and exits non-zero when that input is missing
or stale, so a forgotten FedWatch download surfaces here as a "rates" alert.
>>>>>>> Stashed changes
"""
import datetime as dt
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
ENV_PATH = PROJECT_DIR / ".env"
LOG_DIR = PROJECT_DIR / "logs"

# Steps to run, in order: (label, command). Add build_sheet here only if the
# CVOL inputs ever exist on this box.
STEPS = [
    ("rates", [sys.executable, "rates.py"]),
    # COT is published weekly (Friday, for the prior Tuesday), so most runs
    # fetch nothing new. It is here anyway because writes are keyed on
    # (report_date, symbol) and rewrite in place - a no-op run costs 12 small
    # requests and cannot duplicate rows. Unlike rates.py, missing a day loses
    # nothing: the CFTC api serves full history and --backfill can recover it.
    ("cot", [sys.executable, "cot.py"]),
    ("prices", [sys.executable, "prices.py"]),
    # Refetches the current week every run: actuals appear as releases land,
    # so today's page is never final. Needs camoufox on this box - forexfactory
    # 403s plain http. If it is missing the step fails loudly rather than
    # silently skipping, which is the point of the telegram alert.
    ("calendar", [sys.executable, "ff_calendar.py"]),
    # No credentials needed: quikstrike falls back to qs_session.provision(),
    # which mints and warms its own session. Set QS_QSID/QS_INSID only to reuse
    # a browser session you already have open.
    ("quikstrike", [sys.executable, "quikstrike.py", "--all-measures",
                    "--outdir", "data"]),
    ("sheet", [sys.executable, "build_sheet.py", "--days", "30",
               "--out", "market_data.csv"]),
]


def load_env(path):
    """Minimal .env loader - no dependency on python-dotenv."""
    env = {}
    if not path.exists():
        sys.exit(f"FATAL: no .env at {path}")
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip().strip("'").strip('"')
    return env


def notify(token, chat, text):
    """Send a Telegram message. Never raises - alerting must not itself crash."""
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20)
    except Exception as e:  # noqa: BLE001 - deliberately swallow
        print(f"WARN: telegram notify failed: {e}", file=sys.stderr)


def run_step(label, cmd, log):
    """Run one step, tee output to the log, return True on success."""
    log.write(f"\n>>> {label}: {' '.join(cmd)}\n")
    log.flush()
    proc = subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True)
    log.write(proc.stdout)
    if proc.stderr:
        log.write("[stderr]\n" + proc.stderr)
    log.write(f"<<< {label} exit {proc.returncode}\n")
    log.flush()
    return proc.returncode == 0


def main():
    env = load_env(ENV_PATH)
    token, chat = env.get("TG_TOKEN"), env.get("TG_CHAT")
    if not token or not chat:
        sys.exit("FATAL: TG_TOKEN / TG_CHAT missing from .env")

    LOG_DIR.mkdir(exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log_path = LOG_DIR / f"{dt.date.today().isoformat()}.log"

    failed = []
    with open(log_path, "a") as log:
        log.write(f"\n===== run {stamp} =====\n")
        for label, cmd in STEPS:
            if not run_step(label, cmd, log):
                failed.append(label)

    if failed:
        msg = (f"price-in ⚠️ {stamp}\nFAILED: {', '.join(failed)}"
               f"\nlog: {log_path}")
        notify(token, chat, msg)
        print(f"REPORTED failures: {failed}", file=sys.stderr)
        sys.exit(1)

    # Success is silent by default (no daily spam). Flip to notify() to confirm.
    print(f"ALL OK {stamp}")


if __name__ == "__main__":
    main()