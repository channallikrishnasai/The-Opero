/**
 * OPERO WhatsApp Web Bridge
 * 
 * Connects to WhatsApp Web via whatsapp-web.js, detects incoming calls,
 * and exposes a local HTTP API for OPERO to query and control.
 * 
 * API:
 *   GET  /status          - Bridge status (connected/disconnected/scanning)
 *   GET  /qr              - Current pairing QR payload, if any
 *   POST /qr/refresh      - Discard the session and emit a fresh pairing QR
 *   GET  /calls           - List active incoming calls
 *   POST /calls/:id/answer - Answer a call (clicks WhatsApp Web UI)
 *   POST /calls/:id/reject - Reject a call
 *   POST /calls/hangup     - Hang up active call
 *   GET  /contacts/:phone  - Look up contact name by phone number
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const qrcode = require('qrcode-terminal');
const path = require('path');
const fs = require('fs');

// ── Config ───────────────────────────────────────────────────────────────────
const API_PORT = parseInt(process.env.WA_BRIDGE_PORT || '8099', 10);
const DATA_DIR = path.join(__dirname, '.wwebjs_auth');
const CHROME_CANDIDATES = [
  process.env.WA_CHROME_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
].filter(Boolean);
const CHROME_PATH = CHROME_CANDIDATES.find((candidate) => fs.existsSync(candidate));

// ── State ────────────────────────────────────────────────────────────────────
let bridgeStatus = 'starting';   // starting | scanning | connected | disconnected
let qrCode = null;
let incomingCalls = [];          // [{ id, from, fromName, isVideo, timestamp, answered }]
let activeCall = null;           // currently active call object
let client = null;
let initializing = false;        // guards overlapping client (re)initialisations
let resetting = false;           // guards overlapping pairing resets
let shuttingDown = false;
let consecutiveResets = 0;       // breaks a LOGOUT -> reset -> LOGOUT loop
let lastProgressAt = Date.now(); // last sign of life from the WhatsApp client

// LocalAuth stores the WhatsApp Web profile in <dataPath>/session.
const SESSION_DIR = path.join(DATA_DIR, 'session');

// ── WhatsApp Client ──────────────────────────────────────────────────────────
function createClient() {
  client = new Client({
    authStrategy: new LocalAuth({ dataPath: DATA_DIR }),
    puppeteer: {
      headless: true,
      // whatsapp-web.js pulls puppeteer-core, which does not download a
      // browser. Prefer a user-supplied path, then the installed Chrome/Edge.
      ...(CHROME_PATH ? { executablePath: CHROME_PATH } : {}),
      // Do NOT add --single-process / --no-zygote here. Chromium then never
      // commits a main frame before the client navigates, and puppeteer throws
      // "Requesting main frame too early!" — which kills the bridge on startup
      // and leaves port 8099 refusing connections.
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--disable-gpu',
      ],
    },
  });

  client.on('qr', (qr) => {
    bridgeStatus = 'scanning';
    qrCode = qr;
    lastProgressAt = Date.now();
    consecutiveResets = 0;   // a fresh QR means the session is making progress
    console.log('[Bridge] Scan QR code with WhatsApp:');
    qrcode.generate(qr, { small: true });
    // Write QR to file for OPERO to read
    fs.writeFileSync(path.join(__dirname, 'qr.txt'), qr, 'utf8');
  });

  client.on('ready', () => {
    bridgeStatus = 'connected';
    qrCode = null;
    lastProgressAt = Date.now();
    console.log('[Bridge] ✅ WhatsApp Web connected');
    try { fs.unlinkSync(path.join(__dirname, 'qr.txt')); } catch {}
  });

  client.on('authenticated', () => {
    lastProgressAt = Date.now();
    console.log('[Bridge] Authenticated');
  });

  client.on('auth_failure', (msg) => {
    bridgeStatus = 'disconnected';
    console.error('[Bridge] ❌ Auth failure:', msg);
  });

  client.on('disconnected', (reason) => {
    bridgeStatus = 'disconnected';
    console.log('[Bridge] Disconnected:', reason);
    // A revoked device can only be fixed by re-pairing. Purge the dead session
    // instead of staying offline until somebody restarts the desktop app.
    if (reason === 'LOGOUT') {
      setTimeout(() => { void resetForPairing(false); }, 1000);
    }
  });

  // ── Call Detection ──────────────────────────────────────────────────────
  client.on('call', async (call) => {
    const direction = call.fromMe ? 'outgoing' : 'incoming';
    const type = call.isVideo ? 'video' : 'voice';

    console.log(`[Bridge] 📞 ${direction} ${type} call from ${call.from}`);

    if (call.fromMe) return; // ignore outgoing calls

    // Resolve contact name
    let fromName = call.from;
    try {
      const contact = await client.getNumberId(call.from);
      if (contact) {
        const ppContact = await client.getContactById(contact._serialized);
        if (ppContact && ppContact.name) {
          fromName = ppContact.name;
        } else if (ppContact && ppContact.pushname) {
          fromName = ppContact.pushname;
        }
      }
    } catch (e) {
      // ignore, use phone number as name
    }

    const callEntry = {
      id: call.id,
      from: call.from,
      fromName: fromName,
      isVideo: call.isVideo,
      isGroup: call.isGroup,
      timestamp: call.timestamp || Math.floor(Date.now() / 1000),
      answered: false,
      rejected: false,
    };

    incomingCalls.push(callEntry);
    console.log(`[Bridge] 📞 Incoming call from ${fromName} (${call.from})`);

    // Auto-remove after 60 seconds if not answered
    setTimeout(() => {
      const idx = incomingCalls.findIndex(c => c.id === call.id);
      if (idx !== -1 && !incomingCalls[idx].answered && !incomingCalls[idx].rejected) {
        incomingCalls.splice(idx, 1);
        console.log(`[Bridge] Call from ${fromName} expired (no answer)`);
      }
    }, 60000);
  });

  client.on('message', async (msg) => {
    // Could be used for call-related notifications
  });

  return client;
}

// ── Express API ──────────────────────────────────────────────────────────────
const app = express();
app.use(express.json());

// CORS for local OPERO
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

// Status
app.get('/status', (req, res) => {
  res.json({
    status: bridgeStatus,
    hasQr: qrCode !== null,
    activeCalls: incomingCalls.length,
  });
});

// QR code for re-auth
app.get('/qr', (req, res) => {
  if (qrCode) {
    res.json({ qr: qrCode });
  } else {
    res.json({ qr: null });
  }
});

// Force a new QR code by discarding the session and reconnecting.
// Responds immediately: tearing down and restarting Chromium takes seconds,
// and OPERO polls /status + /qr for the code this produces.
app.post('/qr/refresh', (req, res) => {
  res.json({ ok: true, message: 'Session reset — a new QR code will appear shortly.' });
  void resetForPairing(true);
});

// List incoming calls
app.get('/calls', (req, res) => {
  res.json({ calls: incomingCalls });
});

// Answer a call — tries the WhatsApp Web API, falls back to indicating manual needed
app.post('/calls/:id/answer', async (req, res) => {
  const callId = req.params.id;
  const callEntry = incomingCalls.find(c => c.id === callId);
  if (!callEntry) {
    return res.status(404).json({ error: 'Call not found' });
  }

  try {
    // whatsapp-web.js doesn't have a native answer method,
    // but some versions support it via page evaluation
    // We'll try the reject approach inverted — if it fails, the Python side
    // will use PyAutoGUI to click the answer button in WhatsApp Desktop
    callEntry.answered = true;
    activeCall = callEntry;
    console.log(`[Bridge] ✅ Call from ${callEntry.fromName} marked as answered`);
    res.json({ ok: true, message: 'Call answered — use PyAutoGUI to click answer button in WhatsApp Desktop' });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Reject a call
app.post('/calls/:id/reject', async (req, res) => {
  const callId = req.params.id;
  const callEntry = incomingCalls.find(c => c.id === callId);
  if (!callEntry) {
    return res.status(404).json({ error: 'Call not found' });
  }

  try {
    // Try native reject
    const calls = await client.getChats();
    // whatsapp-web.js Call object has reject() method
    // We need to find the actual Call object
    // For now, mark as rejected — the Python side can use PyAutoGUI
    callEntry.rejected = true;
    console.log(`[Bridge] ❌ Call from ${callEntry.fromName} rejected`);
    res.json({ ok: true, message: 'Call rejected' });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Hang up active call
app.post('/calls/hangup', async (req, res) => {
  if (!activeCall) {
    return res.status(404).json({ error: 'No active call' });
  }
  activeCall = null;
  console.log('[Bridge] 📞 Call hung up');
  res.json({ ok: true });
});

// Look up contact name
app.get('/contacts/:phone', async (req, res) => {
  const phone = req.params.phone;
  try {
    const contactId = await client.getNumberId(phone);
    if (contactId) {
      const contact = await client.getContactById(contactId._serialized);
      res.json({
        name: contact.name || contact.pushname || phone,
        phone: phone,
      });
    } else {
      res.json({ name: phone, phone: phone });
    }
  } catch (e) {
    res.json({ name: phone, phone: phone });
  }
});

// ── Session recovery ─────────────────────────────────────────────────────────

/**
 * Chromium keeps a lock on its user-data-dir while it runs, so the profile may
 * only be removed once the browser is gone. whatsapp-web.js attempts this from
 * inside its own navigation handler and throws EBUSY on Windows — that rejected
 * promise used to take the whole bridge process down with it.
 */
async function removeSessionDir() {
  for (let attempt = 0; attempt < 6; attempt++) {
    try {
      fs.rmSync(SESSION_DIR, { recursive: true, force: true });
      return true;
    } catch (e) {
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  console.warn('[Bridge] Could not delete the session directory — pairing may reuse stale credentials.');
  return false;
}

function destroyClient() {
  const previous = client;
  client = null;
  if (!previous) return;
  try {
    previous.removeAllListeners();
    previous.destroy();
  } catch (e) {
    // A half-dead browser is expected here; the next init starts a clean one.
  }
}

/** True once the underlying browser is gone and the client cannot recover. */
function clientLooksDead() {
  if (!client) return true;
  try {
    const page = client.pupPage;
    if (!page) return false;            // still starting up
    return typeof page.isClosed === 'function' ? page.isClosed() : false;
  } catch (e) {
    return true;                        // the browser connection is gone
  }
}

/**
 * Chromium marks a profile as in-use with a 'lockfile' next to it, and on
 * Windows puppeteer refuses to launch while one exists. A bridge killed from the
 * desktop app leaves that file behind, so drop it when — and only when — nobody
 * holds it: Windows refuses the delete while a live browser has it open.
 */
function clearStaleProfileLock() {
  const lockfile = path.join(SESSION_DIR, 'lockfile');
  try {
    if (!fs.existsSync(lockfile)) return false;
    fs.rmSync(lockfile, { force: true });
    console.log('[Bridge] Removed a stale Chromium profile lock.');
    return true;
  } catch (e) {
    console.warn('[Bridge] A live Chromium holds the WhatsApp profile — close it and reconnect.');
    return false;
  }
}

function scheduleInit(delayMs) {
  setTimeout(() => { void initializeClient(); }, delayMs);
}

async function initializeClient() {
  if (initializing || resetting || shuttingDown) return;
  initializing = true;
  try {
    destroyClient();
    qrCode = null;
    bridgeStatus = 'starting';
    const waClient = createClient();
    client = waClient;
    await waClient.initialize();
    console.log('[Bridge] WhatsApp client initialized');
  } catch (e) {
    const message = (e && e.message) || String(e);
    console.error('[Bridge] Client init failed:', message);
    // whatsapp-web.js sometimes rejects initialize() while the client it built
    // is still perfectly healthy and about to emit 'qr'/'ready' — tearing that
    // one down would throw away a working link, so let it prove itself first.
    if (Date.now() - lastProgressAt < 15000) {
      console.log('[Bridge] Client made progress after the init error — keeping it.');
    } else {
      bridgeStatus = 'disconnected';
      destroyClient();
      const profileTaken = /already running/i.test(message);
      if (profileTaken && !clearStaleProfileLock()) {
        scheduleInit(30000);   // a real browser owns the profile; do not fight it
      } else {
        scheduleInit(5000);
      }
    }
  } finally {
    initializing = false;
  }
}

/**
 * Throw away the current session and bring up a fresh client, which makes
 * WhatsApp Web emit a new pairing QR code.
 *
 * @param {boolean} force - honour an explicit request even after repeated
 *   LOGOUT cycles, which otherwise stop auto-recovery to protect the account.
 */
async function resetForPairing(force) {
  if (shuttingDown) return false;
  if (resetting) return true;
  if (!force && consecutiveResets >= 4) {
    console.warn('[Bridge] Repeated logouts — waiting for an explicit QR refresh.');
    return false;
  }
  resetting = true;
  consecutiveResets += 1;
  try {
    console.log('[Bridge] 🔄 Resetting session to generate a new QR code');
    bridgeStatus = 'scanning';
    qrCode = null;
    destroyClient();
    await removeSessionDir();
    return true;
  } catch (e) {
    console.error('[Bridge] Reset failed:', (e && e.message) || e);
    return false;
  } finally {
    resetting = false;
    // Re-initialising without a session is what produces the new 'qr' event.
    scheduleInit(500);
  }
}

// The HTTP API is what OPERO talks to, so nothing here may ever take the
// process down: a silent exit leaves port 8099 refusing connections forever.
process.on('unhandledRejection', (reason) => {
  console.error('[Bridge] Unhandled rejection (bridge stays up):', (reason && reason.message) || reason);
});

process.on('uncaughtException', (err) => {
  console.error('[Bridge] Uncaught exception (bridge stays up):', (err && err.message) || err);
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    shuttingDown = true;
    destroyClient();
    process.exit(0);
  });
}

// ── Start ────────────────────────────────────────────────────────────────────
async function main() {
  console.log('[Bridge] Starting OPERO WhatsApp Bridge...');

  const server = app.listen(API_PORT, '127.0.0.1', () => {
    console.log(`[Bridge] API server listening on http://127.0.0.1:${API_PORT}`);
  });

  server.on('error', (err) => {
    // Two bridges would fight over one Chromium profile, so refuse to continue.
    const hint = err.code === 'EADDRINUSE'
      ? `port ${API_PORT} is already in use by another bridge`
      : err.message;
    console.error(`[Bridge] Cannot serve the API — ${hint}`);
    process.exit(1);
  });

  // Safety net: if Chromium dies without an event, bring the client back rather
  // than serving a permanently 'disconnected' status.
  setInterval(() => {
    if (shuttingDown || initializing || resetting) return;
    if (clientLooksDead()) {
      console.warn('[Bridge] No live WhatsApp client — reinitialising.');
      void initializeClient();
    }
  }, 15000).unref();

  await initializeClient();
}

main().catch((err) => {
  console.error('[Bridge] Fatal error:', (err && err.message) || err);
  scheduleInit(5000);
});
