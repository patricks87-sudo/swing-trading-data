COCKPIT (Live-Dashboard): https://patricks87-sudo.github.io/swing-trading-data/

KONTEXT (gilt für alle P4/P5/P5.5/P1-Aufgaben in diesem Projekt)
Der Nutzer betreibt hobbymäßiges Swing-Trading in US-Aktien über Trade Republic (seit dem EU-PFOF-Verbot 1.7.2026 Bestpreis-Order-Routing über ca. 30 Handelsplätze). Alle Kursangaben in EUR, umgerechnet mit dem Feld "eurusd" der JSON-Daten. Pipeline über den Handelstag: P4 (~14:50 MESZ, Kandidatensuche) → P5 (~15:30 MESZ, Eröffnungs-Info) → P5.5 (~17:05 MESZ, Hold-Test mit Intraday-Daten) → P1 (~17:35 MESZ, Portfolio-Entscheidung).

PROMPTS (seit 11.10.2026 im GitHub-Repo, nicht mehr als Projektdateien)
Die verbindlichen Kriterien jedes Schritts stehen im Repo und werden bei jedem Lauf live abgerufen:
https://raw.githubusercontent.com/patricks87-sudo/swing-trading-data/main/prompts/P4.md
https://raw.githubusercontent.com/patricks87-sudo/swing-trading-data/main/prompts/P5.md
https://raw.githubusercontent.com/patricks87-sudo/swing-trading-data/main/prompts/P5_5.md
https://raw.githubusercontent.com/patricks87-sudo/swing-trading-data/main/prompts/P1.md
https://raw.githubusercontent.com/patricks87-sudo/swing-trading-data/main/prompts/N.md (Nachrichten-Aufgaben N1–N6, N-Sa, N-So)
Wende IMMER genau den Prompt des angeforderten Schritts an.

DATENQUELLE
Repo patricks87-sudo/swing-trading-data (Branch main). Der GitHub-Actions-Workflow schreibt je Lauf data/{run}_latest.json ({run} = p4, p5, p55, p1). Abruf: https://raw.githubusercontent.com/patricks87-sudo/swing-trading-data/main/data/{run}_latest.json
Inhalt: "eurusd"; "indices" (QQQ, SPY, IWM, SOXX als ETF-Proxies; "VIX" = echter CBOE-VIX via yfinance); "macro" (VIX, US-10J-Rendite); "watchlist" (54 Werte aus 20 Sektoren inkl. „Edelmetalle“, je Eintrag Kursindikatoren, "options_flow", "earnings", "ampel", "setup" und "news"); "breadth" (ohne Edelmetalle); "sectors"; "regime"; "ranking"; "rohstoffe" (Rohstoff-Monitor: Gold, Silber, Kupfer, Öl, Goldminen, Dollar; Rotationsstatus – rein informativ); beim P5.5-Lauf zusätzlich "hold_test".

DETERMINISTISCHE BEWERTUNG (seit 11.10.2026)
Regime, Sektor-Ranking, Score (0–100), Stufe, Bulltrap-Flags, harte Ausschlüsse (Earnings ≤5 Handelstage, Optionsflow bärisch, Volumen <1 Mio.), Einstieg/Schutz-Stop/Stückzahl, die News-Korrektur (aus data/news_signals.json) und der P5.5-Hold-Test werden im Python-Skript (analysis.py) berechnet. Diese Werte übernehmen, nicht neu ableiten oder schätzen. Abweichungen von der News-Korrektur nur mit konkretem Anlass, höchstens ±10 Punkte, mit Begründung. Fehlende Daten werden gekennzeichnet ("Datenbasis unvollständig"), nie als negativ gewertet und nie erfunden.

HANDELSREGELN (seit 11.10.2026)
Risikobudget statt fester Plätze: 75 € Risiko je Trade, Schutz-Stop Einstieg − 2 × ATR, max. 2.500 € je Position, Gesamtrisiko max. 375 €, offene Positionen RISK-ON max. 5 / NEUTRAL max. 3 / RISK-OFF keine neuen, neue pro Tag 2 / 1 / 0, max. 2 Positionen je Sektor. Verkauf spätestens nach 10 Handelstagen zum Schlusskurs. Keine Kursziele, kein Teilverkauf, kein Nachkauf.

SEKTORLISTE
Technology, Semiconductors/AI, Software/Cloud, Cybersecurity, Defense, Financials, Insurance, Payments, Fintech/Brokerage, Healthcare, MedTech, Energy, Utilities, Industrials, Industrials/Infrastructure, Materials, Consumer Discretionary, Transportation (wie im Feld "sector" des Feeds).

FIRMENNAMEN
In allen Texten und im Cockpit volle Firmennamen statt Ticker (z. B. "NVIDIA" statt "NVDA", "Palo Alto Networks" statt "PANW", "AMD (Advanced Micro Devices)" statt "AMD"). Das Feld "ticker" bleibt technisch bestehen.

RÜCKKANAL (GitHub-Connector)
Ergebnisdateien immer komplett neu schreiben (nicht anhängen) in data/. Unmittelbar vor jedem Schreiben den aktuellen Stand inkl. sha abrufen; bei SHA-Konflikt bis zu 3x mit frischem Stand wiederholen.

- data/p4_candidates.json (nur P4): {"generated_at_utc": "...", "run_date": "YYYY-MM-DD", "regime": "RISK-ON|NEUTRAL|RISK-OFF", "candidates": [{"ticker": "...", "name": "...", "sector": "...", "score": 0-100, "feed_score": 0-100, "score_korrektur": 0, "stufe": "Kauf – hohe Qualität|Kauf – solide|Beobachten|Überdehnt – auf Rücksetzer warten", "ampel": {"kapitalfluss": "...", "trendkontext": "...", "optionsflow": "..."}, "levels": {"einstieg_eur": ..., "einstieg_typ": "...", "stop_eur": ..., "ausstieg": "spätestens nach 10 Handelstagen zum Schlusskurs", "stueck": ..., "kapitalbedarf_eur": ..., "risiko_eur": ...}, "news": {"positiv": 0, "negativ": 0, "wichtigste": "Titel der wichtigsten Meldung oder leer"}, "bulltrap_flags": [...], "earnings": "YYYY-MM-DD oder unbekannt", "begruendung": "max. 4 Sätze"}], "ausgeschlossen": [{"name": "...", "grund": "..."}]}
- data/p55_candidates.json (nur P5.5): {"generated_at_utc": "...", "run_date": "YYYY-MM-DD", "ergebnis": "Trade möglich|Kein Trade heute", "kurzbegruendung": "...", "kandidaten": [{"ticker": "...", "name": "...", "sector": "...", "status": "Bestanden|Teilweise|Nicht bestanden|Neutral", "checks": {"ueber_vwap": true, "ueber_eroeffnung": true, "staerker_als_sp500": true, "volumen_ueber_schnitt": true}, "vwap": ..., "relatives_volumen": ..., "einstieg_heute": "ja|limit|nein", "begruendung": "..."}]}
- data/top_empfehlung.json (nur P1): {"generated_at_utc": "...", "top3": [{"ticker": "...", "name": "...", "aktion": "Kauf zum Kurs|Limit-Order|Beobachten", "begruendung": "..."}], "gesamteinschaetzung": "...", "filter_bilanz": "Fazit-Satz aus filter_bilanz.json"}
- data/market_barometer.json (P4, P5, P5.5, P1): {"generated_at_utc": "...", "status": "<regime.status aus dem Feed>", "begruendung": "...", "kurzbegruendung": "max. ca. 150 Zeichen", "sektor_rotation": [{"sektor": "...", "trend": "positiv|neutral|negativ (aus sectors)", "kommentar": "...", "kandidaten": [{"name": "...", "empfehlung": "Kauf|Beobachten|Kein Einstieg|Halten|Verkauf"}]}]}. "Halten" und "Verkauf" nur für Titel, die im Depot (portfolio.json) liegen.
- data/headlines.json (nur noch N-Aufgaben; P4/P5/P5.5/P1 schreiben sie nicht mehr): {"generated_at_utc": "...", "headlines": [{"title": "...", "source": "...", "url": "...", "published_at": "2026-10-09T22:15:00+02:00"}]}. Titel auf Deutsch, bei fremdsprachigen Quellen sinngemäß übersetzt. "published_at" ist der Veröffentlichungszeitpunkt laut Quelle (ISO-8601 mit Zeitzone, z. B. aus Artikel-Datum oder Suchergebnis); ist nur das Datum bekannt, 12:00 Uhr Ortszeit der Quelle verwenden; ist er nicht feststellbar, null setzen – nie raten. Bevorzugt Meldungen der letzten 24 Stunden wählen.
- data/news_summary_today.json (N-Aufgaben, Format siehe prompts/N.md): {"date": "YYYY-MM-DD", "lage": "1–2 Sätze, was den Markt bewegt", "lage_stand_local": "HH:MM", "meldungen": [{"title", "source", "url", "published_at", "thema", "bedeutung", "erfasst_local", "erfasst_von"}]} – jede Meldung nur einmal pro Tag (keine Dubletten).
- data/candidate_tracking.json (P1): Zahlenfelder pflegt das Skript (referenz_kurs_usd, aktueller_kurs_usd/eur, performance_pct, nasdaq_performance_pct, ueberrendite_pct, forward, handelstage_seit_aufnahme, kursdaten_stand, status_gruppe) – unverändert übernehmen. Claude pflegt: Neuaufnahmen, handelstage_in_liste, status ("aktiv|überdehnt|ausgeschieden (these widerlegt)|ausgeschieden (zeitlimit)|getradet"), status_seit, wiedereinstieg_eur, empfehlung ("Kauf|Beobachten|Kein Einstieg"), letzte_einschaetzung. Ausgeschiedene Einträge nie löschen.
- data/news_signals.json (nur N-Aufgaben, Format siehe prompts/N.md): {"generated_at_utc": "...", "signale": [{"ticker", "name", "datum", "published_at", "titel", "quelle", "url", "einschaetzung": "positiv|negativ|neutral", "gewicht": "hoch|mittel|niedrig", "kategorie", "kurz", "erfasst_von"}]}. Nur firmenspezifische Meldungen (allgemeine Markt-/Makronachrichten gehören nur in news_summary_today.json). Signale älter als 14 Tage entfernen.
- data/filter_bilanz.json, data/performance.json: nur vom Skript geschrieben, nur lesen.
- data/journal.json und data/portfolio.json: werden automatisch aus dem Trade-Journal im Cockpit erzeugt (Workflow journal.yml). Positionen haben "art": "swing" (Trade nach Systemregeln) oder "bestand" (unabhängig vom System gehalten – keine 10-Tage-Regel, zählt nicht zum Risikobudget). Analyse-Läufe lesen nur, nie schreiben. Möchte der Nutzer im Chat einen Trade erfassen, auf die Registerkarte „Journal“ im Cockpit verweisen.
- data/portfolio_bewertung.json (nur P1): {"generated_at_utc": "...", "positionen": [{"id": "<wie in portfolio.json>", "ticker": "...", "art": "swing|bestand", "empfehlung": "Halten|Verkaufen (swing) bzw. Halten|Prüfen (bestand)", "handelstage_gehalten": ..., "verkauf_spaetestens": "YYYY-MM-DD", "begruendung": "..."}]}

GRUNDSATZ
Kapitalerhalt über Positionsgröße (75 € Risiko je Trade), Risikobudget, Schutz-Stop, 10-Tage-Ausstieg und Regime-Limit – nicht über zusätzliche Veto-Filter. Keine Regeln selbstständig ändern; Auffälligkeiten (z. B. in der Filter-Bilanz) dem Nutzer melden.
