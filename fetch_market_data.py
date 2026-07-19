#!/usr/bin/env python3
"""
fetch_market_data.py
---------------------
Läuft in GitHub Actions (Cloud, kein eigenes Gerät nötig) zu 4 festen Zeitpunkten
täglich. Holt OHLCV-Daten über die kostenlose Twelve Data API, berechnet
RSI/OBV/ATR/DMA selbst (keine kostenpflichtigen Indikator-Endpunkte nötig)
und schreibt das Ergebnis als JSON in den Ordner data/. Der GitHub-Actions-
Workflow committet und pusht die Datei anschließend automatisch.

Claude liest die Datei danach zeitgesteuert über die GitHub-API und wendet
P4 / P5 / P5.5 / P1 darauf an.

API-Key kommt aus der Umgebungsvariable TWELVEDATA_API_KEY
(in GitHub Actions als Repository-Secret hinterlegt, siehe README.md).
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# KONFIGURATION - hier anpassen
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("TWELVEDATA_API_KEY", "")
BASE_URL = "https://api.twelvedata.com"

# Watchlist: die Ticker, die P4 als Kandidaten prüfen soll.
# Erweitere/kürze diese Liste je nach Free-Tier-Budget (8 Calls/Min, 800/Tag).
WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "AMD", "AVGO", "CRM", "PANW", "NOW",
    "LMT", "NOC", "RTX", "UNH", "ISRG", "V", "MA", "CAT",
]

# Marktbreite / Indizes (Twelve Data Symbole - vor Produktivbetrieb einmal
# manuell gegen die Twelve-Data-Doku prüfen, da Symbol-Verfügbarkeit sich
# je nach Tarif unterscheiden kann)
INDEX_SYMBOLS = {
    "NASDAQ_COMPOSITE": "QQQ",
    "SP500": "SPY",
    "RUSSELL2000": "IWM",
    "VIX": "VIXY",
    # SOX (Philadelphia Semiconductor Index) ist auf dem Free-Tier evtl. nicht
    # direkt verfügbar - SOXX (ETF) dient hier als Näherungswert.
    "SOX_PROXY": "SOXX",
}

EURUSD_URL = "https://api.frankfurter.app/latest?from=USD&to=EUR"

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
    r = requests.get(f"{BASE_URL}/time_series", params=params, timeout=20)
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
    df = df.iloc[::-1].reset_index(drop=True)  # älteste zuerst

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

    return {
        "close": round(close, 4),
        "rsi14": round(last["rsi14"], 2) if pd.notna(last["rsi14"]) else None,
        "obv": round(last["obv"], 0),
        "obv_trend_5d": ("steigend" if df["obv"].iloc[-1] > df["obv"].iloc[-6] else "fallend") if len(df) >= 6 else None,
        "atr14": round(last["atr14"], 4) if pd.notna(last["atr14"]) else None,
        "sma20": round(last["sma20"], 4) if pd.notna(last["sma20"]) else None,
        "sma50": round(last["sma50"], 4) if pd.notna(last["sma50"]) else None,
        "sma200": round(last["sma200"], 4) if last["sma200"] is not None and pd.notna(last["sma200"]) else None,
        "pct_from_sma20": pct_from(last["sma20"]),
        "pct_from_sma50": pct_from(last["sma50"]),
        "chg_5d_pct": chg_5d,
        "avg_volume_20d": round(df["volume"].tail(20).mean(), 0),
        "last_volume": round(df["volume"].iloc[-1], 0),
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
        snapshot["indices"][name] = compute_indicators(vals) if isinstance(vals, list) else vals

    for ticker in WATCHLIST:
        vals = fetch_time_series(ticker, outputsize=260)
        snapshot["watchlist"][ticker] = compute_indicators(vals) if isinstance(vals, list) else vals

    return snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, choices=["p4", "p5", "p55", "p1"])
    args = parser.parse_args()

    if not API_KEY:
        print("FEHLER: TWELVEDATA_API_KEY ist nicht gesetzt.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    snapshot = build_snapshot(args.run)

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
