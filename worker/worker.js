/**
 * Aktienkänguru – Cloudflare Worker für das Cockpit
 *
 * Liefert index.html und die JSON-Dateien aus data/ aus dem (privaten)
 * GitHub-Repo aus. Davor sitzt Cloudflare Access (Login); der Worker prüft
 * zusätzlich das Access-Token, damit er auch bei falsch konfigurierter Route
 * nichts herausgibt.
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

const ERLAUBT = /^(index\.html|data\/[A-Za-z0-9_.-]+\.json)$/;
const CACHE_SEKUNDEN = 30;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method !== "GET" && request.method !== "HEAD") return text(405, "Nur GET erlaubt");

    if (!(await accessOk(request, env))) return text(403, "Kein Zugriff – bitte über das Login anmelden.");

    let pfad = decodeURIComponent(url.pathname).replace(/^\/+/, "");
    if (pfad === "") pfad = "index.html";
    if (!ERLAUBT.test(pfad)) return text(404, "Nicht gefunden");

    // Kurzer Zwischenspeicher am Cloudflare-Rand, damit nicht jeder Aufruf GitHub trifft
    const cache = caches.default;
    const schluessel = new Request("https://cache.intern/" + pfad);
    let antwort = await cache.match(schluessel);
    if (!antwort) {
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
        headers: {
          "Content-Type": pfad.endsWith(".json") ? "application/json; charset=utf-8" : "text/html; charset=utf-8",
          "Cache-Control": "public, max-age=" + CACHE_SEKUNDEN,
        },
      });
      ctx.waitUntil(cache.put(schluessel, antwort.clone()));
    }

    const h = new Headers(antwort.headers);
    h.set("Cache-Control", "private, no-cache");
    h.set("X-Frame-Options", "DENY");
    h.set("X-Content-Type-Options", "nosniff");
    h.set("Referrer-Policy", "strict-origin-when-cross-origin");
    return new Response(request.method === "HEAD" ? null : antwort.body, { status: 200, headers: h });
  },
};

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
