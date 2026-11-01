# Aktienkänguru – Logo

Stand: 01.11.2026 · Status: **final freigegeben**, noch **nicht** im Cockpit eingebaut (`site/logo.svg` ist noch das alte Logo).

## Motiv

Känguru im Sprung schräg nach oben rechts. Rücken und Schwanz bilden einen durchgehenden Schwung; der Schwanz läuft unten links fast in den Terrakotta-Bogen über. Der Bogen steht für den Sprung und gleichzeitig für einen steigenden Kurs (Swing Trading: kurze, kraftvolle Sätze).

## Entstehung

- Idee per Canva-KI-Bildgenerator (Variante „steiler Sprung, Bogen am Schwanz“) als Inspiration.
- Die Dateien hier sind eine **eigene Reinzeichnung als SVG** (kein KI-Bild), damit das Logo als eigene Gestaltung gilt.
- Vor Markenanmeldung/Bezahl-Abo: anwaltliche Markenprüfung (siehe Content-Projekt).

## Dateien (Quelldateien, Vektor)

| Datei | Einsatz |
|---|---|
| `aktienkaenguru-logo.svg` | Hauptlogo auf hellem Grund (Erdbraun + Terrakotta) |
| `aktienkaenguru-logo-dunkel.svg` | Hauptlogo für Dark Mode (Sand + helles Terrakotta) |
| `aktienkaenguru-icon-terrakotta.svg` | App-Icon / X-Profilbild / Favicon (Empfehlung) |
| `aktienkaenguru-icon-erdbraun.svg` | Icon-Variante dunkel |
| `aktienkaenguru-icon-sand.svg` | Icon-Variante hell |

## Farben (aus `site/brand.css`)

| Name | Hex |
|---|---|
| Terrakotta (Marke) | `#c2501f` |
| Terrakotta hell (Dark Mode) | `#f08a4b` |
| Erdbraun | `#2a1d16` |
| Sand | `#fbf7f1` |

## Schriftzug

„Aktien**känguru**“ in *Bricolage Grotesque* 700, Laufweite −0,03em; „Aktien“ in Erdbraun, „känguru“ in Terrakotta (wie `.mark` in `site/brand.css`). Eine Lockup-Datei mit in Pfade umgewandelter Schrift gibt es noch nicht.

## Einbau ins Cockpit (offen)

- `aktienkaenguru-logo.svg` ersetzt `site/logo.svg` (Seitenverhältnis 116:104 statt quadratisch – `.mark svg` ggf. anpassen).
- Favicon aus `aktienkaenguru-icon-terrakotta.svg` erzeugen.
