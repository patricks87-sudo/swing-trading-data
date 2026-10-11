# N – Nachrichten-Check v2.0

Stand: 11.10.2026. Gilt für alle Nachrichten-Aufgaben (N1–N6 werktags, N-Sa, N-So). Ersetzt die bisherige Anweisung im Aufgabentext.

Schlanker Lauf: keine Marktdaten abrufen, keinen GitHub-Actions-Workflow auslösen, keine Kandidaten-Analyse. Repo: `patricks87-sudo/swing-trading-data`, Branch `main`, Schreiben über den GitHub-Connector. Vor jedem Schreiben den aktuellen Stand inkl. `sha` abrufen; bei SHA-Konflikt bis zu 3× mit frischem Stand wiederholen.

## Teil A – Top-3-Schlagzeilen (wie bisher)

1. Recherchiere per Websuche die drei wichtigsten Markt-/Wirtschaftsnachrichten für US-Aktien, bevorzugt aus den letzten 24 Stunden.
2. Schreibe `data/headlines.json` komplett neu: `{"generated_at_utc": "...", "headlines": [{"title": "...", "source": "...", "url": "...", "published_at": "..."}]}`. Titel auf Deutsch (fremdsprachige Quellen sinngemäß übersetzen). `published_at` = Veröffentlichungszeitpunkt laut Quelle, ISO-8601 mit Zeitzone; nur Datum bekannt → 12:00 Uhr; nicht feststellbar → `null`. Nie raten.
3. Lies `data/news_summary_today.json`. Stimmt `date` nicht mit dem heutigen Datum (Europe/Berlin, YYYY-MM-DD) überein oder fehlt die Datei, beginne mit leerer `entries`-Liste. Hänge `{"time_utc": "...", "time_local": "HH:MM", "headlines": [dieselben 3]}` an und schreibe die Datei mit aktuellem `date` komplett neu.

## Teil B – News-Signale zu Kandidaten und Depot (neu)

Zweck: P4 muss nicht mehr selbst für jeden Kandidaten Nachrichten suchen. Der Feed rechnet aus deinen Signalen deterministisch eine Score-Korrektur (max. ±10) und harte News-Ausschlüsse.

### Fokusliste (max. 15 Titel)

1. alle Titel aus `data/portfolio.json` (`positions[].ticker`) – immer zuerst
2. alle Kandidaten aus `data/p4_candidates.json` mit Stufe „Kauf …“ oder „Überdehnt …“
3. Einträge in `data/candidate_tracking.json` mit Status `aktiv` oder `überdehnt`
4. restliche P4-Kandidaten („Beobachten“)

Doppelte Ticker nur einmal.

### Recherche – sparsam

- Bündle mehrere Titel in einer Suche (z. B. „NVIDIA Broadcom AMD stock news today“). Insgesamt **höchstens 6 Websuchen** für Teil B.
- Nur Meldungen der letzten 48 Stunden (am Montag und bei N1: seit Freitag 22:00 MESZ), die für den Kurs der nächsten Tage relevant sind. Reine Kursberichte („Aktie steigt um 2 %“) ohne neuen Inhalt ignorieren.
- Findest du zu einem Titel nichts Relevantes, schreibe nichts dazu – kein Signal ist ein gültiges Ergebnis.

### Bewertung je Meldung

- `einschaetzung`: `positiv` | `negativ` | `neutral` – aus Sicht eines Swing-Trades (5–10 Handelstage, Long)
- `gewicht`: `hoch` (verändert die These: Gewinnwarnung, Prognose-Anhebung, Großauftrag, Übernahme, Verfahren mit wesentlicher Tragweite) | `mittel` (Analysten-Hoch-/Herabstufung, Kursziel deutlich geändert, wichtiger Produkt-/Kundenvertrag) | `niedrig` (Randnotiz)
- `kategorie`: genau eine aus `Gewinnwarnung`, `Verfahren` (SEC, Gericht, Kartell, Regulierung), `Bilanz` (Bilanzskandal, Restatement), `Übernahme` (Titel ist Übernahmeziel), `Earnings`, `Analyst`, `Auftrag/Produkt`, `Management`, `Sektor`, `Sonstiges`

**Achtung:** `Gewinnwarnung`, `Verfahren` oder `Bilanz` mit `negativ` sowie jede `Übernahme` führen im Feed 14 Tage lang zum **harten Ausschluss**. Diese Kategorien nur bei bestätigten Meldungen seriöser Quellen verwenden, nicht bei Gerüchten.

### Datei `data/news_signals.json`

Lies die Datei (falls vorhanden), behalte alle Signale, deren `datum` höchstens 14 Kalendertage zurückliegt, füge die neuen hinzu und schreibe sie komplett neu. Duplikate (gleiche `url`, oder gleicher Ticker mit sinngleichem Titel) nicht erneut anlegen.

```json
{
  "generated_at_utc": "2026-10-12T06:04:00Z",
  "signale": [
    {
      "ticker": "NVDA",
      "name": "NVIDIA",
      "datum": "2026-10-12",
      "published_at": "2026-10-12T07:30:00+02:00",
      "titel": "Deutscher Titel, sinngemäß übersetzt",
      "quelle": "Reuters",
      "url": "https://...",
      "einschaetzung": "positiv",
      "gewicht": "mittel",
      "kategorie": "Analyst",
      "kurz": "Ein Satz, warum das für den Trade zählt.",
      "erfasst_von": "N1"
    }
  ]
}
```

`datum` = Veröffentlichungsdatum (Europe/Berlin). `erfasst_von` = Name dieser Aufgabe (N1 … N6, N-Sa, N-So). Volle Firmennamen im Feld `name`.

## Abschluss

Kurze Ausgabe: die drei Schlagzeilen und je Titel der Fokusliste mit Signal eine Zeile (Name, Einschätzung, Gewicht, Kategorie). Keine weiteren Analysen.
