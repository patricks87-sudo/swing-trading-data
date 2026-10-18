"""Rohstoff-Monitor (seit 18.10.2026).

Beobachtet Gold, Silber, Kupfer, Rohoel, Goldminen (GDX) und den US-Dollar,
prueft, ob Kapital aus schwachen Aktiensektoren in Edelmetalle rotiert, und
berechnet daraus die Rohstoff-Ampel sowie eine taegliche Handlungsempfehlung
fuer Gold und Silber (ungehebelt, nur Hinweis - kein System-Trade).
Datenquelle: yfinance (kostenlos, belastet das Twelve-Data-Kontingent nicht).

Ergebnis landet im Feed unter snapshot["rohstoffe"] und in data/rohstoffe.json
fuer die Cockpit-Seite "Rohstoffe". Die Aktien-Scores aendern sich dadurch
nicht. (Minenaktien wurden am 18.10.2026 wieder aus der Watchlist genommen -
der Rohstoff-Teil betrachtet nur die Rohstoffe selbst.)

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
AMPEL_FORWARD_TAGE = 10      # Rueckblick: Entwicklung 10 Handelstage nach dem Ampelstatus
STOP_TAGESBEWEGUNGEN = 3     # Stop = 3 x mittlere Tagesbewegung (20 Tage) unter Einstieg

# Handelbare Produkte (ungehebelt) fuer die Handlungsempfehlung.
# Gehebelte Produkte bewusst NICHT (Entscheidung 18.10.2026: Rendite-Vorsprung
# zu klein fuer das verdoppelte Verlustrisiko).
PRODUKTE = {
    "GOLD": {"name": "Xetra-Gold (physisch hinterlegt)", "isin": "DE000A0S9GB0"},
    "SILBER": {"name": "WisdomTree Physical Silver", "isin": "JE00B1VS3333"},
}


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
        # mittlere Tagesbewegung (Betrag) der letzten 20 Tage in % - Basis fuer die Stop-Orientierung
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
        if not isinstance(s, dict):
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
                "text": f"{namen} steigen, während Aktien schwächeln ({lage['grund']}). Kapital sucht Sicherheit."}
    if starke:
        return {"status": "Edelmetalle stark", "farbe": "gelb",
                "text": f"{namen} laufen deutlich besser als der S&P 500, die Aktien zeigen aber noch keine Schwäche – "
                        "eher paralleler Aufwärtstrend als Flucht aus Aktien."}
    if lage["aktien_schwach"]:
        return {"status": "Aktien schwach, keine Rotation", "farbe": "gelb",
                "text": f"{lage['grund']}, aber Gold und Silber ziehen (noch) nicht an. Keine Bestätigung für eine Umschichtung."}
    return {"status": "Keine Rotation", "farbe": "grau",
            "text": "Aktien ohne Schwächesignal, Edelmetalle ohne deutliche Überrendite."}


# ---------------------------------------------------------------------------
# Rohstoff-Ampel
# ---------------------------------------------------------------------------

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
    return {"status": status, "kriterien": kriterien, "kriterien_erfuellt": erfuellt,
            "kriterien_unbekannt": unbekannt, "hinweis": hinweis,
            "kurztext": f"Rohstoff-Ampel {status}: {erfuellt}/6 Kriterien" + (f" ({hinweis})" if hinweis else "")}


def _kauf_bedingung(status, ueber_sma50, rs_20d):
    """Gemeinsame Kaufregel fuer Gold/Silber (heute und in der Simulation)."""
    return status == "GRÜN" and bool(ueber_sma50) and rs_20d is not None and rs_20d >= 0


def _historie(daten, spy):
    """Tagesgenaue Rueckrechnung: Ampelstatus (ohne Rotations-Aufwertung, dafuer
    fehlen historische Sektordaten) plus Kaufbedingung je Metall."""
    import pandas as pd

    sym = {k: ROHSTOFFE[k][0] for k in ("GOLD", "SILBER", "GOLDMINEN", "DOLLAR")}
    if any(daten.get(v) is None for v in sym.values()):
        return None
    df = pd.concat({k: daten[v] for k, v in sym.items()} | {"SPY": spy}, axis=1).ffill().dropna()
    if len(df) < 260:
        return None
    sma50 = df.rolling(50).mean()
    sma200 = df.rolling(200).mean()
    rs20 = {m: (df[m].pct_change(20) - df["SPY"].pct_change(20)) * 100 for m in EDELMETALLE}
    krit = pd.DataFrame({
        "g50": df["GOLD"] > sma50["GOLD"],
        "g_trend": sma50["GOLD"] > sma200["GOLD"],
        "s50": df["SILBER"] > sma50["SILBER"],
        "m50": df["GOLDMINEN"] > sma50["GOLDMINEN"],
        "rs": rs20["GOLD"] >= 0,
        "usd": df["DOLLAR"] < sma50["DOLLAR"],
    })
    n = krit.sum(axis=1)
    status = pd.Series("ROT", index=df.index)
    status[n >= 3] = "GELB"
    status[n >= 5] = "GRÜN"
    status[(status == "GRÜN") & (df["GOLD"] < sma200["GOLD"])] = "GELB"
    gueltig = sma200.notna().all(axis=1)
    kauf = {m: (status == "GRÜN") & (df[m] > sma50[m]) & (rs20[m] >= 0) for m in EDELMETALLE}
    bewegung = {m: df[m].pct_change().abs().rolling(20).mean() * 100 for m in EDELMETALLE}
    return {"df": df[gueltig], "status": status[gueltig],
            "kauf": {m: kauf[m][gueltig] for m in EDELMETALLE},
            "bewegung": {m: bewegung[m][gueltig] for m in EDELMETALLE}}


def _ampel_bilanz(h):
    """Rueckblick: wie entwickelten sich Gold und Silber (ungehebelt) in den
    10 Handelstagen nach einem Tag mit GRUEN / GELB / ROT?"""
    if not h:
        return None
    df, status, t = h["df"], h["status"], AMPEL_FORWARD_TAGE
    out = {}
    for st in ("GRÜN", "GELB", "ROT"):
        m = status == st
        eintrag = {"tage": int(m.sum())}
        for metall in EDELMETALLE:
            fwd = (df[metall].shift(-t) / df[metall] - 1) * 100
            mm = m & fwd.notna()
            if mm.sum():
                eintrag[metall] = {"schnitt_pct": _r(fwd[mm].mean()), "im_plus_pct": _r((fwd[mm] > 0).mean() * 100, 0),
                                   "schlimmster_pct": _r(fwd[mm].min())}
        out[st] = eintrag
    return {
        "zeitraum_von": str(df.index[0].date()), "zeitraum_bis": str(df.index[-1].date()),
        "forward_tage": t, "je_status": out,
        "hinweis": "Ohne Stop und ohne Rotations-Aufwertung; überlappende 10-Tage-Fenster – die Tage sind nicht unabhängig.",
    }


def _simulation(h):
    """Spielt die Gold/Silber-Regel echt durch (ungehebelt):
    Einstieg zum Schlusskurs des Folgetags, sobald die Kaufbedingung gilt
    (Ampel GRUEN + Metall ueber SMA50 + 20 Tage mindestens so stark wie S&P 500).
    Ausstieg: Schlusskurs unter dem Stop (3 x mittlere Tagesbewegung unter
    Einstieg) -> zu diesem Schlusskurs; oder Ampel ROT -> Schlusskurs Folgetag.
    Keine Gebuehren, keine Steuern."""
    if not h:
        return None
    df, status = h["df"], h["status"]
    idx = list(df.index)
    ergebnis = {}
    for metall in EDELMETALLE:
        kurs, kauf, bew = df[metall], h["kauf"][metall], h["bewegung"][metall]
        trades, pos, investiert_tage = [], None, 0
        i = 0
        while i < len(idx) - 1:
            if pos is None:
                if bool(kauf.iloc[i]):
                    e = float(kurs.iloc[i + 1])
                    stop_pct = STOP_TAGESBEWEGUNGEN * float(bew.iloc[i])
                    pos = {"einstieg_datum": str(idx[i + 1].date()), "einstieg": e, "i": i + 1,
                           "stop": e * (1 - stop_pct / 100), "stop_pct": round(stop_pct, 1)}
                    i += 2  # ab dem Tag nach dem Einstieg pruefen
                    continue
            else:
                investiert_tage += 1
                c = float(kurs.iloc[i])
                grund, aus_i = None, None
                if c <= pos["stop"]:
                    grund, aus_i = "Stop", i
                elif status.iloc[i] == "ROT":
                    grund, aus_i = "Ampel ROT", i + 1
                if grund:
                    a = float(kurs.iloc[aus_i])
                    trades.append({"einstieg_datum": pos["einstieg_datum"], "ausstieg_datum": str(idx[aus_i].date()),
                                   "handelstage": aus_i - pos["i"], "ergebnis_pct": _r((a / pos["einstieg"] - 1) * 100),
                                   "grund": grund, "stop_pct": pos["stop_pct"]})
                    pos = None
                    i = aus_i + 1
                    continue
            i += 1
        offen = None
        if pos:
            a = float(kurs.iloc[-1])
            offen = {"einstieg_datum": pos["einstieg_datum"], "handelstage": len(idx) - 1 - pos["i"],
                     "ergebnis_pct": _r((a / pos["einstieg"] - 1) * 100), "stop_pct": pos["stop_pct"]}
        erg = [t["ergebnis_pct"] for t in trades]
        gesamt = 1.0
        for x in erg + ([offen["ergebnis_pct"]] if offen else []):
            gesamt *= 1 + x / 100
        ergebnis[metall] = {
            "trades": trades[-20:],
            "offen": offen,
            "anzahl": len(trades),
            "gewinner": sum(1 for x in erg if x > 0),
            "trefferquote_pct": _r(sum(1 for x in erg if x > 0) / len(erg) * 100, 0) if erg else None,
            "schnitt_pct": _r(sum(erg) / len(erg)) if erg else None,
            "bester_pct": _r(max(erg)) if erg else None,
            "schlechtester_pct": _r(min(erg)) if erg else None,
            "schnitt_tage": _r(sum(t["handelstage"] for t in trades) / len(trades), 1) if trades else None,
            "gesamt_pct": _r((gesamt - 1) * 100),
            "kaufen_und_halten_pct": _r((float(kurs.iloc[-1]) / float(kurs.iloc[0]) - 1) * 100),
            "investiert_pct": _r(investiert_tage / max(1, len(idx) - 1) * 100, 0),
        }
    return {"zeitraum_von": str(idx[0].date()), "zeitraum_bis": str(idx[-1].date()),
            "regel": ("Einstieg zum Schlusskurs am Tag nach dem Kaufsignal (Ampel GRÜN + Metall über SMA50 + 20 Tage mindestens "
                      "so stark wie S&P 500). Ausstieg, wenn der Schlusskurs den Stop (3 × mittlere Tagesbewegung unter Einstieg) "
                      "unterschreitet, oder am Tag nach einem Wechsel auf ROT. Ungehebelt, ohne Gebühren und Steuern."),
            "metalle": ergebnis}


# ---------------------------------------------------------------------------
# Taegliche Handlungsempfehlung (nur Hinweis)
# ---------------------------------------------------------------------------

def empfehlung(roh, verlauf):
    """Taegliche Handlungsempfehlung je Metall aus Rohstoff-Ampel + Kurslage.
    Rein regelbasiert, ungehebelt, nur Hinweis (kein System-Trade, kein Journal).
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
        art = {"GRÜN": "mögliches Einstiegssignal", "GELB": "Vorsicht", "ROT": "Ausstiegssignal"}[status]
        veraenderung = {"von": vorher, "nach": status, "art": art,
                        "text": f"Ampel von {vorher} auf {status} gewechselt – {art}."}

    metalle = {}
    for key, name in (("GOLD", "Gold"), ("SILBER", "Silber")):
        w = werte.get(key) or {}
        ueber50 = w.get("ueber_sma50")
        rs = w.get("rs_20d_vs_spy")
        bew = w.get("tagesbewegung_pct")
        if _kauf_bedingung(status, ueber50, rs):
            aktion = "Kaufen"
            text = f"Ampel Grün, {name} über dem 50-Tage-Schnitt und mindestens so stark wie Aktien – Einstieg möglich."
        elif status == "ROT":
            aktion = "Nicht investieren"
            text = f"Edelmetalle schwach – kein Einstieg. Bestehende {name}-Position verkaufen (Ausstiegsregel)."
        else:
            aktion = "Halten, kein Neukauf"
            grund = (f"{name} unter dem 50-Tage-Schnitt" if not ueber50
                     else f"{name} schwächer als Aktien" if (rs is None or rs < 0) else "Ampel nicht Grün")
            text = f"Bestehende Position halten (Stop beachten), aber nicht neu kaufen – {grund}."
        stop = round(STOP_TAGESBEWEGUNGEN * bew, 1) if isinstance(bew, (int, float)) else None
        metalle[key] = {
            "name": name, "aktion": aktion, "text": text,
            "produkt": PRODUKTE[key],
            "stop_orientierung_pct": stop,
            "tagesbewegung_pct": bew,
        }
    return {
        "status": status, "vorher": vorher, "seit": seit, "veraenderung": veraenderung,
        "metalle": metalle,
        "regeln": ("Nur Hinweis, kein System-Trade, ungehebelt. Kaufen: Ampel GRÜN + Metall über dem 50-Tage-Schnitt + "
                   "auf 20 Tage mindestens so stark wie der S&P 500. Halten: Ampel GELB oder Metall selbst schwach. "
                   "Verkaufen: Ampel ROT oder Stop unterschritten. Stop-Orientierung = 3 × mittlere Tagesbewegung des "
                   "Metalls (20 Tage) unter dem Kaufkurs."),
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
    """Rohstoff-Monitor berechnen. Liefert nie eine Exception.
    watchlist wird nicht mehr gebraucht (Parameter bleibt fuer Kompatibilitaet)."""
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
        rotation = _rotation(werte, lage)
        try:
            hist = _historie(daten, spy)
        except Exception as e:
            print(f"Rohstoff-Historie fehlgeschlagen: {e}")
            hist = None

        return {
            "available": True,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "quelle": "yfinance (Terminkontrakte GC=F, SI=F, HG=F, CL=F; GDX; DX-Y.NYB; SPY)",
            "werte": werte,
            "referenz": dict(spy_k, name=REFERENZ[1], symbol=REFERENZ[0]),
            "aktienlage": lage,
            "rotation": rotation,
            "ampel": _ampel(werte, rotation),
            "ampel_bilanz": _ampel_bilanz(hist),
            "simulation": _simulation(hist),
            "gold_silber_ratio": ratio,
            "chart": _chart(daten, spy),
            "parameter": {"rs_rotation_min": RS_ROTATION_MIN, "fuehrer_fall_5d": FUEHRER_FALL_5D,
                          "spy_woche_schwach": SPY_WOCHE_SCHWACH, "stop_tagesbewegungen": STOP_TAGESBEWEGUNGEN},
        }
    except Exception as e:
        return {"available": False, "error": str(e)}
