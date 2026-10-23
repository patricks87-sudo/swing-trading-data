# N – Nachrichten-Check v2.3

Stand: 18.10.2026 (v2.1: keine doppelten Meldungen mehr im Tagesüberblick, News-Signale nur noch firmenspezifisch; v2.2: Teil C – Rohstoffe & Zentralbanken für die Cockpit-Seite „Rohstoffe“; v2.3: Top-3 als Markierung in `meldungen`, aktuelle Meldungen bevorzugt, keine Ersatz-Uhrzeiten, Zahlen widerspruchsfrei). Gilt für alle Nachrichten-Aufgaben (N1–N6 werktags, N-Sa, N-So).

Schlanker Lauf: keine Marktdaten abrufen, keinen GitHub-Actions-Workflow auslösen, keine Kandidaten-Analyse. Repo: `patricks87-sudo/swing-trading-data`, Branch `main`, Schreiben über den GitHub-Connector. Vor jedem Schreiben den aktuellen Stand inkl. `sha` abrufen; bei SHA-Konflikt bis zu 3× mit frischem Stand wiederholen.

## Teil A – Allgemeine Marktnachrichten (was den Markt bewegt)

1. Lies zuerst `data/news_summary_today.json`. Stimmt `date` nicht mit dem heutigen Datum (Europe/Berlin, YYYY-MM-DD) überein oder fehlt die Datei, beginne mit leerer Liste `meldungen`. Ein altes Format mit `entries` wird beim ersten Schreiben in `meldungen` überführt (Dubletten dabei zusammenfassen).
2. Recherchiere per Websuche die wichtigsten aktuellen Markt- und Wirtschaftsnachrichten für US-Aktien (Zinsen/Fed, Konjunkturdaten, Geopolitik, große Unternehmensmeldungen, Sektorbewegungen), bevorzugt aus den letzten Stunden seit dem letzten Lauf.
3. **Keine Dubletten:** Eine Meldung wird nur neu aufgenommen, wenn sie heute noch nicht in `meldungen` steht – gleiche `url` ODER gleiches Ereignis aus einer anderen Quelle zählt als vorhanden. Gibt es zu einem vorhandenen Ereignis wesentliche neue Fakten (z. B. Schlusskurs statt Zwischenstand), aktualisiere den vorhandenen Eintrag (`title`, `url`, `published_at`, `aktualisiert_local`) statt einen neuen anzulegen. Ist nichts wirklich Neues passiert, füge nichts hinzu.
4. Aktualisiere `lage`: ein bis zwei Sätze, was den Markt heute insgesamt bewegt (immer aktuell halten).
5. **Zahlen widerspruchsfrei:** Nennen mehrere Meldungen dieselbe Größe (z. B. Brent-Preis, Indexstand, Rendite), gilt die neueste Angabe. Ältere Einträge mit überholter Zahl anpassen oder die Zahl dort weglassen, und `lage` muss zu den Meldungen passen.
6. **Top-3 neu bestimmen (bei jedem Lauf):** Markiere die drei Meldungen, die den Markt *jetzt* am stärksten bewegen, mit `"top": 1`, `2`, `3` (alle anderen ohne `top`). Vorrang haben Meldungen der letzten 12 Stunden; eine Meldung vom Vortag nur, wenn sie heute noch das bestimmende Thema ist und keine neuere Meldung dasselbe Ereignis abdeckt (z. B. Schlusskurs von gestern → ersetzt durch den heutigen Handelsstart).
7. Schreibe `data/news_summary_today.json` komplett neu:

```json
{
  "date": "2026-10-19",
  "lage": "Ein bis zwei Sätze zur aktuellen Marktlage.",
  "lage_stand_local": "16:15",
  "meldungen": [
    {"title": "Deutscher Titel", "source": "Reuters", "url": "https://...", "published_at": "2026-10-19T14:05:00+02:00",
     "thema": "Zinsen/Fed|Konjunktur|Geopolitik|Unternehmen|Sektor|Rohstoffe|Sonstiges",
     "bedeutung": "Ein Satz, was das für US-Aktien heißt.", "erfasst_local": "16:15", "erfasst_von": "N4", "top": 1}
  ]
}
```

8. Schreibe `data/headlines.json` komplett neu mit genau den drei als `top` markierten Meldungen in dieser Reihenfolge (gleicher Titel, gleiche URL, gleiches `published_at`): `{"generated_at_utc": "...", "headlines": [{"title": "...", "source": "...", "url": "...", "published_at": "..."}]}`. Das Cockpit zeigt keinen eigenen Top-Block mehr, sondern markiert diese Meldungen in der Liste „Markt heute“.

Titel auf Deutsch (fremdsprachige Quellen sinngemäß übersetzen). `published_at` = Veröffentlichungszeitpunkt laut Quelle, ISO-8601 mit Zeitzone (z. B. `2026-10-23T10:17:00-04:00`). **Ist nur das Datum bekannt, nur das Datum schreiben** (`"2026-10-23"`) – keine Ersatz-Uhrzeit wie 12:00 oder 00:00, das Cockpit zeigt dann „Uhrzeit unbekannt“. Nicht feststellbar → `null`. Nie raten. Höchstens 4 Websuchen für Teil A.

## Teil B – News-Signale zu Kandidaten und Depot (neu)

Zweck: P4 muss nicht mehr selbst für jeden Kandidaten Nachrichten suchen. Der Feed rechnet aus deinen Signalen deterministisch eine Score-Korrektur (max. ±10) und harte News-Ausschlüsse.

**Nur firmenspezifische Meldungen.** Ein Signal braucht eine Meldung, die genau dieses Unternehmen betrifft (es wird im Titel oder Kern der Meldung genannt). Allgemeine Markt- und Makronachrichten (Fed, Inflation, Anleiherenditen, Indexbewegungen, „Halbleiterindex fällt“) gehören **nicht** in `news_signals.json`, sondern nur in Teil A – sie stecken bereits im Kursverlauf und würden doppelt zählen. Ein Signal, das schon in der Datei steht (gleiche `url` oder gleiches Ereignis zum selben Ticker), wird nicht erneut angelegt.

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
- `kategorie`: genau eine aus `Gewinnwarnung`, `Verfahren` (SEC, Gericht, Kartell, Regulierung), `Bilanz` (Bilanzskandal, Restatement), `Übernahme` (Titel ist Übernahmeziel), `Earnings`, `Analyst`, `Auftrag/Produkt`, `Management`, `Sektor` (branchenspezifisches Ereignis, das das Unternehmen direkt trifft, z. B. Exportverbot für dessen Chips – keine Indexbewegungen). Andere Kategorien sind nicht zulässig; der Feed wertet `Sektor` höchstens ±1.

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

## Teil C – Rohstoffe & Zentralbanken (neu in v2.2)

Zweck: Die Cockpit-Seite „Rohstoffe“ zeigt, ob Kapital in Gold, Silber & Co. umschichtet. Kursdaten berechnet der Feed selbst; du lieferst nur die **Meldungen**, die Kurse nicht zeigen – vor allem Käufe und Verkäufe von Zentralbanken.

1. **Höchstens 1 Websuche** pro Lauf (z. B. „central bank gold purchases“, „World Gold Council central banks“, „PBoC gold reserves“, „silver demand central bank“). Bei N1 und N-So zusätzlich eine zweite Suche zu Angebot/Nachfrage bei Gold, Silber, Kupfer oder Öl erlaubt.
2. Aufnehmen nur, was für Edelmetalle oder Rohstoffe in den nächsten Wochen relevant ist: gemeldete Zentralbank-Käufe/-Verkäufe (World Gold Council, PBoC, RBI, NBP, CNB, Bundesbank …), große ETF-Zu-/Abflüsse, Förder- oder Exportstopps, OPEC-Beschlüsse, Zölle auf Metalle. Keine reinen Kursberichte.
3. Lies `data/rohstoff_meldungen.json` (falls vorhanden), behalte Einträge, deren `datum` höchstens 60 Tage zurückliegt, füge Neues hinzu (keine Dubletten: gleiche `url` oder gleiches Ereignis) und schreibe die Datei komplett neu. Nichts Neues → Datei nicht anfassen.

```json
{
  "generated_at_utc": "2026-10-19T06:05:00Z",
  "meldungen": [
    {"datum": "2026-10-17", "published_at": "2026-10-17T10:00:00+02:00",
     "titel": "Deutscher Titel", "quelle": "World Gold Council", "url": "https://...",
     "rohstoff": "Gold|Silber|Kupfer|Öl|Rohstoffe allgemein",
     "kategorie": "Zentralbank|ETF-Ströme|Angebot|Nachfrage|Politik/Zölle|Sonstiges",
     "einschaetzung": "positiv|negativ|neutral",
     "kurz": "Ein Satz, was das für den Preis heißt.", "erfasst_von": "N1"}
  ]
}
```

`einschaetzung` bezieht sich auf den Preis des Rohstoffs (Zentralbank kauft Gold → positiv). Rohstoff-Meldungen gehören **nicht** in `news_signals.json` (außer sie betreffen direkt ein Unternehmen der Fokusliste, z. B. Freeport-McMoRan – dann zusätzlich dort als firmenspezifisches Signal). In Teil A weiterhin `thema` = „Rohstoffe“ für marktbewegende Rohstoff-Nachrichten verwenden.

## Abschluss

Kurze Ausgabe: `lage`, die neu aufgenommenen Meldungen (oder „nichts Neues“), neue Rohstoff-Meldungen aus Teil C und je Titel der Fokusliste mit neuem Signal eine Zeile (Name, Einschätzung, Gewicht, Kategorie). Keine weiteren Analysen.
