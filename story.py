#!/usr/bin/env python3
"""story.py — turns the brief's structured facts into a plain-language story.

The rules (in brief.py) do ALL the analysis: percentiles, calendar filtering,
COT composition, and the final verdict. This script does NOT analyse anything.
It hands those finished facts to Claude and asks for a readable narrative —
translation, not interpretation.

Hard constraints enforced in the prompt:
  - use ONLY numbers present in the payload; invent nothing
  - never invent a cause ("because oil rose") that isn't in the data
  - never say buy/sell; the verdict is whatever the rules produced
  - missing data is stated as missing, never guessed

Usage:
    export ANTHROPIC_API_KEY=...
    python3 story.py                      # latest date, all pairs
    python3 story.py --date 2026-08-19
    python3 story.py --pair eurusd --lang fa
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

# reuse the rule engine — never duplicate the logic
import brief as B

def load_env(path=".env"):
    """Read .env into os.environ (same pattern as run_daily.py)."""
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))

MODEL = "claude-sonnet-4-6"
API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """You turn a currency pair's finished market analysis into a short, \
plain-language story for a trader who is still learning the concepts.

ABSOLUTE RULES — breaking any of these makes the output useless and harmful:
1. Use ONLY facts and numbers present in the JSON payload. Never introduce a \
number, level, or statistic that isn't there.
2. Never invent a CAUSE. If the payload doesn't say why something moved, don't \
speculate ("because oil rose", "due to inflation fears"). Describe what the data \
shows, not why you imagine it happened.
3. Never say "buy", "sell", "go long", "go short", or give a price target. The \
only verdict is the one in the payload (trade day / wait day) and the asymmetry \
direction it names.
4. If a field is null or missing, say the data isn't available. Never guess.
5. Explain every technical term in ordinary words the first time it appears \
(e.g. don't write "skew" alone — say what it measures).

STYLE:
- 3 to 5 short paragraphs. Simple sentences. A non-trader friend should follow it.
- Structure: (a) what the situation is, (b) what stands out or conflicts, \
(c) what to do today — the verdict, (d) one important caveat if the payload has one \
(e.g. stale data, an upcoming event).
- Calm and factual. No hype, no urgency, no predictions about where price "will" go.
- Speak about ASYMMETRY, not direction: "if news favours X, the crowd is forced to \
exit and the move is violent" — never "price will rise"."""


def build_payload(pair, cfg, date, sheet, cal, cot, prices):
    """Extract the finished facts the story is allowed to use."""
    decisions = B.load_decisions()
    b = B.brief_for_pair(pair, cfg, date, sheet, cal, cot, prices, decisions)
    today = sheet.get(date, {})
    pd = B.prev_date(sheet, date)
    yest = sheet.get(pd, {}) if pd else {}

    primary = cfg["banks"][0]
    rd = B.rate_reading(sheet, date, primary, decisions)
    cot_read = B.cot_reading(cot.get(cfg["cot"], []))

    return {
        "pair": cfg["label"],
        "date": date,
        "rates": {
            "bank": primary.upper(),
            "next_meeting_odds_pct": rd["odds"],
            "next_meeting_bps": rd["bps"],
            "path_12m_bp": rd["path"],
            "path_12m_prev": rd["prev_path"],
            # Rate sources lag the report date: say how old the reading is,
            # next to the numbers. `note` = why it is missing or withheld.
            "reading_as_of": rd["as_of"],
            "reading_age_business_days": rd["age"],
            "reading_note": rd["note"],
            "odds_meaning": ("odds are for ONE meeting; null odds with bps present "
                             "means the first priced horizon spans several meetings"),
        },
        "vol": {
            "index_name": cfg["cvol"],
            "level": B.f(today.get(cfg["cvol"])),
            "level_prev": B.f(yest.get(cfg["cvol"])),
            "skew": B.f(today.get(cfg["skew"])),
            "skew_prev": B.f(yest.get(cfg["skew"])),
            "skew_meaning": ("negative = insurance against a FALL is more expensive; "
                             "positive = insurance against a RISE is more expensive"),
        },
        "positioning": {
            "fast_money_net": cot_read["net_spec"] if cot_read else None,
            "slow_money_net": cot_read["net_comm"] if cot_read else None,
            "percentile_3y": cot_read["pctile_3y"] if cot_read else None,
            "composition": cot_read["composition"] if cot_read else None,
            "report_date": cot_read["date"] if cot_read else None,
            "note": "COT is a weekly Tuesday snapshot, released Friday — always a few days old",
        },
        "calendar_relevant": [
            {"date": e["date"], "currency": e.get("currency"), "event": e.get("event")}
            for e in B.upcoming_events(cal, date, currencies=cfg["currencies"])
        ],
        "verdict": b["verdict"],
        "context": b["context"],
        "watch": b["watch"],
        "rule_lines": b["lines"],
    }


def call_claude(payload, lang):
    lang_note = ("Write the story in Persian (Farsi)." if lang == "fa"
                 else "Write the story in English.")
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 3000,
        "system": SYSTEM_PROMPT + "\n\n" + lang_note,
        "messages": [{
            "role": "user",
            "content": ("Here is today's finished analysis for one currency pair. "
                        "Turn it into the story:\n\n"
                        + json.dumps(payload, ensure_ascii=False, indent=2))
        }],
    }).encode()

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ANTHROPIC_API_KEY not set")

    req = urllib.request.Request(API_URL, data=body, headers={
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read().decode())
    return "".join(c.get("text", "") for c in data.get("content", [])
                   if c.get("type") == "text").strip()


def main():
    load_env()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=None)
    ap.add_argument("--pair", default=None)
    ap.add_argument("--lang", default="en", choices=["en", "fa"])
    ap.add_argument("--datadir", default=B.DATA)
    ap.add_argument("--sheet", default="market_data.csv")
    ap.add_argument("--json", action="store_true",
                    help="print the payload instead of calling the API (debug)")
    a = ap.parse_args()

    sheet = B.load_sheet(a.sheet)
    cal = B.load_calendar(os.path.join(a.datadir, "calendar.csv"))
    cot = B.load_cot(os.path.join(a.datadir, "cot.csv"))
    prices = B.load_prices(os.path.join(a.datadir, "prices.csv"))
    if not sheet:
        sys.exit(f"no sheet at {a.sheet} — run build_sheet.py first")

    date = a.date or max(sheet)
    pairs = {a.pair: B.PAIRS[a.pair]} if a.pair else B.PAIRS

    print("=" * 64)
    print(f"  TODAY'S STORY — {date}")
    print("=" * 64)
    for p, cfg in pairs.items():
        payload = build_payload(p, cfg, date, sheet, cal, cot, prices)
        if a.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            continue
        print(f"\n▌ {cfg['label']}\n")
        try:
            print(call_claude(payload, a.lang))
        except Exception as e:  # noqa: BLE001
            print(f"[story generation failed: {e}]")
            print("Falling back to the rule output:")
            print(f"  {payload['context']}\n  {payload['verdict']}")
        print()


if __name__ == "__main__":
    main()
