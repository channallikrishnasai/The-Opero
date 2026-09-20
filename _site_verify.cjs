/* Temporary harness: render site/index.html in Chrome, capture shots + console errors. */
const path = require('path');
const fs = require('fs');
const puppeteer = require('./whatsapp_bridge/node_modules/puppeteer');

const PAGE = 'file:///' + path.resolve(__dirname, 'site', 'index.html').replace(/\\/g, '/');
const OUT = path.join(__dirname, '_site_shots');

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: fs.existsSync(CHROME) ? CHROME : undefined,
    args: [
      '--no-sandbox', '--disable-setuid-sandbox',
      '--use-gl=angle', '--use-angle=swiftshader',
      '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
      '--window-size=1440,900',
    ],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });

  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errors.push(m.type() + ': ' + m.text()); });
  page.on('requestfailed', r => errors.push('requestfailed: ' + r.url() + ' ' + (r.failure() || {}).errorText));

  await page.goto(PAGE, { waitUntil: 'load', timeout: 60000 });
  await new Promise(r => setTimeout(r, 3500));   // let the galaxy spin up and counters run

  const stats = await page.evaluate(() => window.__operoSite ? window.__operoSite.stats() : null);
  const counts = await page.evaluate(() => ({
    features: document.querySelectorAll('.feat-card').length,
    chips: document.querySelectorAll('.chip').length,
    flows: document.querySelectorAll('.auto-card').length,
    steps: document.querySelectorAll('.step').length,
    webgl: (() => { try { return !!document.getElementById('galaxy').getContext('webgl2') || !!document.getElementById('galaxy').getContext('webgl'); } catch (e) { return 'err'; } })(),
    canvasSize: (() => { const c = document.getElementById('galaxy'); return c.width + 'x' + c.height; })(),
  }));

  await page.screenshot({ path: path.join(OUT, '01-hero.png') });

  // scroll through the page for section shots
  const shots = [['02-about', '#about'], ['03-features', '#features'], ['04-automations', '#automations'], ['05-arch', '#arch'], ['06-demo', '#demo']];
  for (const [name, sel] of shots) {
    await page.evaluate(s => document.querySelector(s).scrollIntoView({ block: 'start' }), sel);
    await new Promise(r => setTimeout(r, 1400));
    await page.screenshot({ path: path.join(OUT, name + '.png') });
  }

  // interact: filter the feature grid, then hover a chain
  await page.evaluate(() => document.querySelector('#features').scrollIntoView({ block: 'start' }));
  await new Promise(r => setTimeout(r, 400));
  const chip = await page.$('.chip[data-g="Build"]');
  if (chip) { await chip.click(); await new Promise(r => setTimeout(r, 600)); }
  const filtered = await page.evaluate(() => document.querySelectorAll('.feat-card').length);
  await page.screenshot({ path: path.join(OUT, '07-filtered.png') });

  console.log(JSON.stringify({ stats, counts, filteredFeatures: filtered, errors }, null, 1));
  await browser.close();
})().catch(e => { console.error('HARNESS FAILURE', e); process.exit(1); });
