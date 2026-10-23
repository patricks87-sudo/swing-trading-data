"""
analysis.py
-----------
Deterministische Bewertungslogik (eingefuehrt 11.10.2026, Umbau "Filterlogik").

Alles, was sich aus den Feed-Daten berechnen laesst, wird hier in Python
berechnet - nicht vom Sprachmodell im Prompt. Claude prueft in P4/P5.5/P1 nur
noch, was Python nicht kann (News, Ad-hoc-Ereignisse) und darf den Score
dafuer um hoechstens +/-10 Punkte korrigieren (mit Begruendung).

Inhalt:
- compute_sector_stats(): Sektor-Durchschnitte und Sektor-Ranking
- compute_regime():       EINE Marktregime-Definition fuer alle Prompts
- compute_setup():        Bulltrap-Flags, ATR-Stop/Ziele, Score 0-100, harte Ausschluesse
- compute_hold_test():    P5.5-Intraday-Check aus 5-Minuten-Kerzen

Reine Funktionen ohne Netzwerkzugriff -> offline testbar.
"""

from __future__ import annotations

from statistics import mean

# ---------------------------------------------------------------------------
# Parameter (zentral, damit Prompts und Cockpit dieselben Zahlen nutzen)
# ---------------------------------------------------------------------------

REGIME_VIX_MAX = 20.0          # VIX unter diesem Wert = Kriterium erfuellt
REGIME_VIX_PANIC = 30.0        # VIX darueber = immer RISK-OFF
# Seit 11.10.2026 (Nutzer-Entscheidung): keine feste Obergrenze von 2 Plaetzen
# mehr, sondern ein Risikobudget. Neue Positionen pro Tag je Regime, offene
# Positionen insgesamt je Regime, zusaetzlich begrenzt durch Gesamtrisiko und
# Kapital (siehe PORTFOLIO unten).
REGIME_MAX_POSITIONS = {"RISK-ON": 2, "NEUTRAL": 1, "RISK-OFF": 0}      # neue pro Tag
REGIME_MAX_OFFEN = {"RISK-ON": 5, "NEUTRAL": 3, "RISK-OFF": 0}          # offen insgesamt (RISK-OFF: keine neuen)

DEPOT_EUR = 8000.0             # Referenz-Depotgroesse
RISK_PER_TRADE_EUR = 75.0      # ca. 1 % des Depots
MAX_GESAMTRISIKO_EUR = 375.0   # ca. 4 % des Depots ueber alle offenen Positionen
MAX_POSITION_EUR = 2500.0      # max. Kapital je Position
MAX_JE_SEKTOR = 2              # max. offene Positionen je Sektor

# Ausstieg seit 11.10.2026: zeitbasiert nach 10 Handelstagen (in der Auswertung
# die beste Variante), dazu ein weiter Schutz-Stop gegen Ausreisser.
HALTEDAUER_TAGE = 10
STOP_ATR_MULT = 2.0            # Schutz-Stop = Einstieg - 2 x ATR
REF_ZIEL_R = 2.0               # nur fuer den CRV-Teilscore (Einstiegsnaehe), kein Verkaufsziel

EARNINGS_BLOCK_TRADING_DAYS = 5
MIN_AVG_VOLUME = 1_000_000

SCORE_WEIGHTS = {
    "kapitalfluss": 0.20,
    "relative_staerke": 0.20,
    "trendkontext": 0.15,
    "sektorstaerke": 0.15,
    "setup": 0.15,
    "optionsflow": 0.10,
    "crv": 0.05,
}

# Score-Stufen (gelten fuer P4 und P1 gleichermassen)
SCORE_KAUF_HOCH = 75     # "Kauf – hohe Qualität"
SCORE_KAUF = 65          # "Kauf – solide"
SCORE_BEOBACHTEN = 50    # "Beobachten"; darunter "Kein Setup"

SEMI_SECTORS = {"Semiconductors/AI"}


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _clip(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
# Sektoren
# ---------------------------------------------------------------------------

def compute_sector_stats(watchlist: dict, spy: dict) -> dict:
    """Durchschnittliche 5/20-Tage-Performance je Sektor, relative Staerke
    gegenueber dem S&P 500 und ein Ranking (1 = staerkster Sektor)."""
    spy5 = spy.get("chg_5d_pct") if spy else None
    spy20 = spy.get("chg_20d_pct") if spy else None
    groups: dict[str, list] = {}
    for tkr, e in watchlist.items():
        if not isinstance(e, dict) or "error" in e:
            continue
        groups.setdefault(e.get("sector", "Unknown"), []).append(e)

    stats = {}
    for sector, entries in groups.items():
        c5 = [e["chg_5d_pct"] for e in entries if _num(e.get("chg_5d_pct"))]
        c20 = [e["chg_20d_pct"] for e in entries if _num(e.get("chg_20d_pct"))]
        obv_up = [e for e in entries if _num(e.get("obv_trend_5d")) and e["obv_trend_5d"] > 0]
        avg5 = round(mean(c5), 2) if c5 else None
        avg20 = round(mean(c20), 2) if c20 else None
        stats[sector] = {
            "anzahl": len(entries),
            "chg_5d_avg": avg5,
            "chg_20d_avg": avg20,
            "rs_5d_vs_spy": round(avg5 - spy5, 2) if _num(avg5) and _num(spy5) else None,
            "rs_20d_vs_spy": round(avg20 - spy20, 2) if _num(avg20) and _num(spy20) else None,
            "obv_steigend_anteil": round(len(obv_up) / len(entries) * 100, 0) if entries else None,
        }

    # Ranking: 60 % RS 20 Tage + 40 % RS 5 Tage
    def rank_key(item):
        s = item[1]
        r20 = s["rs_20d_vs_spy"] if _num(s["rs_20d_vs_spy"]) else -99
        r5 = s["rs_5d_vs_spy"] if _num(s["rs_5d_vs_spy"]) else -99
        return 0.6 * r20 + 0.4 * r5

    ordered = sorted(stats.items(), key=rank_key, reverse=True)
    n = len(ordered)
    for i, (sector, s) in enumerate(ordered, start=1):
        s["rang"] = i
        s["score"] = round(100 * (1 - (i - 1) / (n - 1)), 0) if n > 1 else 50
        rs20 = s["rs_20d_vs_spy"]
        rs5 = s["rs_5d_vs_spy"]
        if _num(rs20) and _num(rs5) and rs20 > 0 and rs5 > 0:
            s["trend"] = "positiv"
        elif _num(rs20) and _num(rs5) and rs20 < 0 and rs5 < 0:
            s["trend"] = "negativ"
        else:
            s["trend"] = "neutral"
    return dict(ordered)


# ---------------------------------------------------------------------------
# Marktregime - EINE Definition fuer P4, P5, P5.5 und P1
# ---------------------------------------------------------------------------

def compute_regime(indices: dict, breadth: dict, macro: dict) -> dict:
    spy = indices.get("SP500") or {}
    qqq = indices.get("NASDAQ_COMPOSITE") or {}
    vix = (macro or {}).get("vix") or {}
    vix_val = vix.get("close") if vix.get("available") else None

    kriterien = []

    def add(name, ok, wert):
        kriterien.append({"kriterium": name, "erfuellt": None if ok is None else bool(ok), "wert": wert})

    add("S&P 500 über SMA50", (spy.get("pct_from_sma50") or -1) > 0 if _num(spy.get("pct_from_sma50")) else None,
        spy.get("pct_from_sma50"))
    add("Nasdaq über SMA20", (qqq.get("pct_from_sma20") or -1) > 0 if _num(qqq.get("pct_from_sma20")) else None,
        qqq.get("pct_from_sma20"))
    add(f"VIX unter {REGIME_VIX_MAX:g}", vix_val < REGIME_VIX_MAX if _num(vix_val) else None, vix_val)
    p50 = breadth.get("pct_above_sma50")
    add("≥50 % der Watchlist über SMA50", p50 >= 50 if _num(p50) else None, p50)
    p5 = breadth.get("pct_positive_5d")
    add("≥50 % der Watchlist im 5-Tage-Plus", p5 >= 50 if _num(p5) else None, p5)

    erfuellt = sum(1 for k in kriterien if k["erfuellt"] is True)
    unbekannt = sum(1 for k in kriterien if k["erfuellt"] is None)
    # Unbekannte Kriterien zaehlen NICHT als verletzt (frueherer Fehler: fehlende
    # Daten wurden als "nicht erfuellt" gewertet -> kuenstliches Risk-Off).
    bewertbar = len(kriterien) - unbekannt
    hochgerechnet = erfuellt + unbekannt * (erfuellt / bewertbar if bewertbar else 0.5)

    if hochgerechnet >= 4:
        status = "RISK-ON"
    elif hochgerechnet >= 2:
        status = "NEUTRAL"
    else:
        status = "RISK-OFF"

    override = None
    if _num(vix_val) and vix_val > REGIME_VIX_PANIC:
        status, override = "RISK-OFF", f"VIX über {REGIME_VIX_PANIC:g}"
    elif _num(spy.get("sma200")) and _num(spy.get("close")) and spy["close"] < spy["sma200"]:
        status, override = "RISK-OFF", "S&P 500 unter SMA200"

    tnx = (macro or {}).get("us10y") or {}
    hinweise = []
    if tnx.get("available") and _num(tnx.get("close")):
        hinweise.append(
            f"US-10J-Rendite {format(tnx['close'], '.2f').replace('.', ',')} % "
            f"(20 Tage: {format(tnx.get('chg_20d_abs') or 0, '+.2f').replace('.', ',')} Pkt.) – nur Info, kein Kriterium"
        )
    if not vix.get("available"):
        hinweise.append("Echter VIX nicht verfügbar – Kriterium als unbekannt gewertet")

    return {
        "status": status,
        "kriterien_erfuellt": erfuellt,
        "kriterien_unbekannt": unbekannt,
        "kriterien": kriterien,
        "override": override,
        "max_neue_positionen": REGIME_MAX_POSITIONS[status],
        "max_offene_positionen": REGIME_MAX_OFFEN[status],
        "hinweise": hinweise,
        "kurztext": f"{status}: {erfuellt}/5 Kriterien erfüllt" + (f" ({override})" if override else ""),
    }


# ---------------------------------------------------------------------------
# Setup, Score und harte Ausschluesse je Aktie
# ---------------------------------------------------------------------------

def bulltrap_flags(e: dict) -> list[str]:
    flags = []
    if _num(e.get("pct_from_sma20")) and e["pct_from_sma20"] > 8:
        flags.append("Abstand SMA20 > 8 %")
    if _num(e.get("pct_from_sma50")) and e["pct_from_sma50"] > 15:
        flags.append("Abstand SMA50 > 15 %")
    if _num(e.get("rsi14")) and e["rsi14"] > 72:
        flags.append("RSI14 > 72")
    if _num(e.get("chg_5d_pct")) and e["chg_5d_pct"] > 15:
        flags.append("Anstieg > 15 % in 5 Tagen")
    if _num(e.get("atr_pct")) and _num(e.get("atr_pct_avg60")) and e["atr_pct_avg60"] > 0 \
            and e["atr_pct"] > 2 * e["atr_pct_avg60"]:
        flags.append("ATR > 2× 60-Tage-Schnitt")
    if _num(e.get("obv_trend_5d")) and _num(e.get("chg_5d_pct")) and e["obv_trend_5d"] < 0 and e["chg_5d_pct"] > 2:
        flags.append("Kurs steigt, OBV fällt")
    return flags


def _score_kapitalfluss(e):
    pts = 0.0
    o5, o20 = e.get("obv_trend_5d"), e.get("obv_trend_20d")
    if _num(o5) and o5 > 0:
        pts += 40
    if _num(o20) and o20 > 0:
        pts += 40
    vr = e.get("volume_ratio")
    if _num(vr):
        pts += 20 * _clip((vr - 0.7) / 0.6, 0, 1)   # 0,7x -> 0, 1,3x -> volle 20
    elif not _num(o5) and not _num(o20):
        return 50.0
    return pts


def _score_rs(e, spy, sector_stat):
    def scaled(diff, full):  # diff in Prozentpunkten, linear -full..+full -> 0..100
        return _clip(50 + 50 * diff / full)
    parts = []
    if _num(e.get("chg_20d_pct")) and _num(spy.get("chg_20d_pct")):
        parts.append((0.4, scaled(e["chg_20d_pct"] - spy["chg_20d_pct"], 6)))
    if _num(e.get("chg_5d_pct")) and _num(spy.get("chg_5d_pct")):
        parts.append((0.3, scaled(e["chg_5d_pct"] - spy["chg_5d_pct"], 3)))
    if sector_stat and sector_stat.get("anzahl", 0) > 1 and _num(e.get("chg_20d_pct")) \
            and _num(sector_stat.get("chg_20d_avg")):
        parts.append((0.3, scaled(e["chg_20d_pct"] - sector_stat["chg_20d_avg"], 6)))
    if not parts:
        return 50.0
    wsum = sum(w for w, _ in parts)
    return sum(w * s for w, s in parts) / wsum


def _score_trend(e):
    return {"gruen": 100.0, "gelb": 50.0, "rot": 0.0}.get((e.get("ampel") or {}).get("trendkontext"), 50.0)


def _score_setup(e, flags):
    d20, d50 = e.get("pct_from_sma20"), e.get("pct_from_sma50")
    if not _num(d20) or not _num(d50):
        base = 50.0
    elif d50 < 0:
        base = 10.0                      # unter SMA50: kein Swing-Long-Setup
    elif -1.5 <= d20 <= 3:
        base = 100.0                     # Pullback-Zone an der SMA20
    elif 3 < d20 <= 6:
        base = 65.0
    elif d20 > 6:
        base = 30.0                      # weit gelaufen
    else:
        base = 45.0                      # unter SMA20, aber ueber SMA50
    return _clip(base - 25 * len(flags))


def _score_options(e):
    of = e.get("options_flow") or {}
    if not of.get("available"):
        return 50.0
    return {"bullisch": 100.0, "neutral": 50.0, "bearisch": 0.0}.get(of.get("einschaetzung"), 50.0)


def compute_levels(e: dict, eurusd) -> dict:
    """Handelsmarken. Einstieg = aktueller Kurs, wenn er in der Pullback-Zone
    liegt (max. 3 % ueber SMA20), sonst Limit an der SMA20. Schutz-Stop
    2 x ATR, Ausstieg nach 10 Handelstagen (seit 11.10.2026, keine festen
    Kursziele mehr)."""
    close, atr, sma20 = e.get("close"), e.get("atr14"), e.get("sma20")
    if not (_num(close) and _num(atr) and atr > 0):
        return {"available": False}
    if _num(sma20) and close > sma20 * 1.03:
        entry, entry_typ = sma20, "Limit an SMA20 (Rücksetzer abwarten)"
    else:
        entry, entry_typ = close, "am aktuellen Kurs"
    risk = STOP_ATR_MULT * atr
    stop = entry - risk
    ref = entry + REF_ZIEL_R * risk
    crv_now = (ref - close) / (close - stop) if close > stop else 0.0
    fx = eurusd if _num(eurusd) else None
    risk_eur = risk * fx if fx else None
    stueck = int(RISK_PER_TRADE_EUR // risk_eur) if risk_eur else None
    entry_eur = entry * fx if fx else None
    if stueck is not None and entry_eur and stueck * entry_eur > MAX_POSITION_EUR:
        stueck = int(MAX_POSITION_EUR // entry_eur)

    def eur(x):
        return round(x * fx, 2) if fx else None

    return {
        "available": True,
        "einstieg_usd": round(entry, 2),
        "einstieg_typ": entry_typ,
        "stop_usd": round(stop, 2),
        "einstieg_eur": eur(entry),
        "stop_eur": eur(stop),
        "ausstieg": f"spätestens nach {HALTEDAUER_TAGE} Handelstagen zum Schlusskurs",
        "haltedauer_tage": HALTEDAUER_TAGE,
        "risiko_pct": round(risk / entry * 100, 2),
        "crv_am_aktuellen_kurs": round(crv_now, 2),
        "stueck": stueck,
        "kapitalbedarf_eur": round(stueck * entry_eur, 0) if stueck is not None and entry_eur else None,
        "risiko_eur": round(stueck * risk_eur, 0) if stueck is not None and risk_eur else None,
    }


def compute_setup(e: dict, spy: dict, sector_stats: dict, eurusd) -> dict:
    sector = e.get("sector", "Unknown")
    sstat = sector_stats.get(sector) or {}
    flags = bulltrap_flags(e)
    levels = compute_levels(e, eurusd)

    teil = {
        "kapitalfluss": _score_kapitalfluss(e),
        "relative_staerke": _score_rs(e, spy or {}, sstat),
        "trendkontext": _score_trend(e),
        "sektorstaerke": float(sstat.get("score", 50)),
        "setup": _score_setup(e, flags),
        "optionsflow": _score_options(e),
        "crv": _clip((levels.get("crv_am_aktuellen_kurs", 1.0) - 1.0) * 100) if levels.get("available") else 50.0,
    }
    score = round(sum(SCORE_WEIGHTS[k] * v for k, v in teil.items()), 1)

    # Harte Ausschluesse (nicht verhandelbar). News-Ausschluss setzt Claude.
    ausschluesse = []
    ed = e.get("earnings") or {}
    if _num(ed.get("handelstage_bis")) and 0 <= ed["handelstage_bis"] <= EARNINGS_BLOCK_TRADING_DAYS:
        ausschluesse.append(f"Earnings in {ed['handelstage_bis']} Handelstagen ({ed.get('datum')})")
    if (e.get("options_flow") or {}).get("einschaetzung") == "bearisch":
        ausschluesse.append("Optionsflow bärisch")
    if _num(e.get("avg_volume_20d")) and e["avg_volume_20d"] < MIN_AVG_VOLUME:
        ausschluesse.append("Ø-Volumen unter 1 Mio. Aktien")

    hinweise = []
    if sector in SEMI_SECTORS and (sstat.get("rs_5d_vs_spy") or 0) < 0:
        hinweise.append("Halbleiter-Sektor schwächer als S&P 500 (nur für Halbleiter relevant)")
    if not ed.get("available"):
        hinweise.append("Earnings-Termin nicht verfügbar – manuell prüfen")

    if ausschluesse:
        stufe = "Ausgeschlossen"
    elif len(flags) >= 2:
        stufe = "Überdehnt – auf Rücksetzer warten"
    elif score >= SCORE_KAUF_HOCH:
        stufe = "Kauf – hohe Qualität"
    elif score >= SCORE_KAUF:
        stufe = "Kauf – solide"
    elif score >= SCORE_BEOBACHTEN:
        stufe = "Beobachten"
    else:
        stufe = "Kein Setup"

    return {
        "score": score,
        "teilscores": {k: round(v, 0) for k, v in teil.items()},
        "stufe": stufe,
        "bulltrap_flags": flags,
        "ausschluesse": ausschluesse,
        "hinweise": hinweise,
        "levels": levels,
        "wiedereinstieg_usd": round(e["sma20"], 2) if _num(e.get("sma20")) else None,
    }


# ---------------------------------------------------------------------------
# News-Signale (seit 11.10.2026): die Nachrichten-Aufgaben N1-N6/Sa/So
# schreiben data/news_signals.json. Hier wird daraus deterministisch ein
# Korrektur-Vorschlag (max. +/-10) und ggf. ein harter News-Ausschluss.
# ---------------------------------------------------------------------------
NEWS_GEWICHT = {"hoch": 5, "mittel": 3, "niedrig": 1}
NEWS_KORREKTUR_TAGE = 3        # Kalendertage, die in die Score-Korrektur eingehen
NEWS_AUSSCHLUSS_TAGE = 14      # Fenster fuer harte negative News
NEWS_AUSSCHLUSS_KATEGORIEN = {"Gewinnwarnung", "Verfahren", "Bilanz"}
# Seit 18.10.2026: nur firmenspezifische Meldungen zaehlen voll. Branchen-
# meldungen hoechstens +/-1, allgemeine Markt-/Makronachrichten gar nicht
# (die stecken schon im Kursverlauf und damit im Score).
NEWS_FIRMA_KATEGORIEN = {"Gewinnwarnung", "Verfahren", "Bilanz", "Übernahme", "Earnings",
                         "Analyst", "Auftrag/Produkt", "Management"}


def news_bewertung(signale: list, heute) -> dict:
    """Fasst die News-Signale je Ticker zusammen."""
    from datetime import date as _date

    out = {}
    gesehen = set()
    for s in signale or []:
        t = str(s.get("ticker") or "").upper()
        if not t:
            continue
        schluessel = (t, (s.get("url") or "").strip() or str(s.get("titel") or "").strip().lower()[:80])
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        try:
            d = _date.fromisoformat(str(s.get("datum") or "")[:10])
        except ValueError:
            continue
        alter = (heute - d).days
        if alter < 0 or alter > NEWS_AUSSCHLUSS_TAGE:
            continue
        e = out.setdefault(t, {"positiv": 0, "negativ": 0, "neutral": 0, "punkte": 0,
                               "ausschluss": None, "signale": []})
        richtung = str(s.get("einschaetzung") or "neutral").lower()
        kat = str(s.get("kategorie") or "Sonstiges")
        if kat not in NEWS_FIRMA_KATEGORIEN and kat != "Sektor":
            continue  # Markt-/Makronachricht: nur Schlagzeilen, kein Signal je Aktie
        if alter <= NEWS_KORREKTUR_TAGE:
            e[richtung if richtung in ("positiv", "negativ") else "neutral"] += 1
            g = NEWS_GEWICHT.get(str(s.get("gewicht") or "mittel").lower(), 3)
            if kat == "Sektor":
                g = min(g, 1)
            e["punkte"] += g if richtung == "positiv" else -g if richtung == "negativ" else 0
        if (kat in NEWS_AUSSCHLUSS_KATEGORIEN and richtung == "negativ") or kat == "Übernahme":
            e["ausschluss"] = e["ausschluss"] or f"News: {kat} ({d.isoformat()}) – {s.get('titel', '')}"[:160]
        e["signale"].append({k: s.get(k) for k in ("datum", "published_at", "titel", "quelle", "url",
                                                    "einschaetzung", "gewicht", "kategorie")})
    for e in out.values():
        e["korrektur_vorschlag"] = int(max(-10, min(10, e.pop("punkte"))))
        e["signale"].sort(key=lambda x: str(x.get("published_at") or x.get("datum") or ""), reverse=True)
        e["signale"] = e["signale"][:5]
    return out


# ---------------------------------------------------------------------------
# P5.5 - Institutional Hold Test aus 5-Minuten-Kerzen
# ---------------------------------------------------------------------------

def compute_hold_test(bars_today: list[dict], bars_prev_days: list[list[dict]], spy_chg_since_open) -> dict:
    """bars_*: Listen von {open, high, low, close, volume} in zeitlicher
    Reihenfolge. bars_prev_days: je vorherigem Handelstag eine Liste.
    Fehlende Daten -> status "Neutral" (nicht negativ werten)."""
    if not bars_today:
        return {"available": False, "status": "Neutral", "grund": "Keine Intraday-Daten verfügbar"}

    day_open = bars_today[0]["open"]
    last = bars_today[-1]["close"]
    vol_sum = sum(b["volume"] for b in bars_today)
    if vol_sum > 0:
        vwap = sum((b["high"] + b["low"] + b["close"]) / 3 * b["volume"] for b in bars_today) / vol_sum
    else:
        vwap = None

    n = len(bars_today)
    prev_cum = [sum(b["volume"] for b in day[:n]) for day in bars_prev_days if len(day) >= n]
    rel_vol = round(vol_sum / mean(prev_cum), 2) if prev_cum and mean(prev_cum) > 0 else None

    chg_open = (last - day_open) / day_open * 100 if day_open else None
    rs = round(chg_open - spy_chg_since_open, 2) if _num(chg_open) and _num(spy_chg_since_open) else None

    checks = {
        "ueber_vwap": bool(last > vwap) if vwap else None,
        "ueber_eroeffnung": bool(last > day_open),
        "staerker_als_sp500": bool(rs > 0) if rs is not None else None,
        "volumen_ueber_schnitt": bool(rel_vol >= 1.0) if rel_vol is not None else None,
    }
    known = [v for v in checks.values() if v is not None]
    passed = sum(1 for v in known if v)
    if len(known) < 3:
        status = "Neutral"
    elif passed == len(known) == 4:
        status = "Bestanden"
    elif passed >= 2:
        status = "Teilweise"
    else:
        status = "Nicht bestanden"

    return {
        "available": True,
        "status": status,
        "kriterien_erfuellt": passed,
        "kriterien_bewertbar": len(known),
        "checks": checks,
        "eroeffnung": round(day_open, 2),
        "letzter_kurs": round(last, 2),
        "vwap": round(vwap, 2) if vwap else None,
        "chg_seit_eroeffnung_pct": round(chg_open, 2) if _num(chg_open) else None,
        "rs_vs_sp500_seit_eroeffnung": rs,
        "relatives_volumen": rel_vol,
        "kerzen": n,
    }
