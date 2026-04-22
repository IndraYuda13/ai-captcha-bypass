const delay = ms => new Promise(res => setTimeout(res, ms));

async function waitForGrecaptcha(page, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const ready = await page.evaluate(() => !!(window.grecaptcha && window.grecaptcha.execute));
    if (ready) return true;
    await delay(500);
  }
  return false;
}

async function ensureGrecaptcha(page, siteKey) {
  let ready = await waitForGrecaptcha(page, 10000);
  if (ready) return true;
  await page.evaluate((key) => {
    const existing = document.querySelector(`script[src*="recaptcha/api.js?render=${key}"]`);
    if (existing) return;
    const script = document.createElement('script');
    script.src = `https://www.google.com/recaptcha/api.js?render=${key}`;
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);
  }, siteKey);
  ready = await waitForGrecaptcha(page, 10000);
  return ready;
}

module.exports = async function recaptchaV3(page, url, siteKey, action = 'submit') {
  await page.setRequestInterception(false);
  try {
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
  } catch (_) {}

  try {
    await page.mouse.move(100, 100);
    await page.mouse.move(220, 180, { steps: 8 });
  } catch (_) {}

  const ready = await ensureGrecaptcha(page, siteKey);
  if (!ready) throw new Error('Failed to load grecaptcha library');

  const token = await page.evaluate(async (key, act) => {
    return new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('grecaptcha.execute timeout')), 30000);
      try {
        window.grecaptcha.ready(() => {
          window.grecaptcha.execute(key, { action: act })
            .then(token => {
              clearTimeout(t);
              resolve(token || '');
            })
            .catch(err => {
              clearTimeout(t);
              reject(err);
            });
        });
      } catch (e) {
        clearTimeout(t);
        reject(e);
      }
    });
  }, siteKey, action);

  if (!token) throw new Error('Token returned empty');
  return token;
};
