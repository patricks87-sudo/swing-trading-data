#!/usr/bin/env python3
"""
fetch_market_data.py
---------------------
Laeuft in GitHub Actions (Cloud, kein eigenes Geraet noetig), gesteuert
durch scripts/determine_run.py, mehrmals taeglich. Holt OHLCV-Daten ueber
die kostenlose Twelve Data API, berechnet RSI/OBV/ATR/DMA selbst (keine
kostenpflichtigen Indikator-Endpunkte noetig) und schreibt das Ergebnis
als JSON in den Ordner data/. Der GitHub-Actions-Workflow committet und
pusht die Datei anschliessend automatisch.
Claude liest die Datei danach zeitgesteuert ueber die GitHub-API und
wendet P4 / P5 / P5.5 / P1 darauf an.
API-Key kommt aus der Umgebungsvariable TWELVEDATA_API_KEY
(in GitHub Actions als Repository-Secret hinterlegt, siehe README.md).
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# KONFIGURATION - hier anpassen
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("TWELVEDATA_API_KEY", "")
BASE_URL = "https://api.twelvedata.com"

# Watchlist: die Ticker, die P4 als Kandidaten pruefen soll.
# Erweitert (20.09.2026) von 18 auf 50 Werte, damit alle 19 Projekt-Sektoren
# abgedeckt sind - vorher waren z.B. Financials, Insurance, Energy, Utilities,
# Infrastructure, Materials, Consumer Discretionary und Transportation gar
# nicht vertreten, wodurch Sektorrotation in diese Bereiche unsichtbar blieb.
# Dient seit dem Umbau (20.09.2026) zusaetzlich als Stichprobe fuer die
# Markt-Breadth-Berechnung (siehe compute_breadth) - je breiter, desto
# repraesentativer. Erweitere/kuerze je nach Free-Tier-Budget
# (8 Calls/Min, 800/Tag - 50 Watchlist + 5 Indizes = 55 Calls/Lauf, bei 4-6
# Laeufen/Tag ca. 220-330 Calls/Tag, klar unter dem Limit).
WATCHLIST = [
    # Semiconductors/AI
    "NVDA", "AMD", "AVGO", "TSM", "ASML", "MRVL", "SMCI", "QCOM",
    # Software/Cloud
    "MSFT", "CRM", "NOW", "ORCL", "ADBE", "SNOW", "PLTR",
    # Cybersecurity
    "PANW", "CRWD", "ZS", "FTNT",
    # Defense
    "LMT", "NOC", "RTX", "GD",
    # Financials
    "JPM", "GS", "MS",
    # Insurance
    "PGR", "TRV",
    # Payments / Fintech-Brokerage
    "V", "MA", "HOOD", "COIN",
    # Healthcare / MedTech
    "UNH", "ISRG", "TMO",
    # Energy
    "XOM", "CVX",
    # Utilities
    "NEE", "DUK",
    # Industrials / Infrastructure
    "CAT", "DE", "URI",
    # Materials
    "LIN", "FCX",
    # Consumer Discretionary
    "AMZN", "HD", "TSLA",
    # Transportation
    "UNP", "UPS",
    # Technology
    "AAPL",
]

# Statische Sektor-Zuordnung je Ticker - Grundlage fuer das
# Sektorrotations-Barometer im Cockpit (index.html). Rein informativ,
# beeinflusst die Kursdaten nicht.
SECTOR_MAP = {
    "NVDA": "Semiconductors/AI",
    "AMD": "Semiconductors/AI",
    "AVGO": "Semiconductors/AI",
    "TSM": "Semiconductors/AI",
    "ASML": "Semiconductors/AI",
    "MRVL": "Semiconductors/AI",
    "SMCI": "Semiconductors/AI",
    "QCOM": "Semiconductors/AI",
    "MSFT": "Software/Cloud",
    "CRM": "Software/Cloud",
    "NOW": "Software/Cloud",
    "ORCL": "Software/Cloud",
    "ADBE": "Software/Cloud",
    "SNOW": "Software/Cloud",
    "PLTR": "Software/Cloud",
    "PANW": "Cybersecurity",
    "CRWD": "Cybersecurity",
    "ZS": "Cybersecurity",
    "FTNT": "Cybersecurity",
    "LMT": "Defense",
    "NOC": "Defense",
    "RTX": "Defense/Industrials",
    "GD": "Defense",
    "JPM": "Financials",
    "GS": "Financials",
    "MS": "Financials",
    "PGR": "Insurance",
    "TRV": "Insurance",
    "V": "Payments",
    "MA": "Payments",
    "HOOD": "Fintech/Brokerage",
    "COIN": "Fintech/Brokerage",
    "UNH": "Healthcare",
    "ISRG": "MedTech",
    "TMO": "MedTech",
    "XOM": "Energy",
    "CVX": "Energy",
    "NEE": "Utilities",
    "DUK": "Utilities",
    "CAT": "Industrials",
    "DE": "Industrials",
    "URI": "Industrials/Infrastructure",
    "LIN": "Materials",
    "FCX": "Materials",
    "AMZN": "Consumer Discretionary",
    "HD": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary",
    "UNP": "Transportation",
    "UPS": "Transportation",
    "AAPL": "Technology",
}

# Marktbreite / Indizes (Twelve Data Symbole - vor Produktivbetrieb einmal
# manuell gegen die Twelve-Data-Doku pruefen, da Symbol-Verfuegbarkeit sich
# je nach Tarif unterscheiden kann)
INDEX_SYMBOLS = {
    "NASDAQ_COMPOSITE": "QQQ",
    "SP500": "SPY",
    "RUSSELL2000": "IWM",
    # Bis 19.09.2026 VIXY (ETF-Proxy) - durch Rollverluste/Contango bei
    # gehaltenen VIX-Futures strukturell zu hohe Werte, was die Risk-Off-
    # Ampel zu empfindlich gemacht hat. Seit 20.09.2026: echter CBOE-VIX-
    # Index direkt (kein Rollverlust, da aus Optionspreisen berechnet statt
    # aus gehaltenen Futures-Kontrakten). Falls "VIX" im Twelve-Data-
    # Free-Tier nicht verfuegbar sein sollte (Fehler/leere Werte im
    # naechsten Lauf pruefen): Fallback auf "VIXM" (mittelfristige
    # VIX-Futures-ETN, deutlich weniger Rollverlust als VIXY).
    "VIX": "VIX",
    # SOX (Philadelphia Semiconductor Index) ist auf dem Free-Tier evtl. nicht
    # direkt verfuegbar - SOXX (ETF) dient hier als Naeherungswert.
    "SOX_PROXY": "SOXX",
}

EURUSD_URL = "https://api.exchangerate-api.com/v4/latest/USD"

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# ---------------------------------------------------------------------------
# Datenabruf
# ---------------------------------------------------------------------------

def fetch_time_series(symbol: str, interval: str = "1day", outputsize: int = 260):
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": API_KEY,
    }
    # Retry mit exponentiellem Backoff bei 429 (Rate Limit). Dadurch fangen
    # wir kurzfristige Ueberlastungen ab (z.B. wenn ein verspaeteter Cron-Lauf
    # doch einmal mit einem anderen Lauf ueberlappt), statt den ganzen Job
    # sofort abzubrechen.
    max_retries = 4
    backoff_seconds = 15
    for attempt in range(max_retries + 1):
        r = requests.get(f"{BASE_URL}/time_series", params=params, timeout=20)
        if r.status_code == 429 and attempt < max_retries:
            print(f"429 fuer {symbol}, Versuch {attempt + 1}/{max_retries + 1} - warte {backoff_seconds}s")
            time.sleep(backoff_seconds)
            backoff_seconds *= 2
            continue
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "error":
            return {"error": data.get("message", "unknown error")}
        return data.get("values", [])


def fetch_eurusd():
    try:
        r = requests.get(EURUSD_URL, timeout=10)
        r.raise_for_status()
        return r.json()["rates"]["EUR"]
    except Exception as e:
        return {"error": str(e)}

# ---------------------------------------------------------------------------
# Indikatoren selbst berechnen
# ---------------------------------------------------------------------------

def compute_indicators(values):
    import pandas as pd

    if not values or isinstance(values, dict):
        return {"error": "no data"}

    df = pd.DataFrame(values)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df = df.iloc[::-1].reset_index(drop=True)  # aelteste zuerst

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["rsi14"] = 100 - (100 / (1 + rs))

    direction = df["close"].diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    df["obv"] = (direction * df["volume"]).cumsum()

    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["atr14"] = tr.rolling(14).mean()

    df["sma20"] = df["close"].rolling(20).mean()
    df["sma50"] = df["close"].rolling(50).mean()
    df["sma200"] = df["close"].rolling(200).mean() if len(df) >= 200 else None

    last = df.iloc[-1]
    close = last["close"]

    def pct_from(sma):
        if sma is None or pd.isna(sma):
            return None
        return round((close - sma) / sma * 100, 2)

    chg_5d = None
    if len(df) >= 6:
        chg_5d = round((close - df["close"].iloc[-6]) / df["close"].iloc[-6] * 100, 2)

    # 1-Tages-Veraenderung - seit 20.09.2026 zusaetzlich zu chg_5d_pct, wird
    # fuer die watchlist-basierte Advance/Decline-Berechnung gebraucht
    # (siehe compute_breadth).
    chg_1d = None
    if len(df) >= 2:
        prev = df["close"].iloc[-2]
        if prev:
            chg_1d = round((close - prev) / prev * 100, 2)

    return {
        "close": round(close, 4),
        "rsi14": round(last["rsi14"], 2) if pd.notna(last["rsi14"]) else None,
        "obv": round(last["obv"], 0),
        "obv_trend_5d": round(df["obv"].iloc[-1] - df["obv"].iloc[-6], 0) if len(df) >= 6 else None,
        "atr14": round(last["atr14"], 4) if pd.notna(last["atr14"]) else None,
        "sma20": round(last["sma20"], 4) if pd.notna(last["sma20"]) else None,
        "sma50": round(last["sma50"], 4) if pd.notna(last["sma50"]) else None,
        "sma200": round(last["sma200"], 4) if last["sma200"] is not None and pd.notna(last["sma200"]) else None,
        "pct_from_sma20": pct_from(last["sma20"]),
        "pct_from_sma50": pct_from(last["sma50"]),
        "chg_5d_pct": chg_5d,
        "chg_1d_pct": chg_1d,
        "avg_volume_20d": round(df["volume"].tail(20).mean(), 0),
        "last_volume": round(df["volume"].iloc[-1], 0),
    }


def compute_breadth(watchlist: dict) -> dict:
    """Markt-Breadth-Kennzahlen, seit 20.09.2026 aus der (jetzt 50 Werte
    grossen) Watchlist selbst berechnet. Ersetzt die im Feed strukturell
    fehlende NYSE Advance/Decline-Linie und "% Aktien ueber 50 DMA" (siehe
    Wissensdokument, Abschnitt "Bekannte Datenluecken") durch echte, aus den
    tatsaechlich abgerufenen Kursdaten berechnete Werte, statt sie per
    Websuche zu schaetzen oder stillschweigend als "nicht erfuellt" zu
    werten - genau das hatte die Risk-Off-Ampel zuvor strukturell zu
    empfindlich gemacht.
    """
    entries = [v for v in watchlist.values() if isinstance(v, dict) and "error" not in v]

    with_sma50 = [e for e in entries if isinstance(e.get("close"), (int, float)) and isinstance(e.get("sma50"), (int, float))]
    above_sma50 = [e for e in with_sma50 if e["close"] > e["sma50"]]

    with_chg1d = [e for e in entries if isinstance(e.get("chg_1d_pct"), (int, float))]
    advancers = [e for e in with_chg1d if e["chg_1d_pct"] > 0]
    decliners = [e for e in with_chg1d if e["chg_1d_pct"] < 0]

    if decliners:
        ad_ratio = round(len(advancers) / len(decliners), 2)
    elif advancers:
        ad_ratio = float(len(advancers))  # keine Verlierer -> sehr breit positiv
    else:
        ad_ratio = None

    return {
        "pct_above_sma50": round(len(above_sma50) / len(with_sma50) * 100, 1) if with_sma50 else None,
        "advance_decline_ratio": ad_ratio,
        "advancers": len(advancers),
        "decliners": len(decliners),
        "sample_size": len(entries),
    }


# ---------------------------------------------------------------------------
# Hauptlogik
# ---------------------------------------------------------------------------

def build_snapshot(run_label: str):
    snapshot = {
        "run": run_label,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "eurusd": fetch_eurusd(),
        "indices": {},
        "watchlist": {},
    }

    for name, symbol in INDEX_SYMBOLS.items():
        vals = fetch_time_series(symbol, outputsize=260)
        time.sleep(8)
        snapshot["indices"][name] = compute_indicators(vals) if isinstance(vals, list) else vals

    for ticker in WATCHLIST:
        vals = fetch_time_series(ticker, outputsize=260)
        time.sleep(8)
        result = compute_indicators(vals) if isinstance(vals, list) else vals
        if isinstance(result, dict) and "error" not in result:
            result["sector"] = SECTOR_MAP.get(ticker, "Unknown")
        snapshot["watchlist"][ticker] = result

    snapshot["breadth"] = compute_breadth(snapshot["watchlist"])

    return snapshot


def snapshot_is_healthy(snapshot: dict) -> bool:
    """Circuit Breaker gegen stille Fehl-Laeufe (Ursache 1): ein frueherer
    Bug hat dazu gefuehrt, dass fetch_time_series() bei jedem Aufruf None
    zurueckgab, obwohl GitHub Actions den Lauf als 'erfolgreich' meldete -
    alle Werte im Cockpit blieben leer. Diese Funktion prueft, ob ein
    Mindestanteil der Indizes/Watchlist-Eintraege echte Kurswerte enthaelt,
    BEVOR das Ergebnis gespeichert und committet wird."""
    entries = list(snapshot.get("indices", {}).values()) + list(snapshot.get("watchlist", {}).values())
    if not entries:
        return False
    healthy = sum(1 for e in entries if isinstance(e, dict) and isinstance(e.get("close"), (int, float)))
    return (healthy / len(entries)) >= 0.5


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, choices=["p4", "p5", "p55", "p1"])
    args = parser.parse_args()

    if not API_KEY:
        print("FEHLER: TWELVEDATA_API_KEY ist nicht gesetzt.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    snapshot = build_snapshot(args.run)

    if not snapshot_is_healthy(snapshot):
        print(
            "FEHLER: Ueberwiegend fehlende Kursdaten im Snapshot - wird NICHT "
            "gespeichert/committet (Circuit Breaker gegen stille Fehl-Laeufe).",
            file=sys.stderr,
        )
        sys.exit(1)

    filename = f"{args.run}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w") as f:
        json.dump(snapshot, f, indent=2)

    latest_path = os.path.join(OUTPUT_DIR, f"{args.run}_latest.json")
    with open(latest_path, "w") as f:
        json.dump(snapshot, f, indent=2)

    print(f"Geschrieben: {filepath}")


if __name__ == "__main__":
    main()
