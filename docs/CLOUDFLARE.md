UMZUG: EIGENE DOMAIN, LOGIN UND PRIVATES REPO
Stand: 24.10.2026

STATUS
Erledigt – Schritte 1–5:
- Domain aktienkaenguru.de bei INWX, Nameserver auf Cloudflare umgestellt.
- Worker "aktienkaenguru-cockpit" live (Fassung aus PR #15, nur Cockpit – die öffentliche Startseite aus PR #17 ist noch nicht eingespielt).
- Access-App "cockpit" mit Policy "Nur ich" (patricks87@gmx.de), Team-Domain aktienkaenguru.cloudflareaccess.com, Sitzungsdauer 1 Monat.
- workers.dev und Preview-URLs deaktiviert.
- Variablen im Worker: GITHUB_TOKEN (nur lesen), REPO, BRANCH, TEAM_DOMAIN, POLICY_AUD.
Offen:
- Journal direkt im Cockpit (C25): neuen worker/worker.js einspielen und JOURNAL_TOKEN anlegen, siehe Abschnitt JOURNAL-EINGABE IM COCKPIT.
- Schritt 6: geplante Aufgaben sind seit 23.10. auf den GitHub-Connector umgestellt (N6 am 23.10. erfolgreich); offen sind die Projekt-Anweisungen im Claude-Projekt und die Beobachtung von P4–P1.
- Schritt 7: Repo privat stellen.

WORKER-DOMAINS (aktuell)
- cockpit.aktienkaenguru.de, aktienkaenguru.de und www.aktienkaenguru.de – alle drei als Custom Domains am Worker und als Hostnames in der Access-App, also alle hinter Login.
- Hinweis für den späteren öffentlichen Auftritt: www und Root (aktienkaenguru.de) aus der Access-App nehmen und den neuen worker/worker.js einspielen, der dort die öffentliche Startseite ausliefert. Das Cockpit bleibt auf cockpit.aktienkaenguru.de hinter Login.

ABLAUFDATEN
- GitHub-Token (GITHUB_TOKEN, nur lesen) läuft am 23.10.2027 ab → vorher erneuern (siehe FEHLERHILFE, gleicher Ablauf).
- Journal-Token (JOURNAL_TOKEN) – Ablaufdatum hier eintragen, sobald er angelegt ist.
- Domain aktienkaenguru.de verlängert sich am 23.10.2027 bei INWX (4,65 € per Lastschrift).

ZIEL
Unter der Hauptdomain (z. B. aktienkaenguru.de) steht die öffentliche Startseite, das Cockpit läuft unter cockpit.<domain> hinter einem Login. Das GitHub-Repo wird privat, damit Depot, Journal und Kandidaten nicht mehr öffentlich sind.

  Browser → cockpit.<domain> → Cloudflare Access (Login nur mit deiner E-Mail)
          → Cloudflare Worker (worker/worker.js) → privates GitHub-Repo (nur Lesezugriff)
  Browser → <domain>         → derselbe Worker: Startseite aus site/ und unter /public/ nur
                               Marktlage, Indizes, Sektoren, Marktmeldungen und Performance-Kurven
                               (keine Watchlist, keine Kandidaten, kein Depot, kein Journal)

KOSTEN
- Domain: ca. 5–15 € im Jahr beim deutschen Anbieter (z. B. INWX, Netcup, Hetzner). Nur die Domain buchen, kein Paket.
- Cloudflare (DNS, Worker, Access bis 50 Nutzer): kostenlos. Für Zero Trust/Access verlangt Cloudflare bei der Anmeldung meist eine Zahlungsmethode; belastet wird im Free-Tarif nichts.
- GitHub privat: 2.000 Actions-Minuten im Monat frei. Erwarteter Verbrauch ca. 1.000–1.200 Minuten (4 Feed-Läufe à ca. 10 Minuten pro Handelstag). Ohne hinterlegte Zahlungsmethode kann GitHub nichts berechnen – im schlimmsten Fall pausieren die Workflows bis Monatsende.

REIHENFOLGE (damit nichts ausfällt)
Schritte 1–6 gehen, während das Repo noch öffentlich ist. Erst wenn alles läuft, Schritt 7.

1) DOMAIN UND CLOUDFLARE
   a) Domain beim deutschen Anbieter bestellen (Kündigungsfrist vorher prüfen).
   b) Kostenloses Konto bei cloudflare.com anlegen → "Add a site" → Domain eintragen → Free-Tarif.
   c) Cloudflare nennt zwei Nameserver (xyz.ns.cloudflare.com). Beim Domain-Anbieter unter "Nameserver" diese beiden eintragen. Falls DNSSEC beim Anbieter aktiv ist: vorher dort ausschalten.
   d) Warten, bis Cloudflare die Domain als "Active" anzeigt (Minuten bis wenige Stunden).

2) GITHUB-TOKEN NUR ZUM LESEN
   GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token
   - Repository access: Only select repositories → swing-trading-data
   - Permissions → Repository permissions → Contents: Read-only (sonst nichts)
   - Expiration: 1 Jahr (Erinnerung im Kalender setzen – danach neuen Token erzeugen und in Schritt 3 austauschen)
   Token kopieren, er wird nur einmal angezeigt.

3) WORKER ANLEGEN
   Cloudflare → Workers & Pages → Create → Worker → Name "aktienkaenguru-cockpit" → Deploy
   → "Edit code": Inhalt von worker/worker.js komplett einfügen → Deploy
   → Settings → Variables and Secrets:
       GITHUB_TOKEN  Typ Secret  = Token aus Schritt 2
       REPO          Typ Text    = patricks87-sudo/swing-trading-data
       BRANCH        Typ Text    = main
       TEAM_DOMAIN   Typ Text    = kommt aus Schritt 4 (z. B. aktienkaenguru.cloudflareaccess.com)
       POLICY_AUD    Typ Text    = kommt aus Schritt 4
   → Settings → Domains & Routes:
       "Add" → Custom domain → cockpit.<deine-domain>
       "Add" → Custom domain → <deine-domain>  (öffentliche Startseite; optional zusätzlich www.<deine-domain>)
       workers.dev und Preview-URLs auf "Disabled" stellen (sonst gäbe es einen Weg am Login vorbei – der Worker würde dort ohnehin nur 403 liefern).

4) LOGIN MIT CLOUDFLARE ACCESS
   Cloudflare → Zero Trust (Free-Tarif)
   → Team-Name: Ist mit einem Zufallsnamen vorbelegt und muss unter Zero Trust → Settings geändert werden (hier: "aktienkaenguru").
   → Access → Applications → Add an application → Self-hosted
       Application name: Cockpit
       Domain: cockpit.<deine-domain>
       Session duration: z. B. 1 Monat
   → Policy: Name "Nur ich", Action "Allow", Include → Emails → deine E-Mail-Adresse
   → Login-Methode: "One-time PIN" (Code per E-Mail) genügt. Sie muss unter Zero Trust → Integrations → Identity providers aktiv hinzugefügt werden – sonst bietet die Login-Seite nur den Cloudflare-Login an.
   → Login-Seite benennen: unter Reusable components → Custom pages (hier: "AktienKänguru").
   → Speichern. In der Übersicht der Anwendung steht der "Application Audience (AUD) Tag" → als POLICY_AUD im Worker eintragen.
   TEAM_DOMAIN = <team-name>.cloudflareaccess.com (steht in Zero Trust unter Settings als "Team domain").

5) TESTEN
   - cockpit.<deine-domain> im privaten Browserfenster öffnen → Login-Seite von Cloudflare erscheint → E-Mail eingeben → Code → Cockpit erscheint mit Daten.
   - Ohne Login (anderer Browser) darf nur die Login-Seite erscheinen.
   - <deine-domain> ohne Login: die Startseite mit Marktlage und Meldungen erscheint. <deine-domain>/data/portfolio.json muss "Nicht gefunden" liefern.
   Wichtig: Die Access-Anwendung aus Schritt 4 gilt nur für cockpit.<deine-domain> – die Hauptdomain bleibt ohne Login.
   Das Cockpit erkennt selbst, ob es auf GitHub Pages oder hinter dem Worker läuft, und lädt die Daten entsprechend (REPO_BASE in index.html).

6) CLAUDE-PROJEKT UMSTELLEN
   Die geplanten Aufgaben laden Prompts und Feed bisher über raw.githubusercontent.com – das funktioniert bei einem privaten Repo nicht mehr. In den Projekt-Anweisungen des Claude-Projekts die Abschnitte PROMPTS und DATENQUELLE durch die Fassung aus prompts/PROJEKT_ANWEISUNGEN.md ersetzen (Lesen über den GitHub-Connector, der ohnehin schon zum Schreiben genutzt wird). Falls einzelne geplante Aufgaben raw-Links direkt im Aufgabentext enthalten, dort ebenfalls ersetzen.
   Danach einen Lauf beobachten (z. B. eine N-Aufgabe oder P4), ob Prompt und Feed korrekt gelesen werden.

7) REPO PRIVAT STELLEN
   GitHub → Repo → Settings → General → Danger Zone → Change visibility → Private.
   - GitHub Pages wird dabei abgeschaltet (das alte Cockpit unter github.io ist dann weg – gewollt).
   - Die Journal-Issues werden ebenfalls privat. Der Journal-Knopf im Cockpit funktioniert weiter, solange du bei GitHub angemeldet bist.
   - Actions laufen weiter, jetzt mit Minuten-Kontingent. Verbrauch unter Settings → Billing and licensing → Usage beobachten. Dort auch prüfen, dass keine Zahlungsmethode hinterlegt ist bzw. das Actions-Budget auf 0 $ steht.
   - Wichtig: Was bisher öffentlich war, kann bereits kopiert worden sein. Privat schützt nur ab jetzt.

JOURNAL-EINGABE IM COCKPIT (C25)
Mit dem neuen worker/worker.js speichert das Cockpit Journal-Einträge direkt, ohne Sprung zu GitHub. Der Worker legt dafür das Issue "[Trade] …" an; der bestehende Workflow journal.yml verarbeitet es wie bisher und schreibt seine Antwort ins Issue. Das Cockpit zeigt diese Antwort nach etwa 30–60 Sekunden an und lädt das Journal neu.
Solange der neue Worker oder der Token fehlt, bietet das Cockpit nach dem Absenden einen Link "Stattdessen über GitHub eintragen" an – es geht also nichts verloren.
   a) Zweiter Token, nur für das Journal:
      GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token
      - Name: z. B. "aktienkaenguru-journal"
      - Repository access: Only select repositories → swing-trading-data
      - Permissions → Repository permissions → Issues: Read and write (sonst nichts; "Metadata: Read-only" setzt GitHub automatisch)
      - Expiration: 1 Jahr, Datum oben unter ABLAUFDATEN eintragen
      Token kopieren. Er darf nur Issues anlegen und lesen – an Dateien, Depot und Workflows kommt er nicht heran.
   b) Cloudflare → Worker "aktienkaenguru-cockpit" → Settings → Variables and Secrets → Add
      JOURNAL_TOKEN  Typ Secret  = Token aus a)
   c) Cloudflare → Worker → "Edit code": Inhalt von worker/worker.js komplett ersetzen → Deploy.
      Achtung: Der neue Worker liefert auf aktienkaenguru.de/www auch die öffentliche Startseite aus. Solange diese beiden noch in der Access-App stehen, bleibt alles hinter dem Login – das ist unschädlich (siehe B05).
   d) Testen: im Cockpit unter Journal einen Kauf mit Haken "Testeintrag" absenden → "Eintrag #… übermittelt" → nach etwa einer Minute "✓ … gespeichert als T…". Danach den Testeintrag per "Storno" wieder entfernen.
   Sicherheit: Der Worker nimmt Einträge nur auf cockpit.<domain> an, nur mit gültigem Access-Login und nur, wenn die Anfrage vom Cockpit selbst kommt (Origin-Prüfung). Der Workflow verarbeitet weiterhin nur Issues, die unter deinem GitHub-Konto angelegt wurden – das ist beim Token der Fall.

FEHLERHILFE
- "GitHub antwortet nicht wie erwartet (401)": Der Token ist ungültig oder abgelaufen.
  1) GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → beim Token "Regenerate token".
  2) Neuen Token mit dem Kopier-Symbol kopieren (wird nur einmal angezeigt).
  3) Cloudflare → Worker "aktienkaenguru-cockpit" → Settings → Variables and Secrets → bei GITHUB_TOKEN auf den Stift → "Rotate" → neuen Token einfügen → Deploy.

- Journal: "Direkt speichern hat nicht geklappt (GitHub antwortet nicht wie erwartet (401))": JOURNAL_TOKEN ungültig oder abgelaufen → wie oben, nur beim Journal-Token und beim Secret JOURNAL_TOKEN. Bei 403 oder 404 fehlt dem Token das Recht "Issues: Read and write" oder das Repo.
- Journal: "im Worker noch nicht eingerichtet": neuer worker/worker.js ist noch nicht eingespielt oder das Secret JOURNAL_TOKEN fehlt.

ZURÜCK, FALLS ETWAS NICHT KLAPPT
Repo wieder auf "Public" stellen und GitHub Pages (Settings → Pages → Branch main) erneut aktivieren – das alte Cockpit läuft dann wie vorher.

KÜNDIGEN
Domain beim Anbieter kündigen (Frist beachten), danach in Cloudflare die Site entfernen, Worker und Access-Anwendung löschen. Cloudflare hat keine Vertragslaufzeit.
