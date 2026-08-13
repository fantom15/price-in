#!/usr/bin/env python3
"""Visual dashboard for the price-in platform.

The brief says what today looks like; these charts show the PATH that got here.
Nothing is computed that brief.py does not already compute - this module reads
the same CSVs and renders them. No signals, no buy/sell markers, no fitted or
projected lines: what happened, not what "will" happen.

One chart per layer, per pair:

  1. rates       is the priced path hardening or softening?
  2. vol + skew  is fear building or fading, and on which side?
  3. COT + price who is crowded, how extreme vs history, and where was price?

Run:
    streamlit run dashboard.py
"""
import datetime as dt
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import brief as brief_mod

SHEET = "market_data.csv"
DATA = "data"

# Muted palette - this is an analysis tool, not a trading terminal.
INK = "#2f3640"
FAST = "#c0392b"      # leveraged / fast money
SLOW = "#2980b9"      # commercial / slow money
PRICE = "#2f3640"
ACCENT = "#8e6c3a"
GRID = "rgba(0,0,0,0.06)"
ZERO = "rgba(0,0,0,0.35)"
RED_ZONE = "rgba(192,57,43,0.10)"

LOOKBACKS = {"30 days": 30, "90 days": 90, "180 days": 180,
             "1 year": 365, "3 years": 1095, "All": None}

# Chart 4 needs years of skew, which the sheet does not have, so it reads
# data/skew.csv. That file is keyed by QuikStrike ticker rather than by the
# sheet's column name: the same product is EUVL under cvol and EUSK under skew.
SKEW_TICKERS = {"eurusd": "EUSK", "usdcad": "CASK"}


# ── data ──────────────────────────────────────────────────────────────────

@st.cache_data
def load_sheet(path=SHEET):
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    # Sheet values are strings with signs ("+0.16"); coerce everything numeric.
    for c in df.columns:
        if c != "date":
            df[c] = pd.to_numeric(df[c].astype(str).str.replace("+", "", regex=False),
                                  errors="coerce")
    return df.sort_values("date")


@st.cache_data
def load_cot(path=os.path.join(DATA, "cot.csv")):
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["report_date"] = pd.to_datetime(df["report_date"])
    return df.sort_values("report_date")


@st.cache_data
def load_skew_history(path=os.path.join(DATA, "skew.csv")):
    """Long-format skew straight from the QuikStrike pull.

    market_data.csv only holds the sheet window (weeks), which is far too short
    to judge "extreme vs its own history". This file carries years per ticker,
    so the 1-year band in chart 4 is computed from it instead.
    """
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.sort_values("date")


@st.cache_data
def load_prices(path=os.path.join(DATA, "prices.csv")):
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")


def clip(df, col, upto, days):
    """Rows up to `upto`, limited to the lookback window."""
    if df.empty:
        return df
    out = df[df[col] <= pd.Timestamp(upto)]
    if days:
        out = out[out[col] >= pd.Timestamp(upto) - pd.Timedelta(days=days)]
    return out


def note(fig, text):
    """Say what is missing rather than drawing an empty axis."""
    fig.add_annotation(text=text, xref="paper", yref="paper", x=0.5, y=0.5,
                       showarrow=False, font=dict(size=12, color="#888"))
    return fig


def style(fig, height=320, title=""):
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=INK)),
        height=height, margin=dict(l=8, r=8, t=38, b=8),
        plot_bgcolor="white", paper_bgcolor="white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0,
                    xanchor="right", x=1, font=dict(size=10)),
        font=dict(color=INK, size=11))
    fig.update_xaxes(showgrid=True, gridcolor=GRID, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False)
    return fig


# ── chart 3: COT net + price ──────────────────────────────────────────────

def pct_rank_series(s, window=156):
    """Rolling percentile of each value within its trailing `window` reports."""
    return s.rolling(window, min_periods=20).apply(
        lambda w: 100.0 * (w < w.iloc[-1]).sum() / len(w), raw=False)


def chart_cot(cfg, cot, prices, upto, days):
    """Two stacked panels sharing x: price on top, fast/slow money below.

    The red-zone shading marks where net_spec sits below the 15th or above the
    85th percentile of its own trailing 3 years - crowding is only meaningful
    against a long history, which is why the default lookback here is years.
    """
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.42, 0.58], vertical_spacing=0.06)

    px = prices[prices["series"] == cfg["price"]] if not prices.empty else pd.DataFrame()
    px = clip(px, "date", upto, days)
    if px.empty:
        note(fig, f"no price data for {cfg['price']}")
    else:
        fig.add_trace(go.Scatter(x=px["date"], y=px["close"], name=cfg["label"],
                                 line=dict(color=PRICE, width=1.2)), row=1, col=1)

    sym = cot[cot["symbol"] == cfg["cot"]] if not cot.empty else pd.DataFrame()
    if sym.empty:
        note(fig, f"no COT data for symbol {cfg['cot']}")
        return style(fig, 470, f"{cfg['label']} — positioning vs price")

    # Percentile is computed on the FULL history, then clipped, so the ranking
    # reflects 3 years of reports even when the view window is short.
    sym = sym.copy()
    sym["pct"] = pct_rank_series(sym["net_spec"])
    sym = clip(sym, "report_date", upto, days)

    for col, name, colour in [("net_spec", "Leveraged (fast)", FAST),
                              ("net_comm", "Commercial (slow)", SLOW)]:
        fig.add_trace(go.Scatter(x=sym["report_date"], y=sym[col], name=name,
                                 line=dict(color=colour, width=1.3)), row=2, col=1)

    fig.add_hline(y=0, line=dict(color=ZERO, width=1, dash="dot"), row=2, col=1)

    # Shade contiguous stretches where fast money is in the red zone.
    red = sym[(sym["pct"] <= 15) | (sym["pct"] >= 85)]
    if not red.empty:
        dates = list(red["report_date"])
        start = prev = dates[0]
        for d in dates[1:] + [None]:
            if d is None or (d - prev).days > 10:      # weekly reports; >10d = gap
                fig.add_vrect(x0=start, x1=prev + pd.Timedelta(days=7),
                              fillcolor=RED_ZONE, line_width=0,
                              row="all", col=1)
                start = d
            prev = d if d is not None else prev

    latest = sym.iloc[-1]
    sub = (f"{cfg['label']} — positioning vs price   ·   "
           f"fast {latest['net_spec']:+,.0f}")
    if pd.notna(latest["pct"]):
        sub += f" ({latest['pct']:.0f}th pctile 3y)"
    sub += f"   ·   as of {latest['report_date'].date()} (Tue snapshot)"

    fig.update_yaxes(title_text="price", row=1, col=1)
    fig.update_yaxes(title_text="net contracts", row=2, col=1)
    return style(fig, 470, sub)


# ── chart 2: vol + skew ───────────────────────────────────────────────────

def chart_vol(cfg, sheet, upto, days):
    """CVOL level (left) against skew (right).

    The zero line on the skew axis is the whole point: skew below it means
    downside insurance is the richer side, and the DISTANCE from zero plus the
    slope is what "fear easing" actually looks like. Shading either side of
    zero makes put-tilt vs call-tilt readable without checking the sign.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    df = clip(sheet, "date", upto, days)

    lvl, skw = cfg["cvol"], cfg["skew"]
    have_lvl = lvl in df.columns and df[lvl].notna().any()
    have_skw = skw in df.columns and df[skw].notna().any()
    if df.empty or not (have_lvl or have_skw):
        return style(note(fig, f"no vol data for {lvl}/{skw}"), 320,
                     f"{cfg['label']} — vol & skew")

    if have_lvl:
        fig.add_trace(go.Scatter(x=df["date"], y=df[lvl], name=f"{lvl} (level)",
                                 line=dict(color=INK, width=1.4),
                                 connectgaps=False), secondary_y=False)
    if have_skw:
        fig.add_trace(go.Scatter(x=df["date"], y=df[skw], name=f"{skw} (skew)",
                                 line=dict(color=ACCENT, width=1.4),
                                 connectgaps=False), secondary_y=True)
        # Tint the skew axis either side of zero. Drawn against the secondary
        # axis so the bands track skew, not the level.
        lo, hi = df[skw].min(), df[skw].max()
        if pd.notna(lo) and lo < 0:
            fig.add_hrect(y0=min(lo * 1.15, -0.01), y1=0, secondary_y=True,
                          fillcolor="rgba(192,57,43,0.05)", line_width=0)
        if pd.notna(hi) and hi > 0:
            fig.add_hrect(y0=0, y1=max(hi * 1.15, 0.01), secondary_y=True,
                          fillcolor="rgba(39,124,70,0.05)", line_width=0)
        fig.add_hline(y=0, line=dict(color=ZERO, width=1, dash="dot"),
                      secondary_y=True)

    sub = f"{cfg['label']} — vol & skew"
    last = df.dropna(subset=[c for c in (lvl, skw) if c in df.columns],
                     how="all")
    if not last.empty:
        r = last.iloc[-1]
        bits = []
        if have_lvl and pd.notna(r[lvl]):
            bits.append(f"{lvl} {r[lvl]:.2f}")
        if have_skw and pd.notna(r[skw]):
            side = "put" if r[skw] < 0 else "call"
            bits.append(f"skew {r[skw]:+.2f} ({side}-tilted)")
        if bits:
            sub += "   ·   " + "   ·   ".join(bits)

    fig.update_yaxes(title_text="CVOL level", secondary_y=False)
    fig.update_yaxes(title_text="skew", secondary_y=True, showgrid=False)
    return style(fig, 320, sub)


# ── chart 1: rate path ────────────────────────────────────────────────────

def chart_rates(cfg, sheet, upto, days):
    """12m path per bank, with repricing 'slaps' dotted and odds behind.

    Gaps are real: rateprobability only stamps a snapshot on days it ran, so
    the lines are drawn with connectgaps=False rather than interpolating
    across days that were never observed.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    df = clip(sheet, "date", upto, days)
    if df.empty:
        return style(note(fig, "no sheet rows in range"), 320,
                     f"{cfg['label']} — rate path")

    colours = [INK, SLOW]
    drawn, missing = [], []
    for i, bank in enumerate(cfg["banks"]):
        col = f"{bank}_path_12m"
        if col not in df.columns or not df[col].notna().any():
            missing.append(bank.upper())
            continue
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[col], name=f"{bank.upper()} 12m path",
            line=dict(color=colours[i % len(colours)], width=1.5),
            connectgaps=False), secondary_y=False)
        drawn.append(bank)

        # R2: a day that repriced the path by >=8bp is a "slap" - flag it.
        s = df[["date", col]].dropna()
        jump = s[s[col].diff().abs() >= 8]
        if not jump.empty:
            fig.add_trace(go.Scatter(
                x=jump["date"], y=jump[col], mode="markers",
                name=f"{bank.upper()} slap (≥8bp)",
                marker=dict(color=FAST, size=7, symbol="circle-open",
                            line=dict(width=1.6))), secondary_y=False)

        # next-meeting odds, faint, behind the path
        oc = next((c for c in (f"{bank}_odds", f"{bank}_odds_pct")
                   if c in df.columns and df[c].notna().any()), None)
        if oc:
            fig.add_trace(go.Scatter(
                x=df["date"], y=df[oc], name=f"{bank.upper()} next-mtg odds %",
                line=dict(color=colours[i % len(colours)], width=1, dash="dot"),
                opacity=0.45, connectgaps=False), secondary_y=True)

    if not drawn:
        note(fig, "no 12m path data for " + "/".join(b.upper() for b in cfg["banks"]))

    sub = f"{cfg['label']} — priced path"
    if missing:
        # boc_path_12m is not in the sheet at all; say so rather than implying
        # the leg is flat.
        sub += f"   ·   no 12m path for {', '.join(missing)} (not in sheet)"

    fig.update_yaxes(title_text="12m path (bp)", secondary_y=False)
    fig.update_yaxes(title_text="odds %", secondary_y=True, showgrid=False,
                     range=[0, 100])
    return style(fig, 320, sub)


# ── chart 4: skew vs its own 1-year band ──────────────────────────────────

def chart_skew_band(cfg, skew_hist, upto):
    """Today's skew as a line on the distribution of its own trailing year.

    Rule R6 says to judge skew against its OWN normal rather than a fixed
    threshold, and the sheet is far too short for that (weeks). This reads
    data/skew.csv, which carries years per ticker, and shows where today sits
    inside the last 365 days: the 10th/90th percentile edges are drawn so
    "extreme" is a position in the distribution, not an opinion.
    """
    fig = go.Figure()
    tkr = cfg.get("skew_ticker")
    s = skew_hist[skew_hist["ticker"] == tkr] if not skew_hist.empty else pd.DataFrame()
    s = clip(s, "date", upto, 365).dropna(subset=["value"])
    if len(s) < 30:
        return style(note(fig, f"not enough skew history for {tkr} "
                               f"({len(s)} obs in the trailing year)"),
                     260, f"{cfg['label']} — skew vs its own year")

    vals = s["value"]
    cur = vals.iloc[-1]
    p10, p50, p90 = vals.quantile([0.10, 0.50, 0.90])
    pct = 100.0 * (vals < cur).sum() / len(vals)

    fig.add_trace(go.Histogram(x=vals, nbinsx=40, name="trailing year",
                               marker=dict(color="rgba(47,54,64,0.28)"),
                               hovertemplate="skew %{x:.2f}<br>%{y} days<extra></extra>"))
    for x, label, colour, dash in [
            (p10, "10th", ZERO, "dot"), (p50, "median", ZERO, "dot"),
            (p90, "90th", ZERO, "dot"),
            (cur, f"today {cur:+.2f}", FAST, "solid")]:
        fig.add_vline(x=x, line=dict(color=colour, width=2 if dash == "solid" else 1,
                                     dash=dash),
                      annotation_text=label, annotation_position="top",
                      annotation_font=dict(size=10))

    zone = ("extreme" if pct <= 10 or pct >= 90 else
            "elevated" if pct <= 25 or pct >= 75 else "normal")
    sub = (f"{cfg['label']} — skew vs its own year   ·   "
           f"{pct:.0f}th pctile ({zone})   ·   {len(vals)} obs")
    fig.update_xaxes(title_text="skew")
    fig.update_yaxes(title_text="days")
    return style(fig, 260, sub)


# ── page ──────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="price-in dashboard", layout="wide")

    sheet, cot, prices = load_sheet(), load_cot(), load_prices()
    skew_hist = load_skew_history()
    if sheet.empty:
        st.error("no market_data.csv — run build_sheet.py first")
        return

    dates = list(sheet["date"].dt.date)
    st.sidebar.header("view")
    upto = st.sidebar.date_input("as of", value=dates[-1],
                                 min_value=dates[0], max_value=dates[-1])
    lb = st.sidebar.selectbox("lookback", list(LOOKBACKS), index=4)
    days = LOOKBACKS[lb]
    which = st.sidebar.selectbox("pair", ["all"] + list(brief_mod.PAIRS))
    if st.sidebar.button("reload data"):
        st.cache_data.clear()
        st.rerun()

    pairs = brief_mod.PAIRS if which == "all" else {which: brief_mod.PAIRS[which]}

    st.title("price-in")
    st.caption(f"as of {upto} · lookback {lb} · direction stays with the chart")

    # ── brief text (reuses brief.py's rules; nothing recomputed here) ──
    date_str = str(upto)
    b_sheet = brief_mod.load_sheet(SHEET)
    b_cal = brief_mod.load_calendar(os.path.join(DATA, "calendar.csv"))
    b_cot = brief_mod.load_cot(os.path.join(DATA, "cot.csv"))
    b_px = brief_mod.load_prices(os.path.join(DATA, "prices.csv"))

    if date_str not in b_sheet:
        st.warning(f"no sheet row for {date_str} — showing charts only")
    else:
        cols = st.columns(len(pairs))
        for col, (name, cfg) in zip(cols, pairs.items()):
            b = brief_mod.brief_for_pair(name, cfg, date_str, b_sheet,
                                         b_cal, b_cot, b_px)
            with col:
                st.subheader(cfg["label"])
                for layer, tag in [("rates", "rates"), ("vol", "vol"),
                                   ("pos", "pos")]:
                    for i, ln in enumerate(b["lines"][layer]):
                        st.markdown(
                            f"<div style='font-size:0.82rem;line-height:1.45'>"
                            f"<b>{tag if i == 0 else '&nbsp;' * len(tag)}</b> "
                            f"{ln}</div>", unsafe_allow_html=True)
                st.markdown(f"**CONTEXT** {b['context']}")
                for w in b["watch"]:
                    st.markdown(f"**WATCH** {w}")
                st.markdown(f"**VERDICT** {b['verdict']}")

    st.divider()

    # ── charts, per pair ──
    for name, cfg in pairs.items():
        st.subheader(cfg["label"])
        cfg = dict(cfg, skew_ticker=SKEW_TICKERS.get(name))
        left, right = st.columns(2)
        with left:
            st.plotly_chart(chart_rates(cfg, sheet, upto, days),
                            use_container_width=True)
        with right:
            st.plotly_chart(chart_vol(cfg, sheet, upto, days),
                            use_container_width=True)
            st.plotly_chart(chart_skew_band(cfg, skew_hist, upto),
                            use_container_width=True)
        # Widest chart last: crowding only reads against years of history.
        st.plotly_chart(chart_cot(cfg, cot, prices, upto, days),
                        use_container_width=True)


if __name__ == "__main__":
    main()
