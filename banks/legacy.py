"""Read-only: the rateprobability.com snapshots archived before that site
blocked scripted access (data/raw/<bank>/<date>.json, May-Sep 2026).

Nothing is fetched here. These rows keep the pre-switch history in rates.csv.
They carry real meeting dates, while the new sources carry contract/forward
periods, so rates.py drops a legacy (bank, as_of) whenever a new source covers
that same date - the two are never mixed within one snapshot.

Each response held `today` plus four server-reconstructed snapshots
(ago_1w/3w/6w/10w); a `today` reading beats a reconstruction for the same date.
prob_move_pct/num_moves came as magnitude + a cut flag - the sign is restored.
"""
import json
import os

BANKS = ["fed", "ecb", "boe", "boj", "boc", "rba"]
AGO_KEYS = ["ago_1w", "ago_3w", "ago_6w", "ago_10w"]


def _as_of(block):
    # Formats vary by bank ("2026-07-28", ISO timestamp, "... EDT"): take the
    # first whitespace/T-delimited token.
    v = block.get("used_date") or block.get("requested_date") or block.get("as_of")
    return str(v).replace("T", " ").split()[0] if v else None


def _rows(bank, doc):
    gen_time = doc.get("generated_at_utc") or ""
    for key in ["today"] + AGO_KEYS:
        block = doc.get(key)
        if not isinstance(block, dict) or not block.get("rows"):
            continue
        as_of = _as_of(block)
        if not as_of:
            continue
        for r in block["rows"]:
            meeting = r.get("meeting_iso")
            if not meeting:
                continue
            prob, moves = r.get("prob_move_pct"), r.get("num_moves")
            cut = bool(r.get("prob_is_cut"))
            yield {
                "bank": bank,
                "as_of": as_of,
                "as_of_time": gen_time if key == "today" else "",
                "meeting": meeting,
                "implied_rate": r.get("implied_rate_post_meeting"),
                "prob_move_pct": None if prob is None else (-prob if cut else prob),
                "is_cut": int(cut),
                "num_moves": None if moves is None else (
                    -moves if r.get("num_moves_is_cut") else moves),
                "change_bps": r.get("change_bps"),
                "horizon": key,
            }


def build(rawdir, bank, warn):
    """(as_of, meeting) -> row, `today` winning over ago_* for the same key."""
    merged = {}
    d = os.path.join(rawdir, bank)
    if not os.path.isdir(d):
        return merged
    for name in sorted(os.listdir(d)):
        # Only the bare <date>.json files; new sources use <date>.<kind>.<ext>.
        if not name.endswith(".json") or name.count(".") != 1:
            continue
        try:
            with open(os.path.join(d, name)) as f:
                doc = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            warn(f"skipping legacy {bank}/{name}: {e}")
            continue
        for r in _rows(bank, doc):
            key = (r["as_of"], r["meeting"])
            if key not in merged or r["horizon"] == "today":
                merged[key] = r
    return merged
