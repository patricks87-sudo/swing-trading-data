"""
journal.py
----------
Trade-Journal (eingefuehrt 11.10.2026).

Eingabe: Der Nutzer fuellt im Cockpit (Registerkarte "Journal") ein Formular
aus. Das Cockpit oeffnet daraus ein vorausgefuelltes GitHub-Issue mit dem
Titel "[Trade] ..." und einem JSON-Block. Der Workflow
.github/workflows/journal.yml ruft dann dieses Skript auf:

    python scripts/journal.py --issue      (liest ISSUE_TITLE/ISSUE_BODY/ISSUE_NUMBER)
    python scripts/journal.py --bewerten   (nur Kurse/Depot neu bewerten)

Ergebnis:
  data/journal.json   - alle Eintraege (Kauf, Verkauf, Storno) + abgeleitete
                        Positionen, abgeschlossene Trades und Kennzahlen
  data/portfolio.json - offene Positionen im bisherigen Format (P1 liest sie)

Antwort fuer den Issue-Kommentar steht in /tmp/journal_antwort.md, der Status
(ok|fehler) in /tmp/journal_status.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
JOURNAL = os.path.join(DATA_DIR, "journal.json")
PORTFOLIO = os.path.join(DATA_DIR, "portfolio.json")
ANTWORT = "/tmp/journal_antwort.md"
STATUS = "/tmp/journal_status"

HALTEDAUER_TAGE = 10
AKTIONEN = {"kauf", "verkauf", "storno"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return default


def _save(path, doc):
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip().replace(".", "").replace(",", ".") if "," in str(v) else str(v).strip())
    except ValueError:
        return None


def _handelstage(von: date, bis: date) -> int:
    """Handelstage (Mo-Fr, ohne Feiertage) nach 'von' bis einschliesslich 'bis'."""
    n, d = 0, von
    while d < bis:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def _plus_handelstage(von: date, n: int) -> date:
    d = von
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


# --------------------------------------------------------------------------
# Aktuelle Kurse aus dem juengsten Feed (keine Netzabfrage noetig)
# --------------------------------------------------------------------------
def aktueller_feed():
    best, best_ts = None, ""
    for f in glob.glob(os.path.join(DATA_DIR, "p*_latest.json")):
        doc = _load(f, None)
        if doc and str(doc.get("generated_at_utc", "")) > best_ts:
            best, best_ts = doc, str(doc.get("generated_at_utc", ""))
    return best


def kurse_eur(feed):
    out = {}
    if not feed:
        return out, None, {}
    fx = feed.get("eurusd")
    namen = {}
    for datei, feld in (("candidate_tracking.json", "kandidaten"), ("p4_candidates.json", "candidates")):
        for k in (_load(os.path.join(DATA_DIR, datei), {}) or {}).get(feld, []) or []:
            if k.get("ticker") and k.get("name"):
                namen[k["ticker"]] = k["name"]
    for t, w in (feed.get("watchlist") or {}).items():
        c = w.get("close")
        if isinstance(c, (int, float)) and isinstance(fx, (int, float)):
            out[t] = round(c * fx, 2)
    return out, feed.get("generated_at_utc"), namen


# --------------------------------------------------------------------------
# Eingabe pruefen
# --------------------------------------------------------------------------
def parse_issue(title, body):
    m = re.search(r"\{.*\}", body or "", re.S)
    if not m:
        raise ValueError("Kein Daten-Block im Issue gefunden. Bitte das Formular im Cockpit verwenden.")
    try:
        roh = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"Daten-Block ist kein gültiges JSON ({e.msg}).")
    return roh


def pruefe(roh, journal, namen):
    aktion = str(roh.get("aktion", "")).strip().lower()
    if aktion not in AKTIONEN:
        raise ValueError("Aktion muss Kauf, Verkauf oder Storno sein.")
    e = {"aktion": aktion, "test": bool(roh.get("test"))}
    if aktion == "storno":
        ref = str(roh.get("ref", "")).strip().upper()
        ziel = next((x for x in journal["eintraege"] if x["id"] == ref), None)
        if not ziel:
            raise ValueError(f"Eintrag {ref or '(leer)'} nicht gefunden.")
        if ziel.get("storniert"):
            raise ValueError(f"Eintrag {ref} ist bereits storniert.")
        e["ref"] = ref
        e["notiz"] = str(roh.get("notiz", ""))[:500]
        return e

    ticker = str(roh.get("ticker", "")).strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", ticker):
        raise ValueError("Ticker fehlt oder ist ungültig (z. B. NVDA).")
    stueck = _num(roh.get("stueck"))
    kurs = _num(roh.get("kurs_eur"))
    if not stueck or stueck <= 0:
        raise ValueError("Stückzahl muss größer als 0 sein.")
    if not kurs or kurs <= 0:
        raise ValueError("Kurs in EUR muss größer als 0 sein.")
    try:
        datum = date.fromisoformat(str(roh.get("datum") or date.today().isoformat()))
    except ValueError:
        raise ValueError("Datum ungültig (Format JJJJ-MM-TT).")
    if datum > date.today() + timedelta(days=1):
        raise ValueError("Datum liegt in der Zukunft.")
    gebuehr = _num(roh.get("gebuehr_eur"))
    stop = _num(roh.get("stop_eur"))
    e.update({
        "datum": datum.isoformat(),
        "ticker": ticker,
        "name": (str(roh.get("name") or "").strip() or namen.get(ticker) or ticker)[:80],
        "stueck": stueck,
        "kurs_eur": round(kurs, 4),
        "gebuehr_eur": round(gebuehr if gebuehr is not None else 1.0, 2),
        "grund": str(roh.get("grund", "")).strip()[:120],
        "notiz": str(roh.get("notiz", "")).strip()[:1000],
    })
    if stop and stop > 0:
        if aktion == "kauf" and stop >= kurs:
            raise ValueError("Schutz-Stop muss unter dem Kaufkurs liegen.")
        e["stop_eur"] = round(stop, 2)
    if aktion == "verkauf" and not e["test"]:
        bestand = ableiten(journal["eintraege"])[0].get(ticker, {}).get("stueck", 0)
        if stueck > bestand + 1e-9:
            raise ValueError(f"Verkauf von {stueck:g} Stück, im Journal sind aber nur {bestand:g} Stück {ticker} offen.")
    return e


# --------------------------------------------------------------------------
# Positionen und abgeschlossene Trades ableiten (Durchschnittskosten)
# --------------------------------------------------------------------------
def ableiten(eintraege):
    aktive = [x for x in eintraege if x["aktion"] in ("kauf", "verkauf") and not x.get("storniert") and not x.get("test")]
    aktive.sort(key=lambda x: (x["datum"], x["id"]))
    pos, trades = {}, []
    for x in aktive:
        t = x["ticker"]
        p = pos.get(t)
        if x["aktion"] == "kauf":
            if not p:
                p = pos[t] = {"ticker": t, "name": x.get("name", t), "stueck": 0.0, "kosten_eur": 0.0,
                              "kaufdatum": x["datum"], "gebuehren_eur": 0.0, "realisiert_eur": 0.0,
                              "kaeufe": [], "grund": x.get("grund", ""), "stueck_max": 0.0, "einsatz_eur": 0.0}
            p["stueck"] += x["stueck"]
            p["kosten_eur"] += x["stueck"] * x["kurs_eur"] + x["gebuehr_eur"]
            p["gebuehren_eur"] += x["gebuehr_eur"]
            p["einsatz_eur"] += x["stueck"] * x["kurs_eur"] + x["gebuehr_eur"]
            p["stueck_max"] = max(p["stueck_max"], p["stueck"])
            p["kaeufe"].append(x["id"])
            if x.get("stop_eur"):
                p["stop_eur"] = x["stop_eur"]
            p["name"] = x.get("name") or p["name"]
        else:
            if not p or p["stueck"] <= 0:
                continue
            menge = min(x["stueck"], p["stueck"])
            ek = p["kosten_eur"] / p["stueck"]
            erloes = menge * x["kurs_eur"] - x["gebuehr_eur"]
            ergebnis = erloes - menge * ek
            p["realisiert_eur"] += ergebnis
            p["gebuehren_eur"] += x["gebuehr_eur"]
            p["kosten_eur"] -= menge * ek
            p["stueck"] -= menge
            if p["stueck"] <= 1e-9:
                einsatz = p["realisiert_eur"]
                trades.append({
                    "ticker": t, "name": p["name"], "kaufdatum": p["kaufdatum"], "verkaufsdatum": x["datum"],
                    "handelstage": _handelstage(date.fromisoformat(p["kaufdatum"]), date.fromisoformat(x["datum"])),
                    "stueck": round(p["stueck_max"], 4),
                    "ergebnis_eur": round(einsatz, 2),
                    "rendite_pct": round(einsatz / p["einsatz_eur"] * 100, 2) if p["einsatz_eur"] else None,
                    "gebuehren_eur": round(p["gebuehren_eur"], 2),
                    "grund_kauf": p.get("grund", ""), "grund_verkauf": x.get("grund", ""),
                })
                del pos[t]
    return pos, trades


def bewerten(journal):
    feed = aktueller_feed()
    kurse, stand, _ = kurse_eur(feed)
    pos, trades = ableiten(journal["eintraege"])
    heute = date.today()
    positionen = []
    for t, p in sorted(pos.items(), key=lambda kv: kv[1]["kaufdatum"]):
        ek = p["kosten_eur"] / p["stueck"]
        kauf = date.fromisoformat(p["kaufdatum"])
        q = {
            "id": f"{t}-{p['kaufdatum']}",
            "ticker": t, "name": p["name"],
            "stueck": round(p["stueck"], 4),
            "einstand_eur": round(ek, 4),
            "kapital_eur": round(p["kosten_eur"], 2),
            "kaufdatum": p["kaufdatum"],
            "handelstage_gehalten": _handelstage(kauf, heute),
            "verkauf_spaetestens": _plus_handelstage(kauf, HALTEDAUER_TAGE).isoformat(),
            "stop_eur": p.get("stop_eur"),
            "grund": p.get("grund", ""),
            "teilrealisiert_eur": round(p["realisiert_eur"], 2),
            "journal_ids": p["kaeufe"],
        }
        k = kurse.get(t)
        if k is not None:
            q["aktueller_kurs_eur"] = k
            q["wert_eur"] = round(k * p["stueck"], 2)
            q["unrealisiert_eur"] = round(k * p["stueck"] - p["kosten_eur"], 2)
            q["unrealisiert_pct"] = round((k / ek - 1) * 100, 2) if ek else None
            if q.get("stop_eur") and k <= q["stop_eur"]:
                q["hinweis"] = "Stop unterschritten"
        if q["handelstage_gehalten"] >= HALTEDAUER_TAGE:
            q["hinweis"] = (q.get("hinweis", "") + " · " if q.get("hinweis") else "") + "10-Tage-Regel: verkaufen"
        positionen.append(q)

    realisiert = sum(tr["ergebnis_eur"] for tr in trades) + sum(p["realisiert_eur"] for p in pos.values())
    unreal = [q["unrealisiert_eur"] for q in positionen if q.get("unrealisiert_eur") is not None]
    gewinner = [tr for tr in trades if tr["ergebnis_eur"] > 0]
    journal["positionen"] = positionen
    journal["trades"] = sorted(trades, key=lambda tr: tr["verkaufsdatum"], reverse=True)
    journal["kennzahlen"] = {
        "realisiert_eur": round(realisiert, 2),
        "unrealisiert_eur": round(sum(unreal), 2) if unreal else 0.0,
        "gebuehren_eur": round(sum(x.get("gebuehr_eur", 0) for x in journal["eintraege"]
                                   if x["aktion"] in ("kauf", "verkauf") and not x.get("storniert") and not x.get("test")), 2),
        "trades_abgeschlossen": len(trades),
        "trefferquote_pct": round(len(gewinner) / len(trades) * 100) if trades else None,
        "schnitt_trade_eur": round(sum(tr["ergebnis_eur"] for tr in trades) / len(trades), 2) if trades else None,
        "offene_positionen": len(positionen),
        "investiert_eur": round(sum(q["kapital_eur"] for q in positionen), 2),
    }
    journal["kurse_stand_utc"] = stand
    journal["generated_at_utc"] = _now()

    portfolio = {
        "updated_at_utc": _now(),
        "quelle": "automatisch aus data/journal.json (Trade-Journal im Cockpit)",
        "kurse_stand_utc": stand,
        "positions": positionen,
    }
    return journal, portfolio


def neu_journal():
    return {"generated_at_utc": _now(), "waehrung": "EUR", "eintraege": [], "positionen": [], "trades": [], "kennzahlen": {}}


def naechste_id(journal):
    n = 0
    for x in journal["eintraege"]:
        m = re.fullmatch(r"T(\d+)", x.get("id", ""))
        if m:
            n = max(n, int(m.group(1)))
    return f"T{n + 1:04d}"


def verarbeite_issue():
    title = os.environ.get("ISSUE_TITLE", "")
    body = os.environ.get("ISSUE_BODY", "")
    nummer = os.environ.get("ISSUE_NUMBER")
    journal = _load(JOURNAL, None) or neu_journal()
    _, _, namen = kurse_eur(aktueller_feed())
    try:
        e = pruefe(parse_issue(title, body), journal, namen)
    except ValueError as err:
        _antwort("fehler", f"**Nicht gespeichert:** {err}\n\nBitte im Cockpit korrigieren und neu absenden.")
        return 0

    e["id"] = naechste_id(journal)
    e["erfasst_utc"] = _now()
    if nummer:
        e["issue"] = int(nummer)
    if e["aktion"] == "storno":
        for x in journal["eintraege"]:
            if x["id"] == e["ref"]:
                x["storniert"] = True
                x["storniert_durch"] = e["id"]
    journal["eintraege"].append(e)
    journal, portfolio = bewerten(journal)
    _save(JOURNAL, journal)
    _save(PORTFOLIO, portfolio)

    if e["aktion"] == "storno":
        text = f"Eintrag **{e['ref']}** storniert (Storno-Nr. {e['id']})."
    else:
        wort = "Kauf" if e["aktion"] == "kauf" else "Verkauf"
        text = (f"{wort} gespeichert als **{e['id']}**: {e['stueck']:g} × {e['name']} ({e['ticker']}) "
                f"zu {e['kurs_eur']:.2f} € am {e['datum']}, Gebühr {e['gebuehr_eur']:.2f} €.")
        if e.get("test"):
            text += "\n\n_Testeintrag – zählt nicht für Depot und Kennzahlen._"
    k = journal["kennzahlen"]
    text += (f"\n\nDepot laut Journal: {k['offene_positionen']} offene Position(en), "
             f"realisiert {k['realisiert_eur']:+.2f} €, unrealisiert {k['unrealisiert_eur']:+.2f} €.")
    _antwort("ok", text)
    return 0


def _antwort(status, text):
    with open(ANTWORT, "w") as fh:
        fh.write(text + "\n")
    with open(STATUS, "w") as fh:
        fh.write(status)
    print(f"[{status}] {text}")


def nur_bewerten():
    journal = _load(JOURNAL, None)
    if not journal:
        return
    journal, portfolio = bewerten(journal)
    _save(JOURNAL, journal)
    _save(PORTFOLIO, portfolio)


if __name__ == "__main__":
    if "--issue" in sys.argv:
        sys.exit(verarbeite_issue())
    nur_bewerten()
