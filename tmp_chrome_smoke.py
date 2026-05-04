from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')
opts.add_argument('--disable-gpu')
opts.add_argument('--disable-software-rasterizer')
opts.add_argument('--disable-extensions')
opts.add_argument('--disable-background-networking')
opts.add_argument('--disable-sync')
opts.add_argument('--metrics-recording-only')
opts.add_argument('--disable-default-apps')
opts.add_argument('--no-first-run')
opts.add_argument('--no-zygote')
opts.add_argument('--remote-debugging-pipe')
opts.add_argument('--user-data-dir=/tmp/selenium-smoke-profile')
opts.binary_location = '/usr/bin/google-chrome'
service = Service(ChromeDriverManager().install(), service_args=['--verbose'], log_output='/root/.openclaw/workspace/projects/private-captcha-solver/chromedriver-smoke.log')
driver = webdriver.Chrome(service=service, options=opts)
driver.get('https://example.com')
print(driver.title)
driver.quit()
