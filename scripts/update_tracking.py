"""
update_tracking.py
------------------
Forward-Performance-Tracking und Filter-Bilanz (eingefuehrt 11.10.2026).

Wird von fetch_market_data.py beim P1-Lauf aufgerufen (also VOR der
Claude-Analyse). Aktualisiert in data/candidate_tracking.json fuer ALLE
Eintraege - auch fuer aussortierte - die Kursfelder deterministisch und
vergleicht sie mit dem Nasdaq-100 (QQQ) im selben Zeitraum. Gerechnet wird
in USD, damit Wechselkursschwankungen die Bilanz nicht verfaelschen.

Claude (P1) pflegt danach nur noch status, empfehlung, letzte_einschaetzung
und nimmt neue Kandidaten auf - die hier berechneten Zahlenfelder bleiben
unveraendert.

Ergebnis zusaetzlich: data/filter_bilanz.json - Kennzahl, ob die Filter mehr
Verluste vermeiden als sie Gewinne kosten.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from statistics import mean

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
TRACKING = os.path.join(DATA_DIR, "candidate_tracking.json")
BILANZ = os.path.join(DATA_DIR, "filter_bilanz.json")
BENCHMARK = "QQQ"
HORIZONS = (5, 10, 20)

STATUS_GRUPPEN = {
    "aktiv": "Aktiv beobachtet",
    "ueberdehnt": "Überdehnt – auf Rücksetzer warten",
    "getradet": "Getradet",
    "invalidiert": "Aussortiert – These widerlegt",
    "zeitlimit": "Aussortiert – Zeitlimit",
}


def status_gruppe(status: str) -> str:
    s = (status or "").lower()
    if "getradet" in s:
        return "getradet"
    if "überdehnt" in s or "ueberdehnt" in s:
        return "ueberdehnt"
    if "zeitlimit" in s:
        return "zeitlimit"
    if "invalid" in s or "widerlegt" in s:
        return "invalidiert"
    return "aktiv"


def _download(tickers, start):
    import yfinance as yf

    data = yf.download(
        sorted(set(tickers)), start=start.isoformat(), interval="1d",
        auto_adjust=False, progress=False, group_by="ticker", threads=True,
    )
    closes = {}
    for t in set(tickers):
        try:
            col = data[t]["Close"] if len(set(tickers)) > 1 else data["Close"]
            ser = col.dropna()
            closes[t] = [(idx.date(), float(v)) for idx, v in ser.items()]
        except Exception:
            closes[t] = []
    return closes


def _ref_index(series, aufnahme: date):
    """Index des letzten Schlusskurses VOR dem Aufnahmetag (P4 laeuft vor
    US-Handelsbeginn und sieht genau diesen Kurs)."""
    idx = None
    for i, (d, _) in enumerate(series):
        if d < aufnahme:
            idx = i
        else:
            break
    return idx


def _pct(a, b):
    return round((b - a) / a * 100, 2) if a else None


def update(eurusd=None):
    if not os.path.exists(TRACKING):
        print("Kein candidate_tracking.json - nichts zu tun")
        return None
    with open(TRACKING) as fh:
        doc = json.load(fh)
    eintraege = doc.get("kandidaten", [])
    if not eintraege:
        return None

    daten = []
    for k in eintraege:
        try:
            daten.append(date.fromisoformat(k["aufnahmedatum"]))
        except Exception:
            pass
    start = min(daten) - timedelta(days=10) if daten else date.today() - timedelta(days=120)

    try:
        closes = _download([k["ticker"] for k in eintraege] + [BENCHMARK], start)
    except Exception as e:
        print(f"Tracking-Update uebersprungen (yfinance): {e}")
        return None

    bench = closes.get(BENCHMARK) or []
    for k in eintraege:
        ser = closes.get(k.get("ticker")) or []
        try:
            aufnahme = date.fromisoformat(k["aufnahmedatum"])
        except Exception:
            continue
        i = _ref_index(ser, aufnahme)
        j = _ref_index(bench, aufnahme)
        if i is None or not ser:
            k["tracking_hinweis"] = "Kursdaten nicht verfügbar"
            continue
        ref, last = ser[i][1], ser[-1][1]
        k["referenz_kurs_usd"] = round(ref, 2)
        k["aktueller_kurs_usd"] = round(last, 2)
        if isinstance(eurusd, (int, float)):
            k["aktueller_kurs_eur"] = round(last * eurusd, 2)
        k["performance_pct"] = _pct(ref, last)
        k["handelstage_seit_aufnahme"] = len(ser) - 1 - i
        k["kursdaten_stand"] = ser[-1][0].isoformat()
        if j is not None and bench:
            bref, blast = bench[j][1], bench[-1][1]
            k["nasdaq_performance_pct"] = _pct(bref, blast)
            if k["performance_pct"] is not None and k["nasdaq_performance_pct"] is not None:
                k["ueberrendite_pct"] = round(k["performance_pct"] - k["nasdaq_performance_pct"], 2)
        fwd = {}
        for h in HORIZONS:
            if i + h < len(ser) and j is not None and j + h < len(bench):
                p = _pct(ref, ser[i + h][1])
                b = _pct(bench[j][1], bench[j + h][1])
                fwd[f"{h}T"] = {"aktie_pct": p, "nasdaq_pct": b, "ueberrendite_pct": round(p - b, 2)}
        k["forward"] = fwd
        k["status_gruppe"] = status_gruppe(k.get("status"))

    doc["kurse_aktualisiert_utc"] = datetime.now(timezone.utc).isoformat()
    with open(TRACKING, "w") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)

    bilanz = build_bilanz(eintraege)
    with open(BILANZ, "w") as fh:
        json.dump(bilanz, fh, indent=2, ensure_ascii=False)

    # Strategie-Performance vs. Nasdaq/MSCI World (seit 11.10.2026)
    try:
        import performance

        performance.write(eintraege)
        print("performance.json aktualisiert")
    except Exception as e:
        print(f"Performance-Berechnung fehlgeschlagen (Lauf laeuft weiter): {e}")
    return bilanz


def build_bilanz(eintraege):
    gruppen = {}
    for k in eintraege:
        g = status_gruppe(k.get("status"))
        gruppen.setdefault(g, []).append(k)

    def stats(items, key):
        vals = [x for x in (key(k) for k in items) if isinstance(x, (int, float))]
        if not vals:
            return None
        return {
            "anzahl": len(vals),
            "schnitt_ueberrendite_pct": round(mean(vals), 2),
            "trefferquote_pct": round(sum(1 for v in vals if v > 0) / len(vals) * 100, 0),
        }

    out = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "benchmark": "Nasdaq-100 (QQQ)",
           "waehrung": "USD", "gruppen": []}
    for g in ["aktiv", "ueberdehnt", "getradet", "invalidiert", "zeitlimit"]:
        items = gruppen.get(g, [])
        if not items:
            continue
        eintrag = {"gruppe": g, "label": STATUS_GRUPPEN[g], "eintraege": len(items),
                   "seit_aufnahme": stats(items, lambda k: k.get("ueberrendite_pct"))}
        for h in HORIZONS:
            eintrag[f"nach_{h}_tagen"] = stats(items, lambda k, h=h: ((k.get("forward") or {}).get(f"{h}T") or {}).get("ueberrendite_pct"))
        out["gruppen"].append(eintrag)

    aussortiert = gruppen.get("invalidiert", []) + gruppen.get("zeitlimit", [])
    s10 = stats(aussortiert, lambda k: ((k.get("forward") or {}).get("10T") or {}).get("ueberrendite_pct"))
    if s10:
        richtung = "liegengelassene Gewinne" if s10["schnitt_ueberrendite_pct"] > 0 else "vermiedene Verluste"
        out["fazit"] = (
            f"Aussortierte Kandidaten lagen 10 Handelstage nach Aufnahme im Schnitt "
            f"{format(s10['schnitt_ueberrendite_pct'], '+.2f').replace('.', ',')} Prozentpunkte "
            f"{'über' if s10['schnitt_ueberrendite_pct'] > 0 else 'unter'} dem Nasdaq "
            f"(n={s10['anzahl']}) – überwiegend {richtung}."
        )
    return out


if __name__ == "__main__":
    update()
