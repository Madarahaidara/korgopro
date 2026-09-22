/**
 * Test navigateur RÉEL de la liaison web <-> Supabase (Edge/Chrome headless via CDP).
 *
 * Prérequis : un serveur de dev Vite actif (npm run dev).
 * Le navigateur headless est lancé automatiquement (Edge par défaut, ou Chrome).
 *
 * Vérifie dans un vrai moteur de rendu :
 *   - l'application monte sans erreur JS (main.jsx) ;
 *   - web/.env est bien injecté (mode Supabase, pas de comptes de démo) ;
 *   - le client Supabase de l'application atteint réellement l'API depuis
 *     l'origine du navigateur (CORS + réseau, pas de « Failed to fetch ») ;
 *   - Supabase Auth répond (erreur d'identifiants, et non erreur réseau).
 *
 * Usage : node scripts/test-web-browser-live.mjs
 *   KORGO_URL=http://localhost:5173   (défaut : http://localhost:5174)
 *   KORGO_CDP_PORT=9222               (port de débogage)
 */
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { loadEnv } from 'vite';

const BASE_OVERRIDE = (process.env.KORGO_URL || '').replace(/\/$/, '');
const CDP_PORT = Number(process.env.KORGO_CDP_PORT || 9222);
const CDP = `http://127.0.0.1:${CDP_PORT}`;

const env = loadEnv('development', process.cwd(), 'VITE_');
const supabaseUrl = (env.VITE_SUPABASE_URL || '').trim();
const supabaseKey = (env.VITE_SUPABASE_ANON_KEY || '').trim();

let failures = 0;
function check(label, ok, detail = '') {
  if (!ok) failures += 1;
  console.log(`${ok ? 'OK   ' : 'ECHEC'} ${label}${detail ? `  (${detail})` : ''}`);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Détecte le serveur Vite (5173 par défaut, puis 5174 si le port est pris). */
async function resolveBase() {
  if (BASE_OVERRIDE) return BASE_OVERRIDE;
  for (const port of [5173, 5174, 5175]) {
    try {
      await fetch(`http://localhost:${port}/`, { signal: AbortSignal.timeout(2500) });
      return `http://localhost:${port}`;
    } catch (e) {
      /* port suivant */
    }
  }
  throw new Error('Aucun serveur Vite joignable sur 5173/5174/5175. Lancez « npm run dev ».');
}


// ---------------------------------------------------------------------------
// 0. Lancement du navigateur headless (si CDP n'est pas déjà disponible)
// ---------------------------------------------------------------------------
const BROWSERS = [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  '/usr/bin/microsoft-edge',
  '/usr/bin/google-chrome',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
];

async function cdpReady() {
  try {
    await fetch(`${CDP}/json/version`, { signal: AbortSignal.timeout(2000) });
    return true;
  } catch (e) {
    return false;
  }
}

async function ensureBrowser() {
  if (await cdpReady()) {
    console.log('Navigateur déjà disponible sur CDP.');
    return;
  }
  const exe = BROWSERS.find((p) => existsSync(p));
  if (!exe) {
    throw new Error('Edge/Chrome introuvable : lancez-le manuellement avec --remote-debugging-port=' + CDP_PORT);
  }
  console.log(`Lancement de ${exe} (headless, CDP ${CDP_PORT})...`);
  const proc = spawn(exe, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    `--remote-debugging-port=${CDP_PORT}`,
    `--user-data-dir=${join(tmpdir(), 'korgo-cdp-auto')}`,
  ], { stdio: 'ignore', detached: true });
  proc.unref();
  for (let i = 0; i < 40; i += 1) {
    await sleep(500);
    if (await cdpReady()) return;
  }
  throw new Error(`Le navigateur n'a pas exposé CDP sur ${CDP}`);
}

await ensureBrowser();

const BASE = await resolveBase();
console.log(`Application testée : ${BASE}`);

// ---------------------------------------------------------------------------
// 1. Connexion au navigateur
// ---------------------------------------------------------------------------
const targets = await (await fetch(`${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === 'page');
if (!page) {
  console.error('Aucun onglet CDP trouvé. Lancez Edge avec --remote-debugging-port=9222.');
  process.exit(1);
}

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve);
  ws.addEventListener('error', reject);
});

let msgId = 0;
const pending = new Map();
const consoleErrors = [];
const exceptions = [];

ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) reject(new Error(msg.error.message));
    else resolve(msg.result);
    return;
  }
  if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
    consoleErrors.push(msg.params.args.map((a) => a.value ?? a.description ?? '').join(' '));
  }
  if (msg.method === 'Runtime.exceptionThrown') {
    exceptions.push(msg.params.exceptionDetails.exception?.description
      || msg.params.exceptionDetails.text);
  }
});

function send(method, params = {}) {
  const id = ++msgId;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}

async function evaluate(expression) {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) {
    throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  }
  return r.result?.value;
}

/** Attend qu'une expression devienne vraie (le contexte est recréé à la navigation). */
async function waitFor(expression, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    try {
      if (await evaluate(expression)) return true;
    } catch (e) {
      /* contexte pas encore prêt */
    }
    if (Date.now() > deadline) return false;
    await new Promise((r) => setTimeout(r, 300));
  }
}

await send('Runtime.enable');
await send('Page.enable');

// ---------------------------------------------------------------------------
// 2. Chargement de l'application
// ---------------------------------------------------------------------------
console.log(`\n== Chargement de ${BASE} (Edge headless) ==`);
await send('Page.navigate', { url: `${BASE}/` });

const mounted = await waitFor("!!document.querySelector('.login-page')");
check('application montee (page de connexion rendue)', mounted);

console.log('\n== Mode Supabase active dans le navigateur ==');
const labels = await evaluate(
  "Array.from(document.querySelectorAll('.login-field-label')).map(e=>e.textContent).join(' | ')");
check('web/.env pris en compte (.env -> libelle email Supabase)',
  /Email Supabase Auth/i.test(labels || ''), labels);

const bodyText = await evaluate('document.body.innerText');
check('comptes de demonstration masques (mode Supabase)',
  !/Comptes de démonstration/i.test(bodyText || ''));
check('bandeau "Mode local" absent', !/Mode local/i.test(bodyText || ''));
check('mention lecture seule affichee', /lecture seule/i.test(bodyText || ''));

const banner = await evaluate("document.querySelector('.sync-banner')?.innerText.replace(/\\s+/g,' ') || 'absent'");
check('bandeau de synchro absent du login (rendu dans Layout, apres connexion)',
  banner === 'absent', banner);
check('titre de la page de connexion affiche',
  /Connexion/i.test(await evaluate("document.querySelector('.form-title')?.textContent || ''")));

// ---------------------------------------------------------------------------
// 3. Appels Supabase réels depuis l'origine du navigateur
// ---------------------------------------------------------------------------
console.log('\n== Client Supabase de l\u2019application (reseau reel) ==');
const config = await evaluate(`(async () => {
  const m = await import('/src/api/supabase.js');
  return { configured: m.isSupabaseConfigured(), ref: m.supabaseProjectRef() };
})()`);
check('client initialise depuis web/.env',
  config?.configured === true && Boolean(config?.ref), `ref=${config?.ref}`);

const ping = await evaluate(`(async () => {
  const m = await import('/src/api/supabase.js');
  return await m.ping();
})()`);
check('API REST joignable depuis le navigateur (CORS OK)',
  !/failed to fetch|networkerror|load failed/i.test(ping?.message || ''), ping?.message);
check('RLS : refus attendu en role anon (42501)',
  /permission denied/i.test(ping?.message || ''), `latence=${ping?.latency}ms`);

const raw = await evaluate(`(async () => {
  const r = await fetch(${JSON.stringify(`${supabaseUrl}/rest/v1/stores?select=id&limit=1`)}, {
    headers: { apikey: ${JSON.stringify(supabaseKey)} },
  });
  return { status: r.status, body: (await r.text()).slice(0, 90) };
})()`);
check('fetch direct PostgREST : HTTP 401 + code 42501 (pas d\u2019erreur CORS)',
  raw?.status === 401 && /42501/.test(raw?.body || ''), JSON.stringify(raw));

const auth = await evaluate(`(async () => {
  const m = await import('/src/api/authApi.js');
  try {
    await m.login('diag-inexistant@korgo-pro.invalid', 'motdepasse-faux');
    return 'CONNEXION_ACCEPTEE';
  } catch (e) {
    return e.message;
  }
})()`);
check('Supabase Auth repond (identifiants refuses, pas d\u2019erreur reseau)',
  /Connexion Supabase refus/i.test(auth || ''), auth);

// ---------------------------------------------------------------------------
// 4. Console du navigateur
// ---------------------------------------------------------------------------
console.log('\n== Console du navigateur ==');
const realErrors = consoleErrors.filter((m) => !/favicon|DevTools/i.test(m));
check('aucune erreur de console', realErrors.length === 0, realErrors.slice(0, 3).join(' / '));
check('aucune exception JS non geree', exceptions.length === 0, exceptions.slice(0, 2).join(' / '));

// ---------------------------------------------------------------------------
// 5. Fin
// ---------------------------------------------------------------------------
await send('Browser.close').catch(() => {});
ws.close();

console.log(`\n${failures === 0 ? 'TOUS LES TESTS NAVIGATEUR SONT PASSES' : `${failures} TEST(S) EN ECHEC`}`);
process.exitCode = failures === 0 ? 0 : 1;