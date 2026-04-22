const express = require('express');
const cors = require('cors');
const { connect } = require('puppeteer-real-browser');
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const { spawn } = require('child_process');
const recaptchaV3 = require('./recaptchav3');

puppeteer.use(StealthPlugin());

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const app = express();
const port = process.env.PRIVATE_SOLVER_PORT || 7860;
const MAX_CONCURRENT = Number(process.env.PRIVATE_SOLVER_MAX_CONCURRENT || 3);
const DEBUG_DIR = process.env.PRIVATE_SOLVER_DEBUG_DIR || path.join(__dirname, 'debug');
let active = 0;

app.use(cors());
app.use(express.json({ limit: '2mb' }));
fs.mkdirSync(DEBUG_DIR, { recursive: true });

function traceId() {
  return crypto.randomBytes(6).toString('hex');
}

function logEvent(event, fields = {}) {
  console.log(JSON.stringify({ time: new Date().toISOString(), event, ...fields }));
}

async function createBrowser() {
  const { browser, page } = await connect({
    headless: false,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-accelerated-2d-canvas',
      '--no-first-run',
      '--no-zygote',
      '--disable-gpu',
      '--window-size=1920,1080'
    ],
    connectOption: { defaultViewport: null }
  });
  return { browser, page };
}

app.get('/', (_req, res) => res.json({ status: 'ok', service: 'private-captcha-token-harvest', version: '0.1.0', active, maxConcurrent: MAX_CONCURRENT }));

app.post('/recaptchav3', async (req, res) => {
  const requestId = traceId();
  const startedAt = Date.now();
  const { url, siteKey, action } = req.body || {};
  if (!url || !siteKey) return res.status(400).json({ status: 'error', requestId, message: 'Missing url or siteKey' });
  if (active >= MAX_CONCURRENT) return res.status(429).json({ status: 'busy', requestId, message: 'Server busy' });

  active++;
  let browser = null;
  logEvent('recaptchav3_start', { requestId, url, action: action || 'submit' });
  try {
    const created = await createBrowser();
    browser = created.browser;
    const token = await recaptchaV3(created.page, url, siteKey, action || 'submit');
    const durationMs = Date.now() - startedAt;
    logEvent('recaptchav3_success', { requestId, durationMs, tokenLength: token.length });
    res.json({ status: 'success', requestId, durationMs, token });
  } catch (error) {
    const durationMs = Date.now() - startedAt;
    const message = error?.message || String(error);
    logEvent('recaptchav3_error', { requestId, durationMs, message });
    res.status(500).json({ status: 'error', requestId, durationMs, message });
  } finally {
    if (browser) {
      try { await browser.close(); } catch (_) {}
    }
    active--;
  }
});

app.post('/recaptchav2', async (req, res) => {
  const requestId = traceId();
  const startedAt = Date.now();
  const { provider, model, maxRounds, debug } = req.body || {};
  if (active >= MAX_CONCURRENT) return res.status(429).json({ status: 'busy', requestId, message: 'Server busy' });

  active++;
  let browser = null;
  logEvent('recaptchav2_start', { requestId, provider: provider || 'gemini-cli', maxRounds: maxRounds || 5 });
  try {
    const created = await createBrowser();
    browser = created.browser;

    const payload = {
      provider: provider || 'gemini-cli',
      model: model || null,
      max_rounds: Number(maxRounds || 5),
      debug: debug !== false
    };

    const py = spawn('/root/.openclaw/workspace/projects/private-captcha-solver/.venv/bin/python', ['recaptchav2_runner.py'], {
      cwd: __dirname,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';
    py.stdout.on('data', (d) => { stdout += d.toString(); });
    py.stderr.on('data', (d) => { stderr += d.toString(); });
    py.stdin.write(JSON.stringify(payload));
    py.stdin.end();

    const exitCode = await new Promise((resolve) => py.on('close', resolve));
    if (exitCode !== 0) {
      throw new Error(stderr || stdout || `recaptchav2 runner exited with ${exitCode}`);
    }

    const result = JSON.parse(stdout || '{}');
    const durationMs = Date.now() - startedAt;
    logEvent('recaptchav2_done', { requestId, durationMs, stage: result.stage, verified: result.verified });
    res.json({ requestId, durationMs, ...result });
  } catch (error) {
    const durationMs = Date.now() - startedAt;
    const message = error?.message || String(error);
    logEvent('recaptchav2_error', { requestId, durationMs, message });
    res.status(500).json({ status: 'error', requestId, durationMs, message });
  } finally {
    if (browser) {
      try { await browser.close(); } catch (_) {}
    }
    active--;
  }
});

app.listen(port, () => console.log(`Private token-harvest server running on ${port}`));
