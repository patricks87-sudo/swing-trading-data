# Cockpit-Backlog

Mängel und Wünsche zum Cockpit, nummeriert und nacheinander abgearbeitet.
Status: offen · in Arbeit · zur Abnahme · erledigt · zurückgestellt

Erfasst: 23.10.2026 (gemeinsame Durchsicht des Live-Cockpits)

## Paket 1 – Daten und Logik

Umgesetzt am 23.10.2026. Befund: Bei der Durchsicht waren P1 und P5.5 noch vom Vortag (sie laufen erst nachmittags), daher C02–C05. Lösung C17 macht das künftig sichtbar. Für Claude-Texte (z. B. Begründungen) gilt die Komma-Regel aus prompts/PROJEKT_ANWEISUNGEN.md – sie muss noch in die Projekt-Anweisungen des Claude-Projekts übernommen werden.

| Nr. | Bereich | Problem | Ursache / Lösung | Prio | Status |
|---|---|---|---|---|---|
| C01 | Heute · Märkte | Vortagesänderung der Indizes falsch (Nasdaq −0,24 % statt −2,6 %) | Ab P5 enthält der Feed die laufende Sitzung (`partial_last_bar`); die Karte schrieb trotzdem „Schluss Vortag“. Beschriftung je nach Lauf: „heute bis HH:MM“ bzw. „Schluss Vortag“ | hoch | zur Abnahme |
| C02 | Heute · Marktlage | Kriterienzahl unterschiedlich (2/5 vs. 3/5) | Karten aus verschiedenen Läufen, siehe C17 | hoch | zur Abnahme |
| C03 | Heute · Mein Trade | Karte veraltet, Text passt nicht zum Stand | P1-Ergebnis vom Vortag, siehe C17 | hoch | zur Abnahme |
| C04 | Heute · Mein Trade | Trade-Kandidat fehlt in der aktuellen Watchlist | P1 vom Vortag vs. P4 von heute, siehe C17 | hoch | zur Abnahme |
| C05 | Heute · Hold-Test | Hold-Test veraltet, widerspricht Watchlist | P5.5 vom Vortag, siehe C17 | hoch | zur Abnahme |
| C06 | Heute | Unterschiedliche Einstiegspreise für denselben Titel | Werte aus verschiedenen Läufen; Stand je Karte sichtbar machen (C17) | mittel | zur Abnahme |
| C07 | Heute · Mein Depot | „keine Swing-Position“, Karte zeigt aber Positionen | Positionen sind Bestand; Karte zeigt Aufteilung Swing/Bestand | mittel | zur Abnahme |
| C08 | Heute · Sektoren | Sortierung passt nicht zu den angezeigten Werten | Sortiert nach Rang (60 % RS 20 T + 40 % RS 5 T), angezeigt RS 20 T; nach angezeigtem Wert sortieren | mittel | zur Abnahme |
| C09 | Heute · Aktive Kandidaten | Neue Kandidaten mit +0,00 % / 0 Tagen | Am Aufnahmetag gibt es noch keine Entwicklung; „neu“ statt 0,00 % anzeigen | niedrig | zur Abnahme |
| C10 | Heute · Aktive Kandidaten | Status „aktiv“, aber Empfehlung „Kein Einstieg / Ausschluss“ | Heute im Feed hart ausgeschlossene Titel mit Hinweis „heute ausgeschlossen“ kennzeichnen | mittel | zur Abnahme |
| C11 | Heute · Aktive Kandidaten | USD und EUR gemischt | Spalten mit Währung beschriften | niedrig | zur Abnahme |
| C12 | Allgemein | Punkt statt Komma bei Dezimalzahlen | Deutsche Schreibweise überall (Cockpit und Feed-Texte) | mittel | zur Abnahme |
| C13 | Heute · Marktlage | „1 neue Positionen heute“ | Einzahl/Mehrzahl | niedrig | zur Abnahme |
| C14 | Heute · News | News zu Titeln, die weder in Watchlist noch Depot sind | Nur Titel aus Depot, aktueller Watchlist und aktiven Kandidaten zeigen | mittel | zur Abnahme |
| C15 | Heute · News | „Uhrzeit unbekannt“ bei vielen Meldungen | Dann nur Datum zeigen, ohne Zusatz | niedrig | zur Abnahme |
| C16 | Heute · Watchlist | Unklar, wozu „Limit/Markt“ gehört; Signale ohne Erklärung | Einstiegsart eindeutig beschriften, Legende für die Signalpunkte | mittel | zur Abnahme |
| C17 | Heute | Karten aus unterschiedlich alten Läufen, ohne dass es sichtbar ist | Jede Karte zeigt Lauf + Uhrzeit; ist sie älter als der neueste Feed-Tag, wird sie als „veraltet“ markiert und abgeschwächt | hoch | zur Abnahme |

## Paket 2 – Startseite und Design (erst Entwurf, dann Umsetzung)

| Nr. | Bereich | Wunsch | Hinweis | Prio | Status |
|---|---|---|---|---|---|
| C18 | Allgemein | Logo überarbeiten | Wird extern in Canva gestaltet; Logo als eigene Datei, leicht austauschbar | mittel | offen |
| C19 | Heute | Begrüßung „Guten Abend, Patrick“ entfernen | Stattdessen Kernaussage zum Markt heute | hoch | offen |
| C20 | Heute | Kurzfazit-Zeile „NEUTRAL 2/5 …“ zu technisch | Verständliche Aussage | hoch | offen |
| C21 | Heute · Marktlage | Lage auf einen Blick (Ampel, Tacho oder Skala) | Fünf Kriterien erst beim Aufklappen | hoch | offen |
| C22 | Heute · News | Positiv/negativ besser lesbar | z. B. farbige Karten nach Tendenz, kurze Texte, Bewertung auf Abruf | mittel | offen |
| C23 | Startseite | Großer Hero-Banner | | hoch | offen |
| C24 | Startseite | Muss beim ersten Blick fesseln, kein Daten-Dashboard | Gesamtanspruch für Paket 2 | hoch | offen |

## Runde 3

Weitere Punkte nach Abschluss von Paket 1.
