"""Rohstoff-Monitor (seit 18.10.2026).

Beobachtet Gold, Silber, Kupfer, Rohoel, Goldminen (GDX) und den US-Dollar
und prueft, ob Kapital aus schwachen Aktiensektoren in Rohstoffe -
vor allem Edelmetalle - rotiert. Datenquelle: yfinance (kostenlos, belastet
das Twelve-Data-Kontingent nicht).

Ergebnis landet im Feed unter snapshot["rohstoffe"] und zusaetzlich in
data/rohstoffe.json fuer die Cockpit-Seite "Rohstoffe". Rein informativ:
die Scores der Aktien aendern sich dadurch nicht. Die Minenaktien der
Watchlist (Sektor "Edelmetalle") werden ganz normal gescort.

Alle Funktionen brechen den Feed-Lauf nie ab - Kennzeichnen statt Schaetzen.
"""

from __future__ import annotations

import math

# Schluessel -> (Yahoo-Symbol, Anzeigename, Einheit)
ROHSTOFFE = {
    "GOLD": ("GC=F", "Gold", "USD je Feinunze"),
    "SILBER": ("SI=F", "Silber", "USD je Feinunze"),
    "KUPFER": ("HG=F", "Kupfer", "USD je Pfund"),
    "OEL": ("CL=F", "Rohöl WTI", "USD je Barrel"),
    "GOLDMINEN": ("GDX", "Goldminen (GDX)", "USD, ETF als Index"),
    "DOLLAR": ("DX-Y.NYB", "US-Dollar-Index", "Punkte"),
}
REFERENZ = ("SPY", "S&P 500")
EDELMETALLE = ("GOLD", "SILBER")

# Schwellen
RS_ROTATION_MIN = 3.0        # Edelmetall mind. 3 Prozentpunkte besser als S&P 500 (20 Tage)
FUEHRER_FALL_5D = -2.0       # fuehrende Sektoren im Schnitt mind. 2 % gefallen (5 Tage)
SPY_WOCHE_SCHWACH = -1.0     # "schwache Aktienwoche" fuer die Antizyklik-Statistik
CHART_TAGE = 126             # ca. 6 Monate


def _r(x, n=2):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), n)


def _pct(a, b):
    try:
        return (a / b - 1) * 100 if a is not None and b else None
    except Exception:
        return None


def _laden(symbole):
    import yfinance as yf

    daten = {}
    for sym in symbole:
        try:
            h = yf.Ticker(sym).history(period="2y", interval="1d", auto_adjust=True)
            s = h["Close"].dropna() if h is not None and not h.empty else None
            if s is not None and len(s) > 60:
                s.index = s.index.tz_localize(None).normalize() if s.index.tz is not None else s.index.normalize()
                daten[sym] = s[~s.index.duplicated(keep="last")]
        except Exception as e:  # einzelner Ausfall -> nur dieser Wert fehlt
            print(f"Rohstoffe: {sym} nicht ladbar: {e}")
    return daten


def _kennzahlen(s, spy):
    """Trend, Veraenderungen, relative Staerke, Korrelation und Antizyklik-Statistik."""
    import pandas as pd

    close = float(s.iloc[-1])
    sma50 = float(s.tail(50).mean()) if len(s) >= 50 else None
    sma200 = float(s.tail(200).mean()) if len(s) >= 200 else None
    ch = lambda n: _pct(close, float(s.iloc[-1 - n])) if len(s) > n else None
    c5, c20, c60 = ch(5), ch(20), ch(60)
    hoch52 = float(s.tail(252).max())

    if sma50 and sma200 and close > sma50 > sma200:
        trend = "aufwärts"
    elif sma50 and sma200 and close < sma50 < sma200:
        trend = "abwärts"
    else:
        trend = "seitwärts"

    out = {
        "close": _r(close), "datum": str(s.index[-1].date()),
        "chg_5d_pct": _r(c5), "chg_20d_pct": _r(c20), "chg_60d_pct": _r(c60),
        "sma50": _r(sma50), "sma200": _r(sma200),
        "ueber_sma50": close > sma50 if sma50 else None,
        "ueber_sma200": close > sma200 if sma200 else None,
        "trend": trend,
        "abstand_52w_hoch_pct": _r(_pct(close, hoch52)),
    }
    if spy is None:
        return out

    spy_c20 = _pct(float(spy.iloc[-1]), float(spy.iloc[-21])) if len(spy) > 20 else None
    out["rs_20d_vs_spy"] = _r(c20 - spy_c20) if c20 is not None and spy_c20 is not None else None

    # Korrelation der Tagesrenditen (60 gemeinsame Handelstage)
    df = pd.concat([s.rename("x"), spy.rename("m")], axis=1, join="inner").dropna()
    r = df.pct_change().dropna().tail(60)
    out["korrelation_60d"] = _r(r["x"].corr(r["m"])) if len(r) >= 40 else None

    # Antizyklik: in Wochen, in denen der S&P 500 um mehr als 1 % fiel -
    # wie oft stieg dieser Rohstoff? (bis zu 2 Jahre Wochendaten)
    w = df.resample("W-FRI").last().pct_change().dropna() * 100
    schwach = w[w["m"] <= SPY_WOCHE_SCHWACH]
    if len(schwach) >= 5:
        out["antizyklik"] = {
            "wochen_aktien_schwach": int(len(schwach)),
            "davon_gestiegen": int((schwach["x"] > 0).sum()),
            "quote_pct": _r((schwach["x"] > 0).mean() * 100, 0),
            "schnitt_pct": _r(schwach["x"].mean()),
            "schnitt_aktien_pct": _r(schwach["m"].mean()),
            "zeitraum_wochen": int(len(w)),
        }
    return out


def _signal(k):
    if k.get("trend") == "aufwärts" and (k.get("rs_20d_vs_spy") or 0) > 0:
        return "Rückenwind"
    if k.get("trend") == "abwärts":
        return "Gegenwind"
    return "Neutral"


def _aktienlage(spy_k, sectors):
    """Sind die Aktien bzw. die bisher fuehrenden Sektoren schwach?"""
    fuehrer = []
    for name, s in (sectors or {}).items():
        if name == "Edelmetalle" or not isinstance(s, dict):
            continue
        if isinstance(s.get("rs_20d_vs_spy"), (int, float)):
            fuehrer.append((s["rs_20d_vs_spy"], name, s.get("chg_5d_avg")))
    fuehrer.sort(reverse=True)
    top = fuehrer[:3]
    c5 = [x[2] for x in top if isinstance(x[2], (int, float))]
    top_c5 = round(sum(c5) / len(c5), 2) if c5 else None
    spy20 = spy_k.get("chg_20d_pct") if spy_k else None

    gruende = []
    if isinstance(spy20, (int, float)) and spy20 < 0:
        gruende.append(f"S&P 500 auf 20 Tage {spy20:+.1f} %".replace(".", ","))
    if isinstance(top_c5, (int, float)) and top_c5 <= FUEHRER_FALL_5D:
        gruende.append(f"führende Sektoren ({', '.join(x[1] for x in top)}) auf 5 Tage im Schnitt {top_c5:+.1f} %".replace(".", ","))
    return {
        "spy_chg_5d_pct": spy_k.get("chg_5d_pct") if spy_k else None,
        "spy_chg_20d_pct": spy20,
        "fuehrende_sektoren": [x[1] for x in top],
        "fuehrende_chg_5d_avg": top_c5,
        "aktien_schwach": bool(gruende),
        "grund": "; ".join(gruende) if gruende else "Aktien und führende Sektoren ohne Schwächesignal",
    }


def _rotation(werte, lage):
    starke = [k for k in EDELMETALLE if k in werte
              and (werte[k].get("chg_20d_pct") or 0) > 0
              and (werte[k].get("rs_20d_vs_spy") or -99) >= RS_ROTATION_MIN
              and werte[k].get("ueber_sma50")]
    namen = " und ".join(werte[k]["name"] for k in starke)
    if starke and lage["aktien_schwach"]:
        return {"status": "Rotation in Edelmetalle", "farbe": "gruen",
                "text": f"{namen} steigen, während Aktien schwächeln ({lage['grund']}). "
                        "Kapital sucht Sicherheit – Minenaktien im Scanner genauer ansehen."}
    if starke:
        return {"status": "Edelmetalle stark", "farbe": "gelb",
                "text": f"{namen} laufen deutlich besser als der S&P 500, die Aktien zeigen aber noch keine Schwäche – "
                        "eher paralleler Aufwärtstrend als Flucht aus Aktien."}
    if lage["aktien_schwach"]:
        return {"status": "Aktien schwach, keine Rotation", "farbe": "gelb",
                "text": f"{lage['grund']}, aber Gold und Silber ziehen (noch) nicht an. Keine Bestätigung für eine Umschichtung."}
    return {"status": "Keine Rotation", "farbe": "grau",
            "text": "Aktien ohne Schwächesignal, Edelmetalle ohne deutliche Überrendite."}


def _chart(daten, spy):
    import pandas as pd

    reihen_def = [("GOLD", "Gold"), ("SILBER", "Silber"), ("GOLDMINEN", "Goldminen (GDX)"), ("SPY", "S&P 500")]
    serien = {}
    for key, _ in reihen_def:
        sym = REFERENZ[0] if key == "SPY" else ROHSTOFFE[key][0]
        s = spy if key == "SPY" else daten.get(sym)
        if s is not None:
            serien[key] = s
    if "SPY" not in serien:
        return None
    df = pd.concat(serien, axis=1).ffill().dropna().tail(CHART_TAGE)
    if len(df) < 20:
        return None
    basis = df.iloc[0]
    return {
        "daten": [str(d.date()) for d in df.index],
        "reihen": [{"key": k, "label": l, "werte": [_r(v, 2) for v in (df[k] / basis[k] * 100)]}
                   for k, l in reihen_def if k in df.columns],
    }


def berechnen(sectors=None, watchlist=None):
    """Rohstoff-Monitor berechnen. Liefert nie eine Exception."""
    from datetime import datetime, timezone

    try:
        symbole = [v[0] for v in ROHSTOFFE.values()] + [REFERENZ[0]]
        daten = _laden(symbole)
        spy = daten.get(REFERENZ[0])
        if spy is None:
            return {"available": False, "reason": "S&P 500 (SPY) über yfinance nicht ladbar"}

        werte = {}
        for key, (sym, name, einheit) in ROHSTOFFE.items():
            s = daten.get(sym)
            if s is None:
                werte[key] = {"name": name, "symbol": sym, "available": False}
                continue
            k = _kennzahlen(s, spy)
            k.update({"name": name, "symbol": sym, "einheit": einheit, "available": True})
            k["signal"] = _signal(k) if key != "DOLLAR" else None
            werte[key] = k

        spy_k = _kennzahlen(spy, None)
        lage = _aktienlage(spy_k, sectors)
        g, si = werte.get("GOLD", {}), werte.get("SILBER", {})
        ratio = _r(g["close"] / si["close"], 1) if g.get("close") and si.get("close") else None

        minen = []
        for t, e in (watchlist or {}).items():
            if isinstance(e, dict) and e.get("sector") == "Edelmetalle" and "error" not in e:
                st = e.get("setup") or {}
                minen.append({"ticker": t, "close": e.get("close"), "chg_5d_pct": e.get("chg_5d_pct"),
                              "chg_20d_pct": e.get("chg_20d_pct"), "score": st.get("score"), "stufe": st.get("stufe")})
        minen.sort(key=lambda m: m["score"] if isinstance(m["score"], (int, float)) else -1, reverse=True)

        return {
            "available": True,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "quelle": "yfinance (Terminkontrakte GC=F, SI=F, HG=F, CL=F; GDX; DX-Y.NYB; SPY)",
            "werte": werte,
            "referenz": dict(spy_k, name=REFERENZ[1], symbol=REFERENZ[0]),
            "aktienlage": lage,
            "rotation": _rotation(werte, lage),
            "gold_silber_ratio": ratio,
            "minen": minen,
            "sektor_edelmetalle": (sectors or {}).get("Edelmetalle"),
            "chart": _chart(daten, spy),
            "parameter": {"rs_rotation_min": RS_ROTATION_MIN, "fuehrer_fall_5d": FUEHRER_FALL_5D,
                          "spy_woche_schwach": SPY_WOCHE_SCHWACH},
        }
    except Exception as e:
        return {"available": False, "error": str(e)}
