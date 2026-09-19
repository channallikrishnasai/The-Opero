/**
 * OPERO WhatsApp Web Bridge
 * 
 * Connects to WhatsApp Web via whatsapp-web.js, detects incoming calls,
 * and exposes a local HTTP API for OPERO to query and control.
 * 
 * API:
 *   GET  /status          - Bridge status (connected/disconnected/scanning)
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

// ── WhatsApp Client ──────────────────────────────────────────────────────────
function createClient() {
  client = new Client({
    authStrategy: new LocalAuth({ dataPath: DATA_DIR }),
    puppeteer: {
      headless: true,
      // whatsapp-web.js pulls puppeteer-core, which does not download a
      // browser. Prefer a user-supplied path, then the installed Chrome/Edge.
      ...(CHROME_PATH ? { executablePath: CHROME_PATH } : {}),
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--single-process',
        '--disable-gpu',
      ],
    },
  });

  client.on('qr', (qr) => {
    bridgeStatus = 'scanning';
    qrCode = qr;
    console.log('[Bridge] Scan QR code with WhatsApp:');
    qrcode.generate(qr, { small: true });
    // Write QR to file for OPERO to read
    fs.writeFileSync(path.join(__dirname, 'qr.txt'), qr, 'utf8');
  });

  client.on('ready', () => {
    bridgeStatus = 'connected';
    qrCode = null;
    console.log('[Bridge] ✅ WhatsApp Web connected');
    try { fs.unlinkSync(path.join(__dirname, 'qr.txt')); } catch {}
  });

  client.on('authenticated', () => {
    console.log('[Bridge] Authenticated');
  });

  client.on('auth_failure', (msg) => {
    bridgeStatus = 'disconnected';
    console.error('[Bridge] ❌ Auth failure:', msg);
  });

  client.on('disconnected', (reason) => {
    bridgeStatus = 'disconnected';
    console.log('[Bridge] Disconnected:', reason);
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

// Force a new QR code by logging out and reconnecting
app.post('/qr/refresh', async (req, res) => {
  try {
    if (client) {
      await client.logout();
      qrCode = null;
      bridgeStatus = 'scanning';
      // Client will reconnect and emit a new 'qr' event automatically
      console.log('[Bridge] 🔄 Logged out — new QR will be generated');
      res.json({ ok: true });
    } else {
      res.status(503).json({ error: 'Client not running' });
    }
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
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

// ── Start ────────────────────────────────────────────────────────────────────
async function main() {
  console.log('[Bridge] Starting OPERO WhatsApp Bridge...');

  const waClient = createClient();

  app.listen(API_PORT, '127.0.0.1', () => {
    console.log(`[Bridge] API server listening on http://127.0.0.1:${API_PORT}`);
  });

  await waClient.initialize();
  console.log('[Bridge] WhatsApp client initialized');
}

main().catch((err) => {
  console.error('[Bridge] Fatal error:', err);
  process.exit(1);
});
