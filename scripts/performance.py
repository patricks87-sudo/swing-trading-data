"""
performance.py
--------------
Strategie-Performance vs. Nasdaq-100 und MSCI World (eingefuehrt 11.10.2026).

Wird von update_tracking.py beim P1-Lauf aufgerufen und schreibt
data/performance.json - Grundlage fuer das Chart im Cockpit
(Registerkarte "Historie & Bilanz").

Zwei hypothetische Strategien auf Basis ALLER Kandidaten aus
candidate_tracking.json (es wurde bisher real nichts gehandelt):

A) "Alle Kandidaten, 10 Tage gehalten": jeder Kandidat wird zum Schlusskurs
   vor dem Aufnahmetag gekauft und nach 10 Handelstagen verkauft.
   Misst die reine Qualitaet der P4-Auswahl.

B) "Neue Regeln (seit 11.10.2026)": Einstieg zum Eroeffnungskurs am
   Aufnahmetag, wenn der Kurs hoechstens 3 % ueber der SMA20 liegt, sonst
   Limit an der SMA20 (max. 5 Tage gueltig). Stop = Einstieg - 1,5 x ATR14,
   Ziel 1 = 2 x Risiko (halbe Position, Stop auf Einstand), Ziel 2 = 3 x Risiko,
   spaetestens nach 15 Handelstagen Verkauf zum Schlusskurs. Werden Stop und
   Ziel am selben Tag beruehrt, zaehlt konservativ der Stop. Pro Ticker
   hoechstens eine offene Position.

In beiden Strategien sind alle offenen Positionen gleich gewichtet; Tage
ohne Position zaehlen mit 0 % (Cash). Keine Gebuehren, keine Steuern.

Benchmarks: QQQ (Nasdaq-100) und URTH (iShares MSCI World ETF), beide in USD
ab demselben Startdatum. Alles reproduzierbar aus yfinance-Tagesdaten.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from statistics import mean

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUT = os.path.join(DATA_DIR, "performance.json")
BENCH = {"QQQ": "Nasdaq-100 (QQQ)", "URTH": "MSCI World (URTH)"}

HOLD_A = 10
MAX_DAYS_B = 15
LIMIT_DAYS_B = 5
STOP_ATR = 1.5
T1_R, T2_R = 2.0, 3.0


# ---------------------------------------------------------------------------
# Daten
# ---------------------------------------------------------------------------

def download_ohlc(tickers, start):
    """-> {ticker: [ {d, o, h, l, c}, ... ]} aelteste zuerst"""
    import yfinance as yf

    tickers = sorted(set(tickers))
    data = yf.download(tickers, start=start.isoformat(), interval="1d", auto_adjust=True,
                       progress=False, group_by="ticker", threads=True)
    out = {}
    for t in tickers:
        try:
            df = data[t] if len(tickers) > 1 else data
            df = df.dropna(subset=["Close"])
            out[t] = [
                {"d": idx.date(), "o": float(r["Open"]), "h": float(r["High"]),
                 "l": float(r["Low"]), "c": float(r["Close"])}
                for idx, r in df.iterrows()
            ]
        except Exception:
            out[t] = []
    return out


def _atr14(bars, i):
    if i < 14:
        return None
    trs = []
    for j in range(i - 13, i + 1):
        pc = bars[j - 1]["c"]
        b = bars[j]
        trs.append(max(b["h"] - b["l"], abs(b["h"] - pc), abs(b["l"] - pc)))
    return sum(trs) / 14


def _sma(bars, i, n):
    if i + 1 < n:
        return None
    return sum(b["c"] for b in bars[i - n + 1:i + 1]) / n


def _ref_index(bars, aufnahme):
    idx = None
    for i, b in enumerate(bars):
        if b["d"] < aufnahme:
            idx = i
        else:
            break
    return idx


# ---------------------------------------------------------------------------
# Strategien -> Liste von Trades mit taeglichen Renditen {datum: rendite}
# ---------------------------------------------------------------------------

def trades_a(signals, ohlc):
    trades = []
    for s in signals:
        bars = ohlc.get(s["ticker"]) or []
        i = _ref_index(bars, s["aufnahme"])
        if i is None or i + 1 >= len(bars):
            continue
        end = min(i + HOLD_A, len(bars) - 1)
        daily = {}
        for j in range(i + 1, end + 1):
            daily[bars[j]["d"]] = bars[j]["c"] / bars[j - 1]["c"] - 1
        ret = bars[end]["c"] / bars[i]["c"] - 1
        trades.append({"ticker": s["ticker"], "name": s["name"], "start": bars[i + 1]["d"],
                       "ende": bars[end]["d"], "rendite_pct": round(ret * 100, 2),
                       "offen": end == len(bars) - 1 and i + HOLD_A > len(bars) - 1,
                       "daily": daily})
    return trades


def trades_b(signals, ohlc):
    trades = []
    belegt_bis = {}  # ticker -> letzter Tag der offenen Position
    for s in sorted(signals, key=lambda x: x["aufnahme"]):
        bars = ohlc.get(s["ticker"]) or []
        i = _ref_index(bars, s["aufnahme"])
        if i is None or i + 1 >= len(bars):
            continue
        if s["ticker"] in belegt_bis and belegt_bis[s["ticker"]] >= bars[i + 1]["d"]:
            continue
        atr = _atr14(bars, i)
        sma20 = _sma(bars, i, 20)
        if not atr or not sma20:
            continue
        close_ref = bars[i]["c"]
        # Einstieg
        entry_idx, entry = None, None
        if close_ref <= sma20 * 1.03:
            entry_idx, entry = i + 1, bars[i + 1]["o"]
            art = "Eröffnung"
        else:
            for j in range(i + 1, min(i + 1 + LIMIT_DAYS_B, len(bars))):
                if bars[j]["l"] <= sma20:
                    entry_idx, entry = j, min(bars[j]["o"], sma20)
                    break
            art = "Limit SMA20"
        if entry_idx is None:
            continue  # Limit nicht ausgefuehrt
        risk = STOP_ATR * atr
        stop, t1, t2 = entry - risk, entry + T1_R * risk, entry + T2_R * risk
        anteil = 1.0
        realisiert = 0.0
        daily = {}
        prev = entry
        exit_idx = None
        grund = "Zeitlimit"
        last_idx = min(entry_idx + MAX_DAYS_B - 1, len(bars) - 1)
        for j in range(entry_idx, last_idx + 1):
            b = bars[j]
            tages_ret_basis = prev
            # Stop zuerst (konservativ)
            if b["l"] <= stop:
                px = min(b["o"], stop) if j > entry_idx else stop
                realisiert += anteil * (px / entry - 1)
                daily[b["d"]] = anteil * (px / tages_ret_basis - 1)
                anteil = 0.0
                exit_idx, grund = j, ("Stop auf Einstand" if stop >= entry else "Stop")
                break
            tag = 0.0
            if anteil == 1.0 and b["h"] >= t1:
                realisiert += 0.5 * (t1 / entry - 1)
                tag += 0.5 * (t1 / tages_ret_basis - 1)
                anteil = 0.5
                stop = entry
            if anteil > 0 and b["h"] >= t2:
                realisiert += anteil * (t2 / entry - 1)
                tag += anteil * (t2 / tages_ret_basis - 1)
                daily[b["d"]] = tag
                anteil = 0.0
                exit_idx, grund = j, "Ziel 2"
                break
            tag += anteil * (b["c"] / tages_ret_basis - 1)
            daily[b["d"]] = tag
            prev = b["c"]
        if anteil > 0:
            exit_idx = last_idx
            realisiert += anteil * (bars[last_idx]["c"] / entry - 1)
            offen = last_idx == len(bars) - 1 and entry_idx + MAX_DAYS_B - 1 > len(bars) - 1
            if offen:
                grund = "offen"
        belegt_bis[s["ticker"]] = bars[exit_idx]["d"]
        trades.append({"ticker": s["ticker"], "name": s["name"], "start": bars[entry_idx]["d"],
                       "ende": bars[exit_idx]["d"], "einstieg": art, "ausstieg": grund,
                       "rendite_pct": round(realisiert * 100, 2), "offen": grund == "offen",
                       "daily": daily})
    return trades


# ---------------------------------------------------------------------------
# Kurven
# ---------------------------------------------------------------------------

def equity_curve(trades, kalender):
    """Gleichgewichtete Tagesrendite aller offenen Positionen -> Index ab 100."""
    werte, idx, max_offen = [], 100.0, 0
    for d in kalender:
        r = [t["daily"][d] for t in trades if d in t["daily"]]
        max_offen = max(max_offen, len(r))
        if r:
            idx *= 1 + mean(r)
        werte.append(round(idx, 2))
    return werte, max_offen


def bench_curve(bars, kalender):
    by = {b["d"]: b["c"] for b in bars}
    werte, basis, last = [], None, None
    for d in kalender:
        c = by.get(d, last)
        last = c
        if c is None:
            werte.append(None)
            continue
        if basis is None:
            basis = c
        werte.append(round(c / basis * 100, 2))
    return werte


def _stats(trades):
    fertig = [t for t in trades if not t.get("offen")]
    if not trades:
        return {"trades": 0}
    r = [t["rendite_pct"] for t in fertig]
    return {
        "trades": len(trades),
        "abgeschlossen": len(fertig),
        "offen": len(trades) - len(fertig),
        "trefferquote_pct": round(sum(1 for x in r if x > 0) / len(r) * 100, 0) if r else None,
        "schnitt_trade_pct": round(mean(r), 2) if r else None,
        "bester_trade_pct": max(r) if r else None,
        "schlechtester_trade_pct": min(r) if r else None,
    }


def build(eintraege, ohlc=None):
    signals = []
    for k in eintraege:
        try:
            signals.append({"ticker": k["ticker"], "name": k.get("name") or k["ticker"],
                            "aufnahme": date.fromisoformat(k["aufnahmedatum"])})
        except Exception:
            continue
    if not signals:
        return None
    start = min(s["aufnahme"] for s in signals)
    if ohlc is None:
        ohlc = download_ohlc([s["ticker"] for s in signals] + list(BENCH), start - timedelta(days=45))

    qqq = ohlc.get("QQQ") or []
    i0 = _ref_index(qqq, start)
    if i0 is None:
        return None
    kalender = [b["d"] for b in qqq[i0:]]

    ta, tb = trades_a(signals, ohlc), trades_b(signals, ohlc)
    ca, max_a = equity_curve(ta, kalender)
    cb, max_b = equity_curve(tb, kalender)
    reihen = [
        {"key": "neu", "label": "Neue Regeln (Stop/Ziele, simuliert)", "werte": cb},
        {"key": "alle", "label": "Alle Kandidaten, 10 Tage gehalten", "werte": ca},
    ]
    for t, lab in BENCH.items():
        reihen.append({"key": t.lower(), "label": lab, "werte": bench_curve(ohlc.get(t) or [], kalender)})

    def total(w):
        w = [x for x in w if x is not None]
        return round(w[-1] - 100, 2) if w else None

    zusammenfassung = {r["key"]: {"label": r["label"], "gesamt_pct": total(r["werte"])} for r in reihen}

    def clean(trades):
        return [{k: (v.isoformat() if isinstance(v, date) else v) for k, v in t.items() if k != "daily"}
                for t in trades]

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "waehrung": "USD",
        "hinweis": "Hypothetisch, ohne Gebühren und Steuern. Bisher wurde real nicht gehandelt. "
                   "Offene Positionen sind gleich gewichtet, Tage ohne Position zählen als Cash (0 %).",
        "start": kalender[0].isoformat(),
        "daten": [d.isoformat() for d in kalender],
        "reihen": reihen,
        "zusammenfassung": zusammenfassung,
        "statistik": {"neu": dict(_stats(tb), max_gleichzeitig=max_b),
                      "alle": dict(_stats(ta), max_gleichzeitig=max_a)},
        "trades_neu": clean(sorted(tb, key=lambda t: t["start"], reverse=True)),
    }


def write(eintraege):
    res = build(eintraege)
    if res:
        with open(OUT, "w") as fh:
            json.dump(res, fh, indent=2, ensure_ascii=False)
    return res
