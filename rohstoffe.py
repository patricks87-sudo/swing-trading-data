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

# Rohstoff-Ampel (seit 18.10.2026): eigenes Regime fuer den Sektor
# "Edelmetalle" (Minenaktien). Alle anderen Aktien folgen weiter der
# Haupt-Ampel (analysis.compute_regime). Risikobudget (375 EUR) und
# Sektor-Limit (max. 2) gelten gemeinsam.
AMPEL_LIMITS = {
    "GRÜN": {"max_neue_positionen": 1, "max_offene_positionen": 2, "nur_hohe_qualitaet": False},
    "GELB": {"max_neue_positionen": 1, "max_offene_positionen": 1, "nur_hohe_qualitaet": True},
    "ROT": {"max_neue_positionen": 0, "max_offene_positionen": 0, "nur_hohe_qualitaet": False},
}
AMPEL_FORWARD_TAGE = 10      # Bilanz: Entwicklung der Goldminen 10 Handelstage nach dem Signal

# Handelbare Produkte fuer die taegliche Handlungsempfehlung (nur Hinweis,
# kein System-Trade). ISIN vor dem Kauf in Trade Republic pruefen.
PRODUKTE = {
    "GOLD": {
        "1x": {"name": "Xetra-Gold (physisch hinterlegt)", "isin": "DE000A0S9GB0"},
        "2x": {"name": "WisdomTree Gold 2x Daily Leveraged", "isin": "JE00B2NFTL95"},
    },
    "SILBER": {
        "1x": {"name": "WisdomTree Physical Silver", "isin": "JE00B1VS3333"},
        "2x": {"name": "WisdomTree Silver 2x Daily Leveraged", "isin": "JE00B2NFTS64"},
    },
}
MAX_HEBEL = 2


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
            h = yf.Ticker(sym).history(period="3y", interval="1d", auto_adjust=True)
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
        # mittlere Tagesbewegung (Betrag) der letzten 20 Tage in % - Basis fuer Stop-Orientierung
        "tagesbewegung_pct": _r(s.pct_change().abs().tail(20).mean() * 100) if len(s) > 21 else None,
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
    # wie oft stieg dieser Rohstoff? (bis zu 3 Jahre Wochendaten)
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


def _ampel_kriterien(g, si, gdx, usd):
    """Sechs Kriterien der Rohstoff-Ampel aus aktuellen Kennzahlen (Dicts)."""
    def ok(v):
        return None if v is None else bool(v)
    gt = lambda a, b: None if a is None or b is None else a > b
    return [
        {"kriterium": "Gold über SMA50", "erfuellt": ok(gt(g.get("close"), g.get("sma50")))},
        {"kriterium": "Gold-Trend intakt (SMA50 über SMA200)", "erfuellt": ok(gt(g.get("sma50"), g.get("sma200")))},
        {"kriterium": "Silber über SMA50", "erfuellt": ok(gt(si.get("close"), si.get("sma50")))},
        {"kriterium": "Goldminen (GDX) über SMA50", "erfuellt": ok(gt(gdx.get("close"), gdx.get("sma50")))},
        {"kriterium": "Gold stärker als S&P 500 (20 Tage)", "erfuellt": ok(None if g.get("rs_20d_vs_spy") is None else g["rs_20d_vs_spy"] >= 0)},
        {"kriterium": "US-Dollar unter SMA50", "erfuellt": ok(gt(usd.get("sma50"), usd.get("close")))},
    ]


def _ampel_status(kriterien, gold_unter_sma200, rotation_aktiv):
    erfuellt = sum(1 for k in kriterien if k["erfuellt"] is True)
    unbekannt = sum(1 for k in kriterien if k["erfuellt"] is None)
    bewertbar = len(kriterien) - unbekannt
    hoch = erfuellt + unbekannt * (erfuellt / bewertbar if bewertbar else 0.5)
    status = "GRÜN" if hoch >= 5 else "GELB" if hoch >= 3 else "ROT"
    hinweis = None
    if status == "GRÜN" and gold_unter_sma200:
        status, hinweis = "GELB", "Gold unter SMA200 – höchstens Gelb"
    if status == "GELB" and rotation_aktiv and not gold_unter_sma200:
        status, hinweis = "GRÜN", "Rotation aus Aktien in Edelmetalle – Gelb auf Grün angehoben"
    return status, erfuellt, unbekannt, hinweis


def _ampel(werte, rotation):
    g, si, gdx, usd = (werte.get(k, {}) for k in ("GOLD", "SILBER", "GOLDMINEN", "DOLLAR"))
    kriterien = _ampel_kriterien(g, si, gdx, usd)
    gold_unter_200 = bool(g.get("sma200") and g.get("close") and g["close"] < g["sma200"])
    status, erfuellt, unbekannt, hinweis = _ampel_status(
        kriterien, gold_unter_200, rotation.get("status") == "Rotation in Edelmetalle")
    lim = AMPEL_LIMITS[status]
    regel = {"GRÜN": "bis zu 1 neue Minenaktie pro Tag, max. 2 offen",
             "GELB": "nur „Kauf – hohe Qualität“, max. 1 neue und 1 offen",
             "ROT": "keine neuen Minenaktien"}[status]
    return dict(lim, status=status, kriterien=kriterien, kriterien_erfuellt=erfuellt,
                kriterien_unbekannt=unbekannt, hinweis=hinweis, gilt_fuer_sektor="Edelmetalle",
                kurztext=f"Rohstoff-Ampel {status}: {erfuellt}/6 Kriterien – {regel}" + (f" ({hinweis})" if hinweis else ""))


def _ampel_bilanz(daten, spy):
    """Rueckblick: Ampel-Status fuer jeden Handelstag der Historie berechnen
    (ohne Rotations-Aufwertung, die braucht Sektordaten) und messen, wie sich
    die Goldminen (GDX) in den 10 Handelstagen danach entwickelt haben."""
    import pandas as pd

    sym = {k: ROHSTOFFE[k][0] for k in ("GOLD", "SILBER", "GOLDMINEN", "DOLLAR")}
    if any(daten.get(v) is None for v in sym.values()):
        return None
    df = pd.concat({k: daten[v] for k, v in sym.items()} | {"SPY": spy}, axis=1).ffill().dropna()
    if len(df) < 260:
        return None
    sma50 = df.rolling(50).mean()
    sma200 = df.rolling(200).mean()
    rs20 = (df["GOLD"].pct_change(20) - df["SPY"].pct_change(20)) * 100
    krit = pd.DataFrame({
        "g50": df["GOLD"] > sma50["GOLD"],
        "g_trend": sma50["GOLD"] > sma200["GOLD"],
        "s50": df["SILBER"] > sma50["SILBER"],
        "m50": df["GOLDMINEN"] > sma50["GOLDMINEN"],
        "rs": rs20 >= 0,
        "usd": df["DOLLAR"] < sma50["DOLLAR"],
    })
    n = krit.sum(axis=1)
    status = pd.Series("ROT", index=df.index)
    status[n >= 3] = "GELB"
    status[n >= 5] = "GRÜN"
    status[(status == "GRÜN") & (df["GOLD"] < sma200["GOLD"])] = "GELB"
    h = AMPEL_FORWARD_TAGE
    fwd = (df["GOLDMINEN"].shift(-h) / df["GOLDMINEN"] - 1) * 100
    fwd_spy = (df["SPY"].shift(-h) / df["SPY"] - 1) * 100
    gueltig = sma200.notna().all(axis=1) & fwd.notna()
    # Gold/Silber 1x und 2x (taeglich neu gehebelt, inkl. ca. 1 % Jahreskosten)
    def fwd_hebel(serie, hebel):
        r = serie.pct_change() * hebel - (0.01 / 252 if hebel > 1 else 0)
        wachstum = (1 + r).rolling(h).apply(lambda x: x.prod(), raw=True).shift(-h)
        return (wachstum - 1) * 100
    hebel_fwd = {f"{m}_{x}x": fwd_hebel(df[m], x) for m in ("GOLD", "SILBER") for x in (1, 2)}
    out = {}
    for st in ("GRÜN", "GELB", "ROT"):
        m = gueltig & (status == st)
        if m.sum() == 0:
            out[st] = {"tage": 0}
            continue
        out[st] = {
            "tage": int(m.sum()),
            "schnitt_minen_pct": _r(fwd[m].mean()),
            "schnitt_ueber_sp500_pct": _r((fwd[m] - fwd_spy[m]).mean()),
            "trefferquote_pct": _r((fwd[m] > 0).mean() * 100, 0),
            "produkte": {k: {"schnitt_pct": _r(v[m].mean()), "im_plus_pct": _r((v[m] > 0).mean() * 100, 0),
                             "schlechtester_pct": _r(v[m].min())}
                         for k, v in hebel_fwd.items() if v[m].notna().any()},
        }
    tage = status[gueltig]
    return {
        "zeitraum_von": str(tage.index[0].date()) if len(tage) else None,
        "zeitraum_bis": str(tage.index[-1].date()) if len(tage) else None,
        "forward_tage": h,
        "je_status": out,
        "hinweis": "Ohne Aufwertung durch Rotation (braucht historische Sektordaten). Überlappende 10-Tage-Fenster – Tage sind nicht unabhängig.",
    }


def empfehlung(roh, verlauf):
    """Taegliche Handlungsempfehlung je Metall aus Rohstoff-Ampel + Kurslage.
    Rein regelbasiert, nur Hinweis (kein System-Trade, kein Journal).
    verlauf: Liste frueherer Ampel-Eintraege [{"zeit_utc", "datum", "run", "status"}]."""
    am = roh.get("ampel") or {}
    status = am.get("status")
    werte = roh.get("werte") or {}
    vorher = verlauf[-1]["status"] if verlauf else None
    seit = None
    for e in reversed(verlauf or []):
        if e.get("status") != status:
            break
        seit = e.get("datum")
    veraenderung = None
    if vorher and vorher != status:
        art = {"GRÜN": "Einstiegssignal", "GELB": "Vorsicht", "ROT": "Ausstiegssignal"}[status]
        veraenderung = {"von": vorher, "nach": status, "art": art,
                        "text": f"Ampel von {vorher} auf {status} gewechselt – {art}."}

    metalle = {}
    for key, name in (("GOLD", "Gold"), ("SILBER", "Silber")):
        w = werte.get(key) or {}
        p = PRODUKTE[key]
        ueber50 = w.get("ueber_sma50")
        staerker = (w.get("rs_20d_vs_spy") or -1) >= 0
        bew = w.get("tagesbewegung_pct")
        if status == "GRÜN" and ueber50 and staerker:
            aktion, hebel = "Kaufen", 2
            text = f"{name} im Aufwärtstrend und stärker als Aktien – Einstieg möglich, auch mit Faktor 2."
        elif status == "GRÜN":
            aktion, hebel = "Kaufen (ungehebelt)", 1
            text = f"Ampel Grün, aber {name} selbst " + ("unter dem 50-Tage-Schnitt" if not ueber50 else "schwächer als Aktien") + " – höchstens ohne Hebel."
        elif status == "GELB":
            aktion, hebel = "Halten / kein Hebel", 1 if ueber50 else 0
            text = (f"Gemischtes Bild – keine neuen gehebelten Käufe. Bestehende 2x-Positionen eng absichern; "
                    + (f"ungehebelt ist {name} vertretbar." if ueber50 else f"auch ungehebelt erst einsteigen, wenn {name} wieder über dem 50-Tage-Schnitt liegt."))
        else:
            aktion, hebel = "Nicht investieren", 0
            text = f"Edelmetalle schwach – kein Einstieg. Gehebelte {name}-Positionen verkaufen, ungehebelte kritisch prüfen."
        hebel = min(hebel, MAX_HEBEL)
        stop = None
        if hebel >= 1 and isinstance(bew, (int, float)):
            # Orientierung: 3 durchschnittliche Tagesbewegungen des Metalls, mal Hebel
            stop = round(3 * bew * hebel, 1)
        metalle[key] = {
            "name": name, "aktion": aktion, "hebel": hebel, "text": text,
            "produkt": p.get(f"{hebel}x") if hebel else None,
            "stop_orientierung_pct": stop,
            "tagesbewegung_pct": bew,
        }
    return {
        "status": status, "vorher": vorher, "seit": seit, "veraenderung": veraenderung,
        "metalle": metalle,
        "regeln": ("Nur Hinweis, kein System-Trade. Gehebelte Produkte (Faktor 2) werden täglich neu gehebelt: "
                   "in Seitwärtsphasen verlieren sie auch ohne Kursverlust des Metalls an Wert – nur kurz halten "
                   "(Richtwert bis 10 Handelstage) und spätestens verkaufen, wenn die Ampel auf ROT springt."),
        "produkte": PRODUKTE,
    }


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

        rotation = _rotation(werte, lage)
        return {
            "available": True,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "quelle": "yfinance (Terminkontrakte GC=F, SI=F, HG=F, CL=F; GDX; DX-Y.NYB; SPY)",
            "werte": werte,
            "referenz": dict(spy_k, name=REFERENZ[1], symbol=REFERENZ[0]),
            "aktienlage": lage,
            "rotation": rotation,
            "ampel": _ampel(werte, rotation),
            "ampel_bilanz": _ampel_bilanz(daten, spy),
            "gold_silber_ratio": ratio,
            "minen": minen,
            "sektor_edelmetalle": (sectors or {}).get("Edelmetalle"),
            "chart": _chart(daten, spy),
            "parameter": {"rs_rotation_min": RS_ROTATION_MIN, "fuehrer_fall_5d": FUEHRER_FALL_5D,
                          "spy_woche_schwach": SPY_WOCHE_SCHWACH},
        }
    except Exception as e:
        return {"available": False, "error": str(e)}
