"""
performance.py
--------------
Strategie-Performance vs. Nasdaq-100 und MSCI World (eingefuehrt 11.10.2026,
umgebaut auf Depot-Simulation am selben Tag).

Wird von update_tracking.py beim P1-Lauf aufgerufen und schreibt
data/performance.json - Grundlage fuer das Chart im Cockpit
(Registerkarte "Historie & Performance"). Alles in EUR (Kurse mit dem
taeglichen EUR/USD-Kurs umgerechnet), damit es zu deinem Trade-Republic-Depot
passt.

Linien:
A) "Depot-Simulation (deine Regeln)": spielt die aktuellen Regeln auf alle
   historischen Kandidaten nach - Startkapital 8.000 EUR, 75 EUR Risiko je
   Trade, Schutz-Stop 2 x ATR, Verkauf nach 10 Handelstagen zum Schlusskurs,
   Einstieg zum Eroeffnungskurs (Kurs max. 3 % ueber SMA20) bzw. Limit an der
   SMA20 (5 Tage gueltig), max. 5 offene Positionen, max. 375 EUR Gesamt-
   risiko, max. 2.500 EUR je Position, max. 2 Positionen je Sektor, 1 EUR
   Gebuehr je Order. Das Marktregime der Vergangenheit ist nicht gespeichert,
   daher gilt durchgehend das RISK-ON-Limit (5 Positionen).
B) "Alle Kandidaten, 10 Tage gehalten": jeder Kandidat gleich gewichtet,
   ohne Plaetze, Stop und Gebuehren - misst die reine Qualitaet der Auswahl.
C) Nasdaq-100 (QQQ) und MSCI World (URTH), in EUR.

Hypothetisch, ohne Steuern. Reale Trades stehen im Trade-Journal.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from statistics import mean

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUT = os.path.join(DATA_DIR, "performance.json")
BENCH = {"QQQ": "Nasdaq-100 (QQQ)", "URTH": "MSCI World (URTH)"}
FX = "EURUSD=X"

START_EUR = 8000.0
RISK_EUR = 75.0
MAX_OPEN = 5
MAX_RISK_EUR = 375.0
MAX_POS_EUR = 2500.0
MAX_SECTOR = 2
FEE_EUR = 1.0
HOLD = 10
STOP_ATR = 2.0
LIMIT_DAYS = 5


# ---------------------------------------------------------------------------
# Daten
# ---------------------------------------------------------------------------

def download_ohlc(tickers, start):
    """-> {ticker: [ {d, o, h, l, c}, ... ]} aelteste zuerst (USD bzw. Kurs)"""
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


def to_eur(ohlc):
    """Rechnet alle Kurse mit dem Tageskurs EUR/USD (USD je EUR) in EUR um."""
    fx_bars = ohlc.get(FX) or []
    fx = {b["d"]: b["c"] for b in fx_bars}
    if not fx:
        return {t: bars for t, bars in ohlc.items() if t != FX}, False
    days = sorted(fx)
    out = {}
    for t, bars in ohlc.items():
        if t == FX:
            continue
        conv, last, i = [], None, 0
        for b in bars:
            while i < len(days) and days[i] <= b["d"]:
                last = fx[days[i]]
                i += 1
            rate = last or fx[days[0]]
            conv.append({"d": b["d"], "o": b["o"] / rate, "h": b["h"] / rate,
                         "l": b["l"] / rate, "c": b["c"] / rate})
        out[t] = conv
    return out, True


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
# B) Alle Kandidaten, 10 Tage gehalten (gleich gewichtet)
# ---------------------------------------------------------------------------

def trades_alle(signals, ohlc):
    trades = []
    for s in signals:
        bars = ohlc.get(s["ticker"]) or []
        i = _ref_index(bars, s["aufnahme"])
        if i is None or i + 1 >= len(bars):
            continue
        end = min(i + HOLD, len(bars) - 1)
        daily = {bars[j]["d"]: bars[j]["c"] / bars[j - 1]["c"] - 1 for j in range(i + 1, end + 1)}
        trades.append({"rendite_pct": round((bars[end]["c"] / bars[i]["c"] - 1) * 100, 2),
                       "offen": i + HOLD > len(bars) - 1, "daily": daily})
    return trades


def equity_gleichgewichtet(trades, kalender):
    werte, idx = [], 100.0
    for d in kalender:
        r = [t["daily"][d] for t in trades if d in t["daily"]]
        if r:
            idx *= 1 + mean(r)
        werte.append(round(idx, 2))
    return werte


# ---------------------------------------------------------------------------
# A) Depot-Simulation mit den aktuellen Regeln
# ---------------------------------------------------------------------------

def depot_simulation(signals, ohlc, kalender):
    by_t = {t: {b["d"]: (i, b) for i, b in enumerate(bars)} for t, bars in ohlc.items()}
    cash = START_EUR
    offen = []       # dicts: ticker, sector, stueck, einstieg, stop, tage, start
    pending = []     # Limit-Orders: signal, limit, stop_abstand, gueltig_bis_index
    fertig = []
    werte = []
    gebuehren = 0.0
    max_offen = 0
    abgelehnt = {"plaetze": 0, "risiko": 0, "sektor": 0, "kapital": 0, "doppelt": 0, "limit_verfallen": 0}
    sig_by_day = {}
    for s in signals:
        sig_by_day.setdefault(s["aufnahme"], []).append(s)

    def risiko_offen():
        return sum(p["stueck"] * max(0.0, p["einstieg"] - p["stop"]) for p in offen)

    def versuche_kauf(s, preis, stop_abstand, d):
        nonlocal cash, gebuehren
        if any(p["ticker"] == s["ticker"] for p in offen):
            abgelehnt["doppelt"] += 1
            return False
        if len(offen) >= MAX_OPEN:
            abgelehnt["plaetze"] += 1
            return False
        if sum(1 for p in offen if p["sector"] == s["sector"]) >= MAX_SECTOR:
            abgelehnt["sektor"] += 1
            return False
        stueck = int(RISK_EUR // stop_abstand) if stop_abstand > 0 else 0
        stueck = min(stueck, int(MAX_POS_EUR // preis), int((cash - FEE_EUR) // preis))
        if stueck < 1:
            abgelehnt["kapital"] += 1
            return False
        risiko = stueck * stop_abstand
        if risiko_offen() + risiko > MAX_RISK_EUR:
            abgelehnt["risiko"] += 1
            return False
        cash -= stueck * preis + FEE_EUR
        gebuehren += FEE_EUR
        offen.append({"ticker": s["ticker"], "name": s["name"], "sector": s["sector"], "stueck": stueck,
                      "einstieg": preis, "stop": preis - stop_abstand, "tage": 0, "start": d})
        return True

    for d in kalender:
        # 1) Bestehende Positionen: Stop pruefen, Tage zaehlen, Zeitausstieg
        for p in list(offen):
            ib = by_t.get(p["ticker"], {}).get(d)
            if not ib:
                continue
            _, b = ib
            if p["start"] == d:
                # Kauftag: nur Stop pruefen (Einstieg zur Eroeffnung bzw. Limit)
                pass
            p["tage"] += 1
            grund, px = None, None
            if b["l"] <= p["stop"]:
                grund, px = "Stop", min(b["o"], p["stop"]) if p["start"] != d else p["stop"]
            elif p["tage"] >= HOLD:
                grund, px = "10 Tage", b["c"]
            if grund:
                cash += p["stueck"] * px - FEE_EUR
                gebuehren += FEE_EUR
                pnl = p["stueck"] * (px - p["einstieg"]) - 2 * FEE_EUR
                fertig.append({"ticker": p["ticker"], "name": p["name"], "start": p["start"].isoformat(),
                               "ende": d.isoformat(), "stueck": p["stueck"], "ausstieg": grund,
                               "einstieg_eur": round(p["einstieg"], 2), "ausstieg_eur": round(px, 2),
                               "ergebnis_eur": round(pnl, 2),
                               "rendite_pct": round((px / p["einstieg"] - 1) * 100, 2)})
                offen.remove(p)

        # 2) Offene Limit-Orders
        for o in list(pending):
            ib = by_t.get(o["s"]["ticker"], {}).get(d)
            if not ib:
                continue
            i, b = ib
            if b["l"] <= o["limit"]:
                versuche_kauf(o["s"], min(b["o"], o["limit"]), o["stop_abstand"], d)
                pending.remove(o)
            elif i >= o["bis"]:
                abgelehnt["limit_verfallen"] += 1
                pending.remove(o)

        # 3) Neue Signale des Tages
        for s in sig_by_day.get(d, []):
            bars = ohlc.get(s["ticker"]) or []
            i = _ref_index(bars, d)
            if i is None or i + 1 >= len(bars) or bars[i + 1]["d"] != d:
                continue
            atr, sma20 = _atr14(bars, i), _sma(bars, i, 20)
            if not atr or not sma20:
                continue
            stop_abstand = STOP_ATR * atr
            if bars[i]["c"] <= sma20 * 1.03:
                versuche_kauf(s, bars[i + 1]["o"], stop_abstand, d)
            else:
                b = bars[i + 1]
                if b["l"] <= sma20:
                    versuche_kauf(s, min(b["o"], sma20), stop_abstand, d)
                else:
                    pending.append({"s": s, "limit": sma20, "stop_abstand": stop_abstand, "bis": i + LIMIT_DAYS})

        # Stop am Kauftag fuer heute gekaufte Positionen
        for p in list(offen):
            if p["start"] != d or p["tage"] > 0:
                continue
            ib = by_t.get(p["ticker"], {}).get(d)
            if ib and ib[1]["l"] <= p["stop"]:
                px = p["stop"]
                cash += p["stueck"] * px - FEE_EUR
                gebuehren += FEE_EUR
                fertig.append({"ticker": p["ticker"], "name": p["name"], "start": d.isoformat(), "ende": d.isoformat(),
                               "stueck": p["stueck"], "ausstieg": "Stop", "einstieg_eur": round(p["einstieg"], 2),
                               "ausstieg_eur": round(px, 2),
                               "ergebnis_eur": round(p["stueck"] * (px - p["einstieg"]) - 2 * FEE_EUR, 2),
                               "rendite_pct": round((px / p["einstieg"] - 1) * 100, 2)})
                offen.remove(p)
            elif ib:
                p["tage"] = 1

        max_offen = max(max_offen, len(offen))
        wert = cash
        for p in offen:
            ib = by_t.get(p["ticker"], {}).get(d)
            kurs = ib[1]["c"] if ib else p["einstieg"]
            wert += p["stueck"] * kurs
        werte.append(round(wert / START_EUR * 100, 2))

    letzte = kalender[-1] if kalender else None
    offen_liste = []
    for p in offen:
        ib = by_t.get(p["ticker"], {}).get(letzte)
        kurs = ib[1]["c"] if ib else p["einstieg"]
        offen_liste.append({"ticker": p["ticker"], "name": p["name"], "start": p["start"].isoformat(),
                            "stueck": p["stueck"], "einstieg_eur": round(p["einstieg"], 2),
                            "kurs_eur": round(kurs, 2), "tage": p["tage"],
                            "ergebnis_eur": round(p["stueck"] * (kurs - p["einstieg"]) - FEE_EUR, 2)})
    r = [t["ergebnis_eur"] for t in fertig]
    stat = {
        "startkapital_eur": START_EUR,
        "endwert_eur": round(START_EUR * werte[-1] / 100, 2) if werte else START_EUR,
        "trades_abgeschlossen": len(fertig),
        "trades_offen": len(offen_liste),
        "trefferquote_pct": round(sum(1 for x in r if x > 0) / len(r) * 100, 0) if r else None,
        "schnitt_trade_eur": round(mean(r), 2) if r else None,
        "bester_trade_eur": max(r) if r else None,
        "schlechtester_trade_eur": min(r) if r else None,
        "gebuehren_eur": round(gebuehren, 2),
        "max_gleichzeitig": max_offen,
        "nicht_gekauft": abgelehnt,
    }
    return werte, stat, sorted(fertig, key=lambda t: t["start"], reverse=True), offen_liste


# ---------------------------------------------------------------------------
# Gesamt
# ---------------------------------------------------------------------------

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


def build(eintraege, ohlc=None):
    signals = []
    for k in eintraege:
        try:
            signals.append({"ticker": k["ticker"], "name": k.get("name") or k["ticker"],
                            "sector": k.get("sector") or "Unknown",
                            "aufnahme": date.fromisoformat(k["aufnahmedatum"])})
        except Exception:
            continue
    if not signals:
        return None
    start = min(s["aufnahme"] for s in signals)
    if ohlc is None:
        ohlc = download_ohlc([s["ticker"] for s in signals] + list(BENCH) + [FX], start - timedelta(days=45))
    ohlc, in_eur = to_eur(ohlc)

    qqq = ohlc.get("QQQ") or []
    i0 = _ref_index(qqq, start)
    if i0 is None:
        return None
    kalender = [b["d"] for b in qqq[i0:]]

    depot, stat, trades, offen = depot_simulation(signals, ohlc, kalender)
    alle = trades_alle(signals, ohlc)
    reihen = [
        {"key": "neu", "label": "Depot-Simulation (deine Regeln)", "werte": depot},
        {"key": "alle", "label": "Alle Kandidaten, 10 Tage gehalten", "werte": equity_gleichgewichtet(alle, kalender)},
    ]
    for t, lab in BENCH.items():
        reihen.append({"key": t.lower(), "label": lab, "werte": bench_curve(ohlc.get(t) or [], kalender)})

    def total(w):
        w = [x for x in w if x is not None]
        return round(w[-1] - 100, 2) if w else None

    fertig_alle = [t["rendite_pct"] for t in alle if not t["offen"]]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "waehrung": "EUR" if in_eur else "USD",
        "hinweis": ("Hypothetisch, ohne Steuern. Depot-Simulation mit 8.000 € Start, 75 € Risiko je Trade, "
                    "Schutz-Stop 2× ATR, Verkauf nach 10 Handelstagen, max. 5 Positionen / 375 € Gesamtrisiko / "
                    "2 je Sektor, 1 € Gebühr je Order. Echte Trades stehen im Trade-Journal."),
        "start": kalender[0].isoformat(),
        "daten": [d.isoformat() for d in kalender],
        "reihen": reihen,
        "zusammenfassung": {r["key"]: {"label": r["label"], "gesamt_pct": total(r["werte"])} for r in reihen},
        "statistik": {
            "neu": stat,
            "alle": {"trades": len(alle), "abgeschlossen": len(fertig_alle),
                     "trefferquote_pct": round(sum(1 for x in fertig_alle if x > 0) / len(fertig_alle) * 100, 0) if fertig_alle else None,
                     "schnitt_trade_pct": round(mean(fertig_alle), 2) if fertig_alle else None},
        },
        "trades_neu": trades,
        "offen_neu": offen,
    }


def write(eintraege):
    res = build(eintraege)
    if res:
        with open(OUT, "w") as fh:
            json.dump(res, fh, indent=2, ensure_ascii=False)
    return res
