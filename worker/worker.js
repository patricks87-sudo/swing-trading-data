/**
 * Aktienkänguru – Cloudflare Worker für das Cockpit
 *
 * Zwei Adressen, ein Worker:
 * - cockpit.<domain>: index.html und alle JSON-Dateien aus data/ aus dem
 *   (privaten) GitHub-Repo. Davor sitzt Cloudflare Access (Login); der Worker
 *   prüft zusätzlich das Access-Token, damit er auch bei falsch konfigurierter
 *   Route nichts herausgibt.
 * - <domain> (öffentlich): Startseite aus site/ und unter /public/ nur
 *   Auszüge der Marktdaten – Marktlage, Indizes, Sektoren, Marktmeldungen,
 *   Performance-Kurven. Keine Watchlist, keine Kandidaten, kein Depot, kein Journal.
 *
 * Einstellungen (Cloudflare → Worker → Settings → Variables and Secrets):
 *   GITHUB_TOKEN  (Secret)  Fine-grained Token, nur dieses Repo, Contents: Read-only
 *   REPO                    patricks87-sudo/swing-trading-data
 *   BRANCH                  main
 *   TEAM_DOMAIN             z. B. aktienkaenguru.cloudflareaccess.com
 *   POLICY_AUD              "Application Audience (AUD) Tag" der Access-Anwendung
 *
 * Anleitung: docs/CLOUDFLARE.md
 */

// Cockpit (hinter dem Login): Seite, Logo und alle Daten-Dateien
const ERLAUBT = /^(index\.html|site\/logo\.svg|data\/[A-Za-z0-9_.-]+\.json)$/;
// Öffentliche Startseite: nur diese Dateien aus site/
const OEFFENTLICH = { "": "site/index.html", "index.html": "site/index.html", "brand.css": "site/brand.css", "logo.svg": "site/logo.svg" };
const CACHE_SEKUNDEN = 30;
const TYPEN = { json: "application/json; charset=utf-8", html: "text/html; charset=utf-8", css: "text/css; charset=utf-8", svg: "image/svg+xml" };

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method !== "GET" && request.method !== "HEAD") return text(405, "Nur GET erlaubt");
    const pfad = decodeURIComponent(url.pathname).replace(/^\/+/, "");

    // cockpit.<domain>: nur mit gültigem Cloudflare-Access-Login
    if (url.hostname.startsWith("cockpit.")) {
      if (!(await accessOk(request, env))) return text(403, "Kein Zugriff – bitte über das Login anmelden.");
      const datei = pfad === "" ? "index.html" : pfad;
      if (!ERLAUBT.test(datei)) return text(404, "Nicht gefunden");
      return ausliefern(request, await repoDatei(env, ctx, datei), "private, no-cache");
    }

    // Hauptdomain: öffentliche Startseite und öffentliche Auszüge der Marktdaten
    if (pfad in OEFFENTLICH) return ausliefern(request, await repoDatei(env, ctx, OEFFENTLICH[pfad]), "public, max-age=60");
    if (pfad === "public/news.json") {
      const n = await repoJson(env, ctx, "data/news_summary_today.json");
      return json(request, n && { date: n.date, kernaussage: n.kernaussage, lage: n.lage, lage_stand_local: n.lage_stand_local, meldungen: n.meldungen });
    }
    if (pfad === "public/markt.json") {
      // neuester Feed-Lauf, nur Markt-Felder (keine Watchlist, keine Kandidaten)
      const laeufe = (await Promise.all(["p4", "p5", "p55", "p1"].map((r) => repoJson(env, ctx, "data/" + r + "_latest.json")))).filter(Boolean);
      const f = laeufe.sort((a, b) => new Date(b.generated_at_utc) - new Date(a.generated_at_utc))[0];
      const gold = f && f.rohstoffe && f.rohstoffe.werte && f.rohstoffe.werte.GOLD;
      return json(request, f && { generated_at_utc: f.generated_at_utc, run: f.run, regime: f.regime, indices: f.indices, macro: f.macro, sectors: f.sectors,
        rohstoffe: gold ? { werte: { GOLD: { close: gold.close, tagesbewegung_pct: gold.tagesbewegung_pct } } } : undefined });
    }
    if (pfad === "public/performance.json") {
      // Simulation als Kurven und Kennzahlen, ohne einzelne Trades
      const p = await repoJson(env, ctx, "data/performance.json"), st = (p && p.statistik && p.statistik.neu) || {};
      return json(request, p && { generated_at_utc: p.generated_at_utc, hinweis: p.hinweis, start: p.start, daten: p.daten, reihen: p.reihen, zusammenfassung: p.zusammenfassung,
        statistik: { neu: { trefferquote_pct: st.trefferquote_pct, trades_abgeschlossen: st.trades_abgeschlossen, trades_offen: st.trades_offen,
          schnitt_trade_eur: st.schnitt_trade_eur, bester_trade_eur: st.bester_trade_eur, schlechtester_trade_eur: st.schlechtester_trade_eur } } });
    }
    return text(404, "Nicht gefunden");
  },
};

// Datei aus dem Repo, kurz am Cloudflare-Rand zwischengespeichert, damit nicht jeder Aufruf GitHub trifft
async function repoDatei(env, ctx, pfad) {
  const cache = caches.default;
  const schluessel = new Request("https://cache.intern/" + pfad);
  let antwort = await cache.match(schluessel);
  if (antwort) return antwort;
  const gh = await fetch(
    "https://api.github.com/repos/" + env.REPO + "/contents/" + pfad + "?ref=" + encodeURIComponent(env.BRANCH || "main"),
    {
      headers: {
        Authorization: "Bearer " + env.GITHUB_TOKEN,
        Accept: "application/vnd.github.raw",
        "User-Agent": "aktienkaenguru-worker",
        "X-GitHub-Api-Version": "2022-11-28",
      },
    },
  );
  if (gh.status === 404) return text(404, "Nicht gefunden");
  if (!gh.ok) return text(502, "GitHub antwortet nicht wie erwartet (" + gh.status + ")");
  antwort = new Response(gh.body, {
    headers: { "Content-Type": TYPEN[pfad.split(".").pop()] || "application/octet-stream", "Cache-Control": "public, max-age=" + CACHE_SEKUNDEN },
  });
  ctx.waitUntil(cache.put(schluessel, antwort.clone()));
  return antwort;
}

async function repoJson(env, ctx, pfad) {
  const a = await repoDatei(env, ctx, pfad);
  if (a.status !== 200) return null;
  try { return await a.clone().json(); } catch (e) { return null; }
}

function ausliefern(request, antwort, cacheControl) {
  if (antwort.status !== 200) return antwort;
  const h = new Headers(antwort.headers);
  h.set("Cache-Control", cacheControl);
  h.set("X-Frame-Options", "DENY");
  h.set("X-Content-Type-Options", "nosniff");
  h.set("Referrer-Policy", "strict-origin-when-cross-origin");
  return new Response(request.method === "HEAD" ? null : antwort.body, { status: 200, headers: h });
}

function json(request, daten) {
  if (!daten) return text(404, "Noch keine Daten");
  return ausliefern(request, new Response(JSON.stringify(daten), { headers: { "Content-Type": TYPEN.json } }), "public, max-age=60");
}

function text(status, body) {
  return new Response(body, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
}

// ---- Cloudflare-Access-Token (JWT) prüfen ----
let SCHLUESSEL = null, SCHLUESSEL_ZEIT = 0;

async function accessOk(request, env) {
  if (!env.TEAM_DOMAIN || !env.POLICY_AUD) return false; // ohne Konfiguration nichts herausgeben
  const jwt = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!jwt) return false;
  const teile = jwt.split(".");
  if (teile.length !== 3) return false;
  let kopf, inhalt;
  try {
    kopf = JSON.parse(b64text(teile[0]));
    inhalt = JSON.parse(b64text(teile[1]));
  } catch (e) {
    return false;
  }
  const jetzt = Math.floor(Date.now() / 1000);
  const aud = Array.isArray(inhalt.aud) ? inhalt.aud : [inhalt.aud];
  if (!aud.includes(env.POLICY_AUD)) return false;
  if (inhalt.iss !== "https://" + env.TEAM_DOMAIN) return false;
  if (typeof inhalt.exp !== "number" || inhalt.exp < jetzt) return false;

  const jwk = (await zertifikate(env.TEAM_DOMAIN)).find((k) => k.kid === kopf.kid);
  if (!jwk) return false;
  const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  return crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, b64bytes(teile[2]), new TextEncoder().encode(teile[0] + "." + teile[1]));
}

async function zertifikate(team) {
  if (SCHLUESSEL && Date.now() - SCHLUESSEL_ZEIT < 3600 * 1000) return SCHLUESSEL;
  const r = await fetch("https://" + team + "/cdn-cgi/access/certs");
  SCHLUESSEL = r.ok ? (await r.json()).keys || [] : [];
  SCHLUESSEL_ZEIT = Date.now();
  return SCHLUESSEL;
}

function b64bytes(s) {
  const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

function b64text(s) {
  return new TextDecoder().decode(b64bytes(s));
}
