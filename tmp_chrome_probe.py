import shutil, tempfile
from selenium import webdriver
from selenium.common.exceptions import WebDriverException

URL = 'https://2captcha.com/demo/recaptcha-v2'
combos = [
    ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--remote-debugging-pipe'],
    ['--headless','--no-sandbox','--disable-dev-shm-usage','--remote-debugging-pipe'],
    ['--headless=new','--no-sandbox','--disable-dev-shm-usage'],
    ['--headless','--no-sandbox','--disable-dev-shm-usage'],
    ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-software-rasterizer','--remote-debugging-pipe'],
    ['--headless','--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-software-rasterizer','--remote-debugging-pipe'],
]
for idx, flags in enumerate(combos, 1):
    prof = tempfile.mkdtemp(prefix=f'chrome-probe-{idx}-')
    driver = None
    try:
        opts = webdriver.ChromeOptions()
        for f in flags:
            opts.add_argument(f)
        opts.add_argument(f'--user-data-dir={prof}')
        opts.add_argument('--window-size=1366,768')
        opts.add_argument('--disable-extensions')
        opts.add_argument('--disable-background-networking')
        opts.add_argument('--disable-sync')
        opts.add_argument('--metrics-recording-only')
        opts.add_argument('--disable-default-apps')
        opts.add_argument('--no-first-run')
        opts.add_argument('--no-zygote')
        opts.binary_location = '/usr/bin/google-chrome'
        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(60)
        driver.get(URL)
        title = driver.title
        print(f'PROBE {idx} OK flags={flags} title={title!r}', flush=True)
    except Exception as e:
        print(f'PROBE {idx} FAIL flags={flags} err={type(e).__name__}: {e}', flush=True)
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        shutil.rmtree(prof, ignore_errors=True)
