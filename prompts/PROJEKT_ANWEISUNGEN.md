COCKPIT (Live-Dashboard): https://patricks87-sudo.github.io/swing-trading-data/

KONTEXT (gilt für alle P4/P5/P5.5/P1-Aufgaben in diesem Projekt)
Der Nutzer betreibt hobbymäßiges Swing-Trading in US-Aktien über Trade Republic (seit dem EU-PFOF-Verbot 1.7.2026 Bestpreis-Order-Routing über ca. 30 Handelsplätze). Alle Kursangaben in EUR, umgerechnet mit dem Feld "eurusd" der JSON-Daten. Pipeline über den Handelstag: P4 (~14:50 MESZ, Kandidatensuche) → P5 (~15:30 MESZ, Eröffnungs-Info) → P5.5 (~17:05 MESZ, Hold-Test mit Intraday-Daten) → P1 (~17:35 MESZ, Portfolio-Entscheidung).

PROMPTS (seit 11.10.2026 im GitHub-Repo, nicht mehr als Projektdateien)
Die verbindlichen Kriterien jedes Schritts stehen im Repo und werden bei jedem Lauf live abgerufen:
https://raw.githubusercontent.com/patricks87-sudo/swing-trading-data/main/prompts/P4.md
https://raw.githubusercontent.com/patricks87-sudo/swing-trading-data/main/prompts/P5.md
https://raw.githubusercontent.com/patricks87-sudo/swing-trading-data/main/prompts/P5_5.md
https://raw.githubusercontent.com/patricks87-sudo/swing-trading-data/main/prompts/P1.md
Wende IMMER genau den Prompt des angeforderten Schritts an.

DATENQUELLE
Repo patricks87-sudo/swing-trading-data (Branch main). Der GitHub-Actions-Workflow schreibt je Lauf data/{run}_latest.json ({run} = p4, p5, p55, p1). Abruf: https://raw.githubusercontent.com/patricks87-sudo/swing-trading-data/main/data/{run}_latest.json
Inhalt: "eurusd"; "indices" (QQQ, SPY, IWM, SOXX als ETF-Proxies; "VIX" = echter CBOE-VIX via yfinance); "macro" (VIX, US-10J-Rendite); "watchlist" (50 Werte aus 19 Sektoren, je Eintrag Kursindikatoren, "options_flow", "earnings", "ampel" und "setup"); "breadth"; "sectors"; "regime"; "ranking"; beim P5.5-Lauf zusätzlich "hold_test".

DETERMINISTISCHE BEWERTUNG (seit 11.10.2026)
Regime, Sektor-Ranking, Score (0–100), Stufe, Bulltrap-Flags, harte Ausschlüsse (Earnings ≤5 Handelstage, Optionsflow bärisch, Volumen <1 Mio.), Einstieg/Stop/Ziele/Stückzahl und der P5.5-Hold-Test werden im Python-Skript (analysis.py) berechnet. Diese Werte übernehmen, nicht neu ableiten oder schätzen. Claude prüft zusätzlich News und darf den Score dafür um höchstens ±10 Punkte korrigieren (mit Begründung). Fehlende Daten werden gekennzeichnet ("Datenbasis unvollständig"), nie als negativ gewertet und nie erfunden.

SEKTORLISTE
Technology, Semiconductors/AI, Software/Cloud, Cybersecurity, Defense, Financials, Insurance, Payments, Fintech/Brokerage, Healthcare, MedTech, Energy, Utilities, Industrials, Industrials/Infrastructure, Materials, Consumer Discretionary, Transportation (wie im Feld "sector" des Feeds).

FIRMENNAMEN
In allen Texten und im Cockpit volle Firmennamen statt Ticker (z. B. "NVIDIA" statt "NVDA", "Palo Alto Networks" statt "PANW", "AMD (Advanced Micro Devices)" statt "AMD"). Das Feld "ticker" bleibt technisch bestehen.

RÜCKKANAL (GitHub-Connector)
Ergebnisdateien immer komplett neu schreiben (nicht anhängen) in data/. Unmittelbar vor jedem Schreiben den aktuellen Stand inkl. sha abrufen; bei SHA-Konflikt bis zu 3x mit frischem Stand wiederholen.

- data/p4_candidates.json (nur P4): {"generated_at_utc": "...", "run_date": "YYYY-MM-DD", "regime": "RISK-ON|NEUTRAL|RISK-OFF", "candidates": [{"ticker": "...", "name": "...", "sector": "...", "score": 0-100, "feed_score": 0-100, "score_korrektur": 0, "stufe": "Kauf – hohe Qualität|Kauf – solide|Beobachten|Überdehnt – auf Rücksetzer warten", "ampel": {"kapitalfluss": "...", "trendkontext": "...", "optionsflow": "..."}, "levels": {"einstieg_eur": ..., "einstieg_typ": "...", "stop_eur": ..., "ziel1_eur": ..., "ziel2_eur": ..., "stueck": ..., "kapitalbedarf_eur": ...}, "bulltrap_flags": [...], "earnings": "YYYY-MM-DD oder unbekannt", "begruendung": "max. 4 Sätze"}], "ausgeschlossen": [{"name": "...", "grund": "..."}]}
- data/p55_candidates.json (nur P5.5): {"generated_at_utc": "...", "run_date": "YYYY-MM-DD", "ergebnis": "Trade möglich|Kein Trade heute", "kurzbegruendung": "...", "kandidaten": [{"ticker": "...", "name": "...", "sector": "...", "status": "Bestanden|Teilweise|Nicht bestanden|Neutral", "checks": {"ueber_vwap": true, "ueber_eroeffnung": true, "staerker_als_sp500": true, "volumen_ueber_schnitt": true}, "vwap": ..., "relatives_volumen": ..., "einstieg_heute": "ja|limit|nein", "begruendung": "..."}]}
- data/top_empfehlung.json (nur P1): {"generated_at_utc": "...", "top3": [{"ticker": "...", "name": "...", "aktion": "Kauf zum Kurs|Limit-Order|Beobachten", "begruendung": "..."}], "gesamteinschaetzung": "...", "filter_bilanz": "Fazit-Satz aus filter_bilanz.json"}
- data/market_barometer.json (P4, P5, P5.5, P1): {"generated_at_utc": "...", "status": "<regime.status aus dem Feed>", "begruendung": "...", "kurzbegruendung": "max. ca. 150 Zeichen", "sektor_rotation": [{"sektor": "...", "trend": "positiv|neutral|negativ (aus sectors)", "kommentar": "...", "kandidaten": [{"name": "...", "empfehlung": "Kauf|Beobachten|Kein Einstieg|Halten|Verkauf"}]}]}. "Halten" und "Verkauf" nur für Titel, die im Depot (portfolio.json) liegen.
- data/headlines.json (alle Läufe und N-Aufgaben): {"generated_at_utc": "...", "headlines": [{"title": "...", "source": "...", "url": "..."}]}. Titel auf Deutsch, bei fremdsprachigen Quellen sinngemäß übersetzt.
- data/candidate_tracking.json (P1): Zahlenfelder pflegt das Skript (referenz_kurs_usd, aktueller_kurs_usd/eur, performance_pct, nasdaq_performance_pct, ueberrendite_pct, forward, handelstage_seit_aufnahme, kursdaten_stand, status_gruppe) – unverändert übernehmen. Claude pflegt: Neuaufnahmen, handelstage_in_liste, status ("aktiv|überdehnt|ausgeschieden (these widerlegt)|ausgeschieden (zeitlimit)|getradet"), status_seit, wiedereinstieg_eur, empfehlung ("Kauf|Beobachten|Kein Einstieg"), letzte_einschaetzung. Ausgeschiedene Einträge nie löschen.
- data/filter_bilanz.json: nur vom Skript geschrieben, nur lesen.
- data/portfolio.json: vom Nutzer im Chat gepflegt, Analyse-Läufe lesen nur.
- data/portfolio_bewertung.json (nur P1): {"generated_at_utc": "...", "positionen": [{"id": "<wie in portfolio.json>", "ticker": "...", "empfehlung": "Halten|Nachkaufen|Teilverkauf|Verkaufen", "begruendung": "..."}]}

GRUNDSATZ
Kapitalerhalt über Positionsgröße (75 € Risiko je Trade), Stop und Regime-Limit – nicht über zusätzliche Veto-Filter. Keine Regeln selbstständig ändern; Auffälligkeiten (z. B. in der Filter-Bilanz) dem Nutzer melden.
