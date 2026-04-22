// Helper delay
const delay = ms => new Promise(res => setTimeout(res, ms));

module.exports = async function(page, url, siteKey, action = 'submit') {
    return new Promise(async (resolve, reject) => {
        // Global Timeout 60 Detik (Server Side)
        const timeoutTimer = setTimeout(() => reject(new Error("Timeout Global (60s)")), 60000);

        try {
            console.log(`[RV3] Processing: ${url} | Action: ${action}`);

            // 1. Matikan Intercept (Biarkan loading 100% natural)
            await page.setRequestInterception(false);

            // 2. Navigasi & Tunggu Network Tenang
            // Kita pakai 'networkidle2' agar script Google pasti termuat
            try {
                await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
            } catch (e) {
                console.log("[RV3] Navigation timeout, but proceeding...");
            }

            // 3. Simulasi Manusia (Pancingan Mouse)
            try {
                await page.mouse.move(100, 100);
                await page.mouse.move(200, 200, { steps: 5 });
            } catch (e) {}

            // 4. Eksekusi Token (Logic di dalam Browser)
            const token = await page.evaluate(async (key, act) => {
                return new Promise(async (res, rej) => {
                    // Timeout Internal Browser 30 Detik (Diperpanjang)
                    const t = setTimeout(() => rej("Google Execute Timeout (30s)"), 30000);

                    // Fungsi Tunggu Library Google
                    const waitForGrecaptcha = () => {
                        return new Promise(resolve => {
                            let attempts = 0;
                            const check = setInterval(() => {
                                attempts++;
                                if (typeof window.grecaptcha !== 'undefined' && window.grecaptcha.execute) {
                                    clearInterval(check);
                                    resolve(true);
                                }
                                if (attempts > 20) { // 10 detik nunggu
                                    clearInterval(check);
                                    resolve(false);
                                }
                            }, 500);
                        });
                    };

                    // Cek & Inject
                    let ready = await waitForGrecaptcha();
                    
                    if (!ready) {
                        console.log("Injecting script manually...");
                        const script = document.createElement('script');
                        script.src = `https://www.google.com/recaptcha/api.js?render=${key}`;
                        script.async = true;
                        script.defer = true;
                        document.head.appendChild(script);
                        // Tunggu lagi setelah inject
                        ready = await waitForGrecaptcha();
                    }

                    if (!ready) {
                        clearTimeout(t);
                        rej("Failed to load grecaptcha library");
                        return;
                    }

                    // Eksekusi Final
                    try {
                        window.grecaptcha.ready(() => {
                            window.grecaptcha.execute(key, { action: act })
                                .then(token => {
                                    clearTimeout(t);
                                    res(token);
                                })
                                .catch(err => {
                                    clearTimeout(t);
                                    rej("Execution Error: " + (err.message || err));
                                });
                        });
                    } catch (e) {
                        clearTimeout(t);
                        rej("Critical Error: " + e.message);
                    }
                });
            }, siteKey, action);

            clearTimeout(timeoutTimer);
            
            if (token) {
                console.log(`[RV3] SUCCESS! Token length: ${token.length}`);
                resolve(token);
            } else {
                reject(new Error("Token returned empty"));
            }

        } catch (e) {
            clearTimeout(timeoutTimer);
            // Bersihkan pesan error agar enak dibaca
            const msg = e.message.replace("Evaluation failed: ", "");
            reject(new Error(msg));
        }
    });
};