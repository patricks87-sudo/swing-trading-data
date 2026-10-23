SETUP-DOKU: MARKTDATEN-FEED (GITHUB ACTIONS)
Stand: 18.10.2026 (Rohstoff-Monitor mit eigener Rohstoff-Ampel, Gold/Silber-Empfehlung und Simulation; Bestandspositionen im Journal, News ohne Dubletten, Ampel je Lauf; davor 11.10.2026: Risikobudget, 10-Tage-Ausstieg, Trade-Journal, News-Signale).

ÜBERBLICK
Repository: github.com/patricks87-sudo/swing-trading-data (public, Branch main)
Cockpit: https://patricks87-sudo.github.io/swing-trading-data/ (Umzug auf eigene Domain mit Login und privatem Repo: docs/CLOUDFLARE.md)
Zweck: An jedem US-Handelstag holt ein GitHub-Actions-Workflow viermal Marktdaten (Watchlist + Indizes) von der Twelve Data API, ergänzt kostenlose Zusatzdaten über yfinance (echter VIX, US-10J-Rendite, Earnings-Termine, Optionsflow, 5-Minuten-Kerzen) und berechnet daraus deterministisch in Python Marktregime, Sektor-Ranking, Score, Handelsmarken und den P5.5-Hold-Test. Ergebnis: data/{run}_latest.json. Claude (geplante Aufgaben P4/P5/P5.5/P1) liest diese Datei, prüft News und schreibt die Ergebnisdateien für das Cockpit.

Grundprinzip seit 11.10.2026: Alles, was sich aus Daten berechnen lässt, rechnet Python – reproduzierbar und von Tag zu Tag vergleichbar. Claude übernimmt diese Werte und darf den Score nur wegen News um höchstens ±10 Punkte korrigieren (mit Begründung).

DATEIEN IM REPO
- fetch_market_data.py – Hauptskript: Datenabruf (Twelve Data + yfinance), Indikatoren, Breadth, Ampel, JSON-Export; ruft analysis.py auf; beim P1-Lauf zusätzlich scripts/update_tracking.py
- analysis.py – deterministische Bewertung: compute_sector_stats(), compute_regime(), compute_setup() (Score, Stufe, Bulltrap-Flags, harte Ausschlüsse, ATR-Levels), compute_hold_test() (P5.5). Alle Parameter zentral oben in der Datei.
- scripts/update_tracking.py – Forward-Performance aller Tracking-Einträge vs. Nasdaq-100 (QQQ) und Filter-Bilanz; ruft danach scripts/performance.py auf
- scripts/performance.py – Depot-Simulation in EUR (8.000 € Start, aktuelle Regeln) vs. „alle Kandidaten 10 Tage gehalten“, Nasdaq-100 (QQQ) und MSCI World (URTH) → data/performance.json
- scripts/journal.py – Trade-Journal: verarbeitet Einträge aus dem Cockpit (data/journal.json) und leitet data/portfolio.json ab; bewertet offene Positionen bei jedem Feed-Lauf mit den aktuellen Kursen neu
- scripts/determine_run.py – wählt bei Cron-Ticks den fälligen Lauf (p4/p5/p55/p1) nach Uhrzeit Europe/Berlin, mit Dedupe
- prompts/P4.md, P5.md, P5_5.md, P1.md, N.md – verbindliche Analyse-Prompts (seit 11.10.2026 im Repo statt als Projektdateien; die geplanten Aufgaben laden sie live)
- prompts/PROJEKT_ANWEISUNGEN.md – Kopie der Projekt-Anweisungen (inkl. RÜCKKANAL-Formate)
- docs/SETUP.md – diese Doku
- index.html – Cockpit „Aktienkänguru“ (GitHub Pages bzw. hinter dem Cloudflare Worker; lädt Daten je nach Umgebung von raw.githubusercontent.com oder /data/)
- worker/worker.js – Cloudflare Worker: liefert index.html und data/*.json aus dem (privaten) Repo, nur mit gültigem Cloudflare-Access-Login
- docs/CLOUDFLARE.md – Anleitung Domain, Login, privates Repo
- site/ – Entwurf der öffentlichen Startseite (noch nicht veröffentlicht; Impressum, Datenschutz und Risikohinweis vorher rechtlich prüfen)
- rohstoffe.py – Rohstoff-Monitor: Kennzahlen Gold/Silber/Kupfer/Öl/GDX/Dollar, Rohstoff-Ampel, Gold/Silber-Empfehlung, Rückblick und Trade-Simulation (yfinance); wird von fetch_market_data.py bei jedem Lauf aufgerufen
- requirements.txt – requests, pandas, yfinance>=0.2.40
- .github/workflows/journal.yml – Trade-Journal: startet bei jedem neuen Issue mit Titel „[Trade] …“ des Repo-Inhabers, speichert den Eintrag, kommentiert das Ergebnis und schließt das Issue
- .github/workflows/fetch_market_data.yml – Workflow (Cron + manueller Trigger); installiert requirements.txt; holt vor dem Push mit "git pull --rebase" den neuesten Stand (seit 11.10.2026, verhindert abgelehnte Pushes, wenn parallel geschrieben wurde)
- data/ – Feed-Snapshots ({run}_latest.json, {run}_{timestamp}.json) und Ergebnisdateien der Claude-Läufe; seit 18.10.2026 zusätzlich rohstoffe.json (Rohstoff-Seite), rohstoff_ampel_verlauf.json (Ampelstatus je Lauf) und rohstoff_meldungen.json (Rohstoff-/Zentralbank-Meldungen der N-Aufgaben, 60 Tage)

SECRET
TWELVEDATA_API_KEY – unter Settings → Secrets and variables → Actions. yfinance braucht keinen Key.

ABLAUF EINES HANDELSTAGS (MESZ; Winterzeit ab Ende Oktober eine Stunde früher)
Jede geplante Claude-Aufgabe startet zuerst per workflow_dispatch den passenden Feed-Lauf, wartet auf dessen Ende und lädt dann ihren Prompt aus prompts/.
- P4 ~14:50 – Kandidatensuche (vor US-Eröffnung, Tageskerzen = Vortagesschluss). Schreibt p4_candidates.json, market_barometer.json.
- P5 ~15:30 – Eröffnungs-Info ohne Veto. Schreibt market_barometer.json.
- P5.5 ~17:05 – Hold-Test aus echten 5-Minuten-Kerzen, entscheidet nur über den Einstiegszeitpunkt. Schreibt p55_candidates.json, market_barometer.json.
- P1 ~17:35 – Portfolio-Entscheidung. Der Feed-Lauf aktualisiert vorher candidate_tracking.json (Kursfelder) und filter_bilanz.json. Schreibt top_empfehlung.json, candidate_tracking.json, portfolio_bewertung.json, market_barometer.json.
- N1–N6 (werktags 08:00/10:30/13:00/16:15/18:30/21:00) und N-Sa/N-So (18:00) – Prompt prompts/N.md (v2.2; Teil C seit 18.10.2026: Rohstoff- und Zentralbank-Meldungen → rohstoff_meldungen.json, max. 1 Suche, bei N1/N-So 2): Tagesüberblick news_summary_today.json mit „lage“ und Meldungen ohne Dubletten (jede Meldung nur einmal am Tag), Top-3 in headlines.json, und News-Signale nur zu firmenspezifischen Meldungen für Depot und Kandidaten (news_signals.json, max. 6 Suchen). Seitdem suchen P4–P1 keine Schlagzeilen mehr selbst (spart Rechenzeit).
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

ROHSTOFF-MONITOR (rohstoffe.py, seit 18.10.2026, Cockpit-Registerkarte „Rohstoffe“)
Bei jedem Feed-Lauf über yfinance (belastet Twelve Data nicht): Gold (GC=F), Silber (SI=F), Kupfer (HG=F), Rohöl WTI (CL=F), Goldminen-ETF GDX, US-Dollar-Index (DX-Y.NYB), Referenz SPY, je 3 Jahre Tagesdaten. Je Wert: 5/20/60-Tage-Veränderung, Trend (Kurs/SMA50/SMA200), relative Stärke zum S&P 500 (20 Tage), Korrelation der Tagesrenditen zum S&P 500 (60 Tage), Abstand zum 52-Wochen-Hoch, Signal Rückenwind/Neutral/Gegenwind und eine Antizyklik-Statistik: in wie vielen Wochen mit S&P 500 ≤ −1 % der Rohstoff gestiegen ist (Quote und Durchschnitt). Aktienlage „schwach“, wenn S&P 500 auf 20 Tage im Minus oder die drei führenden Sektoren (nach RS 20 Tage) auf 5 Tage im Schnitt ≤ −2 %. Rotationsstatus: „Rotation in Edelmetalle“ (Gold oder Silber 20 Tage im Plus, ≥ 3 Prozentpunkte besser als S&P 500, über SMA50 – UND Aktienlage schwach), „Edelmetalle stark“ (ohne Aktienschwäche), „Aktien schwach, keine Rotation“, „Keine Rotation“. Ausgabe im Feed unter „rohstoffe“ und in data/rohstoffe.json. Ändert keine Aktien-Scores.
ROHSTOFF-AMPEL (rohstoffe.ampel, seit 18.10.2026): nur für Gold/Silber, gilt NICHT für Aktien (Minenaktien wurden am 18.10.2026 wieder aus der Watchlist genommen). Sechs Kriterien: Gold über SMA50; Gold-SMA50 über SMA200; Silber über SMA50; GDX über SMA50; Gold 20 Tage mindestens so stark wie S&P 500; US-Dollar-Index unter SMA50. 5–6 = GRÜN, 3–4 = GELB, 0–2 = ROT. Gold unter SMA200 → höchstens GELB; Rotationsstatus „Rotation in Edelmetalle“ hebt GELB auf GRÜN (außer Gold unter SMA200).
HANDLUNGSEMPFEHLUNG GOLD & SILBER (rohstoffe.empfehlung): nur Hinweis, kein System-Trade, kein Journal, UNGEHEBELT (Hebelprodukte am 18.10.2026 verworfen: Rendite-Vorsprung zu klein für das verdoppelte Verlustrisiko). Kaufen: Ampel GRÜN + Metall über SMA50 + 20 Tage mindestens so stark wie S&P 500. Halten (kein Neukauf): Ampel GELB oder Metall selbst schwach. Nicht investieren/verkaufen: Ampel ROT oder Stop unterschritten. Stop-Orientierung = 3 × mittlere Tagesbewegung (20 Tage) unter Kaufkurs. Produkte: Xetra-Gold DE000A0S9GB0, WisdomTree Physical Silver JE00B1VS3333 (Handelbarkeit bei Trade Republic vor Kauf prüfen). Ampel-Wechsel gegenüber dem vorigen Lauf wird hervorgehoben; Verlauf in data/rohstoff_ampel_verlauf.json (letzte 400 Läufe).
RÜCKBLICK (rohstoffe.ampel_bilanz): Ampel für jeden Handelstag der letzten ~2 Jahre (3 Jahre Daten, 200 Tage Vorlauf), Ø-Entwicklung Gold/Silber 10 Handelstage danach je Status (ohne Stop). TRADE-SIMULATION (rohstoffe.simulation): die Empfehlungsregel echt durchgespielt – Einstieg Schlusskurs am Tag nach dem Kaufsignal, Ausstieg bei Schlusskurs unter Stop oder am Tag nach Wechsel auf ROT; je Metall Trades, Trefferquote, Ø, bester/schlechtester Trade, Gesamtergebnis, Vergleich mit Kaufen-und-Halten, Anteil investierter Tage. Ohne Gebühren/Steuern, ohne Rotations-Aufwertung.
Meldungen zu Zentralbank-Käufen, ETF-Strömen, Angebot/Nachfrage sammeln die Nachrichten-Aufgaben (N.md Teil C) 60 Tage lang in data/rohstoff_meldungen.json.

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
close, rsi14, obv, obv_trend_5d, obv_trend_20d, atr14, atr_pct, atr_pct_avg60, sma20/50/200, pct_from_sma20/50, chg_1d/5d/20d/60d_pct, sma200_trend, pct_above_sma200_10d, avg_volume_20d, last_volume, volume_ratio, volume_ratio_basis, high_20d, sector, options_flow, earnings, ampel, setup, news.
ampel (deterministisch): kapitalfluss (OBV-5T und Volumen), trendkontext (SMA200-Trend, 60-Tage-Performance, 10 Tage über SMA200), optionsflow – jeweils gruen/gelb/rot/unbekannt.

MARKTREGIME (analysis.compute_regime – einzige gültige Definition für alle Prompts)
Fünf Kriterien: S&P 500 über SMA50; Nasdaq über SMA20; VIX unter 20; ≥50 % der Watchlist über SMA50; ≥50 % der Watchlist im 5-Tage-Plus.
4–5 erfüllt = RISK-ON (max. 2 neue Positionen pro Tag, max. 5 offen), 2–3 = NEUTRAL (max. 1 neue, max. 3 offen), 0–1 = RISK-OFF (keine neuen). Unabhängig davon RISK-OFF bei VIX > 30 oder S&P 500 unter SMA200. Fehlende Daten zählen nicht als verletzt. SOX ist kein Regime-Kriterium mehr.

SEKTOREN (analysis.compute_sector_stats)
Durchschnittliche 5- und 20-Tage-Performance je Sektor, relative Stärke zum S&P 500, Rang (60 % RS 20 Tage + 40 % RS 5 Tage), Trend positiv/neutral/negativ.

SCORE UND STUFEN (analysis.compute_setup)
Score 0–100: Kapitalfluss 20 %, relative Stärke (vs. S&P 500 und Sektor) 20 %, Trendkontext 15 %, Sektorstärke 15 %, Setup-Qualität 15 % (Abstand zu SMA20/50, minus 25 Punkte je Bulltrap-Flag), Optionsflow 10 %, CRV am aktuellen Kurs 5 %.
Stufen: ≥75 "Kauf – hohe Qualität", 65–74 "Kauf – solide", 50–64 "Beobachten", <50 "Kein Setup". Bei 2+ Bulltrap-Flags: "Überdehnt – auf Rücksetzer warten".
Bulltrap-Flags: Abstand SMA20 > 8 %, Abstand SMA50 > 15 %, RSI14 > 72, +15 % in 5 Tagen, ATR > 2× 60-Tage-Schnitt, Kurs steigt bei fallendem OBV.
Harte Ausschlüsse (Stufe "Ausgeschlossen"): Earnings in ≤5 Handelstagen, Optionsflow bärisch, Ø-Volumen < 1 Mio. Aktien, harte negative News aus news_signals.json (Gewinnwarnung/Verfahren/Bilanz negativ oder Übernahmeziel, 14 Tage).
NEWS-SIGNALE (analysis.news_bewertung): Signale der letzten 3 Tage ergeben einen Korrektur-Vorschlag (hoch ±5, mittel ±3, niedrig ±1, max. ±10) im Feld watchlist.{T}.news; P4 übernimmt ihn als score_korrektur. Seit 18.10.2026 zählen nur firmenspezifische Kategorien voll, „Sektor“ höchstens ±1, Markt-/Makromeldungen gar nicht (sie stecken schon im Kurs); doppelte Signale werden ignoriert.
Abgeschafft am 11.10.2026: Mindestschwellen Flow ≥85 / Gesamtscore ≥88, institutioneller Marktfilter als Veto, SOX als Bedingung für Nicht-Halbleiter, CRV-Minimum 2,5:1, festes Kursziel 5–10 %.

HANDELSMARKEN (analysis.compute_levels)
Einstieg = aktueller Kurs, wenn höchstens 3 % über SMA20, sonst Limit an SMA20. Schutz-Stop = Einstieg − 2 × ATR. Verkauf spätestens nach 10 Handelstagen zum Schlusskurs; keine Kursziele, kein Teilverkauf, kein Nachkauf (seit 11.10.2026 – die Auswertung seit August zeigte, dass 10 Tage halten besser abschnitt als Ziele und enge Stops). Stückzahl = 75 € Risiko ÷ (Einstieg − Stop), max. 2.500 € Kapital. Alle Werte in USD und EUR.

RISIKOBUDGET (statt früher 2 fester Plätze, Parameter oben in analysis.py)
Depot 8.000 €, 75 € Risiko je Trade, Gesamtrisiko aller offenen Positionen max. 375 €, max. 2.500 € je Position, offen max. 5 (RISK-ON) / 3 (NEUTRAL), neue pro Tag 2 / 1 / 0, max. 2 Positionen je Sektor.

P5.5-HOLD-TEST (analysis.compute_hold_test)
Vier Checks aus 5-Minuten-Kerzen der laufenden Sitzung: Kurs über VWAP, Kurs über Eröffnung, seit Eröffnung stärker als SPY, kumuliertes Volumen über dem Schnitt der Vortage zur gleichen Uhrzeit. 4/4 = Bestanden, 2–3 = Teilweise, 0–1 = Nicht bestanden, weniger als 3 bewertbar = Neutral. Ergebnis steuert in P1 nur den Einstiegszeitpunkt (heute zum Kurs / Limit / nicht heute).

KANDIDATEN-TRACKING UND FILTER-BILANZ (scripts/update_tracking.py, beim P1-Lauf)
Für alle Einträge in candidate_tracking.json – auch aussortierte – rechnet das Skript in USD: referenz_kurs_usd (Schluss vor Aufnahmetag), aktueller Kurs, performance_pct, nasdaq_performance_pct, ueberrendite_pct, forward (5/10/20 Handelstage nach Aufnahme, jeweils vs. Nasdaq), handelstage_seit_aufnahme, status_gruppe. Claude pflegt nur Status, Empfehlung, Einschätzung und Neuaufnahmen.
Status: aktiv, überdehnt (bleibt mit Wiedereinstieg an SMA20 auf der Liste), ausgeschieden (these widerlegt), ausgeschieden (zeitlimit), getradet. Empfehlungen für Kandidaten: Kauf / Beobachten / Kein Einstieg ("Halten"/"Verkauf" nur für echte Depotpositionen).
filter_bilanz.json fasst die Überrendite je Statusgruppe zusammen. Erste Auswertung (11.10.2026, Daten seit August): wegen Überdehnung/Invalidierung aussortierte Kandidaten lagen 10 Tage nach Aufnahme im Schnitt +4,6 Prozentpunkte über dem Nasdaq (n=19), per Zeitlimit aussortierte −2,2 Prozentpunkte (n=9).

TRADE-JOURNAL (seit 11.10.2026)
Eingabe im Cockpit (Registerkarte "Journal"): Formular → öffnet ein vorausgefülltes GitHub-Issue „[Trade] …“ mit JSON-Block → Patrick klickt „Create“ → journal.yml ruft scripts/journal.py auf → data/journal.json (alle Einträge, IDs T0001 …) und data/portfolio.json (offene Positionen mit Einstand, Stop, Handelstagen, Verkaufsdatum, unrealisiertem Ergebnis) → Kommentar und Issue geschlossen. Storno per Knopf in der Eintragsliste, Verkauf per Knopf „Verkauf eintragen“ an der Position (bei 0 Stück verschwindet sie). Testeinträge werden gespeichert, zählen aber nicht. Seit 18.10.2026 Feld „art“: swing (Systemtrade, 10-Tage-Regel, Risikobudget) oder bestand (unabhängig vom System gehalten: keine 10-Tage-Regel, nicht im Risikobudget, getrennte Kennzahlen, P1 gibt „Halten“ oder „Prüfen“). Kurse für Titel außerhalb der Watchlist (z. B. SAP.DE) holt der nächste Feed-Lauf über yfinance (USD-Kurse in EUR umgerechnet). Durchschnittskosten-Methode, Gebühr Standard 1 €. P1 liest portfolio.json und empfiehlt je Position Halten oder Verkaufen (Stop, 10 Tage, harte News).

COCKPIT (index.html)
Design seit 19.10.2026: „Aktienkänguru“ (Terrakotta/Sand, hell und dunkel nach Systemeinstellung, Umschalter oben rechts, Schriften Bricolage Grotesque/Plus Jakarta Sans). Begriffe bewusst neutral, keine Kaufaufforderungen in der Anzeige: Marktlage „Rückenwind / Gemischt / Abwarten“ (RISK-ON/NEUTRAL/RISK-OFF klein daneben), Stufen „Setup stark / Setup solide“ statt „Kauf – …“ (nur Anzeige, die Werte im Feed bleiben unverändert), Titel im eigenen Depot sind in der Watchlist mit „Im Depot“ markiert.
Registerkarte "Heute": Begrüßung mit Claudes Kurzkommentar (nur wenn er zum aktuellen Feed passt) und optional „Meine Notiz“ aus data/notiz.json ({"text": "...", "updated_at_utc": "..."}; fehlt die Datei, bleibt der Kasten ausgeblendet). Oben drei Karten: Marktlage (Status aus dem neuesten Feed-Lauf, fünf Kriterien im Klartext mit Abstand in %, erlaubte neue/offene Positionen, darunter Kurzzeile zur Rohstoff-Ampel), Mein Trade heute (erster Eintrag aus top_empfehlung.json mit Handelsmarken aus p4_candidates.json; ist er nicht vom Tag des Feeds, steht „Stand <Datum>“ daneben) und Mein Depot (portfolio.json). Darunter Kennzahlen (Depot-Simulation vs. Nasdaq-100/MSCI World, Trefferquote, Ø Ergebnis je Trade, VIX), Watchlist als Tabelle (Zeile anklicken für Begründung, Handelsmarken, Flags, News), Seitenleiste mit Märkten und Sektoren (Stärke vs. S&P 500, 20 Tage), dann „Markt heute“ (seit 23.10.2026 ein Block statt Top-3 + „Was den Markt bewegt“: Lage, alle Meldungen neueste zuerst, jede nur einmal – doppelt heißt gleicher Inhalt, nicht gleiche URL; die drei wichtigsten mit „Top 1–3“ markiert, Feld "top" bzw. Abgleich mit headlines.json; Meldungen älter als 24 Std. eingeklappt; ohne bekannte Uhrzeit nur das Datum, auch bei alten Ersatzwerten 12:00/00:00), News zu Watchlist & Depot, P5.5-Hold-Test und aktive Kandidaten.
Registerkarte "Performance" (vorher „Historie & Performance“): Performance-Grafik (Depot-Simulation in EUR vs. alle Kandidaten/QQQ/URTH), Filter-Bilanz und alle aussortierten/getradeten Kandidaten mit Performance seit Aufnahme und Forward-Performance vs. Nasdaq.
Registerkarte "Rohstoffe" (seit 18.10.2026): Rohstoff-Ampel mit sechs Kriterien (jeweils tatsächlicher Abstand in %), Rotationsstatus, Handlungsempfehlung Gold & Silber (ungehebelt, nur Hinweis; Ampelwechsel farbig hervorgehoben), Simulation der Regel mit Trade-Liste, Rückblick je Ampelstatus, Rohstoff-Karten, 6-Monats-Chart, Antizyklik-Tabelle, Meldungen. Auf „Heute“ steht unter der Haupt-Ampel eine Kurzzeile zur Rohstoff-Ampel. Aktualisierung: Kennzahlen/Ampel/Empfehlung/Simulation bei jedem Feed-Lauf (werktags P4 ~14:50, P5 ~15:30, P5.5 ~17:05, P1 ~17:35; reine Python-Rechnung, die Prompts lesen sie nur mit), Meldungen bei jeder N-Aufgabe. Wochenende/US-Feiertage: Stand des letzten Handelstags. Auch die Haupt-Ampel zeigt ihre fünf Kriterien jetzt als Klartext mit Abstand in %.
Registerkarte "Journal": Eingabeformular, offene Positionen mit unrealisiertem Ergebnis und Verkaufsdatum, abgeschlossene Trades, alle Einträge mit Storno.

BEKANNTE FEHLER UND FIXES (Historie)
1) 404 bei echten Indizes im Free-Plan → ETF-Proxies.
2) 429 Rate Limit → 8 s Pause je Abruf.
3) Risk-Off strukturell zu empfindlich (VIXY-Contango, fehlende Breadth als "nicht erfüllt" gewertet) → 20.09.2026: Watchlist 16→50, breadth-Berechnung. Der geplante Wechsel auf den echten VIX scheiterte damals am Free Tier (404), VIXM wurde als Ersatz eingesetzt.
4) Zu eindimensional auf OBV-Kapitalfluss → 27.09.2026: langfristiger Trendkontext.
5) Optionsflow nur qualitativ → 27.09.2026: yfinance + Ampel. Workflow installierte yfinance zunächst nicht (pip install requests pandas) → von Patrick am 04.10.2026 auf requirements.txt umgestellt.
6) System lieferte fast nie einen Trade (Filterkaskade, P5.5 mangels Intraday-Daten nie bestehbar, SOX mehrfach gezählt, CRV-Minimum unvereinbar mit festem 7,5-%-Ziel, drei unterschiedliche Regime-Definitionen, VIXM-Kurs als "VIX") → 11.10.2026: Umbau Filterlogik (analysis.py, echter VIX über yfinance, Earnings, Intraday-Hold-Test, ATR-Levels, Forward-Tracking, Prompts ins Repo, Cockpit-Umbau).
7) Workflow-Push wurde abgelehnt, wenn parallel ins Repo geschrieben wurde → 11.10.2026: "git pull --rebase" vor "git push".
8) Zwei feste Plätze und Ziel-/Stop-Ausstiege ließen Rendite liegen (alte Regeln +10,2 %, alle Kandidaten 10 Tage gehalten +14,1 %, QQQ +3,9 % seit 12.08.2026) → 11.10.2026: Risikobudget, Schutz-Stop 2× ATR, Ausstieg nach 10 Handelstagen.

BEKANNTE EINSCHRÄNKUNGEN
- breadth ist eine Näherung auf Basis der 50-Ticker-Watchlist.
- yfinance ist inoffiziell; Ausfälle erscheinen als "unbekannt"/"Datenbasis unvollständig".
- Keine Fundamentaldaten oder Short Interest im Feed; Analysten- und Unternehmensnachrichten nur über die News-Signale der N-Aufgaben.
- Das Journal läuft über öffentliche GitHub-Issues (Repo ist öffentlich).
- Score-Schwellen (75/65/50) sind ein erster Wurf und sollen nach 2–3 Wochen anhand der Filter-Bilanz nachjustiert werden.
