SETUP-DOKU: MARKTDATEN-FEED (GITHUB ACTIONS)
Stand: 11.10.2026 (Umbau Filterlogik). Ersetzt die Fassung vom 27.09.2026.

ÜBERBLICK
Repository: github.com/patricks87-sudo/swing-trading-data (public, Branch main)
Cockpit: https://patricks87-sudo.github.io/swing-trading-data/
Zweck: An jedem US-Handelstag holt ein GitHub-Actions-Workflow viermal Marktdaten (Watchlist + Indizes) von der Twelve Data API, ergänzt kostenlose Zusatzdaten über yfinance (echter VIX, US-10J-Rendite, Earnings-Termine, Optionsflow, 5-Minuten-Kerzen) und berechnet daraus deterministisch in Python Marktregime, Sektor-Ranking, Score, Handelsmarken und den P5.5-Hold-Test. Ergebnis: data/{run}_latest.json. Claude (geplante Aufgaben P4/P5/P5.5/P1) liest diese Datei, prüft News und schreibt die Ergebnisdateien für das Cockpit.

Grundprinzip seit 11.10.2026: Alles, was sich aus Daten berechnen lässt, rechnet Python – reproduzierbar und von Tag zu Tag vergleichbar. Claude übernimmt diese Werte und darf den Score nur wegen News um höchstens ±10 Punkte korrigieren (mit Begründung).

DATEIEN IM REPO
- fetch_market_data.py – Hauptskript: Datenabruf (Twelve Data + yfinance), Indikatoren, Breadth, Ampel, JSON-Export; ruft analysis.py auf; beim P1-Lauf zusätzlich scripts/update_tracking.py
- analysis.py – deterministische Bewertung: compute_sector_stats(), compute_regime(), compute_setup() (Score, Stufe, Bulltrap-Flags, harte Ausschlüsse, ATR-Levels), compute_hold_test() (P5.5). Alle Parameter zentral oben in der Datei.
- scripts/update_tracking.py – Forward-Performance aller Tracking-Einträge vs. Nasdaq-100 (QQQ) und Filter-Bilanz
- scripts/determine_run.py – wählt bei Cron-Ticks den fälligen Lauf (p4/p5/p55/p1) nach Uhrzeit Europe/Berlin, mit Dedupe
- prompts/P4.md, P5.md, P5_5.md, P1.md – verbindliche Analyse-Prompts (seit 11.10.2026 im Repo statt als Projektdateien; die geplanten Aufgaben laden sie live)
- prompts/PROJEKT_ANWEISUNGEN.md – Kopie der Projekt-Anweisungen (inkl. RÜCKKANAL-Formate)
- docs/SETUP.md – diese Doku
- index.html – Cockpit (GitHub Pages)
- requirements.txt – requests, pandas, yfinance>=0.2.40
- .github/workflows/fetch_market_data.yml – Workflow (Cron + manueller Trigger); installiert requirements.txt; holt vor dem Push mit "git pull --rebase" den neuesten Stand (seit 11.10.2026, verhindert abgelehnte Pushes, wenn parallel geschrieben wurde)
- data/ – Feed-Snapshots ({run}_latest.json, {run}_{timestamp}.json) und Ergebnisdateien der Claude-Läufe

SECRET
TWELVEDATA_API_KEY – unter Settings → Secrets and variables → Actions. yfinance braucht keinen Key.

ABLAUF EINES HANDELSTAGS (MESZ; Winterzeit ab Ende Oktober eine Stunde früher)
Jede geplante Claude-Aufgabe startet zuerst per workflow_dispatch den passenden Feed-Lauf, wartet auf dessen Ende und lädt dann ihren Prompt aus prompts/.
- P4 ~14:50 – Kandidatensuche (vor US-Eröffnung, Tageskerzen = Vortagesschluss). Schreibt p4_candidates.json, market_barometer.json, headlines.json.
- P5 ~15:30 – Eröffnungs-Info ohne Veto. Schreibt market_barometer.json, headlines.json.
- P5.5 ~17:05 – Hold-Test aus echten 5-Minuten-Kerzen, entscheidet nur über den Einstiegszeitpunkt. Schreibt p55_candidates.json, market_barometer.json, headlines.json.
- P1 ~17:35 – Portfolio-Entscheidung. Der Feed-Lauf aktualisiert vorher candidate_tracking.json (Kursfelder) und filter_bilanz.json. Schreibt top_empfehlung.json, candidate_tracking.json, portfolio_bewertung.json, market_barometer.json, headlines.json.
- N1–N6 (werktags 08:00/10:30/13:00/16:15/18:30/21:00) und N-Sa/N-So (18:00) – nur Schlagzeilen (headlines.json, news_summary_today.json).
Zusätzlich läuft der Workflow per Cron alle 5 Minuten zwischen 12:00 und 16:59 UTC; determine_run.py holt verpasste Läufe nach und verhindert Doppelläufe.
Manueller Testlauf: Actions → "Fetch Market Data" → "Run workflow" → run = p4/p5/p55/p1. An Handelstagen nicht vor ~14:45 MESZ manuell starten (Dedupe würde den regulären P4-Lauf blockieren).

WATCHLIST (50 Werte, 19 Sektoren)
Semiconductors/AI: NVIDIA, AMD (Advanced Micro Devices), Broadcom, Taiwan Semiconductor, ASML Holding, Marvell Technology, Super Micro Computer, Qualcomm
Software/Cloud: Microsoft, Salesforce, ServiceNow, Oracle, Adobe, Snowflake, Palantir Technologies
Cybersecurity: Palo Alto Networks, CrowdStrike, Zscaler, Fortinet
Defense: Lockheed Martin, Northrop Grumman, General Dynamics; Defense/Industrials: RTX Corporation
Financials: JPMorgan Chase, Goldman Sachs, Morgan Stanley
Insurance: Progressive, Travelers
Payments: Visa, Mastercard; Fintech/Brokerage: Robinhood, Coinbase
Healthcare: UnitedHealth Group; MedTech: Intuitive Surgical, Thermo Fisher Scientific
Energy: ExxonMobil, Chevron; Utilities: NextEra Energy, Duke Energy
Industrials: Caterpillar, Deere & Company; Industrials/Infrastructure: United Rentals
Materials: Linde, Freeport-McMoRan
Consumer Discretionary: Amazon, Home Depot, Tesla; Transportation: Union Pacific, UPS
Technology: Apple
Die Watchlist ist zugleich Stichprobe für die Marktbreite (breadth).

DATENQUELLEN
Twelve Data (Free Tier, 8 Calls/Min, 800/Tag): Tageskerzen (260 Tage) für 50 Watchlist-Werte und 4 ETF-Proxies: NASDAQ_COMPOSITE → QQQ, SP500 → SPY, RUSSELL2000 → IWM, SOX_PROXY → SOXX. 54 Calls je Lauf, Pause 8 s je Abruf, Laufzeit ca. 8–9 Minuten.
Wichtig: Während der US-Sitzung (P5/P5.5/P1) ist die letzte Tageskerze unvollständig und enthält bei Twelve Data nur einen Bruchteil des Volumens. volume_ratio wird deshalb in diesen Läufen auf Basis des Vortags berechnet (Feld volume_ratio_basis); Intraday-Volumen kommt ausschließlich aus dem Hold-Test.
yfinance (kostenlos, inoffiziell, ohne SLA – Ausfälle werden als "available": false gekennzeichnet, nie geschätzt):
- indices.VIX und macro.vix – echter CBOE-VIX (^VIX). Bis 11.10.2026 stand hier VIXM; dessen Kurs ist ein Fondspreis und kein VIX-Stand, die Regel "VIX < 18" war damit wirkungslos.
- macro.us10y – US-10J-Rendite (^TNX), nur Information, kein Regime-Kriterium
- watchlist.{T}.earnings – nächster Earnings-Termin und Handelstage bis dahin
- watchlist.{T}.options_flow – Call/Put-Volumen und Open Interest der nächsten Verfallsserie (7–56 Tage); bullisch bei Call/Put ≥1,5 und Call-Volumen/OI ≥0,15 (seit 04.10.2026, vorher 0,3), bärisch bei Call/Put ≤0,7
- hold_test (nur P5.5) – 5-Minuten-Kerzen der letzten 5 Tage für die P4-Kandidaten und SPY
- scripts/update_tracking.py – Tagesschlusskurse für Tracking-Einträge und QQQ
Der Circuit Breaker snapshot_is_healthy() prüft nur die Twelve-Data-Kursdaten; ein yfinance-Ausfall blockiert nie einen Lauf.

FELDER JE WATCHLIST-EINTRAG
close, rsi14, obv, obv_trend_5d, obv_trend_20d, atr14, atr_pct, atr_pct_avg60, sma20/50/200, pct_from_sma20/50, chg_1d/5d/20d/60d_pct, sma200_trend, pct_above_sma200_10d, avg_volume_20d, last_volume, volume_ratio, volume_ratio_basis, high_20d, sector, options_flow, earnings, ampel, setup.
ampel (deterministisch): kapitalfluss (OBV-5T und Volumen), trendkontext (SMA200-Trend, 60-Tage-Performance, 10 Tage über SMA200), optionsflow – jeweils gruen/gelb/rot/unbekannt.

MARKTREGIME (analysis.compute_regime – einzige gültige Definition für alle Prompts)
Fünf Kriterien: S&P 500 über SMA50; Nasdaq über SMA20; VIX unter 20; ≥50 % der Watchlist über SMA50; ≥50 % der Watchlist im 5-Tage-Plus.
4–5 erfüllt = RISK-ON (max. 2 neue Positionen), 2–3 = NEUTRAL (max. 1), 0–1 = RISK-OFF (0). Unabhängig davon RISK-OFF bei VIX > 30 oder S&P 500 unter SMA200. Fehlende Daten zählen nicht als verletzt. SOX ist kein Regime-Kriterium mehr.

SEKTOREN (analysis.compute_sector_stats)
Durchschnittliche 5- und 20-Tage-Performance je Sektor, relative Stärke zum S&P 500, Rang (60 % RS 20 Tage + 40 % RS 5 Tage), Trend positiv/neutral/negativ.

SCORE UND STUFEN (analysis.compute_setup)
Score 0–100: Kapitalfluss 20 %, relative Stärke (vs. S&P 500 und Sektor) 20 %, Trendkontext 15 %, Sektorstärke 15 %, Setup-Qualität 15 % (Abstand zu SMA20/50, minus 25 Punkte je Bulltrap-Flag), Optionsflow 10 %, CRV am aktuellen Kurs 5 %.
Stufen: ≥75 "Kauf – hohe Qualität", 65–74 "Kauf – solide", 50–64 "Beobachten", <50 "Kein Setup". Bei 2+ Bulltrap-Flags: "Überdehnt – auf Rücksetzer warten".
Bulltrap-Flags: Abstand SMA20 > 8 %, Abstand SMA50 > 15 %, RSI14 > 72, +15 % in 5 Tagen, ATR > 2× 60-Tage-Schnitt, Kurs steigt bei fallendem OBV.
Harte Ausschlüsse (Stufe "Ausgeschlossen"): Earnings in ≤5 Handelstagen, Optionsflow bärisch, Ø-Volumen < 1 Mio. Aktien. Negative News prüft Claude.
Abgeschafft am 11.10.2026: Mindestschwellen Flow ≥85 / Gesamtscore ≥88, institutioneller Marktfilter als Veto, SOX als Bedingung für Nicht-Halbleiter, CRV-Minimum 2,5:1, festes Kursziel 5–10 %.

HANDELSMARKEN (analysis.compute_levels)
Einstieg = aktueller Kurs, wenn höchstens 3 % über SMA20, sonst Limit an SMA20. Stop = Einstieg − 1,5 × ATR. Ziel 1 = Einstieg + 2 × Risiko (Teilverkauf, Stop auf Einstand), Ziel 2 = Einstieg + 3 × Risiko. Stückzahl = 75 € Risiko ÷ (Einstieg − Stop), max. 3.000 € Kapital. Alle Werte in USD und EUR.

P5.5-HOLD-TEST (analysis.compute_hold_test)
Vier Checks aus 5-Minuten-Kerzen der laufenden Sitzung: Kurs über VWAP, Kurs über Eröffnung, seit Eröffnung stärker als SPY, kumuliertes Volumen über dem Schnitt der Vortage zur gleichen Uhrzeit. 4/4 = Bestanden, 2–3 = Teilweise, 0–1 = Nicht bestanden, weniger als 3 bewertbar = Neutral. Ergebnis steuert in P1 nur den Einstiegszeitpunkt (heute zum Kurs / Limit / nicht heute).

KANDIDATEN-TRACKING UND FILTER-BILANZ (scripts/update_tracking.py, beim P1-Lauf)
Für alle Einträge in candidate_tracking.json – auch aussortierte – rechnet das Skript in USD: referenz_kurs_usd (Schluss vor Aufnahmetag), aktueller Kurs, performance_pct, nasdaq_performance_pct, ueberrendite_pct, forward (5/10/20 Handelstage nach Aufnahme, jeweils vs. Nasdaq), handelstage_seit_aufnahme, status_gruppe. Claude pflegt nur Status, Empfehlung, Einschätzung und Neuaufnahmen.
Status: aktiv, überdehnt (bleibt mit Wiedereinstieg an SMA20 auf der Liste), ausgeschieden (these widerlegt), ausgeschieden (zeitlimit), getradet. Empfehlungen für Kandidaten: Kauf / Beobachten / Kein Einstieg ("Halten"/"Verkauf" nur für echte Depotpositionen).
filter_bilanz.json fasst die Überrendite je Statusgruppe zusammen. Erste Auswertung (11.10.2026, Daten seit August): wegen Überdehnung/Invalidierung aussortierte Kandidaten lagen 10 Tage nach Aufnahme im Schnitt +4,6 Prozentpunkte über dem Nasdaq (n=19), per Zeitlimit aussortierte −2,2 Prozentpunkte (n=9).

COCKPIT (index.html)
Registerkarte "Heute": Schlagzeilen, Marktampel mit den fünf Regime-Kriterien, Sektorrotation, Indizes (inkl. echtem VIX und 10J-Rendite), P4-Kandidaten mit Score/Stufe/Handelsmarken, P5.5-Hold-Test, aktive Kandidaten, Top-Empfehlung.
Registerkarte "Historie & Bilanz": Filter-Bilanz und alle aussortierten/getradeten Kandidaten mit Performance seit Aufnahme und Forward-Performance vs. Nasdaq.

BEKANNTE FEHLER UND FIXES (Historie)
1) 404 bei echten Indizes im Free-Plan → ETF-Proxies.
2) 429 Rate Limit → 8 s Pause je Abruf.
3) Risk-Off strukturell zu empfindlich (VIXY-Contango, fehlende Breadth als "nicht erfüllt" gewertet) → 20.09.2026: Watchlist 16→50, breadth-Berechnung. Der geplante Wechsel auf den echten VIX scheiterte damals am Free Tier (404), VIXM wurde als Ersatz eingesetzt.
4) Zu eindimensional auf OBV-Kapitalfluss → 27.09.2026: langfristiger Trendkontext.
5) Optionsflow nur qualitativ → 27.09.2026: yfinance + Ampel. Workflow installierte yfinance zunächst nicht (pip install requests pandas) → von Patrick am 04.10.2026 auf requirements.txt umgestellt.
6) System lieferte fast nie einen Trade (Filterkaskade, P5.5 mangels Intraday-Daten nie bestehbar, SOX mehrfach gezählt, CRV-Minimum unvereinbar mit festem 7,5-%-Ziel, drei unterschiedliche Regime-Definitionen, VIXM-Kurs als "VIX") → 11.10.2026: Umbau Filterlogik (analysis.py, echter VIX über yfinance, Earnings, Intraday-Hold-Test, ATR-Levels, Forward-Tracking, Prompts ins Repo, Cockpit-Umbau).
7) Workflow-Push wurde abgelehnt, wenn parallel ins Repo geschrieben wurde → 11.10.2026: "git pull --rebase" vor "git push".

BEKANNTE EINSCHRÄNKUNGEN
- breadth ist eine Näherung auf Basis der 50-Ticker-Watchlist.
- yfinance ist inoffiziell; Ausfälle erscheinen als "unbekannt"/"Datenbasis unvollständig".
- Keine Fundamentaldaten, Analystenrevisionen oder Short Interest im Feed.
- Score-Schwellen (75/65/50) sind ein erster Wurf und sollen nach 2–3 Wochen anhand der Filter-Bilanz nachjustiert werden.
